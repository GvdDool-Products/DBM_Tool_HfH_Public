import streamlit as st
from datetime import datetime
from db_core import (
    get_connection, get_enum_options, get_address_geometry,
    update_building_geometry, update_building_geom_flag,
    get_geometry_data, update_building_entr_flag,
    update_building_entrance_geometry, add_building,
    delete_building, update_building_details, update_safety,
    update_technical_audit, update_fieldwork_status
)
from github_bridge import push_database

try:
    import folium
    from streamlit_folium import st_folium
    import shapely.wkt
except ImportError:
    folium = None
    st_folium = None
    shapely = None

# --- TECHNICAL AUDIT ENUMS (Stage 3) ---
ENUM_TECH_TYPE = {
    "FOUNDATION": ["Strip", "Slab / Raft", "Pad / Column", "Pile", "Other (custom)..."],
    "FND_WALLS": ["Concrete Block", "Monolithic Concrete", "Brickwork", "Stone / Rubble", "Other (custom)..."],
    "BASEMENT": ["Full Basement", "Partial Basement", "Crawl Space", "No Basement", "Other (custom)..."],
    "WALLS": ["Brickwork", "Aerated Concrete", "Concrete Panel", "Timber / Log", "Stone", "Other (custom)..."],
    "LINTELS": ["Reinforced Concrete", "Steel Beam / Angle", "Brick Arch", "Timber", "Other (custom)..."],
    "ROOF_TYPE": ["Timber Truss / Rafters", "Steel Truss", "Reinforced Concrete Slab", "Monolithic", "Other (custom)..."],
    "ROOF_MAT": ["Metal Sheet / Tile", "Ceramic Tile", "Bitumen Shingle", "Asbestos Sheet (Slate)", "Flat Membrane", "Other (custom)..."],
    "WINDOWS": ["PVC Double Glazed", "Timber Frame", "Aluminium Frame", "Single Pane", "Other (custom)..."],
    "DOORS": ["Metal / Armored", "Timber Solid", "Timber Hollow", "PVC", "Other (custom)..."],
    "ENTRANCE": ["Concrete Porch", "Metal Stairs", "Timber Deck", "Ramp Included", "Other (custom)..."],
    "PAVEMENT": ["Asphalt", "Concrete", "Paving Stones (FEM)", "Gravel", "Other (custom)..."],
    "FINISHES": ["Plaster / Paint", "Wallpaper", "Ceramic Tile", "Drywall / Gyp", "Timber Paneling", "Other (custom)..."]
}

def render_tech_type_picker(label, current_val, enum_key, key_prefix, disabled=False):
    """ Helper to render a Selectbox + Optional Text Input for 'Other' """
    options = ENUM_TECH_TYPE.get(enum_key, ["Other (custom)..."])
    
    # Determine default index
    default_idx = 0
    if current_val and current_val in options:
        default_idx = options.index(current_val)
    elif current_val:
        default_idx = len(options) - 1 # Select "Other" if value exists but isn't in list
    
    selected = st.selectbox(label, options, index=default_idx, key=f"sel_{key_prefix}", disabled=disabled)
    
    # If "Other" is selected, show text input
    if selected == "Other (custom)...":
        # Initial value for text input is the current_val if it wasn't in the enum options
        init_text = current_val if current_val not in options else ""
        return st.text_input(f"Custom {label}", value=init_text, key=f"txt_{key_prefix}", placeholder="Enter custom type...", disabled=disabled)
    
    return selected

def render_tech_cond_slider(label, current_val, key_prefix, disabled=False):
    """ Helper to render a 0-5 slider with descriptive labels """
    # Map range 0-5 to labels
    # 0: Missing, 1: Poor, 2: Satisfactory, 3: Fair, 4: Good, 5: Excellent
    labels = {
        0: "0: Missing / NA",
        1: "1: Poor",
        2: "2: Satisfactory",
        3: "3: Fair",
        4: "4: Good",
        5: "5: Excellent"
    }
    
    val = int(current_val or 3)
    # Ensure val is in 0-5 range
    val = max(0, min(5, val))
    
    return st.select_slider(
        label,
        options=[0, 1, 2, 3, 4, 5],
        value=val,
        format_func=lambda x: labels.get(x, str(x)),
        key=f"sld_{key_prefix}",
        disabled=disabled,
        help="0: Missing, 1: Poor, 5: Excellent"
    )

def building_page(property_id):
    """
    Building Preparation Page
    =========================
    Purpose: Create a complete 'before' snapshot of the building record
    prior to fieldwork scheduling.

    Data sources and their role:
    ------------------------------------------------------------
    TBL_CORE_PROPERTY
        - ID_COMPLEX_FLAG      : If True, multiple buildings exist on this
                                 property. Enables 'Add Building' button and
                                 renders a building selector above the form.
        - GEOM_PROP_CREATED    : Flag indicating the parcel boundary polygon
                                 has been captured and validated.
        - ID_PROPERTY_GEOM     : FK to TBL_CORE_GEOMETRY — parcel boundary
        - ID_ADDRESS_GEOM      : FK to TBL_CORE_GEOMETRY — address point

    TBL_CORE_ADDRESS
        - ADDR_TYPE            : Determines the role of the address point on
                                 the map. PHYSICAL = grey marker (postal and
                                 entrance are the same). Other = blue marker
                                 (entrance point separately required).
        - ADDR_GEOM_CREATED    : Flag indicating the address point has been
                                 geocoded and validated by the user.

    TBL_CORE_BUILDING
        - SYS_BLD_ID           : Primary key — identifies which building
                                 record is being edited (important for
                                 complex/multi-building properties).
        - ID_BUILDING_GEOM     : FK to TBL_CORE_GEOMETRY — building footprint
        - GEOM_BLD_CREATED     : Flag indicating the building footprint
                                 polygon has been captured and validated.
        - BLD_TYPE, BLD_NC_CODE, BLD_FLOORS,
          BLD_TOTAL_AREA, BLD_LIVING_AREA
                               : Static office-knowable fields — populated
                                 before fieldwork from existing records,
                                 cadastral data, or desk research.

    Map layer summary:
    ------------------------------------------------------------
    Layer               Source table         Validation flag
    Address point       TBL_CORE_ADDRESS     ADDR_GEOM_CREATED
    Parcel boundary     TBL_CORE_PROPERTY    GEOM_PROP_CREATED
    Building footprint  TBL_CORE_BUILDING    GEOM_BLD_CREATED

    Geometry state logic:
    ------------------------------------------------------------
    point_ready   = ADDR_GEOM_CREATED == 1
    polygon_ready = GEOM_BLD_CREATED  == 1
    parcel_ready  = GEOM_PROP_CREATED == 1

    ADDR_TYPE == PHYSICAL → grey marker (address is the entrance)
    ADDR_TYPE != PHYSICAL → blue marker (entrance separately captured)
    """

    st.markdown("### 🏗️ Building Preparation")
    st.caption("Complete the building record before scheduling fieldwork.")

    # ------------------------------------------------------------------
    # DATA LOADING
    # Load property, address and all building records linked to this
    # property. b_list is a list to support complex/multi-building
    # properties where ID_COMPLEX_FLAG = 1.
    # ------------------------------------------------------------------
    conn = get_connection()
    c = conn.cursor()

    # Property record — geometry FKs and complex flag
    c.execute("SELECT * FROM TBL_CORE_PROPERTY WHERE SYS_PROPERTY_ID = ?", (property_id,))
    row  = c.fetchone()
    cols = [d[0] for d in c.description]
    p_dict = dict(zip(cols, row)) if row else {}

    # Address record — addr_type and geometry validation flag
    c.execute("SELECT * FROM TBL_CORE_ADDRESS WHERE FK_PROPERTY_ID = ?", (property_id,))
    row  = c.fetchone()
    cols = [d[0] for d in c.description]
    a_dict = dict(zip(cols, row)) if row else {}

    # Building records — list supports single and complex properties
    # Joined with Inspection and Suitability tables
    c.execute("""
        SELECT b.*, 
               i.INSP_ROUTINE_REPAIR, i.INSP_MAJOR_REPAIR, 
               i.INSP_RECONSTRUCTION, i.INSP_REFITTING,
               s.SUIT_IDP_YES, s.SUIT_AFTER_RECON, s.SUIT_AFTER_REFIT, s.SUIT_UNSUITABLE,
               sa.SAFE_PWD_ACCESS, sa.SAFE_FIRE, sa.SAFE_SANITARY, sa.SAFE_CIVIL_DEF,
               sa.SAFE_HAZARD_ZONE, sa.SAFE_CLASS, sa.SAFE_CAT, sa.SAFE_NOTES,
               ta.*
        FROM TBL_CORE_BUILDING b
        LEFT JOIN TBL_CORE_INSPECTION i ON b.SYS_BLD_ID = i.FK_BLD_ID
        LEFT JOIN TBL_CORE_SUITABILITY s ON b.SYS_BLD_ID = s.FK_BUILDING_ID
        LEFT JOIN TBL_CORE_SAFETY sa ON b.SYS_BLD_ID = sa.FK_BUILDING_ID
        LEFT JOIN TBL_CORE_BUILDING_TECH_AUDIT ta ON b.SYS_BLD_ID = ta.FK_BLD_ID
        WHERE b.FK_PROPERTY_ID = ?
    """, (property_id,))
    rows = c.fetchall()
    cols = [d[0] for d in c.description]
    b_list = [dict(zip(cols, row)) for row in rows]
    
    # ------------------------------------------------------------------
    # BUILDING CONTEXT MANAGER
    # ------------------------------------------------------------------
    if not b_list:
        st.error("No building records found for this property.")
        conn.close()
        return

    # Track which building is active in session state
    if 'active_bld_id' not in st.session_state or st.session_state.get('last_prop_id') != property_id:
        st.session_state.active_bld_id = b_list[0]['SYS_BLD_ID']
        st.session_state.last_prop_id = property_id

    # Add Building Action
    def on_add_building():
        new_id = add_building(property_id)
        if new_id:
            st.session_state.active_bld_id = new_id
            st.success("Building added!")
        else:
            st.error("Failed to add building.")

    # Remove Building Action
    def on_remove_building():
        if len(b_list) > 1:
            last_bid = b_list[-1]['SYS_BLD_ID']
            if delete_building(last_bid):
                st.success("Building removed!")
                if st.session_state.active_bld_id == last_bid:
                    st.session_state.active_bld_id = b_list[0]['SYS_BLD_ID']
            else:
                st.error("Failed to remove building.")

    # ------------------------------------------------------------------
    # NAVIGATION NAVBAR (Only for complex properties)
    # ------------------------------------------------------------------
    is_complex = bool(p_dict.get('ID_COMPLEX_FLAG', 0))
    
    if is_complex:
        nav_cols = st.columns([1] * len(b_list) + [0.4, 0.4])
        for i, b_item in enumerate(b_list):
            bid = b_item['SYS_BLD_ID']
            label = f"Building {i+1}"
            is_active = (bid == st.session_state.active_bld_id)
            if nav_cols[i].button(label, 
                                  key=f"nav_{bid}", 
                                  type="primary" if is_active else "secondary",
                                  use_container_width=True):
                st.session_state.active_bld_id = bid
                st.rerun()
        
        # Add button
        if nav_cols[-2].button("➕", help="Add new building to plot"):
            on_add_building()
            st.rerun()
            
        # Remove button
        can_remove = len(b_list) > 1
        if nav_cols[-1].button("➖", 
                               help="Remove the last added building", 
                               disabled=not can_remove):
            on_remove_building()
            st.rerun()
    
    # Identify current building record
    b_id = st.session_state.active_bld_id
    current_bld = next((b for b in b_list if b['SYS_BLD_ID'] == b_id), b_list[0])
    
    # Initialize form submission flags and workflow status to avoid UnboundLocalError
    submitted_core = False
    submitted_adv = False
    submitted_insp = False
    submitted_suit = False
    submitted_safe = False
    submitted_tech = False
    submitted_s2 = False
    # Default to current building's fieldwork status if not overridden by the selector
    new_fw_status = current_bld.get('BLD_FIELDWORK_STATUS') or 0
    
    conn.close()

    # ------------------------------------------------------------------
    # GEOMETRY STATE
    # Derived from validation flags and address type.
    # Used to drive map display and status indicators.
    # ------------------------------------------------------------------
    point_ready  = bool(a_dict.get('ADDR_GEOM_CREATED', 0))
    parcel_ready = bool(p_dict.get('GEOM_PROP_CREATED', 0))
    addr_type    = a_dict.get('ADDR_TYPE', 'UNKNOWN')

    # Point marker style — physical address doubles as entrance point
    point_style  = 'physical' if addr_type == 'PHYSICAL' else 'entrance'
    
    # NEW: Fetch geometries early so they're available for both columns
    map_centre     = None
    zoom           = 6
    addr_geom_data = None
    entr_geom_data = None
    
    if point_ready:
        addr_geom_data = get_address_geometry(a_dict.get('ID_ADDR_GEOM'))
        if addr_geom_data:
            map_centre = [addr_geom_data['latitude'], addr_geom_data['longitude']]
            zoom       = 17
            
    # Fetch Building Entrance Point (if non-physical OR complex)
    if b_id and (str(addr_type).upper() != 'PHYSICAL' or is_complex):
        # Use the existing get_address_geometry function since it handles WKT parsing for points
        entr_geom_data = get_address_geometry(b_id)
        
        # If entrance exists, prefer it as map centre if not draft mode
        if entr_geom_data and not st.session_state.get('edit_entr_mode'):
            map_centre = [entr_geom_data['latitude'], entr_geom_data['longitude']]
    
    # Phase 2 & 3: Session state cleanup for suggestions and entrance editing
    if 'current_bld_id_for_suggestion' not in st.session_state:
        st.session_state.current_bld_id_for_suggestion = None
    if 'edit_entr_mode' not in st.session_state:
        st.session_state.edit_entr_mode = False
    if 'draft_entr_location' not in st.session_state:
        st.session_state.draft_entr_location = None
    
    # If we switched buildings, discard any pending suggestions AND any active edit modes from the previous one
    if b_id and st.session_state.get('last_bld_id') != b_id:
        st.session_state.pop('pending_footprint', None)
        st.session_state.pop('pending_bld_geom_id', None)
        st.session_state.edit_entr_mode = False
        st.session_state.draft_entr_location = None
        st.session_state.last_bld_id = b_id

    col_info, col_map = st.columns([2, 5])

    with col_info:
        st.markdown("#### 📝 Building Records")
        
        # ----------------------------------------------------------
        # VALIDATION TOGGLE (Live reactivity)
        # ----------------------------------------------------------
        is_validated = False
        has_geom = False
        if current_bld:
            b_geom_id = current_bld.get('ID_BUILDING_GEOM')
            
            existing_geom_data = get_geometry_data(b_geom_id)
            has_geom = bool(existing_geom_data and existing_geom_data.get('wkt'))
            
            is_validated_ui = st.toggle(
                "✅ Footprint Validated",
                value=bool(current_bld.get('GEOM_BLD_CREATED', 0)),
                disabled=not has_geom,
                key=f"val_toggle_reactive_{b_id}",
                help="Switch to GREEN (validated) or BLUE (draft)."
            )
            
            # --- IMMEDIATE PERSISTENCE (Validation) ---
            if is_validated_ui != bool(current_bld.get('GEOM_BLD_CREATED', 0)):
                if update_building_geom_flag(b_geom_id, is_accepted=is_validated_ui):
                    push_database(f"Updated footprint validation for building {b_id}")
                    st.rerun()
            
            is_validated = is_validated_ui

            # --- FIELDWORK SELECTION ---
            # 0: Not Selected, 1: Planned (Selected), 2: In Progress, 3: Data Received
            current_fw_status = current_bld.get('BLD_FIELDWORK_STATUS') or 0
            status_labels = {0: "⚪ Not Selected", 1: "🟡 Planned", 2: "🟠 In Progress", 3: "🟢 Results Available"}
            
            if current_fw_status == 0:
                if st.button("🎯 Select for Fieldwork", use_container_width=True, key=f"select_fw_{b_id}"):
                    if update_fieldwork_status(b_id, 1):
                        push_database(f"Selected building {b_id} for fieldwork")
                        st.rerun()
            else:
                st.markdown(f"**Fieldwork Status:** `{status_labels.get(current_fw_status)}` ")
                with st.expander("⚙️ Manage Selection", expanded=False):
                    st.warning("⚠️ Removing this building from fieldwork will hide all technical audit data.")
                    confirm = st.checkbox("I understand and want to deselect this building", key=f"confirm_deselect_{b_id}")
                    if st.button("❌ Confirm Deselection", disabled=not confirm, type="primary", key=f"deselect_fw_{b_id}"):
                        if update_fieldwork_status(b_id, 0):
                            push_database(f"Deselected building {b_id} from fieldwork")
                            st.rerun()
            
            # Use saved status for compatibility
            new_fw_status = current_fw_status

            st.divider()
            
            if not has_geom:
                st.caption("⚠️ No footprint found yet. Use the Search tool above.")

        # ----------------------------------------------------------
        # BUILDING CORE STATS FORM
        # ----------------------------------------------------------
        with st.form(f"core_stats_form_{b_id}"):
            st.markdown("##### 📏 Space & Capacity")
            area_col1, area_col2, area_col3 = st.columns(3)
            with area_col1:
                b_area = st.number_input("Total Area (m²)", 
                                         value=float(current_bld.get('BLD_TOTAL_AREA') or 0.0),
                                         format="%.2f",
                                         key=f"area_{b_id}")
                b_footprint = st.number_input("Footprint Area (m²)", 
                                              value=float(current_bld.get('BLD_FOOTPRINT_AREA') or 0.0),
                                              format="%.2f",
                                              key=f"footprint_{b_id}")
            with area_col2:
                b_living = st.number_input("Living Area (m²)", 
                                           value=float(current_bld.get('BLD_LIVING_AREA') or 0.0),
                                           format="%.2f",
                                           key=f"living_{b_id}")
                b_volume = st.number_input("Total Volume (m³)", 
                                           value=float(current_bld.get('BLD_TOTAL_VOLUME') or 0.0),
                                           format="%.2f",
                                           key=f"volume_{b_id}")
            with area_col3:
                b_free_area = st.number_input("Free Area (m²)", 
                                              value=float(current_bld.get('BLD_FREE_AREA') or 0.0),
                                              format="%.2f",
                                              key=f"free_area_{b_id}")
                b_floors = st.number_input("Floors", 
                                           value=int(current_bld.get('BLD_FLOORS') or 1),
                                           step=1,
                                           key=f"floors_{b_id}")
            
            # --- SQL DEBUG PREVIEW (Core) ---
            with st.expander("🔍 Debug: SQL Update Preview (Core)"):
                sql_preview = f"""-- Updates TBL_CORE_BUILDING
UPDATE TBL_CORE_BUILDING 
SET BLD_TOTAL_AREA = {float(b_area or 0.0)}, BLD_FLOORS = {int(b_floors or 1)}, 
    BLD_LIVING_AREA = {float(b_living or 0.0)}, BLD_FOOTPRINT_AREA = {float(b_footprint or 0.0)}, 
    BLD_TOTAL_VOLUME = {float(b_volume or 0.0)}, BLD_FREE_AREA = {float(b_free_area or 0.0)},
    BLD_FIELDWORK_STATUS = {int(new_fw_status)}
WHERE SYS_BLD_ID = '{b_id}';

-- Validation Flag (saved immediately on toggle)
UPDATE TBL_BUILDING_GEOM SET GEOM_BLD_CREATED = {int(is_validated)} WHERE SYS_GEOM_ID = '{b_geom_id}';"""
                st.code(sql_preview, language="sql")

            submitted_core = st.form_submit_button("💾 Save Attributes", use_container_width=True)

        # # ----------------------------------------------------------
        # # DEBUG SUMMARY
        # # ----------------------------------------------------------
        # with st.expander("🔍 Debug: Data Summary"):
        #     col_d1, col_d2 = st.columns(2)
        #     with col_d1:
        #         st.write(f"Complex: {is_complex}")
        #         st.write(f"Point ready: {point_ready}")
        #     with col_d2:
        #         st.write(f"Geom stored: {has_geom}")
        #         st.write(f"Live Toggle: {is_validated}")

    with col_map:
        # -- Map Toolbar Header (Row 1: Overall Status) --
        tool_col1, tool_col2, tool_col3, tool_col4 = st.columns([1.5, 1, 1, 1])
        
        with tool_col1:
            # 1. Location Pin Status (Universal)
            is_pin_set = False
            if is_complex or addr_type != 'PHYSICAL':
                is_pin_set = bool(current_bld.get('GEOM_ENTR_CREATED', 0))
            else:
                is_pin_set = point_ready

            if is_pin_set:
                st.markdown("📍 **Pin set**")
            else:
                st.markdown("📍 **Pin Required**")

            # 2. Footprint Status
            if current_bld.get('GEOM_BLD_CREATED', 0):
                st.markdown("✅ **Footprint**")
            elif has_geom:
                st.markdown("🔵 **Draft FP**")
            else:
                st.markdown("📍 **No FP**")
        
        with tool_col2:
            # Re-evaluation Tool (Search)
            can_search = not is_validated and (point_ready or entr_geom_data)
            
            # Determine search coordinates and tooltip
            search_lat, search_lon = None, None
            search_help = "Search for a footprint at the marker location."
            
            if is_complex or addr_type != 'PHYSICAL':
                if entr_geom_data:
                    search_lat, search_lon = entr_geom_data['latitude'], entr_geom_data['longitude']
                    search_help = "Searching using the Building Entrance location."
                elif addr_geom_data:
                    search_lat, search_lon = addr_geom_data['latitude'], addr_geom_data['longitude']
                    search_help = "⚠️ No building entrance set. Searching using general Address location."
            else:
                if addr_geom_data:
                    search_lat, search_lon = addr_geom_data['latitude'], addr_geom_data['longitude']
                    search_help = "Searching using the Physical Address location."
            
            if can_search and search_lat is not None:
                if st.button("🔍 Search", 
                             use_container_width=True,
                             help=search_help):
                    from utils.auxiliaryDataImport import fetch_osm_footprint
                    with st.spinner("OSM..."):
                        footprint = fetch_osm_footprint(search_lat, search_lon)
                        if footprint:
                            st.session_state.pending_footprint = footprint
                            st.session_state.pending_bld_geom_id = b_geom_id
            else:
                st.button("🔍 Search", disabled=True, use_container_width=True, help="Set a location first to enable search.")

        has_suggestion = st.session_state.get('pending_footprint') is not None and st.session_state.get('pending_bld_geom_id') == b_geom_id
        
        with tool_col3:
            if st.button("📂 Store", 
                         type="primary", 
                         disabled=not has_suggestion,
                         use_container_width=True,
                         help="Save suggested footprint as draft."):
                if update_building_geometry(st.session_state.pending_bld_geom_id,
                                            st.session_state.pending_footprint):
                    update_building_geom_flag(st.session_state.pending_bld_geom_id, is_accepted=False)
                    st.session_state.pop('pending_footprint', None)
                    st.session_state.pop('pending_bld_geom_id', None)
                    push_database(f"Building footprint stored as draft for {property_id}")
                    st.rerun()
        
        with tool_col4:
            if st.button("🗑️ Discard", 
                         disabled=not has_suggestion,
                         use_container_width=True,
                         help="Discard OSM suggestion."):
                st.session_state.pop('pending_footprint', None)
                st.session_state.pop('pending_bld_geom_id', None)
                st.rerun()

        # -- Map Toolbar Header (Row 2: Entrance - Conditional) --
        if addr_type != 'PHYSICAL' or is_complex:
            st.divider()
            etr_col1, etr_col2, etr_col3, etr_col4 = st.columns([1.2, 1, 1, 1])
            
            with etr_col1:
                st.markdown("🚪 **Entrance Tool**")
            
            with etr_col2:
                edit_entr_active = st.toggle(
                    "✏️ Entrance",
                    value=st.session_state.edit_entr_mode,
                    help="Capture a separate entrance for this building.",
                    key="edit_entr_toggle"
                )
                st.session_state.edit_entr_mode = edit_entr_active
                if not edit_entr_active:
                    st.session_state.draft_entr_location = None

            has_draft_entr = st.session_state.get('draft_entr_location') is not None
            
            with etr_col3:
                save_entr = st.button("💾 Save Ent",
                                      type="primary",
                                      disabled=not (edit_entr_active and has_draft_entr),
                                      use_container_width=True,
                                      help="Save the building entrance point.")
                if save_entr:
                    result = update_building_entrance_geometry(
                        bld_id    = b_id,
                        latitude  = st.session_state.draft_entr_location[0],
                        longitude = st.session_state.draft_entr_location[1],
                        updated_by = st.session_state.get('user_email', 'SYSTEM')
                    )
                    if result:
                        update_building_entr_flag(b_id, is_accepted=True)
                        st.session_state.draft_entr_location = None
                        st.session_state.edit_entr_mode = False
                        push_database(f"Entrance point updated for building {b_id}")
                        st.success("✅ Entrance saved!")
                        st.rerun()

            with etr_col4:
                reset_entr = st.button("🔄 Reset Ent",
                                       disabled=not (edit_entr_active and has_draft_entr),
                                       use_container_width=True,
                                       help="Discard temporary entrance pin.")
                if reset_entr:
                    st.session_state.draft_entr_location = None
                    st.rerun()

        # ----------------------------------------------------------
        # MAP DISPLAY (Reactive to is_validated)
        # ----------------------------------------------------------
        if map_centre is None:
            st.info("🗺️ Map will appear once an address point is confirmed.")
        
        elif folium and st_folium:
            m = folium.Map(location=map_centre, zoom_start=zoom)

            # ----------------------------------------------------------
            # ADDRESS & ENTRANCE MARKERS
            # ----------------------------------------------------------
            # 1. Official Address Marker (Always Green)
            if addr_geom_data:
                folium.Marker(
                    location=[addr_geom_data['latitude'], addr_geom_data['longitude']],
                    tooltip="Postal Address",
                    icon=folium.Icon(color='green', icon='home', opacity=0.7)
                ).add_to(m)

            # 2. Building Entrance (Implicit Point - Blue Flag)
            is_entr_draft = False
            if addr_type != 'PHYSICAL' or is_complex:
                # Determine display location (Actual vs Draft)
                e_lat, e_lon = None, None
                if entr_geom_data:
                    e_lat, e_lon = entr_geom_data['latitude'], entr_geom_data['longitude']
                
                if st.session_state.edit_entr_mode and st.session_state.draft_entr_location:
                    e_lat, e_lon = st.session_state.draft_entr_location
                    is_entr_draft = True
                
                if e_lat is not None:
                    folium.Marker(
                        location=[e_lat, e_lon],
                        tooltip="Building Entrance",
                        icon=folium.Icon(color='orange' if is_entr_draft else 'blue', icon='flag')
                    ).add_to(m)
                    
                    if is_entr_draft:
                        m.location = [e_lat, e_lon] # Centre on draft
                        zoom = 18

            # ----------------------------------------------------------
            # Footprint Rendering (REACTIVE TO TOGGLE)
            # ----------------------------------------------------------
            for b_item in b_list:
                bid = b_item.get('SYS_BLD_ID')
                b_geom_id = b_item.get('ID_BUILDING_GEOM')
                is_active = (bid == st.session_state.active_bld_id)
                
                if b_geom_id:
                    g_data = get_geometry_data(b_geom_id)
                    if g_data and g_data.get('wkt') and shapely:
                        # ACTIVE vs GHOST STYLING
                        if is_active:
                            if is_validated:
                                style = {'fillColor': '#2ecc71', 'color': '#27ae60', 'weight': 4, 'fillOpacity': 0.7}
                            else:
                                style = {'fillColor': '#3498db', 'color': '#2980b9', 'weight': 3, 'fillOpacity': 0.4, 'dashArray': '5, 5'}
                        else:
                            # Sibling buildings are ghosted
                            style = {'fillColor': '#95a5a6', 'color': '#7f8c8d', 'weight': 1, 'fillOpacity': 0.1}

                        try:
                            geom_obj = shapely.wkt.loads(g_data['wkt'])
                            folium.GeoJson(geom_obj, style_function=lambda x, s=style: s).add_to(m)
                        except Exception as e:
                            st.error(f"Render error for {bid}: {e}")

            # ----------------------------------------------------------
            # OSM Footprint Trigger (Automatic + Manual)
            # ----------------------------------------------------------
            # Automatic fetch ONLY if no geom exists at all for CURRENT building
            if current_bld and point_ready and not is_validated:
                b_geom_id = current_bld.get('ID_BUILDING_GEOM')
                existing_geom_check = get_geometry_data(b_geom_id)
                has_any_geom = existing_geom_check and existing_geom_check.get('wkt')

                if not has_any_geom and 'pending_footprint' not in st.session_state:
                    from utils.auxiliaryDataImport import fetch_osm_footprint
                    footprint = fetch_osm_footprint(map_centre[0], map_centre[1])
                    if footprint:
                        st.session_state.pending_footprint    = footprint
                        st.session_state.pending_bld_geom_id = b_geom_id

            # Render suggestion if it exists (regardless of whether it was auto or manual)
            if st.session_state.get('pending_footprint') and st.session_state.get('pending_bld_geom_id') == b_geom_id:
                folium.GeoJson(
                    st.session_state.pending_footprint,
                    name="OSM Suggested Footprint",
                    style_function=lambda x: {'fillColor': '#f39c12', 'color': '#d35400', 'weight': 3, 'fillOpacity': 0.5},
                    tooltip="OSM Suggested Footprint"
                ).add_to(m)
                #st.caption("🏠 **OSM Suggested Footprint found** — please review and 'Store' or 'Discard'.")

            map_output = st_folium(m, use_container_width=True, height=500, key="bld_map")
            
            # Handle Map Clicks for Entrance Repositioning
            if st.session_state.edit_entr_mode and map_output.get("last_clicked"):
                clicked = map_output["last_clicked"]
                st.session_state.draft_entr_location = (clicked["lat"], clicked["lng"])
                st.rerun()

            # -- Coordinate Display Row (Below map) --
            if st.session_state.edit_entr_mode:
                st.divider()
                st.markdown("**📍 New Entrance Coordinates:**")
                c_lat, c_lon = st.columns(2)
                if st.session_state.draft_entr_location:
                    d_lat, d_lon = st.session_state.draft_entr_location
                    c_lat.markdown(f"**Latitude:** `{d_lat:.6f}`")
                    c_lon.markdown(f"**Longitude:** `{d_lon:.6f}`")
                else:
                    c_lat.markdown(f"**Latitude:** `0.000000`")
                    c_lon.markdown(f"**Longitude:** `0.000000`")
                    st.info("👆 *Click on the map to set the building entrance point*")

    # ------------------------------------------------------------------
    # ADVANCED DETAILS & DOCUMENTATION (Full Width Expander)
    # ------------------------------------------------------------------
    st.divider()
    with st.expander("🛠️ Building Details & Documentation", expanded=False):
        with st.form(f"advanced_details_form_{b_id}"):
            col_adv1, col_adv2 = st.columns(2)
            
            with col_adv1:
                st.markdown("**Intended Use & Classification**")
                # Intended Use Selection
                bld_type_options = get_enum_options("BLD_TYPE")
                b_type_codes    = [o[0] for o in bld_type_options]
                b_type_labels   = [o[1] for o in bld_type_options]
                label_to_code_bld = dict(zip(b_type_labels, b_type_codes))

                current_b_type = current_bld.get('BLD_TYPE', 'UNKNOWN')
                try:
                    b_type_idx = b_type_codes.index(current_b_type)
                except ValueError:
                    b_type_idx = 0

                selected_b_type_label = st.selectbox("Intended Use / Building Type", b_type_labels, index=b_type_idx, key=f"type_{b_id}")
                new_bld_type = label_to_code_bld.get(selected_b_type_label, "UNKNOWN")

                new_use_desc = st.text_area("Intended Use Description",
                                            value=current_bld.get('BLD_USE_DESC', '') or '',
                                            height=68,
                                            key=f"desc_{b_id}")
                
                new_nc_code = st.text_input("NC 018:2023 Building Code", 
                                            value=current_bld.get('BLD_NC_CODE', '') or '',
                                            key=f"nc_{b_id}")
                
                new_eng_sys = st.toggle("Engineering Systems Present",
                                         value=bool(current_bld.get('BLD_ENG_SYS', 0)),
                                         key=f"eng_{b_id}")

            with col_adv2:
                st.markdown("**Technical Documentation**")
                new_bti_exist = st.toggle("BTI Technical Passport Exists", 
                                           value=bool(current_bld.get('BLD_BTI_PASSPORT_EXIST', 0)),
                                           key=f"bti_exist_{b_id}")
                new_bti_desc  = st.text_area("BTI Passport Description / Details", 
                                             value=current_bld.get('BLD_BTI_PASSPORT_DESC', '') or '',
                                             height=150,
                                             key=f"bti_desc_{b_id}")

            # --- SQL DEBUG PREVIEW (Advanced) ---
            with st.expander("🔍 Debug: SQL Update Preview (Advanced)"):
                safe_bti_desc = (new_bti_desc or "").replace("'", "''")
                sql_preview_adv = f"""UPDATE TBL_CORE_BUILDING 
SET BLD_TYPE = '{new_bld_type}', BLD_NC_CODE = '{new_nc_code or ""}', 
    BLD_USE_DESC = '{(new_use_desc or "").replace("'", "''")}', BLD_BTI_PASSPORT_EXIST = {int(new_bti_exist or 0)},
    BLD_BTI_PASSPORT_DESC = '{safe_bti_desc}', BLD_ENG_SYS = {int(new_eng_sys or 0)}
WHERE SYS_BLD_ID = '{b_id}'"""
                st.code(sql_preview_adv, language="sql")

            # --- Documentation READINESS CHECK ---
            prop_geodetic_ok = bool(p_dict.get('PROP_GEODETIC_SURVEY_EXIST', 0))
            prop_geological_ok = bool(p_dict.get('PROP_GEOLOGICAL_INVEST_EXIST', 0))
            is_ready = prop_geodetic_ok and prop_geological_ok and new_bti_exist
            
            if is_ready:
                st.success("✅ **Fully Documented & Ready**")
                st.caption("Geodetic, Geological, and BTI records are confirmed.")
            else:
                missing = []
                if not prop_geodetic_ok: missing.append("Geodetic Survey")
                if not prop_geological_ok: missing.append("Geological Investigation")
                if not new_bti_exist: missing.append("BTI Technical Passport")
                st.warning(f"⚠️ **Pending Documentation: {', '.join(missing)}**")

            submitted_adv = st.form_submit_button("💾 Save Documentation & Details", use_container_width=True)

    # ------------------------------------------------------------------
    # INSPECTION DETAILS (pre-visit) (Full Width Expander)
    # ------------------------------------------------------------------
    with st.expander("🔍 Inspection Details (pre-visit)", expanded=False):
        with st.form(f"inspection_details_form_{b_id}"):
            insp_col1, insp_col2 = st.columns(2)
            
            with insp_col1:
                st.markdown("**Stage 1: Initial Assessment**")
                new_insp_routine = st.toggle("Need for routine repairs (Minor)",
                                             value=bool(current_bld.get('INSP_ROUTINE_REPAIR', 0)),
                                             help="Minor repairs needed",
                                             key=f"insp_routine_{b_id}")
                new_insp_major = st.toggle("Need for major repairs (Excludes immediate use)",
                                           value=bool(current_bld.get('INSP_MAJOR_REPAIR', 0)),
                                           help="Major repairs needed - Excludes immediate use",
                                           key=f"insp_major_{b_id}")
            
            with insp_col2:
                st.markdown("**Stage 2: Structural Assessment**")
                new_insp_reconstruction = st.toggle("Need for reconstruction (Major structural)",
                                                    value=bool(current_bld.get('INSP_RECONSTRUCTION', 0)),
                                                    help="Need for reconstruction - Major structural work",
                                                    key=f"insp_recon_{b_id}")
                new_insp_refitting = st.toggle("Need for refitting (Functional adaptation)",
                                               value=bool(current_bld.get('INSP_REFITTING', 0)),
                                               help="Need for refitting - Functional adaptation",
                                               key=f"insp_refit_{b_id}")

                sql_preview_insp = f"""-- Updates target TBL_CORE_INSPECTION only
UPDATE TBL_CORE_INSPECTION 
SET INSP_ROUTINE_REPAIR = {int(new_insp_routine or 0)}, INSP_MAJOR_REPAIR = {int(new_insp_major or 0)},
    INSP_RECONSTRUCTION = {int(new_insp_reconstruction or 0)}, INSP_REFITTING = {int(new_insp_refitting or 0)}
WHERE FK_BLD_ID = '{b_id}'"""
                st.code(sql_preview_insp, language="sql")

            submitted_insp = st.form_submit_button("💾 Save Inspection Details", use_container_width=True)

    # ------------------------------------------------------------------
    # IDP SUITABILITY ASSESSMENT (Full Width Expander)
    # ------------------------------------------------------------------
    with st.expander("🏠 IDP Suitability Assessment", expanded=False):
        with st.form(f"suitability_details_form_{b_id}"):
            suit_col1, suit_col2 = st.columns(2)
            
            with suit_col1:
                st.markdown("**Stage 1: Initial Assessment**")
                new_suit_idp_yes = st.toggle("Suitable for IDP housing (YES)",
                                             value=bool(current_bld.get('SUIT_IDP_YES', 0)),
                                             help="Suitable for IDP housing",
                                             key=f"suit_idp_yes_{b_id}")
                new_suit_unsuitable = st.toggle("Unsuitable for IDP housing",
                                                value=bool(current_bld.get('SUIT_UNSUITABLE', 0)),
                                                help="Unsuitable for IDP housing",
                                                key=f"suit_unsuitable_{b_id}")
            
            with suit_col2:
                st.markdown("**Stage 2: Post-Investment Assessment**")
                new_suit_recon = st.toggle("Suitable after reconstruction",
                                            value=bool(current_bld.get('SUIT_AFTER_RECON', 0)),
                                            help="Suitable after reconstruction",
                                            key=f"suit_recon_{b_id}")
                new_suit_refit = st.toggle("Suitable after refitting",
                                            value=bool(current_bld.get('SUIT_AFTER_REFIT', 0)),
                                            help="Suitable after refitting",
                                            key=f"suit_refit_{b_id}")

            # --- SQL DEBUG PREVIEW (Suitability) ---
            with st.expander("🔍 Debug: SQL Update Preview (Suitability)"):
                sql_preview_suit = f"""-- Updates target TBL_CORE_SUITABILITY only
UPDATE TBL_CORE_SUITABILITY 
SET SUIT_IDP_YES = {int(new_suit_idp_yes or 0)}, SUIT_AFTER_RECON = {int(new_suit_recon or 0)},
    SUIT_AFTER_REFIT = {int(new_suit_refit or 0)}, SUIT_UNSUITABLE = {int(new_suit_unsuitable or 0)}
WHERE FK_BUILDING_ID = '{b_id}'"""
                st.code(sql_preview_suit, language="sql")

            submitted_suit = st.form_submit_button("💾 Save Suitability Details", use_container_width=True)

    st.divider() # --- Transition to Stage 3 (Fieldwork) ---

    # ------------------------------------------------------------------
    # STRUCTURAL & UTILITY ASSESSMENT (Stage 3)
    # ------------------------------------------------------------------
    if current_bld:
        # Fieldwork Logic (matching Audit)
        expander_title_s2 = "📋 Structural & Utility Assessment (Stage 3)"
        if new_fw_status == 0:
            expander_title_s2 += " — [disabled]"
        elif new_fw_status == 1:
            expander_title_s2 += " — (Planned)"
        
        with st.expander(expander_title_s2, expanded=False):
            if new_fw_status == 0:
                st.info("ℹ️ Select building for fieldwork to enable this section.")
            else:
                user_role = st.session_state.get('user_role', 'EXPERT').upper()
                is_admin = (user_role == 'ADMIN')
                is_surveyor = (user_role == 'SURVEYOR')
                
                # Locked in Planned (1) or Received (3)
                is_locked_s2 = (new_fw_status == 1) or (new_fw_status == 3)
                can_edit_s2 = not is_locked_s2
                if is_locked_s2 and is_admin:
                    can_edit_s2 = st.checkbox("Admin: Enable Stage 2/3 Editing", value=False, key=f"admin_edit_s2_{b_id}")

                if is_locked_s2 and not is_admin:
                    if new_fw_status == 1:
                        st.info("🟡 Status: Planned. Data is read-only until fieldwork begins.")
                    else:
                        st.warning("🔒 This data is locked (Status: Results Available).")

                with st.form(f"structural_utility_form_{b_id}"):
                    st.markdown("##### 🧱 Structural Integrity")
                    str_col1, str_col2 = st.columns(2)
                    with str_col1:
                        new_insp_deviations_exist = st.toggle("Vertical deviations (out-of-plumb / leaning)", 
                                                             value=bool(current_bld.get('INSP_DEVIATIONS_EXIST', 0)),
                                                             key=f"insp_dev_ex_{b_id}", disabled=not can_edit_s2)
                    with str_col2:
                        new_insp_deviations_desc = st.text_input("Deviations Description", 
                                                                value=current_bld.get('INSP_DEVIATIONS_DESC', '') or '',
                                                                key=f"insp_dev_desc_{b_id}", disabled=not can_edit_s2)
                    
                    str_col3, str_col4 = st.columns(2)
                    with str_col3:
                        new_insp_damage_exist = st.toggle("Deformations and damage/failures", 
                                                         value=bool(current_bld.get('INSP_DAMAGE_EXIST', 0)),
                                                         key=f"insp_dmg_ex_{b_id}", disabled=not can_edit_s2)
                    with str_col4:
                        new_insp_damage_desc = st.text_input("Damage Description", 
                                                            value=current_bld.get('INSP_DAMAGE_DESC', '') or '',
                                                            key=f"insp_dmg_desc_{b_id}", disabled=not can_edit_s2)

                    st.divider()
                    st.markdown("##### 🔌 Building Services / Engineering Systems")
                    
                    # Row 1: Electricity & Water
                    util_col1, util_col2 = st.columns(2)
                    with util_col1:
                        new_insp_elec_exist = st.toggle("Electricity supply", value=bool(current_bld.get('INSP_ELECTRICITY_EXIST', 0)), key=f"util_elec_ex_{b_id}", disabled=not can_edit_s2)
                        new_insp_elec_desc = st.text_input("Electricity Notes", value=current_bld.get('INSP_ELECTRICITY_DESC', '') or '', key=f"util_elec_desc_{b_id}", disabled=not can_edit_s2)
                    with util_col2:
                        new_insp_water_exist = st.toggle("Water supply", value=bool(current_bld.get('INSP_WATER_EXIST', 0)), key=f"util_water_ex_{b_id}", disabled=not can_edit_s2)
                        new_insp_water_desc = st.text_input("Water Notes", value=current_bld.get('INSP_WATER_DESC', '') or '', key=f"util_water_desc_{b_id}", disabled=not can_edit_s2)
                    
                    # Row 2: Wastewater & Gas
                    util_col3, util_col4 = st.columns(2)
                    with util_col3:
                        new_insp_waste_exist = st.toggle("Wastewater drainage / sewerage", value=bool(current_bld.get('INSP_WASTEWATER_EXIST', 0)), key=f"util_waste_ex_{b_id}", disabled=not can_edit_s2)
                        new_insp_waste_desc = st.text_input("Wastewater Notes", value=current_bld.get('INSP_WASTEWATER_DESC', '') or '', key=f"util_waste_desc_{b_id}", disabled=not can_edit_s2)
                    with util_col4:
                        new_insp_gas_exist = st.toggle("Gas supply", value=bool(current_bld.get('INSP_GAS_EXIST', 0)), key=f"util_gas_ex_{b_id}", disabled=not can_edit_s2)
                        new_insp_gas_desc = st.text_input("Gas Notes", value=current_bld.get('INSP_GAS_DESC', '') or '', key=f"util_gas_desc_{b_id}", disabled=not can_edit_s2)
                    
                    # Row 3: Heating
                    util_col5, _ = st.columns(2)
                    with util_col5:
                        new_insp_heat_exist = st.toggle("Heat supply / heating", value=bool(current_bld.get('INSP_HEATING_EXIST', 0)), key=f"util_heat_ex_{b_id}", disabled=not can_edit_s2)
                        new_insp_heat_desc = st.text_input("Heating Notes", value=current_bld.get('INSP_HEATING_DESC', '') or '', key=f"util_heat_desc_{b_id}", disabled=not can_edit_s2)

                    # --- SQL DEBUG PREVIEW (Structural/Utility) ---
                    with st.expander("🔍 Debug: SQL Update Preview"):
                        sql_preview_s2 = f"""-- Updates TBL_CORE_INSPECTION with detailed fieldwork findings
UPDATE TBL_CORE_INSPECTION 
SET INSP_DEVIATIONS_EXIST = {int(new_insp_deviations_exist)}, INSP_DEVIATIONS_DESC = '{new_insp_deviations_desc.replace("'", "''")}',
    INSP_DAMAGE_EXIST = {int(new_insp_damage_exist)}, INSP_DAMAGE_DESC = '{new_insp_damage_desc.replace("'", "''")}',
    INSP_ELECTRICITY_EXIST = {int(new_insp_elec_exist)}, INSP_ELECTRICITY_DESC = '{new_insp_elec_desc.replace("'", "''")}',
    INSP_WATER_EXIST = {int(new_insp_water_exist)}, INSP_WATER_DESC = '{new_insp_water_desc.replace("'", "''")}',
    INSP_WASTEWATER_EXIST = {int(new_insp_waste_exist)}, INSP_WASTEWATER_DESC = '{new_insp_waste_desc.replace("'", "''")}',
    INSP_GAS_EXIST = {int(new_insp_gas_exist)}, INSP_GAS_DESC = '{new_insp_gas_desc.replace("'", "''")}',
    INSP_HEATING_EXIST = {int(new_insp_heat_exist)}, INSP_HEATING_DESC = '{new_insp_heat_desc.replace("'", "''")}'
WHERE FK_BLD_ID = '{b_id}';"""
                        st.code(sql_preview_s2, language="sql")

                    has_save_permission_s2 = is_admin or is_surveyor
                    if not has_save_permission_s2:
                        st.warning("👤 Contact the administrator in case of an error (View-only).")
                        submitted_s2 = st.form_submit_button("💾 Save Structural & Utility assessment", use_container_width=True, disabled=True)
                    else:
                        submitted_s2 = st.form_submit_button("💾 Save Structural & Utility assessment", use_container_width=True, disabled=not can_edit_s2)


    # ------------------------------------------------------------------
    # DETAILED TECHNICAL SURVEY (Stage 3)
    # ------------------------------------------------------------------
    if current_bld:
        # Use reactive toggle state (new_fw_status) for the expander
        is_pending = not current_bld.get('AUDIT_DATE')
        
        # Expander Header Logic
        expander_title = "🔬 Detailed Technical Survey (Stage 3)"
        if new_fw_status == 0:
            expander_title += " — [disabled]"
        elif new_fw_status == 1:
            expander_title += " — (Planned)"
        elif is_pending:
            expander_title += " — (pending)"
            
        with st.expander(expander_title, expanded=False):
            if new_fw_status == 0:
                st.info("ℹ️ Select building for fieldwork to enable this section.")
            else:
                # Permission & Locking Logic
                user_role = st.session_state.get('user_role', 'EXPERT').upper()
                user_email = st.session_state.get('username', '').lower()
                audit_eng = (current_bld.get('AUDIT_ENGINEER') or '').lower()
                
                is_admin = (user_role == 'ADMIN')
                is_surveyor = (user_role == 'SURVEYOR')
                is_auditor = (audit_eng != "" and audit_eng in user_email) or (user_email != "" and user_email in audit_eng)
                
                # Planned (1) or Received (3) state locking
                is_locked = (new_fw_status == 3) or (new_fw_status == 1)
                
                if is_locked:
                    if new_fw_status == 3:
                        st.warning("🔒 This data is locked (Status: Results Available).")
                    else:
                        st.info("🟡 Status: Planned. Data is read-only until fieldwork begins.")
                    
                    can_edit = False
                    if is_admin:
                        can_edit = st.checkbox("Admin: Enable Editing", value=False, key=f"admin_edit_{b_id}")
                else:
                    can_edit = True

                # Use a container instead of a form to allow reactivity for "Other" dropdowns
                tech_container = st.container()
                with tech_container:
                    st.markdown("##### 🏗️ Substructure")
                    s_col1, s_col2 = st.columns(2)
                    with s_col1:
                        t_fnd_type = render_tech_type_picker("Foundation Type", current_bld.get('TECH_FND_TYPE'), "FOUNDATION", f"fnd_type_{b_id}", disabled=not can_edit)
                        t_fnd_cond = render_tech_cond_slider("Foundation Condition", current_bld.get('TECH_FND_COND'), f"fnd_cond_{b_id}", disabled=not can_edit)
                        t_basement_type = render_tech_type_picker("Basement Type", current_bld.get('TECH_BASEMENT_TYPE'), "BASEMENT", f"base_type_{b_id}", disabled=not can_edit)
                    with s_col2:
                        t_fnd_walls_type = render_tech_type_picker("Foundation Walls Type", current_bld.get('TECH_FND_WALLS_TYPE'), "FND_WALLS", f"fnd_walls_type_{b_id}", disabled=not can_edit)
                        t_fnd_walls_cond = render_tech_cond_slider("Foundation Walls Condition", current_bld.get('TECH_FND_WALLS_COND'), f"fnd_walls_cond_{b_id}", disabled=not can_edit)
                        t_basement_cond = render_tech_cond_slider("Basement Condition", current_bld.get('TECH_BASEMENT_COND'), f"base_cond_{b_id}", disabled=not can_edit)
                    
                    t_substructure_desc = st.text_area("Substructure Narrative / Synthesis", value=current_bld.get('TECH_SUBSTRUCTURE_DESC', '') or '', height=100, key=f"t_sub_desc_{b_id}", disabled=not can_edit)

                    st.divider()
                    st.markdown("##### 🏠 Envelope & Shell")
                    e_col1, e_col2 = st.columns(2)
                    with e_col1:
                        t_walls_type = render_tech_type_picker("External Walls Type", current_bld.get('TECH_WALLS_TYPE'), "WALLS", f"walls_type_{b_id}", disabled=not can_edit)
                        t_walls_cond = render_tech_cond_slider("External Walls Condition", current_bld.get('TECH_WALLS_COND'), f"walls_cond_{b_id}", disabled=not can_edit)
                        t_lintels_type = render_tech_type_picker("Lintels Type", current_bld.get('TECH_LINTELS_TYPE'), "LINTELS", f"lintels_type_{b_id}", disabled=not can_edit)
                        t_lintels_cond = render_tech_cond_slider("Lintels Condition", current_bld.get('TECH_LINTELS_COND'), f"lintels_cond_{b_id}", disabled=not can_edit)
                        t_windows_type = render_tech_type_picker("Window Units Type", current_bld.get('TECH_WINDOWS_TYPE'), "WINDOWS", f"win_type_{b_id}", disabled=not can_edit)
                        t_windows_cond = render_tech_cond_slider("Window Units Condition", current_bld.get('TECH_WINDOWS_COND'), f"win_cond_{b_id}", disabled=not can_edit)
                    with e_col2:
                        t_roof_type = render_tech_type_picker("Roof Structure Type", current_bld.get('TECH_ROOF_TYPE_TYPE'), "ROOF_TYPE", f"roof_type_{b_id}", disabled=not can_edit)
                        t_roof_type_cond = render_tech_cond_slider("Roof Structure Condition", current_bld.get('TECH_ROOF_TYPE_COND'), f"roof_cond_{b_id}", disabled=not can_edit)
                        t_roof_mat = render_tech_type_picker("Roof Covering Type", current_bld.get('TECH_ROOF_MAT_TYPE'), "ROOF_MAT", f"roof_mat_{b_id}", disabled=not can_edit)
                        t_roof_mat_cond = render_tech_cond_slider("Roof Covering Condition", current_bld.get('TECH_ROOF_MAT_COND'), f"roof_mat_cond_{b_id}", disabled=not can_edit)
                        t_doors_type = render_tech_type_picker("Door Units Type", current_bld.get('TECH_DOORS_TYPE'), "DOORS", f"door_type_{b_id}", disabled=not can_edit)
                        t_doors_cond = render_tech_cond_slider("Door Units Condition", current_bld.get('TECH_DOORS_COND'), f"door_cond_{b_id}", disabled=not can_edit)
                
                    t_envelope_desc = st.text_area("Envelope Narrative / Synthesis", value=current_bld.get('TECH_ENVELOPE_DESC', '') or '', height=100, key=f"t_env_desc_{b_id}", disabled=not can_edit)

                    st.divider()
                    st.markdown("##### ✨ Finishes & Site")
                    f_col1, f_col2 = st.columns(2)
                    with f_col1:
                        t_entrance_type = render_tech_type_picker("Entrance Porches Type", current_bld.get('TECH_ENTRANCE_TYPE'), "ENTRANCE", f"entr_type_{b_id}", disabled=not can_edit)
                        t_entrance_cond = render_tech_cond_slider("Entrance Porches Condition", current_bld.get('TECH_ENTRANCE_COND'), f"entr_cond_{b_id}", disabled=not can_edit)
                        t_int_finish_type = render_tech_type_picker("Interior Finishes Type", current_bld.get('TECH_INT_FINISH_TYPE'), "FINISHES", f"int_type_{b_id}", disabled=not can_edit)
                        t_int_finish_cond = render_tech_cond_slider("Interior Finishes Condition", current_bld.get('TECH_INT_FINISH_COND'), f"int_cond_{b_id}", disabled=not can_edit)
                    with f_col2:
                        t_pavement_type = render_tech_type_picker("Perimeter Paving Type", current_bld.get('TECH_PAVEMENT_TYPE'), "PAVEMENT", f"pave_type_{b_id}", disabled=not can_edit)
                        t_pavement_cond = render_tech_cond_slider("Perimeter Paving Condition", current_bld.get('TECH_PAVEMENT_COND'), f"pave_cond_{b_id}", disabled=not can_edit)
                    
                    t_finishes_desc = st.text_area("Finishes & Site Narrative / Synthesis", value=current_bld.get('TECH_FINISHES_DESC', '') or '', height=100, key=f"t_fin_desc_{b_id}", disabled=not can_edit)

                    st.divider()
                    # Loading existing date if possible, else default to now
                    existing_date_str = current_bld.get('AUDIT_DATE')
                    try:
                        default_date = datetime.fromisoformat(existing_date_str).date() if existing_date_str else datetime.now().date()
                    except (ValueError, TypeError):
                        default_date = datetime.now().date()
                    
                    t_audit_date = st.date_input("Audit Date", value=default_date, key=f"t_audit_date_{b_id}", disabled=not can_edit)
                    t_audit_engineer = st.text_input("Audit Engineer", value=current_bld.get('AUDIT_ENGINEER', '') or '', key=f"t_audit_engineer_{b_id}", disabled=not can_edit)

                    # Save button permissions
                    has_save_permission = is_admin or is_surveyor or is_auditor
                    
                    # --- SQL DEBUG PREVIEW (Technical) ---
                    with st.expander("🔍 Debug: SQL Update Preview (Technical)"):
                        sql_preview_tech = f"""-- Updates target TBL_CORE_BUILDING_TECH_AUDIT
UPDATE TBL_CORE_BUILDING_TECH_AUDIT
SET TECH_FND_TYPE = '{t_fnd_type}', TECH_FND_COND = {int(t_fnd_cond)},
    TECH_WALLS_TYPE = '{t_walls_type}', TECH_WALLS_COND = {int(t_walls_cond)},
    TECH_ROOF_TYPE_TYPE = '{t_roof_type}', TECH_ROOF_TYPE_COND = {int(t_roof_type_cond)},
    AUDIT_DATE = '{t_audit_date.isoformat()}', AUDIT_ENGINEER = '{t_audit_engineer}'
    -- (and all other 30+ technical fields...)
WHERE FK_BUILDING_ID = '{b_id}';

-- Also preserves Fieldwork Status in TBL_CORE_BUILDING
UPDATE TBL_CORE_BUILDING SET BLD_FIELDWORK_STATUS = {int(new_fw_status)} WHERE SYS_BLD_ID = '{b_id}';"""
                        st.code(sql_preview_tech, language="sql")

                    if not has_save_permission:
                        st.warning("👤 Contact the auditor or administrator in case of an error (View-only).")
                        submitted_tech = st.button("💾 Save Technical Audit", use_container_width=True, disabled=True, key=f"btn_tech_dis_{b_id}")
                    else:
                        submitted_tech = st.button("💾 Save Technical Audit", use_container_width=True, disabled=not can_edit, key=f"btn_tech_save_{b_id}")

    # ------------------------------------------------------------------
    # SAFETY ASSESSMENT (Stage 3 & 4)
    # ------------------------------------------------------------------
    if current_bld:
        with st.expander("🛡️ Safety Assessment — Stage 3 & 4", expanded=False):
            with st.form(f"safety_details_form_{b_id}"):
                st.markdown("**Core Safety Compliance**")
                col_s1, col_s2 = st.columns(2)
                
                with col_s1:
                    new_safe_fire = st.toggle("Fire safety compliance (DBN V.1.1-7-2016)",
                                             value=bool(current_bld.get('SAFE_FIRE', 0)),
                                             help="Stage 3 compliance",
                                             key=f"safe_fire_{b_id}")
                    new_safe_sanitary = st.toggle("Sanitary compliance",
                                                 value=bool(current_bld.get('SAFE_SANITARY', 0)),
                                                 help="Stage 3 compliance",
                                                 key=f"safe_sanitary_{b_id}")
                    new_safe_civil = st.toggle("Civil defense shelter availability",
                                              value=bool(current_bld.get('SAFE_CIVIL_DEF', 0)),
                                              help="Stage 3 compliance",
                                              key=f"safe_civil_{b_id}")
                
                with col_s2:
                    new_safe_class = st.toggle("Building consequence / responsibility class (DSTU-N B V.1.2-16:2013)",
                                              value=bool(current_bld.get('SAFE_CLASS', 0)),
                                              help="Stage 3 compliance",
                                              key=f"safe_class_{b_id}")
                    new_safe_cat = st.toggle("Structural importance / responsibility category (DBN V.1.2-14-2009)",
                                            value=bool(current_bld.get('SAFE_CAT', 0)),
                                            help="Stage 3 compliance",
                                            key=f"safe_cat_{b_id}")
                    new_pwd_access = st.toggle("Accessibility for PwD",
                                               value=bool(current_bld.get('SAFE_PWD_ACCESS', 0)),
                                               help="Stage 4 compliance",
                                               key=f"safe_pwd_{b_id}")
                
                st.markdown("**Hazard Zones & Notes**")
                new_hazard = st.text_input("Hazard zones / sanitary zones",
                                           value=current_bld.get('SAFE_HAZARD_ZONE', '') or '',
                                           key=f"safe_hazard_{b_id}")
                
                new_safe_notes = st.text_area("Safety Description / Notes",
                                              value=current_bld.get('SAFE_NOTES', '') or '',
                                              height=100,
                                              key=f"safe_notes_{b_id}")

                # --- SQL DEBUG PREVIEW (Safety) ---
                with st.expander("🔍 Debug: SQL Update Preview (Safety)"):
                    sql_preview_safe = f"""-- Updates target TBL_CORE_SAFETY
UPDATE TBL_CORE_SAFETY 
SET SAFE_FIRE = {int(new_safe_fire)}, SAFE_SANITARY = {int(new_safe_sanitary)},
    SAFE_CIVIL_DEF = {int(new_safe_civil)}, SAFE_CLASS = {int(new_safe_class)},
    SAFE_CAT = {int(new_safe_cat)}, SAFE_PWD_ACCESS = {int(new_pwd_access)},
    SAFE_HAZARD_ZONE = '{new_hazard or ""}', SAFE_NOTES = '{(new_safe_notes or "").replace("'", "''")}'
WHERE FK_BUILDING_ID = '{b_id}';

-- Also preserves Fieldwork Status in TBL_CORE_BUILDING
UPDATE TBL_CORE_BUILDING SET BLD_FIELDWORK_STATUS = {int(new_fw_status)} WHERE SYS_BLD_ID = '{b_id}';"""
                    st.code(sql_preview_safe, language="sql")

                submitted_safe = st.form_submit_button("💾 Save Safety Details", use_container_width=True)

    # ------------------------------------------------------------------
    # SAVE LOGIC
    # ----------------------------------------------------------
    if submitted_core:
        if current_bld:
            b_id = current_bld.get('SYS_BLD_ID')
            b_geom_id = current_bld.get('ID_BUILDING_GEOM')
            
            # Update Validation Flag (Preserve live toggle state)
            update_building_geom_flag(b_geom_id, is_accepted=is_validated)
            
            # Update Core Metadata (Preserve current advanced fields)
            success = update_building_details(
                b_id, b_area, b_floors, 
                bti_exist=current_bld.get('BLD_BTI_PASSPORT_EXIST') or 0,
                bti_desc=current_bld.get('BLD_BTI_PASSPORT_DESC') or '',
                ready_flag=current_bld.get('BLD_READY_FLAG') or 0,
                bld_type=current_bld.get('BLD_TYPE') or 'UNKNOWN',
                use_desc=current_bld.get('BLD_USE_DESC') or '',
                nc_code=current_bld.get('BLD_NC_CODE') or '',
                living_area=b_living,
                eng_sys=current_bld.get('BLD_ENG_SYS') or 0,
                footprint_area=b_footprint,
                total_volume=b_volume,
                insp_routine=current_bld.get('INSP_ROUTINE_REPAIR') or 0,
                insp_major=current_bld.get('INSP_MAJOR_REPAIR') or 0,
                insp_reconstruction=current_bld.get('INSP_RECONSTRUCTION') or 0,
                insp_refitting=current_bld.get('INSP_REFITTING') or 0,
                suit_idp_yes=current_bld.get('SUIT_IDP_YES') or 0,
                suit_recon=current_bld.get('SUIT_AFTER_RECON') or 0,
                suit_refit=current_bld.get('SUIT_AFTER_REFIT') or 0,
                suit_unsuitable=current_bld.get('SUIT_UNSUITABLE') or 0,
                free_area=b_free_area,
                fieldwork_status=new_fw_status,
                insp_deviations_exist=current_bld.get('INSP_DEVIATIONS_EXIST') or 0,
                insp_deviations_desc=current_bld.get('INSP_DEVIATIONS_DESC') or '',
                insp_damage_exist=current_bld.get('INSP_DAMAGE_EXIST') or 0,
                insp_damage_desc=current_bld.get('INSP_DAMAGE_DESC') or '',
                insp_elec_exist=current_bld.get('INSP_ELECTRICITY_EXIST') or 0,
                insp_elec_desc=current_bld.get('INSP_ELECTRICITY_DESC') or '',
                insp_water_exist=current_bld.get('INSP_WATER_EXIST') or 0,
                insp_water_desc=current_bld.get('INSP_WATER_DESC') or '',
                insp_waste_exist=current_bld.get('INSP_WASTEWATER_EXIST') or 0,
                insp_waste_desc=current_bld.get('INSP_WASTEWATER_DESC') or '',
                insp_gas_exist=current_bld.get('INSP_GAS_EXIST') or 0,
                insp_gas_desc=current_bld.get('INSP_GAS_DESC') or '',
                insp_heat_exist=current_bld.get('INSP_HEATING_EXIST') or 0,
                insp_heat_desc=current_bld.get('INSP_HEATING_DESC') or ''
            )
            if success:
                push_database(f"Updated building core attributes ({property_id})")
                st.success(f"✅ Core attributes saved for building {b_id}.")
                st.rerun()
            else:
                st.error(f"❌ Database error: Failed to update core attributes for {b_id}.")

    if submitted_adv:
        if current_bld:
            b_id = current_bld.get('SYS_BLD_ID')
            b_geom_id = current_bld.get('ID_BUILDING_GEOM')

            # Update Validation Flag (Preserve live toggle state)
            update_building_geom_flag(b_geom_id, is_accepted=is_validated)

            # Update Advanced Metadata (Preserve current core attributes)
            success = update_building_details(
                b_id, 
                total_area=current_bld.get('BLD_TOTAL_AREA') or 0.0,
                floors=current_bld.get('BLD_FLOORS') or 1,
                bti_exist=new_bti_exist,
                bti_desc=new_bti_desc,
                ready_flag=is_ready,
                bld_type=new_bld_type,
                use_desc=new_use_desc,
                nc_code=new_nc_code,
                living_area=current_bld.get('BLD_LIVING_AREA') or 0.0,
                eng_sys=int(new_eng_sys),
                footprint_area=current_bld.get('BLD_FOOTPRINT_AREA') or 0.0,
                total_volume=current_bld.get('BLD_TOTAL_VOLUME') or 0.0,
                insp_routine=current_bld.get('INSP_ROUTINE_REPAIR') or 0,
                insp_major=current_bld.get('INSP_MAJOR_REPAIR') or 0,
                insp_reconstruction=current_bld.get('INSP_RECONSTRUCTION') or 0,
                insp_refitting=current_bld.get('INSP_REFITTING') or 0,
                suit_idp_yes=current_bld.get('SUIT_IDP_YES') or 0,
                suit_recon=current_bld.get('SUIT_AFTER_RECON') or 0,
                suit_refit=current_bld.get('SUIT_AFTER_REFIT') or 0,
                suit_unsuitable=current_bld.get('SUIT_UNSUITABLE') or 0,
                free_area=current_bld.get('BLD_FREE_AREA') or 0.0,
                fieldwork_status=new_fw_status,
                insp_deviations_exist=current_bld.get('INSP_DEVIATIONS_EXIST') or 0,
                insp_deviations_desc=current_bld.get('INSP_DEVIATIONS_DESC') or '',
                insp_damage_exist=current_bld.get('INSP_DAMAGE_EXIST') or 0,
                insp_damage_desc=current_bld.get('INSP_DAMAGE_DESC') or '',
                insp_elec_exist=current_bld.get('INSP_ELECTRICITY_EXIST') or 0,
                insp_elec_desc=current_bld.get('INSP_ELECTRICITY_DESC') or '',
                insp_water_exist=current_bld.get('INSP_WATER_EXIST') or 0,
                insp_water_desc=current_bld.get('INSP_WATER_DESC') or '',
                insp_waste_exist=current_bld.get('INSP_WASTEWATER_EXIST') or 0,
                insp_waste_desc=current_bld.get('INSP_WASTEWATER_DESC') or '',
                insp_gas_exist=current_bld.get('INSP_GAS_EXIST') or 0,
                insp_gas_desc=current_bld.get('INSP_GAS_DESC') or '',
                insp_heat_exist=current_bld.get('INSP_HEATING_EXIST') or 0,
                insp_heat_desc=current_bld.get('INSP_HEATING_DESC') or ''
            )
            if success:
                push_database(f"Updated building documentation ({property_id})")
                st.success(f"✅ Documentation saved for building {b_id}.")
                st.rerun()
            else:
                st.error(f"❌ Database error: Failed to update documentation for {b_id}.")

    if submitted_s2:
        if current_bld:
            b_id = current_bld.get('SYS_BLD_ID')
            b_geom_id = current_bld.get('ID_BUILDING_GEOM')

            # Update Validation Flag (Preserve live toggle state)
            update_building_geom_flag(b_geom_id, is_accepted=is_validated)

            # Update Stage 2 Details
            success = update_building_details(
                b_id, 
                total_area=current_bld.get('BLD_TOTAL_AREA') or 0.0,
                floors=current_bld.get('BLD_FLOORS') or 1,
                bti_exist=current_bld.get('BLD_BTI_PASSPORT_EXIST') or 0,
                bti_desc=current_bld.get('BLD_BTI_PASSPORT_DESC') or '',
                ready_flag=current_bld.get('BLD_READY_FLAG') or 0,
                bld_type=current_bld.get('BLD_TYPE') or 'UNKNOWN',
                use_desc=current_bld.get('BLD_USE_DESC') or '',
                nc_code=current_bld.get('BLD_NC_CODE') or '',
                living_area=current_bld.get('BLD_LIVING_AREA') or 0.0,
                eng_sys=current_bld.get('BLD_ENG_SYS') or 0,
                footprint_area=current_bld.get('BLD_FOOTPRINT_AREA') or 0.0,
                total_volume=current_bld.get('BLD_TOTAL_VOLUME') or 0.0,
                insp_routine=current_bld.get('INSP_ROUTINE_REPAIR') or 0,
                insp_major=current_bld.get('INSP_MAJOR_REPAIR') or 0,
                insp_reconstruction=current_bld.get('INSP_RECONSTRUCTION') or 0,
                insp_refitting=current_bld.get('INSP_REFITTING') or 0,
                suit_idp_yes=current_bld.get('SUIT_IDP_YES') or 0,
                suit_recon=current_bld.get('SUIT_AFTER_RECON') or 0,
                suit_refit=current_bld.get('SUIT_AFTER_REFIT') or 0,
                suit_unsuitable=current_bld.get('SUIT_UNSUITABLE') or 0,
                free_area=current_bld.get('BLD_FREE_AREA') or 0.0,
                fieldwork_status=new_fw_status,
                insp_deviations_exist=int(new_insp_deviations_exist),
                insp_deviations_desc=new_insp_deviations_desc,
                insp_damage_exist=int(new_insp_damage_exist),
                insp_damage_desc=new_insp_damage_desc,
                insp_elec_exist=int(new_insp_elec_exist),
                insp_elec_desc=new_insp_elec_desc,
                insp_water_exist=int(new_insp_water_exist),
                insp_water_desc=new_insp_water_desc,
                insp_waste_exist=int(new_insp_waste_exist),
                insp_waste_desc=new_insp_waste_desc,
                insp_gas_exist=int(new_insp_gas_exist),
                insp_gas_desc=new_insp_gas_desc,
                insp_heat_exist=int(new_insp_heat_exist),
                insp_heat_desc=new_insp_heat_desc
            )
            if success:
                push_database(f"Updated building structural/utility assessment ({property_id})")
                st.success(f"✅ Stage 2 assessment saved for building {b_id}.")
                st.rerun()
            else:
                st.error(f"❌ Database error: Failed to update Stage 2 assessment for {b_id}.")

    if submitted_insp:
        if current_bld:
            b_id = current_bld.get('SYS_BLD_ID')
            b_geom_id = current_bld.get('ID_BUILDING_GEOM')

            # Update Validation Flag (Preserve live toggle state)
            update_building_geom_flag(b_geom_id, is_accepted=is_validated)

            # Update Inspection Metadata (Preserve current core and advanced fields)
            success = update_building_details(
                b_id, 
                total_area=current_bld.get('BLD_TOTAL_AREA') or 0.0,
                floors=current_bld.get('BLD_FLOORS') or 1,
                bti_exist=current_bld.get('BLD_BTI_PASSPORT_EXIST') or 0,
                bti_desc=current_bld.get('BLD_BTI_PASSPORT_DESC') or '',
                ready_flag=current_bld.get('BLD_READY_FLAG') or 0,
                bld_type=current_bld.get('BLD_TYPE') or 'UNKNOWN',
                use_desc=current_bld.get('BLD_USE_DESC') or '',
                nc_code=current_bld.get('BLD_NC_CODE') or '',
                living_area=current_bld.get('BLD_LIVING_AREA') or 0.0,
                eng_sys=current_bld.get('BLD_ENG_SYS') or 0,
                footprint_area=current_bld.get('BLD_FOOTPRINT_AREA') or 0.0,
                total_volume=current_bld.get('BLD_TOTAL_VOLUME') or 0.0,
                insp_routine=int(new_insp_routine),
                insp_major=int(new_insp_major),
                insp_reconstruction=int(new_insp_reconstruction),
                insp_refitting=int(new_insp_refitting),
                suit_idp_yes=current_bld.get('SUIT_IDP_YES') or 0,
                suit_recon=current_bld.get('SUIT_AFTER_RECON') or 0,
                suit_refit=current_bld.get('SUIT_AFTER_REFIT') or 0,
                suit_unsuitable=current_bld.get('SUIT_UNSUITABLE') or 0,
                free_area=current_bld.get('BLD_FREE_AREA') or 0.0,
                fieldwork_status=new_fw_status,
                insp_deviations_exist=current_bld.get('INSP_DEVIATIONS_EXIST') or 0,
                insp_deviations_desc=current_bld.get('INSP_DEVIATIONS_DESC') or '',
                insp_damage_exist=current_bld.get('INSP_DAMAGE_EXIST') or 0,
                insp_damage_desc=current_bld.get('INSP_DAMAGE_DESC') or '',
                insp_elec_exist=current_bld.get('INSP_ELECTRICITY_EXIST') or 0,
                insp_elec_desc=current_bld.get('INSP_ELECTRICITY_DESC') or '',
                insp_water_exist=current_bld.get('INSP_WATER_EXIST') or 0,
                insp_water_desc=current_bld.get('INSP_WATER_DESC') or '',
                insp_waste_exist=current_bld.get('INSP_WASTEWATER_EXIST') or 0,
                insp_waste_desc=current_bld.get('INSP_WASTEWATER_DESC') or '',
                insp_gas_exist=current_bld.get('INSP_GAS_EXIST') or 0,
                insp_gas_desc=current_bld.get('INSP_GAS_DESC') or '',
                insp_heat_exist=current_bld.get('INSP_HEATING_EXIST') or 0,
                insp_heat_desc=current_bld.get('INSP_HEATING_DESC') or ''
            )
            if success:
                push_database(f"Updated building inspection details ({property_id})")
                st.success(f"✅ Inspection details saved for building {b_id}.")
                st.rerun()
            else:
                st.error(f"❌ Database error: Failed to update inspection details for {b_id}.")

    if submitted_suit:
        if current_bld:
            b_id = current_bld.get('SYS_BLD_ID')
            b_geom_id = current_bld.get('ID_BUILDING_GEOM')

            # Update Validation Flag (Preserve live toggle state)
            update_building_geom_flag(b_geom_id, is_accepted=is_validated)

            # Update Suitability Metadata (Preserve current core, advanced and inspection fields)
            success = update_building_details(
                b_id, 
                total_area=current_bld.get('BLD_TOTAL_AREA') or 0.0,
                floors=current_bld.get('BLD_FLOORS') or 1,
                bti_exist=current_bld.get('BLD_BTI_PASSPORT_EXIST') or 0,
                bti_desc=current_bld.get('BLD_BTI_PASSPORT_DESC') or '',
                ready_flag=current_bld.get('BLD_READY_FLAG') or 0,
                bld_type=current_bld.get('BLD_TYPE') or 'UNKNOWN',
                use_desc=current_bld.get('BLD_USE_DESC') or '',
                nc_code=current_bld.get('BLD_NC_CODE') or '',
                living_area=current_bld.get('BLD_LIVING_AREA') or 0.0,
                eng_sys=current_bld.get('BLD_ENG_SYS') or 0,
                footprint_area=current_bld.get('BLD_FOOTPRINT_AREA') or 0.0,
                total_volume=current_bld.get('BLD_TOTAL_VOLUME') or 0.0,
                insp_routine=current_bld.get('INSP_ROUTINE_REPAIR') or 0,
                insp_major=current_bld.get('INSP_MAJOR_REPAIR') or 0,
                insp_reconstruction=current_bld.get('INSP_RECONSTRUCTION') or 0,
                insp_refitting=current_bld.get('INSP_REFITTING') or 0,
                suit_idp_yes=int(new_suit_idp_yes),
                suit_recon=int(new_suit_recon),
                suit_refit=int(new_suit_refit),
                suit_unsuitable=int(new_suit_unsuitable),
                free_area=current_bld.get('BLD_FREE_AREA') or 0.0,
                fieldwork_status=new_fw_status
            )
            if success:
                push_database(f"Updated building suitability assessment ({property_id})")
                st.success(f"✅ Suitability assessment saved for building {b_id}.")
                st.rerun()
            else:
                st.error(f"❌ Database error: Failed to update suitability assessment for {b_id}.")

    if submitted_safe:
        if current_bld:
            b_id = current_bld.get('SYS_BLD_ID')
            b_geom_id = current_bld.get('ID_BUILDING_GEOM')

            # Update Validation Flag (Preserve live toggle state)
            update_building_geom_flag(b_geom_id, is_accepted=is_validated)

            # Update Safety Metadata
            success = update_safety(
                building_id=b_id,
                pwd_access=int(new_pwd_access),
                fire=int(new_safe_fire),
                sanitary=int(new_safe_sanitary),
                civil_def=int(new_safe_civil),
                hazard_zone=new_hazard,
                safe_class=int(new_safe_class),
                safe_cat=int(new_safe_cat),
                safe_notes=new_safe_notes
            )
            if success:
                push_database(f"Updated building safety assessment ({property_id})")
                st.success(f"✅ Safety assessment saved for building {b_id}.")
                st.rerun()
            else:
                st.error(f"❌ Database error: Failed to update safety assessment for {b_id}.")

    if submitted_tech:
        if current_bld:
            b_id = current_bld.get('SYS_BLD_ID')
            b_geom_id = current_bld.get('ID_BUILDING_GEOM')

            # Update Validation Flag
            update_building_geom_flag(b_geom_id, is_accepted=is_validated)

            # Update Technical Audit
            success = update_technical_audit(
                building_id=b_id,
                audit_date=t_audit_date.isoformat(),
                audit_engineer=t_audit_engineer,
                fnd_type=t_fnd_type,
                fnd_cond=t_fnd_cond,
                fnd_walls_type=t_fnd_walls_type,
                fnd_walls_cond=t_fnd_walls_cond,
                basement_type=t_basement_type,
                basement_cond=t_basement_cond,
                substructure_desc=t_substructure_desc,
                walls_type=t_walls_type,
                walls_cond=t_walls_cond,
                lintels_type=t_lintels_type,
                lintels_cond=t_lintels_cond,
                roof_type_type=t_roof_type,
                roof_type_cond=t_roof_type_cond,
                roof_mat_type=t_roof_mat,
                roof_mat_cond=t_roof_mat_cond,
                windows_type=t_windows_type,
                windows_cond=t_windows_cond,
                doors_type=t_doors_type,
                doors_cond=t_doors_cond,
                envelope_desc=t_envelope_desc,
                entrance_type=t_entrance_type,
                entrance_cond=t_entrance_cond,
                pavement_type=t_pavement_type,
                pavement_cond=t_pavement_cond,
                int_finish_type=t_int_finish_type,
                int_finish_cond=t_int_finish_cond,
                finishes_desc=t_finishes_desc
            )
            if success:
                push_database(f"Updated building technical audit ({property_id})")
                st.success(f"✅ Technical audit saved for building {b_id}.")
                st.rerun()
            else:
                st.error(f"❌ Database error: Failed to update technical audit for {b_id}.")

    # NOTE: The validation toggle also needs to persist its state if changed.
    # Currently it's a reactive toggle, but we save it in both form handlers.
