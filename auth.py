import streamlit as st
import pandas as pd
import hashlib
import os
import uuid

USER_DB = "users.csv"

# -------------------------------------------------
# INITIALIZE DB
# -------------------------------------------------
def init_db():
    if not os.path.exists(USER_DB):
        df = pd.DataFrame(columns=["username", "password", "salt", "full_name", "email", "role"])
        # Create Specific Admin
        salt = uuid.uuid4().hex
        # CREDENTIALS: Dharashakti@123 / 123456789
        hashed_pw = hashlib.sha256((salt + "123456789").encode()).hexdigest()
        
        new_admin = pd.DataFrame([{
            "username": "Dharashakti@123",
            "password": hashed_pw,
            "salt": salt,
            "full_name": "System Administrator",
            "email": "admin@dharashakti.com",
            "role": "admin"
        }])
        df = pd.concat([df, new_admin], ignore_index=True)
        df.to_csv(USER_DB, index=False)
    else:
        # Quick check to ensure our specific admin exists in existing DB
        df = pd.read_csv(USER_DB)
        if "Dharashakti@123" not in df["username"].values:
            salt = uuid.uuid4().hex
            hashed_pw = hashlib.sha256((salt + "123456789").encode()).hexdigest()
            new_admin = pd.DataFrame([{
                "username": "Dharashakti@123",
                "password": hashed_pw,
                "salt": salt,
                "full_name": "System Administrator",
                "email": "admin@dharashakti.com",
                "role": "admin"
            }])
            df = pd.concat([df, new_admin], ignore_index=True)
            df.to_csv(USER_DB, index=False)

# -------------------------------------------------
# AUTH FUNCTIONS
# -------------------------------------------------
def verify_user(identifier, password):
    """
    Verify user by Username OR Email.
    identifier: can be username or email
    """
    init_db()
    df = pd.read_csv(USER_DB)
    
    # Check if identifier matches username OR email
    user_row = df[ (df["username"] == identifier) | (df["email"] == identifier) ]
    
    if user_row.empty:
        return False, None
    
    row = user_row.iloc[0]
    salt = row["salt"]
    stored_hash = row["password"]
    
    # Hash input with salt
    input_hash = hashlib.sha256((str(salt) + password).encode()).hexdigest()
    
    if input_hash == stored_hash:
        return True, row
    return False, None

def register_user(full_name, email, password, role="user"):
    """
    Register new user. Username will be auto-set to Email for simplicity, 
    or we can generate one. Let's make Username = Email.
    """
    init_db()
    df = pd.read_csv(USER_DB)
    
    # Check if email exists
    if email in df["email"].values:
        return False, "Email already registered."
    
    salt = uuid.uuid4().hex
    hashed_pw = hashlib.sha256((salt + password).encode()).hexdigest()
    
    new_user = pd.DataFrame([{
        "username": email, # Use Email as Username
        "password": hashed_pw,
        "salt": salt,
        "full_name": full_name,
        "email": email,
        "role": role
    }])
    
    df = pd.concat([df, new_user], ignore_index=True)
    df.to_csv(USER_DB, index=False)
    
    # Create user workspace
    user_dir = f"outputs/{email}" # Workspace based on email
    os.makedirs(user_dir, exist_ok=True)
    
    return True, "Registration successful."

def get_all_users():
    init_db()
    return pd.read_csv(USER_DB)
