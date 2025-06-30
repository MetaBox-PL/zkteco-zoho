from zk import ZK, const
import os
import mysql.connector
from dotenv import load_dotenv

# Load environment variables
load_dotenv("e.env")

# ZKTeco config
ZK_IP = os.getenv("ZK_IP")
ZK_PORT = int(os.getenv("ZK_PORT", "4370"))
ZK_PASSWORD = int(os.getenv("ZK_PASSWORD", "0"))

print(f"DEBUG: ZK_IP: {ZK_IP}")
print(f"DEBUG: ZK_PORT: {ZK_PORT}")
print(f"DEBUG: ZK_PASSWORD: {ZK_PASSWORD} (Type: {type(ZK_PASSWORD)})")

# DB config
DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASS"),
    "database": os.getenv("DB_NAME")
}

def normalize(name):
    """Lowercase and remove all spaces."""
    return name.replace(" ", "").lower()

def fetch_employees_from_db():
    """Fetch all employee names and IDs from the database."""
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT id, name FROM employees")
    rows = cursor.fetchall()

    cursor.close()
    conn.close()

    # Return dictionary: {normalized_name: id}
    return {normalize(row["name"]): row["id"] for row in rows}

def update_biometric_id_in_db(employee_id, biometric_id):
    """Update biometric_id for a given employee."""
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE employees SET biometric_id = %s WHERE id = %s
    """, (biometric_id, employee_id))

    conn.commit()
    cursor.close()
    conn.close()

def match_and_update_users():
    print("🔌 Connecting to ZKTeco device...")
    zk = ZK(ZK_IP, port=ZK_PORT, timeout=5, password=ZK_PASSWORD)

    try:
        conn = zk.connect()
        conn.disable_device()

        device_users = conn.get_users()
        known_employees = fetch_employees_from_db()

        matched = 0
        for user in device_users:
            device_name = normalize(user.name.strip())
            biometric_id = user.user_id

            if device_name in known_employees:
                employee_id = known_employees[device_name]
                update_biometric_id_in_db(employee_id, biometric_id)
                print(f"✅ Matched & updated: {user.name} → biometric_id={biometric_id}")
                matched += 1
            else:
                print(f"❌ Not in DB: {user.name} (ID: {biometric_id})")

        conn.enable_device()
        conn.disconnect()

        print(f"\n🔁 Done. {matched} user(s) matched and updated.")

    except Exception as e:
        print(f"❌ Connection failed: {e}")

if __name__ == "__main__":
    match_and_update_users()
