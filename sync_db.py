import os
import json
import requests
import mysql.connector
from dotenv import load_dotenv
from zk import ZK

load_dotenv("e.env")

# ZKTeco config
ZK_IP = os.getenv("ZK_IP")
ZK_PORT = int(os.getenv("ZK_PORT", "4370"))
ZK_PASSWORD = int(os.getenv("ZK_PASSWORD", "0"))

# Zoho config
DOMAIN = os.getenv("ZOHO_DOMAIN", "zoho.com")
CLIENT_ID = os.getenv("ZOHO_CLIENT_ID")
CLIENT_SECRET = os.getenv("ZOHO_CLIENT_SECRET")
REFRESH_TOKEN = os.getenv("ZOHO_REFRESH_TOKEN")

# DB config
DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASS"),
    "database": os.getenv("DB_NAME")
}

def normalize(name):
    return name.replace(" ", "").lower()

def get_access_token():
    resp = requests.post(f"https://accounts.{DOMAIN}/oauth/v2/token", data={
        "refresh_token": REFRESH_TOKEN,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "refresh_token"
    })
    resp.raise_for_status()
    return resp.json()["access_token"]

def fetch_zoho_employees():
    print("🔄 Syncing Zoho People employees...")
    token = get_access_token()
    url = f"https://people.{DOMAIN}/people/api/forms/P_EmployeeView/records"
    headers = {"Authorization": f"Zoho-oauthtoken {token}"}
    resp = requests.get(url, headers=headers)

    try:
        data = resp.json()
    except Exception:
        print("❌ Zoho: Failed to parse employee data.")
        return []

    if isinstance(data, list):
        employees = []
        for record in data:
            emp_id = record.get("Employee ID")
            full_name = record.get("ownerName") or (
                f"{record.get('First Name', '').strip()} {record.get('Last Name', '').strip()}"
            ).strip()
            if emp_id and full_name:
                employees.append({"zoho_emp_id": emp_id, "name": full_name})
        print(f"✅ Zoho: {len(employees)} employee(s) fetched.")
        return employees
    else:
        print("⚠️ Zoho: Unexpected data format.")
        return []

def sync_employees_to_db(employees):
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
    print(f"✅ DB: Synced {len(employees)} Zoho employee(s).")

def fetch_employees_from_db():
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, name FROM employees")
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return {normalize(row["name"]): row["id"] for row in rows}

def update_biometric_id_in_db(employee_id, biometric_id):
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE employees SET biometric_id = %s WHERE id = %s
    """, (biometric_id, employee_id))
    conn.commit()
    cursor.close()
    conn.close()

def sync_zkteco_users_to_db():
    print("🔄 Syncing biometric IDs from ZKTeco...")
    zk = ZK(ZK_IP, port=ZK_PORT, timeout=5, password=ZK_PASSWORD)
    try:
        conn = zk.connect()
        conn.disable_device()
        device_users = conn.get_users()
        known_employees = fetch_employees_from_db()
        matched = 0

        for user in device_users:
            name = normalize(user.name.strip())
            biometric_id = user.user_id
            if name in known_employees:
                employee_id = known_employees[name]
                update_biometric_id_in_db(employee_id, biometric_id)
                matched += 1

        conn.enable_device()
        conn.disconnect()
        print(f"✅ ZKTeco: {matched} biometric ID(s) updated.")

    except Exception as e:
        print(f"❌ ZKTeco: Connection failed → {e}")

def main():
    employees = fetch_zoho_employees()
    if employees:
        sync_employees_to_db(employees)
    sync_zkteco_users_to_db()

if __name__ == "__main__":
    main()
