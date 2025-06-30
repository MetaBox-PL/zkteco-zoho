import os
import json
import mysql.connector
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv("e.env")

# Database configuration
DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASS"),
    "database": os.getenv("DB_NAME")
}

# Zoho API configuration
DOMAIN = os.getenv("ZOHO_DOMAIN", "zoho.com")
CLIENT_ID = os.getenv("ZOHO_CLIENT_ID")
CLIENT_SECRET = os.getenv("ZOHO_CLIENT_SECRET")
REFRESH_TOKEN = os.getenv("ZOHO_REFRESH_TOKEN")


def get_access_token():
    """Retrieve a new Zoho People access token using the refresh token."""
    response = requests.post(f"https://accounts.{DOMAIN}/oauth/v2/token", data={
        "refresh_token": REFRESH_TOKEN,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "refresh_token"
    })
    response.raise_for_status()
    return response.json()["access_token"]


def fetch_zoho_employees():
    """Fetch employee records from Zoho People."""
    print("🔄 Fetching employee records from Zoho People...")
    token = get_access_token()
    url = f"https://people.{DOMAIN}/people/api/forms/P_EmployeeView/records"
    headers = {"Authorization": f"Zoho-oauthtoken {token}"}

    try:
        response = requests.get(url, headers=headers)
        data = response.json()
    except Exception as e:
        print(f"❌ Failed to parse Zoho response: {e}")
        return []

    if isinstance(data, list):
        employees = []
        for record in data:
            emp_id = record.get("Employee ID")
            full_name = record.get("ownerName")
            if not full_name:
                first = record.get("First Name", "").strip()
                last = record.get("Last Name", "").strip()
                full_name = f"{first} {last}".strip()
            if emp_id and full_name:
                employees.append({
                    "zoho_emp_id": emp_id,
                    "name": full_name
                })
        print(f"✅ Fetched {len(employees)} employee(s).")
        return employees
    else:
        print("⚠️ Unexpected Zoho API response format.")
        return []


def sync_employees_to_db(employees):
    """Insert or update employee data in the local database."""
    if not employees:
        print("⚠️ No employee data to sync.")
        return

    print("💾 Syncing data to local database...")
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor()

    insert_query = """
        INSERT INTO employees (zoho_emp_id, name)
        VALUES (%s, %s)
        ON DUPLICATE KEY UPDATE name = VALUES(name)
    """

    for emp in employees:
        cursor.execute(insert_query, (emp["zoho_emp_id"], emp["name"]))

    conn.commit()
    cursor.close()
    conn.close()
    print(f"✅ Synced {len(employees)} employee(s) to the database.")


def main():
    employees = fetch_zoho_employees()
    sync_employees_to_db(employees)


if __name__ == "__main__":
    main()
