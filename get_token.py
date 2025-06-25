# zoho_auth_tool.py

import requests
import json
import os
import webbrowser
from datetime import datetime
from dotenv import load_dotenv

# Load env file
load_dotenv("e.env")

ENV_FILE = "e.env"
TOKEN_FILE = "zoho_tokens.json"

# Load from .env
CLIENT_ID = os.getenv("ZOHO_CLIENT_ID")
CLIENT_SECRET = os.getenv("ZOHO_CLIENT_SECRET")
REDIRECT_URI = os.getenv("ZOHO_REDIRECT_URI", "http://localhost:8080")
REFRESH_TOKEN = os.getenv("ZOHO_REFRESH_TOKEN")
DOMAIN = "accounts.zoho.com"  # Use accounts.zoho.in if your region is India

SCOPES = {
    1: "ZohoPeople.attendance.ALL",
    2: "ZohoPeople.employee.READ",
    3: "ZohoPeople.employee.ALL",
    4: "ZohoPeople.timetracker.ALL",
    5: "ZohoPeople.forms.ALL"
}

# ----------------------------------------
# 📦 Token File Helpers
# ----------------------------------------

def save_tokens(tokens):
    with open(TOKEN_FILE, 'w') as f:
        json.dump(tokens, f, indent=2)
    print(f"🔑 Access token saved to {TOKEN_FILE}")

    # Update .env if refresh token changed
    if "refresh_token" in tokens:
        update_env_variable("ZOHO_REFRESH_TOKEN", tokens["refresh_token"])


def load_tokens():
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, 'r') as f:
            return json.load(f)
    return {}

def update_env_variable(key, value):
    """Update a variable in .env file"""
    lines = []
    found = False
    with open(ENV_FILE, 'r') as f:
        for line in f:
            if line.startswith(f"{key}="):
                lines.append(f"{key}={value}\n")
                found = True
            else:
                lines.append(line)
    if not found:
        lines.append(f"{key}={value}\n")

    with open(ENV_FILE, 'w') as f:
        f.writelines(lines)
    print(f"✅ Updated {key} in {ENV_FILE}")


# ----------------------------------------
# 🔁 OAuth Logic
# ----------------------------------------

def get_authorization_url(scope_list=None):
    if not scope_list:
        scope_list = ["ZohoPeople.attendance.ALL"]

    scope_str = ",".join(scope_list)
    url = (
        f"https://{DOMAIN}/oauth/v2/auth?"
        f"scope={scope_str}&"
        f"client_id={CLIENT_ID}&"
        "response_type=code&"
        "access_type=offline&"
        f"redirect_uri={REDIRECT_URI}&"
        "prompt=consent"
    )
    print("\n🔗 Authorization URL:")
    print(url)
    if input("Open in browser? (y/n): ").strip().lower() == "y":
        webbrowser.open(url)


def exchange_code_for_tokens(auth_code):
    url = f"https://{DOMAIN}/oauth/v2/token"
    data = {
        "code": auth_code,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code"
    }

    print("🔄 Exchanging auth code for access/refresh token...")
    response = requests.post(url, data=data)

    try:
        response.raise_for_status()
        tokens = response.json()
        save_tokens(tokens)
        print("✅ Tokens received and saved.")
        return tokens
    except Exception as e:
        print("❌ Error exchanging code:", e)
        print("📦 Response:", response.text)


def refresh_access_token():
    refresh_token = os.getenv("ZOHO_REFRESH_TOKEN")

    if not refresh_token:
        print("❌ No refresh token available.")
        return None

    url = f"https://{DOMAIN}/oauth/v2/token"
    data = {
        "refresh_token": refresh_token,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "refresh_token"
    }

    print("🔄 Requesting new access token using refresh token...")
    response = requests.post(url, data=data)

    try:
        response.raise_for_status()
        tokens = response.json()
        if "access_token" not in tokens:
            print("❌ No access_token in response:", tokens)
            return None
        save_tokens(tokens)
        return tokens["access_token"]
    except Exception as e:
        print("❌ Failed to refresh access token:", e)
        print("📦 Response:", response.text)
        return None


# ----------------------------------------
# 🔧 Menu Interface
# ----------------------------------------

def main_menu():
    print("🔐 Zoho OAuth Tool\n")

    while True:
        print("\nOptions:")
        print("1. Generate Authorization URL")
        print("2. Exchange Auth Code for Tokens")
        print("3. Refresh Access Token")
        print("4. View Saved Tokens")
        print("5. Exit")

        choice = input("Select an option (1–5): ").strip()

        if choice == "1":
            print("🔍 Select Scopes (comma-separated, default = 1):")
            for k, v in SCOPES.items():
                print(f"{k}. {v}")
            selected = input("Scopes: ").strip() or "1"
            scope_keys = [int(x.strip()) for x in selected.split(",") if x.strip().isdigit()]
            scope_list = [SCOPES.get(k) for k in scope_keys if k in SCOPES]
            get_authorization_url(scope_list)

        elif choice == "2":
            auth_code = input("Paste the authorization code: ").strip()
            exchange_code_for_tokens(auth_code)

        elif choice == "3":
            access_token = refresh_access_token()
            if access_token:
                print("✅ New Access Token:", access_token)

        elif choice == "4":
            tokens = load_tokens()
            if tokens:
                print("\n🔎 Current Tokens:")
                print(json.dumps(tokens, indent=2))
            else:
                print("⚠️ No saved token data found.")

        elif choice == "5":
            print("👋 Exiting.")
            break
        else:
            print("❌ Invalid option.")


if __name__ == "__main__":
    main_menu()
