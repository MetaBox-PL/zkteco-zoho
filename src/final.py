import os
import time
import mysql.connector
import requests
from zk import ZK
from dotenv import load_dotenv
from pathlib import Path
from datetime import datetime

# Load environment variables
load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env")

DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASS"),
    "database": os.getenv("DB_NAME"),
}

DOMAIN = os.getenv("ZOHO_DOMAIN", "zoho.com")
CLIENT_ID = os.getenv("ZOHO_CLIENT_ID")
CLIENT_SECRET = os.getenv("ZOHO_CLIENT_SECRET")
REFRESH_TOKEN = os.getenv("ZOHO_REFRESH_TOKEN")

ZK_IP = os.getenv("ZK_IP", "192.168.68.52")
ZK_PORT = int(os.getenv("ZK_PORT", "4370"))
ZK_PASSWORD = os.getenv("ZK_PASSWORD", None)

def get_access_token():
    r = requests.post(f"https://accounts.{DOMAIN}/oauth/v2/token", data={
        "refresh_token": REFRESH_TOKEN,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "refresh_token"
    })
    r.raise_for_status()
    return r.json()["access_token"]

def send_attendance_to_zoho(emp_id, timestamp, atype):
    token = get_access_token()
    url = f"https://people.{DOMAIN}/people/api/attendance"
    headers = {"Authorization": f"Zoho-oauthtoken {token}"}
    data = {
        "employeeId": emp_id,
        "checkIn": timestamp if atype == "Check-in" else "",
        "checkOut": timestamp if atype == "Check-out" else ""
    }
    r = requests.post(url, headers=headers, data=data)
    if r.status_code == 200:
        print(f"✅ Sent {atype} for {emp_id} at {timestamp}")
        return True
    else:
        print(f"❌ Failed to send {atype} for {emp_id}: {r.text}")
        return False

def fetch_employee_mappings(conn):
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT zoho_emp_id, biometric_id FROM employees WHERE biometric_id IS NOT NULL")
    rows = cursor.fetchall()
    cursor.close()
    return {str(row["biometric_id"]): row["zoho_emp_id"] for row in rows}

def log_exists(conn, bio_id, ts):
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM attendance_logs WHERE biometric_id=%s AND timestamp=%s", (bio_id, ts))
    exists = cursor.fetchone() is not None
    cursor.close()
    return exists

def save_log(conn, bio_id, ts, emp_id, atype):
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO attendance_logs (biometric_id, timestamp, zoho_emp_id, type, created_at) VALUES (%s, %s, %s, %s, NOW())",
        (bio_id, ts, emp_id, atype)
    )
    conn.commit()
    cursor.close()

def main():
    print("🔥 Starting final.py...")

    conn = mysql.connector.connect(**DB_CONFIG)
    mapping = fetch_employee_mappings(conn)
    unknown_ids = set()

    zk = ZK(ZK_IP, port=ZK_PORT, password=ZK_PASSWORD, timeout=10, force_udp=True)
    try:
        dev = zk.connect()
        dev.disable_device()
        print("✅ Connected to ZKTeco. Listening for new logs...")

        while True:
            logs = dev.get_attendance()
            if not logs:
                time.sleep(5)
                continue

            for log in logs:
                bio_id = str(log.user_id)
                ts = log.timestamp.strftime("%Y-%m-%d %H:%M:%S")
                status = log.status

                emp_id = mapping.get(bio_id)
                if not emp_id:
                    if bio_id not in unknown_ids:
                        print(f"⚠️ Unknown biometric ID {bio_id}. Skipping future warnings for this ID.")
                        unknown_ids.add(bio_id)
                    continue

                atype = "Check-in" if status == 0 else "Check-out"

                if log_exists(conn, bio_id, ts):
                    continue  # Already recorded

                success = send_attendance_to_zoho(emp_id, ts, atype)
                if success:
                    save_log(conn, bio_id, ts, emp_id, atype)

            time.sleep(5)

    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        dev.enable_device()
        dev.disconnect()
        conn.close()
        print("🔒 DB connection closed. Device disconnected.")

if __name__ == "__main__":
    main()
