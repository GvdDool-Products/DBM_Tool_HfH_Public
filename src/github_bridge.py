import os
import streamlit as st
from github import Github
import base64

# Configuration from Streamlit Secrets
def get_config():
    try:
        config = {
            "token": st.secrets["GITHUB_TOKEN"],
            "repo_name": st.secrets["REPO_NAME"],
            "db_path": st.secrets.get("DB_FILE_PATH", "data/database.sqlite"),
            "branch": st.secrets.get("REPO_BRANCH", "main")
        }
        # Check for placeholders
        if "your_personal_access_token" in config["token"] or "your_username" in config["repo_name"]:
            return None
            
        return config
    except Exception:
        return None

def pull_database():
    """
    Downloads database.sqlite and stores the commit SHA to prevent overwrite conflicts.
    """
    config = get_config()
    if not config:
        st.warning("GitHub Secrets not configured. Persistence disabled.")
        return False

    try:
        g = Github(config["token"])
        repo = g.get_repo(config["repo_name"])
                
        # Check if the database file exists in the repo
        contents = repo.get_contents(config["db_path"], ref=config["branch"])
        if contents:
            st.write("✅ DATABASE FOUND in GitHub repo")
        else:
            st.write("❌ DATABASE NOT FOUND in GitHub repo")
            return False

        # Ensure local folder exists
        local_folder = os.path.dirname(config["db_path"])
        os.makedirs(local_folder, exist_ok=True)

        # Write file locally
        with open(config["db_path"], "wb") as f:
            f.write(contents.decoded_content)
        st.write(f"✅ DATABASE COPIED LOCALLY to {config['db_path']}")

        # Store SHA to prevent overwrite conflicts
        # KEY: Store the SHA of the file we just pulled
        st.session_state['db_sha'] = contents.sha
        
        st.sidebar.success(f"✅ DB Synced (v.{contents.sha[:7]})")
        return True
    except Exception as e:
        st.sidebar.error(f"❌ Pull failed: {e}")
        return False

def push_database(commit_message="Update database from Streamlit App"):
    """
    Commits local DB using Optimistic Locking (SHA Check).
    """
    config = get_config()
    if not config:
        return False

    try:
        g = Github(config["token"])
        repo = g.get_repo(config["repo_name"])
        
        # 1. Get current remote SHA
        remote_contents = repo.get_contents(config["db_path"], ref=config["branch"])
        remote_sha = remote_contents.sha
        
        # 2. Get the SHA we started with
        local_base_sha = st.session_state.get('db_sha')
        
        # 3. SAFETY CHECK: Has the remote file changed since we pulled?
        if local_base_sha and remote_sha != local_base_sha:
            st.sidebar.error("⚠️ CONFLICT: Database changed on server! Pulling latest version...")
            # LOGIC for handling conflict (Pull -> Re-apply?)
            # For now, we abort to prevent overwrite
            return False
            
        # 4. Read local file
        with open(config["db_path"], "rb") as f:
            content = f.read()
            
        # 5. Push
        commit = repo.update_file(
            config["db_path"],
            commit_message,
            content,
            remote_sha, # Use the fresh remote SHA to ensure the chain is valid
            branch=config["branch"]
        )
        
        # 6. Update local SHA to the new commit's file SHA
        st.session_state['db_sha'] = commit['content'].sha
        st.sidebar.success(f"🚀 Saved (v.{commit['content'].sha[:7]})")
        return True
        
    except Exception as e:
        st.sidebar.error(f"❌ Push failed: {e}")
        return False
