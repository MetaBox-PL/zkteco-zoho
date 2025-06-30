import os
from urllib.parse import urlencode
from dotenv import load_dotenv

load_dotenv("e.env")

client_id = os.getenv("ZOHO_CLIENT_ID")
redirect_uri = os.getenv("ZOHO_REDIRECT_URI")
scopes = [
    "ZohoPeople.attendance.ALL",
    "ZohoPeople.employee.ALL",
]

params = {
    "client_id": client_id,
    "response_type": "code",
    "redirect_uri": redirect_uri,
    "scope": " ".join(scopes),
    "access_type": "offline",
    "prompt": "consent"
}

url = "https://accounts.zoho.com/oauth/v2/auth?" + urlencode(params)
print("🌐 Open the following URL in your browser to authorize:")
print(url)
