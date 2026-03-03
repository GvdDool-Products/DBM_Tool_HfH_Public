import sys
import os

# Add the 'src' directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

import streamlit as st
from db_core import init_db, seed_enums
from auth_manager import login_ui, logout
from st_admin_page import admin_page
from github_bridge import pull_database
from st_locking_page import locking_page
from st_inspection_page import inspection_page

# -----------------------
# Page Configuration
# -----------------------
st.set_page_config(page_title="IDP Housing Suitability Database", layout="wide")

# -----------------------
# GitHub Sync (Pull latest DB)
# -----------------------
pull_success = False
if 'db_synced' not in st.session_state:
    pull_success = pull_database()
    st.session_state['db_synced'] = pull_success
else:
    pull_success = st.session_state['db_synced']

# -----------------------
# Initialize Database
# -----------------------
# ONLY initialize if we pulled successfully OR we are running locally.
# This prevents creating a "blank" DB if the connection to GitHub fails.
if pull_success or os.environ.get("STREAMLIT_RUNTIME_CHECK") != "cloud":
    init_db()
    seed_enums()  # Populate TBL_ENUM / TBL_ENUM_I18N (safe to re-run)
else:
    st.error("🛑 Database Sync Failed. Initialization halted to prevent data loss.")
    st.stop()

# -----------------------
# Handle logout trigger via session state
# -----------------------
if st.session_state.get("logout_trigger"):
    st.session_state["authentication_status"] = None  # reset login
    st.session_state["logout_trigger"] = False
    st.rerun()  # force Streamlit to restart script from top

# -----------------------
# Login
# -----------------------
logged_in = login_ui()  # Always call login_ui at top

if logged_in:
    # -----------------------
    # Sidebar Navigation & Logout
    # -----------------------
    st.sidebar.title(f"Welcome, {st.session_state['username']}")

    # Logout button
    if st.sidebar.button("Log Out"):
        # Set session flag to trigger rerun
        st.session_state["logout_trigger"] = True
        logout()  # Clears session keys
        st.rerun()

    st.sidebar.divider()
    st.sidebar.title("Navigation")
    page = st.sidebar.radio(
        "Go to",
        ["Dashboard", "Property Inspection", "Fieldwork Scheduling", "Account & Admin"]
    )

    # -----------------------
    # Main Header
    # -----------------------
    st.title("IDP Housing Suitability Database")
    st.markdown("### Ukraine Residential Refitting Project")

    # -----------------------
    # Page Content
    # -----------------------
    if page == "Dashboard":
        st.header("Project Overview")
        st.info("Project status updates and high-level metrics.")

        col1, col2, col3 = st.columns(3)
        col1.metric("Properties Tracked", "0")
        col2.metric("Scheduled Visits", "0")
        col3.metric("Completed Inspections", "0")

    elif page == "Property Inspection":
        inspection_page()

    elif page == "Fieldwork Scheduling":
        st.header("Fieldwork Management")
        st.write("Assign properties to field teams.")

    elif page == "Account & Admin":
        admin_page()

else:
    # -----------------------
    # Not logged in -> show login UI
    # -----------------------
    st.warning("Please log in to continue.")
