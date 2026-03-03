import streamlit as st
from db_core import (
    get_connection, get_enum_options, get_address_geometry,
    update_building_geometry, update_building_geom_flag,
    get_geometry_data, update_building_entr_flag,
    update_building_entrance_geometry, add_building,
    delete_building
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
    c.execute("SELECT * FROM TBL_CORE_BUILDING WHERE FK_PROPERTY_ID = ?", (property_id,))
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
            
            is_validated = st.toggle(
                "✅ Footprint Validated",
                value=bool(current_bld.get('GEOM_BLD_CREATED', 0)),
                disabled=not has_geom,
                key="val_toggle_reactive",
                help="Switch to GREEN (validated) or BLUE (draft)."
            )
            
            if not has_geom:
                st.caption("⚠️ No footprint found yet. Use the Search tool above.")

        # ----------------------------------------------------------
        # BUILDING METADATA FORM
        # ----------------------------------------------------------
        with st.form("building_metadata_form"):
            st.markdown("**Core Attributes**")
            b_area = st.number_input("Total Area (m²)", 
                                     value=current_bld.get('BLD_TOTAL_AREA', 0.0),
                                     format="%.2f")
            b_floors = st.number_input("Floors", 
                                       value=current_bld.get('BLD_FLOORS', 1),
                                       step=1)
            
            submitted = st.form_submit_button("💾 Save Building Changes", use_container_width=True)

        # ----------------------------------------------------------
        # DEBUG SUMMARY
        # ----------------------------------------------------------
        with st.expander("🔍 Debug: Data Summary"):
            col_d1, col_d2 = st.columns(2)
            with col_d1:
                st.write(f"Complex: {is_complex}")
                st.write(f"Point ready: {point_ready}")
            with col_d2:
                st.write(f"Geom stored: {has_geom}")
                st.write(f"Live Toggle: {is_validated}")

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

    if submitted:
        # Update validation flag and metadata
        if current_bld:
            b_id = current_bld.get('SYS_BLD_ID')
            b_geom_id = current_bld.get('ID_BUILDING_GEOM')
            
            # 1. Update Validation Flag
            update_building_geom_flag(b_geom_id, is_accepted=is_validated)
            
            # 2. Update Metadata Fields (Placeholder for bld_core functions)
            # For now, we update the TBL_CORE_BUILDING record directly
            conn = get_connection()
            c = conn.cursor()
            try:
                c.execute("""
                    UPDATE TBL_CORE_BUILDING
                    SET BLD_TOTAL_AREA = ?,
                        BLD_FLOORS     = ?
                    WHERE SYS_BLD_ID = ?
                """, (b_area, int(b_floors), b_id))
                conn.commit()
            finally:
                conn.close()
            
        push_database(f"Updated building details ({property_id})")
        st.success("✅ Building details and validation status saved.")
        st.rerun()
