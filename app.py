import streamlit as st
import pandas as pd
import os
import hashlib

from simulation.auto_mode import auto_mode_ui
from simulation.manual_mode import manual_mode_ui
from deinterleaving.dbscan_ui import dbscan_ui


st.set_page_config(page_title="Radar PDW De-Interleaving System", layout="centered")

st.title("Radar PDW De-Interleaving System")
st.subheader("Secure Offline Application")

USER_DB = "users.csv"

# -------------------------------------------------
# CREATE USER DATABASE IF NOT EXISTS
# -------------------------------------------------
if not os.path.exists(USER_DB):
    df = pd.DataFrame(columns=["username", "password"])
    df.to_csv(USER_DB, index=False)

# -------------------------------------------------
# SESSION STATE INITIALIZATION
# -------------------------------------------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if "user" not in st.session_state:
    st.session_state.user = ""

if "confirm_logout" not in st.session_state:
    st.session_state.confirm_logout = False

# -------------------------------------------------
# PASSWORD HASH
# -------------------------------------------------
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# -------------------------------------------------
# SIGNUP
# -------------------------------------------------
def signup(username, password):
    df = pd.read_csv(USER_DB)

    if username in df["username"].values:
        return False, "Username already exists"

    new_user = pd.DataFrame(
        [[username, hash_password(password)]],
        columns=["username", "password"]
    )
    df = pd.concat([df, new_user], ignore_index=True)
    df.to_csv(USER_DB, index=False)

    return True, "Signup successful"

# -------------------------------------------------
# LOGIN
# -------------------------------------------------
def login(username, password):
    df = pd.read_csv(USER_DB)
    hashed = hash_password(password)

    user = df[
        (df["username"] == username) &
        (df["password"] == hashed)
    ]

    return not user.empty

# -------------------------------------------------
# LOGIN / SIGNUP UI
# -------------------------------------------------
if not st.session_state.logged_in:

    tab1, tab2 = st.tabs(["Login", "Signup"])

    with tab1:
        st.subheader("Login")
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")

        if st.button("Login"):
            if login(u, p):
                st.session_state.logged_in = True
                st.session_state.user = u
                st.success("Login successful")
                st.rerun()
            else:
                st.error("Invalid credentials")

    with tab2:
        st.subheader("Signup")
        u = st.text_input("New Username")
        p = st.text_input("New Password", type="password")

        if st.button("Signup"):
            ok, msg = signup(u, p)
            if ok:
                st.success(msg)
            else:
                st.error(msg)

# -------------------------------------------------
# MAIN APPLICATION (AFTER LOGIN)
# -------------------------------------------------
else:
    st.success(f"Welcome, {st.session_state.user}")

    st.sidebar.title("Navigation")

    page = st.sidebar.radio(
        "Select Module",
        ["Auto Mode", "Manual Mode", "De-Interleaving", "Logout"]
    )

    # -----------------------------
    # AUTO MODE
    # -----------------------------
    if page == "Auto Mode":
        auto_mode_ui()

    # -----------------------------
    # MANUAL MODE
    # -----------------------------
    elif page == "Manual Mode":
        manual_mode_ui()

    # -----------------------------
    # DE-INTERLEAVING MODE
    # -----------------------------
    elif page == "De-Interleaving":
        dbscan_ui()

    # -----------------------------
    # LOGOUT (WITH CONFIRMATION)
    # -----------------------------
    elif page == "Logout":

        if not st.session_state.confirm_logout:
            st.warning("Are you sure you want to logout?")

            col1, col2 = st.columns(2)

            with col1:
                if st.button("Yes, Logout"):
                    st.session_state.confirm_logout = True
                    st.rerun()

            with col2:
                if st.button("Cancel"):
                    st.session_state.confirm_logout = False
                    st.rerun()

        else:
            # Perform logout
            st.session_state.logged_in = False
            st.session_state.user = ""
            st.session_state.confirm_logout = False
            st.success("Logged out successfully")
            st.rerun()
