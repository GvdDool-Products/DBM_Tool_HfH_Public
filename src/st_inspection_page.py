import streamlit as st
import pandas as pd
from db_core import (
    get_connection, get_enum_options, 
    add_property, delete_property,
    update_complex_flag,
    update_legal_ownership, update_property_address, 
    update_landplot, update_governance,
    get_address_geometry, update_address_geometry,
    reset_address_geometry
)
from github_bridge import push_database
from datetime import datetime
from utils.auxiliaryDataImport import geocode_address

import streamlit.components.v1 as components

# ------------------------------------------------------------------
# DESIGN PATTERN: UI Skeleton Management
# Following the 'Genesis' pattern from db_core.py, this page 
# provides the administrative interface for property skeletons.
# 
# Components:
#   1. Selection  : Select property (filtered by role/unit if needed).
#   2. Status     : Visual summary of missing skeleton data.
#   3. Tabs       : Separated forms to reduce cognitive load.
#   4. Validate   : Specific step for Geocoding (API + User interaction).
# ------------------------------------------------------------------

def activate_tab(tab_key, property_index=0):
    """
    Force activate a Streamlit tab by index using JS injection.
    Used to keep user on the same tab after st.rerun().
    """

    # Store property index for restoration after rerun
    st.session_state.property_index = property_index
    
    match tab_key:
        case 'legal':       tab_index = 0
        case 'address':     tab_index = 1
        case 'land':        tab_index = 2
        case 'governance':  tab_index = 3
        case _:             tab_index = 0  # default to first tab

    components.html(f"""
        <script>
            window.parent.document.querySelectorAll('[data-baseweb="tab"]')[{tab_index}].click();
        </script>
    """, height=0)

try:
    import folium
    from streamlit_folium import st_folium
except ImportError:
    folium = None
    st_folium = None

def get_properties_list():
    """Fetches a list of all properties for the selection dropdown/table."""
    conn = get_connection()
    query = """
    SELECT 
        p.SYS_PROPERTY_ID, 
        p.ID_ADMIN_UNIT, 
        p.ID_CADASTRAL_NO,
        a.CITY,
        a.ADDR_LINE1
    FROM TBL_CORE_PROPERTY p
    LEFT JOIN TBL_CORE_ADDRESS a ON p.SYS_PROPERTY_ID = a.FK_PROPERTY_ID
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

def get_property_skeleton(property_id):
    """Fetches all skeleton data for a specific property."""
    conn = get_connection()
    c = conn.cursor()
    
    data = {}

    # 0. Property
    c.execute("SELECT * FROM TBL_CORE_PROPERTY WHERE SYS_PROPERTY_ID = ?", (property_id,))
    row = c.fetchone()
    cols = [d[0] for d in c.description]
    data['property_dict'] = dict(zip(cols, row)) if row else {}
    
    # 1. Legal Ownership
    c.execute("SELECT * FROM TBL_CORE_LEGAL_OWNERSHIP WHERE FK_PROPERTY_ID = ?", (property_id,))
    row = c.fetchone()
    cols = [d[0] for d in c.description]
    data['legal_dict'] = dict(zip(cols, row)) if row else {}

    # 2. Address
    c.execute("SELECT * FROM TBL_CORE_ADDRESS WHERE FK_PROPERTY_ID = ?", (property_id,))
    row = c.fetchone()
    cols = [d[0] for d in c.description]
    data['address_dict'] = dict(zip(cols, row)) if row else {}

    # 3. Land Plot
    c.execute("SELECT * FROM TBL_CORE_LANDPLOT WHERE FK_PROPERTY_ID = ?", (property_id,))
    row = c.fetchone()
    cols = [d[0] for d in c.description]
    data['land_dict'] = dict(zip(cols, row)) if row else {}

    # 4. Governance
    c.execute("SELECT * FROM TBL_CORE_GOVERNANCE WHERE FK_PROPERTY_ID = ?", (property_id,))
    row = c.fetchone()
    cols = [d[0] for d in c.description]
    data['gov_dict'] = dict(zip(cols, row)) if row else {}

    conn.close()
    return data

def get_skeleton_status(data, is_pending=False):
    """Calculates completeness status of the property skeleton."""
    missing = []
    
    # Check Legal
    l = data.get('legal_dict', {})
    if not l.get('OWN_TYPE') or l.get('OWN_TYPE') == 'UNKNOWN':
        missing.append("Ownership Type")
    
    # Check Address — two sequential states
    a = data.get('address_dict', {})
    addr_line = a.get('ADDR_LINE1')
    addr_geom = a.get('ADDR_GEOM_CREATED', 0)

    if not addr_line or addr_line == 'UNKNOWN':
        # Step 1 not done — address text missing
        missing.append("Address Not Given")
    elif addr_geom == 0 and not is_pending:
        # Step 1 done, step 2 not done — text exists but no geometry
        missing.append("Geometry Not Set")
    elif addr_geom == 0 and is_pending:
        # Step 1 done, step 2 in progress — geocode pending user confirmation
        missing.append("Geometry Pending")

    # Check Governance
    g = data.get('gov_dict', {})
    if not g.get('GOV_COMMISSION_DEC'):
        missing.append("Gov Decision")

    if not missing:
        return "✅ Ready for Inspection", "green"
    elif len(missing) >= 3:
        return "🔴 Skeleton Required", "red"
    else:
        return f"🟡 {', '.join(missing)} Missing", "orange"

def inspection_page():
    st.header("Property Inspection & Inventory")
    st.write("""Review and complete the property record before proceeding to the physical building assessment. "
         "Ensure ownership details, address and location are confirmed, and any available governance "
         "documentation is recorded.""")

    # Before the tabs are rendered
    if 'active_tab' not in st.session_state:
        st.session_state.active_tab = 0
    if 'draft_addr_location' not in st.session_state:
        st.session_state.draft_addr_location = None
    if 'edit_addr_mode' not in st.session_state:
        st.session_state.edit_addr_mode = False

    # 1. PROPERTY SELECTION
    properties_df = get_properties_list()
    
    if properties_df.empty:
        st.info("No properties found. Please add or import properties first.")
        return

    # Create a nice display label for selection
    properties_df['display_label'] = properties_df.apply(
        lambda x: f"{x['ID_CADASTRAL_NO']} | {x['ID_ADMIN_UNIT']} ({x['CITY'] or 'No City Data'})", axis=1
    )
    
    selected_label = st.selectbox("Select Property to Manage", properties_df['display_label'])
    selected_id = properties_df[properties_df['display_label'] == selected_label]['SYS_PROPERTY_ID'].values[0]

    # Store after every render — user click or rerun
    st.session_state.property_index = properties_df['display_label'].tolist().index(selected_label)

    # data management functions: add and delete records:
    col_add, col_del, col_spacer = st.columns([1, 1, 6])
    with col_add:
        if st.button("➕ Add Property", type="secondary"):
            st.session_state.show_add_property = True
    with col_del:
        if st.button("🗑️ Delete Property", type="secondary"):
            st.session_state.show_delete_confirm = True

    # Add Property form
    if st.session_state.get('show_add_property'):
        with st.form("add_property_form"):
            st.subheader("Add New Property")
            col_a, col_b = st.columns(2)
            with col_a:
                new_cadastral_no = st.text_input("Cadastral Number")
            with col_b:
                new_admin_unit   = st.text_input("Administrative Unit")
            
            col_s, col_c = st.columns([1, 5])
            with col_s:
                submitted_add = st.form_submit_button("Create Property", type="primary")
            with col_c:
                cancel = st.form_submit_button("Cancel")

        if submitted_add:
            new_id = add_property(new_admin_unit, new_cadastral_no)
            if new_id:
                st.session_state.show_add_property = False
                push_database(f"New property added: {new_id}")
                st.success(f"✅ Property created successfully.")
                st.rerun()
            else:
                st.error("❌ Error creating property.")
        if cancel:
            st.session_state.show_add_property = False
            st.rerun()
        ### Add end
        
    # Delete confirmation
    if st.session_state.get('show_delete_confirm'):
        st.warning(f"⚠️ Are you sure you want to delete **{selected_label}**? This cannot be undone.")
        col_yes, col_no = st.columns([1, 5])
        with col_yes:
            if st.button("Yes, Delete", type="primary"):
                if delete_property(selected_id):
                    st.session_state.show_delete_confirm = False
                    st.session_state.property_index = 0
                    push_database(f"Property deleted: {selected_id}")
                    st.success("✅ Property deleted.")
                    st.rerun()
                else:
                    st.error("❌ Error deleting property.")
        with col_no:
            if st.button("Cancel"):
                st.session_state.show_delete_confirm = False
                st.rerun()
    ### Delete end

    # 2. PROPERTY SKELETON MANAGEMENT
    if selected_id:
        skeleton_data = get_property_skeleton(selected_id)
        p_dict = skeleton_data.get('property_dict', {})
        
        is_pending = ('pending_geocode' in st.session_state or st.session_state.get('geocode_rejected'))
        status_text, color = get_skeleton_status(skeleton_data, is_pending=is_pending)
        
        # Display Summary Card
        st.divider()
        col1, col2 = st.columns([3, 1])
        with col1:
            st.subheader(f"Property: {selected_label}")
        with col2:
            st.markdown(f"**Status:** :{color}[{status_text}]")
        
        # 2. STAGE 1: TABBED SKELETON MANAGEMENT
        tab_legal, tab_addr, tab_land, tab_gov = st.tabs([
            "⚖️ Legal & Ownership", 
            "📍 Address Details", 
            "🌳 Land Plot", 
            "🏛️ Governance"
        ])

        with tab_legal:
            st.subheader("Legal Ownership Details")
            l_dict = skeleton_data.get('legal_dict', {})
            
            with st.form("legal_form"):
                col1, col2 = st.columns(2)
                with col1:
                    own_type_rules = get_enum_options("OWN_TYPE")
                    own_type_codes   = [o[0] for o in own_type_rules]
                    own_type_labels  = [o[1] for o in own_type_rules]
                    label_to_code_type = dict(zip(own_type_labels, own_type_codes))

                    current_own_type = l_dict.get('OWN_TYPE', 'UNKNOWN')
                    try:
                        own_type_idx = own_type_codes.index(current_own_type)
                    except ValueError:
                        own_type_idx = 0

                    selected_type_label = st.selectbox("Ownership Type", own_type_labels, index=own_type_idx)
                    new_own_type = label_to_code_type.get(selected_type_label, "UNKNOWN")

                    entity_rules = get_enum_options("OWN_ENTITY")
                    entity_codes   = [o[0] for o in entity_rules]
                    entity_labels  = [o[1] for o in entity_rules]
                    label_to_code_entity = dict(zip(entity_labels, entity_codes))

                    current_own_entity = l_dict.get('OWN_ENTITY', 'UNKNOWN')
                    try:
                        own_entity_idx = entity_codes.index(current_own_entity)
                    except ValueError:
                        own_entity_idx = 0

                    selected_entity_label = st.selectbox("Owner Entity Type", entity_labels, index=own_entity_idx)
                    new_entity = label_to_code_entity.get(selected_entity_label, "UNKNOWN")

                with col2:
                    new_doc_exists = st.toggle("Legal Document Exists", value=bool(l_dict.get('LEG_DOC_EXIST', 0)))
                    new_consent = st.toggle("Owner Consent Obtained", value=bool(l_dict.get('OWN_CONSENT', 0)))
                    new_complex    = st.toggle("Complex / Multi-Building Property", value=bool(p_dict.get('ID_COMPLEX_FLAG', 0)))
                
                new_encumbrances = st.text_area("Encumbrances / Restrictions", value=l_dict.get('ENCUMBRANCES', '') or '')
                
                ### update legal
                with st.expander("🏛️ Land & Legal Status — Stage 2"):
                    st.caption("These fields will be available for editing in Stage 2.")
                    col_land1, col_land2 = st.columns(2)
                    with col_land1:
                        st.text_input("Land Use Designation",
                                      value=l_dict.get('LAND_USE_DESIG', '') or '',
                                      disabled=True)
                        st.text_input("Land Ownership Form",
                                      value=l_dict.get('LAND_OWN_FORM', '') or '',
                                      disabled=True)
                    with col_land2:
                        st.text_input("Land Title Document Reference",
                                      value=l_dict.get('LAND_TITLE_DOC', '') or '',
                                      disabled=True)
                ###
                if st.form_submit_button("Update Legal Info"):
                    if update_legal_ownership(selected_id, new_own_type, new_entity, new_doc_exists, new_consent, new_encumbrances):
                        update_complex_flag(selected_id, new_complex)
                        push_database(f"Legal info updated for {selected_id}")
                        st.success("Legal information updated successfully!")
                        
                        #activate_tab('legal')
                        activate_tab('legal', property_index=st.session_state.get('property_index', 0))
                        st.rerun()
                    else:
                        st.error("Error updating legal info.")
        
        ### Tab Address
        with tab_addr:
            a_dict = get_property_skeleton(selected_id).get('address_dict', {})
            st.subheader("Precise Address Information")

            # 1. LAYOUT: Colum Layout outside the form for interactivity
            col_info, col_map = st.columns([2, 4])

            with col_info:
                with st.form("address_text_form"):
                    st.markdown("**Postal Address Details**")
                    new_line1 = st.text_input("Street & Number",
                                            value=a_dict.get('ADDR_LINE1', '') or '',
                                            help="Format: Street Name, Number — e.g. Saksaganskogo, 36")
                    new_line2 = st.text_input("Apartment / Unit / Additional",
                                            value=a_dict.get('ADDR_LINE2', '') or '')
                    col_city, col_post = st.columns(2)
                    with col_city:
                        new_city = st.text_input("City / Town", value=a_dict.get('CITY', '') or '')
                    with col_post:
                        new_postcode = st.text_input("Postal Code", value=a_dict.get('POSTCODE', '') or '')
                    new_country = st.text_input("Country", value=a_dict.get('COUNTRY', '') or '')

                    addr_type_options  = get_enum_options("ADDR_TYPE")
                    addr_type_codes    = [o[0] for o in addr_type_options]
                    addr_type_labels   = [o[1] for o in addr_type_options]
                    label_to_code_addr = dict(zip(addr_type_labels, addr_type_codes))

                    current_addr_type = a_dict.get('ADDR_TYPE', 'UNKNOWN')
                    try:
                        addr_type_idx = addr_type_codes.index(current_addr_type)
                    except ValueError:
                        addr_type_idx = 0

                    selected_addr_type_label = st.selectbox("Address Type", addr_type_labels, index=addr_type_idx)
                    new_addr_type = label_to_code_addr.get(selected_addr_type_label, "UNKNOWN")
                    
                    submitted = st.form_submit_button("Update Address Text & Geocode", use_container_width=True)

                # Sync with toggle in col_map
                edit_mode_active = st.session_state.get('edit_addr_mode', False)
                if not edit_mode_active:
                    st.session_state.draft_addr_location = None

            with col_map:
                # -- Map Toolbar Header --
                tool_col1, tool_col2, tool_col3, tool_col4 = st.columns([1.2, 1, 1, 1])
                
                with tool_col1:
                    if st.session_state.get('pending_geocode'):
                        st.markdown("⏳ **Pending**")
                    elif a_dict.get('ADDR_GEOM_CREATED', 0):
                        st.markdown("✅ **Confirmed**")
                    else:
                        st.markdown("📍 **No Geom**")
                
                with tool_col2:
                    edit_mode_active = st.toggle(
                        "✏️ Edit",
                        value=st.session_state.edit_addr_mode,
                        help="Point to a new location on the map.",
                        key="edit_addr_mode_toggle"
                    )
                    st.session_state.edit_addr_mode = edit_mode_active

                has_draft = st.session_state.get('draft_addr_location') is not None
                
                with tool_col3:
                    save_pos = st.button("💾 Save", 
                                         type="primary", 
                                         disabled=not (edit_mode_active and has_draft),
                                         use_container_width=True,
                                         help="Save the new marker location.")
                
                with tool_col4:
                    reset_pos = st.button("🔄 Reset", 
                                          disabled=not (edit_mode_active and has_draft),
                                          use_container_width=True,
                                          help="Discard the temporary pin.")
                    if reset_pos:
                        st.session_state.draft_addr_location = None
                        st.rerun()

                # -- Handle Save Action --
                if save_pos:
                    result = update_address_geometry(
                        addr_geom_id     = a_dict.get('ID_ADDR_GEOM'),
                        latitude         = st.session_state.draft_addr_location[0],
                        longitude        = st.session_state.draft_addr_location[1],
                        resolved_address = a_dict.get('ADDR_LINE1', 'Manual Entry'),
                        updated_by       = st.session_state.get('user_email', 'SYSTEM')
                    )
                    if result:
                        st.session_state.draft_addr_location = None
                        st.session_state.edit_addr_mode = False
                        push_database(f"Geometry manually updated for {selected_id}")
                        st.success("✅ Marker location saved successfully!")
                        activate_tab('address', property_index=st.session_state.get('property_index', 0))
                        st.rerun()
                    else:
                        st.error("❌ Error saving manual geometry.")

                if st.session_state.get('pending_geocode') and folium and st_folium:
                    result = st.session_state.pending_geocode
                    m = folium.Map(
                        location=[result['latitude'], result['longitude']], 
                        zoom_start=16
                    )
                    folium.Marker(
                        location=[result['latitude'], result['longitude']],
                        tooltip=result['resolved_address'],
                        icon=folium.Icon(color='orange', icon='question-sign')
                    ).add_to(m)
                    
                    st_folium(m, use_container_width=True, height=500, key="pending_map")
                    st.caption(f"📍 Resolved: {result['resolved_address']}")
                    
                    if st.button("📍 Validate Address Location", type="primary", use_container_width=True):
                        result = update_address_geometry(
                            addr_geom_id     = st.session_state.pending_geom_id,
                            latitude         = st.session_state.pending_geocode['latitude'],
                            longitude        = st.session_state.pending_geocode['longitude'],
                            resolved_address = st.session_state.pending_geocode['resolved_address'],
                            updated_by       = st.session_state.get('user_email', 'SYSTEM')
                        )
                        
                        push_database(f"Geometry validated for {selected_id}")
                        st.session_state.pending_geocode = None
                        st.session_state.pending_geom_id = None
                        activate_tab('address', property_index=st.session_state.get('property_index', 0))
                        st.rerun()

                elif a_dict.get('ADDR_GEOM_CREATED', 0) and folium and st_folium:
                    geom = get_address_geometry(a_dict.get('ID_ADDR_GEOM'))
                    if geom:
                        display_lat, display_lng = geom['latitude'], geom['longitude']
                        is_draft = False
                        
                        if edit_mode_active and st.session_state.get('draft_addr_location'):
                            display_lat, display_lng = st.session_state.draft_addr_location
                            is_draft = True

                        m = folium.Map(location=[display_lat, display_lng], zoom_start=18 if is_draft else 16)
                        
                        # Original Marker
                        folium.Marker(
                            location=[geom['latitude'], geom['longitude']],
                            tooltip="Original Location",
                            icon=folium.Icon(color='green', icon='home', opacity=0.6 if is_draft else 1.0)
                        ).add_to(m)
                        
                        # Temporary Pin
                        if is_draft:
                            folium.Marker(
                                location=[display_lat, display_lng],
                                tooltip="New Temporary Location (Unsaved)",
                                icon=folium.Icon(color='orange', icon='info-sign')
                            ).add_to(m)
                        
                        map_output = st_folium(m, use_container_width=True, height=500, key="confirmed_map")
                        
                        if edit_mode_active and map_output.get("last_clicked"):
                            clicked = map_output["last_clicked"]
                            st.session_state.draft_addr_location = (clicked["lat"], clicked["lng"])
                            st.rerun()

                        # -- Coordinate Display Row (Stable placement below map) --
                        if edit_mode_active:
                            st.divider()
                            st.markdown("**📍 New Placement Coordinates:**")
                            c_lat, c_lon = st.columns(2)
                            if st.session_state.draft_addr_location:
                                d_lat, d_lon = st.session_state.draft_addr_location
                                c_lat.markdown(f"**Latitude:** `{d_lat:.6f}`")
                                c_lon.markdown(f"**Longitude:** `{d_lon:.6f}`")
                            else:
                                c_lat.markdown(f"**Latitude:** `0.000000`")
                                c_lon.markdown(f"**Longitude:** `0.000000`")
                                st.info("👆 *Click on the map to set the new location*")
                else:
                    st.info("🗺️ Map will appear here once a location is found.")

            if submitted:
                if update_property_address(selected_id, new_line1, new_line2,
                            new_city, new_postcode, new_country,
                            new_addr_type):
                    
                    reset_address_geometry(
                        addr_geom_id = a_dict.get('ID_ADDR_GEOM'),
                        updated_by   = st.session_state.get('user_email', 'SYSTEM')
                    )
            
                    result = geocode_address({
                        'ADDR_LINE1': new_line1, 'ADDR_LINE2': new_line2,
                        'CITY':       new_city,  'POSTCODE':   new_postcode,
                        'COUNTRY':    new_country
                    })
                    if result:
                        st.session_state.pending_geocode = result
                        st.session_state.pending_geom_id = a_dict.get('ID_ADDR_GEOM')
                    else:
                        st.session_state.pending_geocode = None
                        st.warning("⚠️ Address saved but location could not be found.")
                    
                    push_database(f"Address updated for {selected_id}")
                    activate_tab('address', property_index=st.session_state.get('property_index', 0))
                    st.rerun()
                else:
                    st.error("❌ Error saving address.")
        ### Tab Land
        with tab_land:
            st.subheader("Land Plot Characteristics")
            ln_dict = skeleton_data.get('land_dict', {})
            
            with st.form("land_form"):
                col1, col2 = st.columns(2)
                with col1:
                    new_size = st.number_input("Plot Size (sqm)", 
                                                value=float(ln_dict.get('LAND_SIZE', 0) or 0))
                    new_cat  = st.text_input("Land Category", 
                                              value=ln_dict.get('LAND_CATEGORY', '') or '')
                with col2:
                    new_intended_use = st.text_input("Intended Use", 
                                                      value=ln_dict.get('LAND_INTENDED_USE', '') or '')

                with st.expander("🔍 Inspection / Fieldwork Results — Stage 2"):
                    st.caption("These fields will be completed during fieldwork in Stage 2.")
                    col_f1, col_f2 = st.columns(2)
                    with col_f1:
                        st.text_input("Factual Use", 
                                      value=ln_dict.get('LAND_FACTUAL_USE', '') or '',
                                      disabled=True)
                        st.text_input("Vegetation", 
                                      value=ln_dict.get('LAND_VEGETATION', '') or '',
                                      disabled=True)
                    with col_f2:
                        st.checkbox("Temporary Structures Present", 
                                    value=bool(ln_dict.get('LAND_TEMP_STRUCT', 0)),
                                    disabled=True)

                # TODO: excluding the Phase 2 fields, as these are not available at this stage
                # Update the fields when the data is available and form is agreed
                if st.form_submit_button("Update Land Plot"):
                    if update_landplot(selected_id, new_size, new_cat, new_intended_use):
                        push_database(f"Land plot updated for {selected_id}")
                        st.success("Land plot info updated successfully!")
                        
                        #activate_tab('land')
                        activate_tab('land', property_index=st.session_state.get('property_index', 0))
                        st.rerun()
                    else:
                        st.error("Error updating land plot.")

        with tab_gov:
            st.subheader("Governance & External Tracking")
            g_dict = skeleton_data.get('gov_dict', {})
            
            with st.form("gov_form"):
                new_comm = st.text_input("Commission Decision No", 
                                          value=g_dict.get('GOV_COMMISSION_DEC', '') or '')
                
                col1, col2 = st.columns(2)
                with col1:
                    db_date = g_dict.get('GOV_DECISION_DATE', None)
                    try:
                        default_date = datetime.fromisoformat(db_date).date() if db_date else datetime.now().date()
                    except ValueError:
                        default_date = datetime.now().date()
                    new_date       = st.date_input("Decision Date", value=default_date)
                    new_disclosure = st.toggle("Information Disclosure Consent", 
                                               value=bool(g_dict.get('GOV_DISCLOSURE', 0)))
                with col2:
                    st.empty()

                with st.expander("🔗 External System References — Under Development"):
                    st.caption("These fields can be filled in manually, but cross-referencing with external systems is not yet supported. Automatic synchronisation will be added when external system data is received.")
                    col_ext1, col_ext2 = st.columns(2)
                    with col_ext1:
                        new_ias     = st.text_input("IAS Entry Reference", 
                                                     value=g_dict.get('GOV_IAS_ENTRY', '') or '')
                        new_funding = st.text_input("Funding Source", 
                                                     value=g_dict.get('GOV_FUNDING', '') or '')
                    with col_ext2:
                        new_dream   = st.text_input("DREAM / SIDAR Reference", 
                                                     value=g_dict.get('GOV_DREAM_SIDAR', '') or '')

                if st.form_submit_button("Update Governance Info"):
                    if update_governance(selected_id, new_comm, new_date.isoformat(),
                                         new_disclosure, new_ias, new_funding, new_dream):
                        push_database(f"Governance info updated for {selected_id}")
                        st.success("Governance info updated successfully!")
                        
                        #activate_tab('governance')
                        activate_tab('governance', property_index=st.session_state.get('property_index', 0))
                        st.rerun()
                    else:
                        st.error("Error updating governance info.")
        
        ### END PROPERTY INFO TABS

        st.divider()
        st.subheader("🚀 Next Stage: Physical Inspection Preparation")
        if st.button("Proceed to Building Assessment", type="primary"):
            st.session_state.show_building_page = True
            st.session_state.building_property_id = selected_id

        if st.session_state.get('show_building_page'):
            # Verify the stored property matches the selected one
            if st.session_state.building_property_id != selected_id:
                # User switched property — reset building page
                st.session_state.show_building_page = False
                st.session_state.pop('pending_footprint', None)
                st.session_state.pop('pending_bld_geom_id', None)
            else:
                from st_building_page import building_page
                building_page(st.session_state.building_property_id)
