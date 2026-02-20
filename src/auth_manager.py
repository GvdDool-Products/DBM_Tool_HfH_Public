import streamlit as st
import streamlit_authenticator as stauth
from db_core import get_users, add_user, init_db, clear_first_login_flag
from github_bridge import push_database

def hash_password(password):
    return stauth.Hasher.hash(password)

def init_auth():
    """Fetch users from the DB and prepare the authenticator object"""
    db_users = get_users()
    
    # If no users exist (new DB), seed the initial testingLocal user
    if not db_users:
        admin_pw_hash = stauth.Hasher.hash('Local123')
        add_user('testingLocal', admin_pw_hash, 'ADMIN')
        db_users = get_users()

    # Format for streamlit-authenticator (0.4.x)
    credentials = {'usernames': {}}
    for email, pw_hash, role, first_login in db_users:
        credentials['usernames'][email] = {
            'email': email,
            'name': email,
            'password': pw_hash,
            'roles': [role.upper()] # Ensure uppercase for compatibility
        }

    # BUMP COOKIE VERSION TO _v5 and set expiry to 0
    # This ensures sessions do NOT persist after the browser/program is closed.
    authenticator = stauth.Authenticate(
        credentials,
        'housing_suitability_db_v5', # New version
        'abcdefghijklmnopqrstuvwxyz1234567890_SECURE_KEY', 
        cookie_expiry_days=0  # 0 means the cookie expires when the browser closes
    )
    
    return authenticator

def login_ui():
    """Primary Login Logic"""
    # 0. Check if already authenticated (either via Dev Mode or DB)
    if st.session_state.get('authentication_status'):
        return True

    # 1. SIMPLE AUTH BYPASS (Sidebar Dev Mode)
    st.sidebar.title("Simple Auth (Dev Mode)")
    simple_user = st.sidebar.text_input("User", key="simple_u")
    simple_pass = st.sidebar.text_input("Pass", type="password", key="simple_p")
    
    if (simple_user == "testingLocal" and simple_pass == "Local123") or \
       (simple_user == "testingCloud" and simple_pass == "Cloud987"):
        st.session_state['username'] = simple_user
        st.session_state['user_role'] = 'ADMIN'
        st.session_state['authentication_status'] = True
        st.rerun() # Rerun to bypass stauth call below

    # 2. STANDARD AUTHENTICATOR
    try:
        authenticator = init_auth()
        
        # Determine the form name based on failure status
        form_name = "Login"
        if st.session_state.get('authentication_status') is False:
            form_name = "Login - username or password incorrect!"
        
        # Render the login widget
        authentication_status = authenticator.login(
            location='main', 
            fields={'Form name': form_name}
        )
        
        if st.session_state.get('authentication_status'):
            st.session_state['authenticator'] = authenticator
            username = st.session_state['username']
            
            # Record first login activation
            if clear_first_login_flag(username):
                push_database(f"User {username} activated (first login)")
            
            # Handle plural roles list
            roles = st.session_state.get('roles', [])
            st.session_state['user_role'] = roles[0] if roles else 'EXPERT'
                
            return True

    except Exception as e:
        # Emergency Recovery: If the authenticator itself crashes (likely cookie conflict)
        st.error(f"🔑 Authentication Error: {e}")
        if st.button("✨ Clear Session & Reset"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()
            
    return False

def logout():
    """Unified Logout"""
    # 1. Clear authenticator internal state
    if 'authenticator' in st.session_state:
        try:
            st.session_state['authenticator'].logout(location='unrendered')
        except:
            pass
    
    # 2. Aggressively wipe the session state
    # We delete everything EXCEPT the bridge/sync keys so the next user doesn't have to re-pull
    keep_keys = ['db_synced', 'db_sha']
    for key in list(st.session_state.keys()):
        if key not in keep_keys:
            del st.session_state[key]
    
    # 3. Trigger a rerun
    st.rerun()
