import streamlit as st
import streamlit_authenticator as stauth
import bcrypt
from db_core import get_users, add_user, init_db

def hash_password(password):
    return stauth.Hasher.hash(password)

def init_auth():
    # Fetch users from the DB
    db_users = get_users()
    
    # If no users exist, seed the initial testingLocal user
    if not db_users:
        # We use the new Hasher.hash method for the seed
        admin_pw_hash = stauth.Hasher.hash('Local123')
        add_user('testingLocal', admin_pw_hash, 'admin')
        db_users = get_users()

    # Format for streamlit-authenticator
    credentials = {'usernames': {}}
    for email, pw_hash, role, first_login in db_users:
        credentials['usernames'][email] = {
            'email': email,
            'name': email,
            'password': pw_hash,
            'roles': [role] # Updated for 0.4.2 plural roles
        }

    authenticator = stauth.Authenticate(
        credentials,
        'housing_suitability_db_v3', # New cookie name to clear old sessions
        'abcdefghijklmnopqrstuvwxyz1234567890_SECURE_KEY', 
        cookie_expiry_days=0.1 # Short expiry for testing
    )
    
    return authenticator

def login_ui():
    # 1. SIMPLE AUTH BYPASS (User requested for local/cloud testing)
    # This allows a quick entry without the complex library if needed
    st.sidebar.title("Simple Auth (Dev Mode)")
    simple_user = st.sidebar.text_input("User", key="simple_u")
    simple_pass = st.sidebar.text_input("Pass", type="password", key="simple_p")
    
    if (simple_user == "testingLocal" and simple_pass == "Local123") or \
       (simple_user == "testingCloud" and simple_pass == "Cloud987"):
        st.session_state['username'] = simple_user
        st.session_state['user_role'] = 'admin'
        st.session_state['authentication_status'] = True
        return True

    # 2. STANDARD AUTHENTICATOR
    authenticator = init_auth()
    
    # Determine the form name based on failure status for dynamic feedback
    form_name = "Login"
    if st.session_state.get('authentication_status') is False:
        form_name = "Login - user name or password incorrect, please try again!"
    
    # Render the login widget with custom fields
    authentication_status = authenticator.login(
        location='main', 
        fields={'Form name': form_name}
    )
    
    if st.session_state.get('authentication_status'):
        # Library stores the status and username in session state
        st.session_state['authenticator'] = authenticator
        username = st.session_state['username']
        
        # Clear the "First Login Pending" status in the DB
        from db_core import clear_first_login_flag
        if clear_first_login_flag(username):
            from github_bridge import push_database
            push_database(f"User {username} activated (first login)")
        
        # In 0.4.2, roles are stored in st.session_state['roles']
        # This is typically a list, so we take the first one or default to 'expert'
        roles = st.session_state.get('roles', [])
        if roles:
            st.session_state['user_role'] = roles[0]
        else:
            st.session_state['user_role'] = 'expert'
            
        return True
    
    # If not logged in, we return False. 
    # Importantly, the authenticator.login() call above already rendered the form.
    return False

def logout():
    # 1. Clear Streamlit-Authenticator session
    if 'authenticator' in st.session_state:
        # In unrendered mode, it clears the cookies/state without showing the button
        st.session_state['authenticator'].logout(location='unrendered')
    
    # 2. Force clear our custom session keys (for Simple Auth or stauth fallback)
    keys_to_clear = ['username', 'user_role', 'authentication_status', 'roles', 'name', 'logout']
    for key in keys_to_clear:
        if key in st.session_state:
            del st.session_state[key]
    
    st.rerun()
