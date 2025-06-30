import os
import requests
import mysql.connector
from zk import ZK
from datetime import datetime
from dotenv import load_dotenv
from pathlib import Path

# ─── Load environment from root .env ───
load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env")

# ─── Config ───
DOMAIN        = os.getenv("ZOHO_DOMAIN", "zoho.com")
CLIENT_ID     = os.getenv("ZOHO_CLIENT_ID")
CLIENT_SECRET = os.getenv("ZOHO_CLIENT_SECRET")
REFRESH_TOKEN = os.getenv("ZOHO_REFRESH_TOKEN")

DB_CONFIG = {
    "host":     os.getenv("DB_HOST", "127.0.0.1"),
    "port":     int(os.getenv("DB_PORT", 3306)),
    "user":     os.getenv("DB_USER"),
    "password": os.getenv("DB_PASS"),
    "database": os.getenv("DB_NAME"),
}

ZK_IP       = os.getenv("ZK_IP")
ZK_PORT     = int(os.getenv("ZK_PORT", 4370))
ZK_PASSWORD = os.getenv("ZK_PASSWORD", None)

# ─── Token Cache ───
_token_cache = {}
def get_access_token():
    import time
    now = time.time()
    info = _token_cache.get("info")
    if info and now < info["fetched"] + info["expires_in"] - 60:
        return info["access_token"]

    resp = requests.post(
        f"https://accounts.{DOMAIN}/oauth/v2/token",
        data={
            "refresh_token": REFRESH_TOKEN,
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "grant_type": "refresh_token"
        }
    )
    resp.raise_for_status()
    d = resp.json()
    _token_cache["info"] = {
        "access_token": d["access_token"],
        "expires_in":   int(d.get("expires_in", 3600)),
        "fetched":      now
    }
    return d["access_token"]

# ─── Fetch Zoho Employees ───
def fetch_zoho_employees():
    token   = get_access_token()
    url     = f"https://people.{DOMAIN}/people/api/forms/P_EmployeeView/records?per_page=200"
    headers = {"Authorization": f"Zoho-oauthtoken {token}"}

    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    data = resp.json()
    records = data.get("data") if isinstance(data, dict) else data

    employees = []
    for r in records:
        emp_id = r.get("Employee ID")
        name = r.get("ownerName") or f"{r.get('First Name', '').strip()} {r.get('Last Name', '').strip()}".strip()
        status = 1 if r.get("Employee Status", "").lower() == "active" else 0
        if emp_id and name:
            employees.append((emp_id, name, status))
    return employees

def sync_zoho(conn):
    emps = fetch_zoho_employees()
    cursor = conn.cursor()
    ins = upd = 0

    for emp_id, name, active in emps:
        cursor.execute("SELECT id FROM employees WHERE zoho_emp_id = %s", (emp_id,))
        if cursor.fetchone():
            cursor.execute(
                "UPDATE employees SET name=%s, active=%s WHERE zoho_emp_id=%s",
                (name, active, emp_id)
            )
            upd += 1
        else:
            cursor.execute(
                "INSERT INTO employees (zoho_emp_id,name,active,created_at) VALUES (%s,%s,%s,NOW())",
                (emp_id, name, active)
            )
            ins += 1

    conn.commit()
    cursor.close()
    print(f"✅ Zoho sync: fetched={len(emps)}, inserted={ins}, updated={upd}")

# ─── Sync Biometric IDs ───
def sync_biometric(conn):
    zk  = ZK(ZK_IP, port=ZK_PORT, password=ZK_PASSWORD, timeout=10, force_udp=True)
    dev = zk.connect()
    dev.disable_device()

    cursor = conn.cursor()
    updated = 0

    for user in dev.get_users():
        normalized_name = user.name.strip().replace(" ", "").replace("-", "").lower()
        bio_id = user.user_id

        cursor.execute(
            "SELECT id FROM employees WHERE REPLACE(REPLACE(LOWER(name),' ',''),'-','')=%s",
            (normalized_name,)
        )
        if cursor.fetchone():
            cursor.execute(
                "UPDATE employees SET biometric_id=%s WHERE REPLACE(REPLACE(LOWER(name),' ',''),'-','')=%s",
                (bio_id, normalized_name)
            )
            updated += 1
        else:
            print(f"⚠️  ZKTeco user '{user.name}' (UID:{bio_id}) not in employees")

    conn.commit()
    cursor.close()
    dev.enable_device()
    dev.disconnect()

    print(f"✅ Biometric sync: updated_biometric_ids={updated}")

# ─── Main ───
def main():
    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        sync_zoho(conn)
        sync_biometric(conn)
    finally:
        conn.close()
        print("🔒 Database connection closed.")

if __name__ == "__main__":
    main()
