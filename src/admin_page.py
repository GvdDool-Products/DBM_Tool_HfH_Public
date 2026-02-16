import streamlit as st
import pandas as pd
from db_core import get_users, add_user
from auth_manager import hash_password

def admin_page():
    # 1. USER PROFILE SECTION (Always visible)
    st.header("My Account")
    
    current_username = st.session_state.get('username', 'Unknown')
    current_role = st.session_state.get('user_role', 'expert')
    
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
                    from db_core import update_user_password
                    from auth_manager import hash_password
                    new_hash = hash_password(new_pw)
                    if update_user_password(current_username, new_hash):
                        from github_bridge import push_database
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
    if current_role == 'admin':
        st.header("Expert Team Management")
        
        # Expert List
        st.subheader("Current Experts")
        users = get_users()
        
        if users:
            for email, pw_hash, role, first_login in users:
                col1, col2, col3 = st.columns([3, 1, 1])
                with col1:
                    st.write(f"**{email}** ({role})")
                with col2:
                    if first_login:
                        st.caption("🆕 First Login Pending")
                    else:
                        st.caption("✅ Active")
                with col3:
                    if email != current_username:
                        if st.button("Delete", key=f"del_{email}"):
                            from db_core import delete_user
                            if delete_user(email):
                                from github_bridge import push_database
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
                new_role = st.selectbox("Role", ["expert", "admin"])
                temp_password = st.text_input("Temporary Password", type="password")
                submit = st.form_submit_button("Create User")
                
                if submit:
                    if new_email and temp_password:
                        pw_hash = hash_password(temp_password)
                        if add_user(new_email, pw_hash, new_role):
                            from github_bridge import push_database
                            push_database(f"New user created: {new_email}")
                            st.success(f"User {new_email} created successfully!")
                            st.rerun()
                        else:
                            st.error("User already exists or database error.")
                    else:
                        st.error("Please fill in all fields.")
    else:
        st.info("💡 You are logged in as an expert. Expert management is restricted to administrators.")

    # 3. DATABASE EXPLORER (Visible to all except 'visitor')
    if current_role != 'visitor':
        st.divider()
        st.header("🔍 Database Explorer")
        st.write("Quickly inspect the system's storage structure.")
        
        if st.checkbox("Show Table Schema"):
            import sqlite3
            from db_core import get_connection
            
            try:
                conn = get_connection()
                # Get all table names
                tables_df = pd.read_sql_query("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';", conn)
                
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
