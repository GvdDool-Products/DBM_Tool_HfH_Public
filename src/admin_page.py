import streamlit as st
import pandas as pd
from db_core import get_users, add_user, get_enum_options, get_connection, update_user_password, delete_user
from github_bridge import push_database

from auth_manager import hash_password
from utils.auxiliaryDataImport import AuxiliaryDataImporter, AVAILABLE_DATASETS

def admin_page():
    # 1. USER PROFILE SECTION (Always visible)
    st.header("My Account")
    
    current_username = st.session_state.get('username', 'Unknown')
    current_role = st.session_state.get('user_role', 'Expert')
    
    st.write(f"**Username:** `{current_username}`")
    st.write(f"**Role:** `{current_role}`")
    
    # "User Details with a toggle: edit"
    edit_mode = st.checkbox("Edit Profile / Change Password")
    
    if edit_mode:
        with st.form("change_password_form"):
            st.subheader("Update Credentials")
            new_pw = st.text_input("New Password", type="password")
            confirm_pw = st.text_input("Confirm New Password", type="password")
            save_pw = st.form_submit_button("Save Changes")
            
            if save_pw:
                if new_pw and new_pw == confirm_pw:
                    #from auth_manager import hash_password

                    new_hash = hash_password(new_pw)           # Update password form
                    
                    if update_user_password(current_username, new_hash):
                        push_database(f"Password updated for {current_username}")
                        st.success("Credentials updated successfully!")
                    else:
                        st.error("Database error.")
                elif new_pw != confirm_pw:
                    st.error("Passwords do not match.")
                else:
                    st.error("Please enter a valid password.")

    st.divider()

    # 2. ADMIN-ONLY MANAGEMENT SECTION
    role_options = get_enum_options("ROLE")
    role_codes = [code for code, label in role_options]
    admin_code = next((code for code, label in role_options if code == "ADMIN"), "ADMIN")
    if current_role == admin_code:
        st.header("Expert Team Management")
        
        # Expert List
        st.subheader("Current Experts")
        users = get_users()

        # Build mapping from ROLE code → label
        role_options = get_enum_options("ROLE")  # [(ENUM_CODE, ENUM_LABEL)]
        code_to_label = {code: label for code, label in role_options}
        
        if users:
            for email, pw_hash, role, first_login in users:
                role_label = code_to_label.get(role, role)  # fallback to code if label missing

                col1, col2, col3 = st.columns([3, 1, 1])
                with col1:
                    st.write(f"**{email}** ({role_label})")  # show human-readable label
                with col2:
                    if first_login:
                        st.caption("🆕 First Login Pending")
                    else:
                        st.caption("✅ Active")
                with col3:
                    if email != current_username:
                        if st.button("Delete", key=f"del_{email}"):
                                push_database(f"User {email} deleted")
                                st.success(f"Deleted {email}")
                                st.rerun()
                    else:
                        st.write("(You)")
                st.divider()
        else:
            st.info("No experts registered.")
        
        # Add New User
        st.subheader("Register New Expert")
        with st.expander("Add Expert Account"):
            with st.form("add_user_form"):
                new_email = st.text_input("Username / Email")
                
                # Fetch all active ROLE enums
                role_options = get_enum_options("ROLE")  # returns list of (ENUM_CODE, ENUM_LABEL)
                role_codes = [code for code, label in role_options]
                role_labels = [label for code, label in role_options]
                label_to_code = {label: code for code, label in role_options}

                # Streamlit selectbox using labels
                new_role_label = st.selectbox("Role", role_labels)
                #new_role = st.selectbox("Role", ["expert", "admin"]) - old code
                new_role = label_to_code[new_role_label]  # <-- fix here
                temp_password = st.text_input("Temporary Password", type="password")
                submit = st.form_submit_button("Create User")
                
                if submit:
                    if new_email and temp_password:
                        pw_hash = hash_password(temp_password)

                        if add_user(new_email, pw_hash, new_role):
                            push_database(f"New user created: {new_email}")
                            st.success(f"User {new_email} created successfully!")
                            st.rerun()
                        else:
                            st.error("User already exists or database error.")
                    else:
                        st.error("Please fill in all fields.")
    else:
        st.info("💡 You are logged in as an expert. Expert management is restricted to administrators.")

    # 2b. AUXILIARY DATA MANAGEMENT (Visible to Admin and Expert)
    # Fetch roles again for consistency
    allowed_roles = ["ADMIN", "EXPERT"]
    
    if current_role in allowed_roles:
        st.divider()
        st.header("🌍 Import Auxiliary Data")
        st.write("Ingest administrative boundaries and other auxiliary datasets.")
        
        importer = AuxiliaryDataImporter(get_connection)
        
        # Dataset selection
        datasets = importer.get_available_datasets()
        dataset_names = sorted([d["name"] for d in datasets])
        dataset_ids = {d["name"]: d["id"] for d in datasets}
        
        selected_name = st.selectbox("Select Dataset to Ingest", dataset_names)
        selected_id = dataset_ids[selected_name]
        
        # Display dataset info
        dataset_info = next((d for d in datasets if d["id"] == selected_id), None)
        if dataset_info:
            st.info(f"**Source:** {dataset_info['source']} | **Type:** {dataset_info['type']}\n\n{dataset_info['description']}")
        
        # Check if already loaded
        is_loaded = importer.is_dataset_loaded(selected_id)
        
        col1, col2 = st.columns([1, 4])
        with col1:
            if st.button("Ingest Data", type="primary"):
                if is_loaded:
                    st.warning(f"Dataset '{selected_name}' is already loaded. Use confirmation below to overwrite.")
                else:
                    with st.spinner(f"Ingesting {selected_name}..."):
                        success, message = importer.ingest_dataset(selected_id)
                        if success:
                            st.success(message)
                            push_database(f"Auxiliary data ingested: {selected_id}")
                        else:
                            st.error(message)
        
        if is_loaded:
            with st.expander("Overwrite Existing Data"):
                st.warning("Overwriting will delete existing records for this dataset.")
                if st.button("Confirm Overwrite", key=f"overwrite_{selected_id}"):
                    with st.spinner(f"Overwriting {selected_name}..."):
                        success, message = importer.ingest_dataset(selected_id, overwrite=True)
                        if success:
                            st.success(message)
                            push_database(f"Auxiliary data overwritten: {selected_id}")
                        else:
                            st.error(message)

    # 3. DATABASE EXPLORER (Visible to all except 'visitor')
    # ToDo: add VISITOR role to the enum table
    if current_role != 'VISITOR':
        st.divider()
        st.header("🔍 Database Explorer")
        st.write("Quickly inspect the system's storage structure.")
        
        if st.checkbox("Show Table Schema"):
            
            try:
                conn = get_connection()
                # Get all table names
                tables_df = pd.read_sql_query("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name NOT LIKE 'TBL_SYS_USERS' AND name NOT LIKE 'TBL_REF_ENUM%' ORDER BY name;", conn)
                
                if not tables_df.empty:
                    selected_table = st.selectbox("Select a table to inspect:", tables_df['name'])
                    
                    if selected_table:
                        st.write(f"**Fields in `{selected_table}`:**")
                        # Get column info
                        cols_df = pd.read_sql_query(f"PRAGMA table_info({selected_table});", conn)
                        # Clean up display (cid, name, type, notnull, dflt_value, pk)
                        st.dataframe(cols_df[['name', 'type', 'notnull', 'pk']], width='stretch')
                        
                        if st.checkbox(f"Preview First 5 Rows of {selected_table}"):
                            data_df = pd.read_sql_query(f"SELECT * FROM {selected_table} LIMIT 5;", conn)
                            st.dataframe(data_df, width='stretch')
                else:
                    st.warning("No tables found in database.")
                
                conn.close()
            except Exception as e:
                st.error(f"Error accessing schema: {e}")
