import streamlit as st
import pandas as pd
from lock_manager import get_all_properties_with_lock_status, toggle_lock

def locking_page():
    st.header("Fieldwork Scheduling (Lock Manager)")
    st.write("Manage property access for field teams. **Lock a property** to check it out for editing.")
    
    # 1. Get Data
    df = get_all_properties_with_lock_status()
    
    if df.empty:
        st.info("No properties found in the database.")
        return

    # 2. Prepare Display Data
    # We want a checkbox column. 
    # Streamlit data_editor is perfect for this.
    
    current_user = st.session_state.get('username', 'Unknown')
    
    # Add a computed column for "Can I Edit?" to control disabled state is harder in data_editor
    # So we used a grid approach or st.data_editor with careful config.
    # User asked for: "tick box... greyed (disabled) for anyone else"
    
    # We will iterate row by row for maximum control over the UI state
    # A dataframe display is cleaner, but standard st.dataframe doesn't support action buttons well.
    # st.data_editor supports checkboxes but "disabling specific cells" is complex.
    
    # Better UX: A structured table with a custom "Lock Action" column.
    
    # Headers
    col1, col2, col3, col4 = st.columns([1, 4, 2, 2])
    col1.markdown("**Lock**")
    col2.markdown("**Address**")
    col3.markdown("**Status**")
    col4.markdown("**Locked By**")
    st.divider()

    for index, row in df.iterrows():
        prop_id = row['ID_PROPERTY']
        address = row['Full_Address']
        is_locked = bool(row['IS_LOCKED'])
        locked_by = row['LOCKED_BY']
        locked_at = row['LOCKED_AT']
        
        c1, c2, c3, c4 = st.columns([1, 4, 2, 2])
        
        # LOGIC:
        # If Locked by ME: Checkbox is CHECKED. User can Click to UNCHECK (Unlock).
        # If Locked by OTHERS: Checkbox is CHECKED. User CANNOT Click (Disabled).
        # If Unlocked: Checkbox is UNCHECKED. User can Click to CHECK (Lock).
        
        is_my_lock = (locked_by == current_user)
        
        disabled = False
        if is_locked and not is_my_lock:
            disabled = True
            
        # Draw the checkbox
        # key must be unique per row
        new_state = c1.checkbox(
            "Lock", 
            value=is_locked, 
            key=f"lock_{prop_id}", 
            disabled=disabled,
            label_visibility="collapsed"
        )
        
        # Detect Change
        if new_state != is_locked:
            # User clicked the box
            if toggle_lock(prop_id, current_user, is_locked):
                # Trigger Sync immediately
                from github_bridge import push_database
                action = "Locked" if new_state else "Unlocked"
                push_database(f"Property {action} by {current_user}")
                st.rerun()
            else:
                st.error("Failed to update lock.")
        
        # Address
        c2.write(address)
        
        # Status Text
        if is_locked:
            if is_my_lock:
                c3.markdown("🟢 **Checked Out (You)**")
            else:
                c3.markdown("🔴 **Locked**")
        else:
            c3.markdown("⚪ Available")
            
        # Locked By Info
        if is_locked:
            c4.caption(f"{locked_by} @ {locked_at}")
            
        st.divider()
