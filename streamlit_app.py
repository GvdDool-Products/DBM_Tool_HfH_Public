import sys
import os

# Add the 'src' directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

import streamlit as st
import pandas as pd
from db_core import init_db
from auth_manager import login_ui, logout
from admin_page import admin_page
from github_bridge import pull_database
from locking_page import locking_page

# Page Configuration
st.set_page_config(page_title="IDP Housing Suitability Database", layout="wide")

# Handle GitHub Synchronization (Pull latest on start)
if 'db_synced' not in st.session_state:
    if pull_database():
        st.session_state['db_synced'] = True

# Initialize Database
init_db()

# Requirement: Multi-user Login
if login_ui():
    # Sidebar Navigation & Logout
    st.sidebar.title(f"Welcome, {st.session_state['username']}")
    st.sidebar.markdown(f"**Role:** {st.session_state.get('user_role', 'expert')}")
    
    # Unified Logout Button
    if st.sidebar.button("Log Out"):
        logout()
        
    st.sidebar.divider()
    
    st.sidebar.title("Navigation")
    page = st.sidebar.radio("Go to", ["Dashboard", "Property Entry", "Fieldwork Scheduling", "Account & Admin"])

    # Main Header
    st.title("IDP Housing Suitability Database")
    st.markdown("### Ukraine Residential Refitting Project")

    if page == "Dashboard":
        st.header("Project Overview")
        st.info("Project status updates and high-level metrics.")
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Properties Tracked", "0")
        col2.metric("Scheduled Visits", "0")
        col3.metric("Completed Inspections", "0")

    elif page == "Property Entry":
        st.header("Property Registration")
        st.write("Expert data entry for real estate suitability.")

    elif page == "Fieldwork Scheduling":
        st.header("Fieldwork Management")
        st.write("Assign properties to field teams.")

    elif page == "Account & Admin":
        admin_page()
else:
    st.stop()
