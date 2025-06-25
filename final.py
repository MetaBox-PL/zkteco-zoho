import os, json, time, requests
from zk import ZK
from datetime import datetime, timedelta
from dotenv import load_dotenv

# ─── Load Env ───────────────────────────────────────────────
load_dotenv("e.env")

ZK_IP       = os.getenv("ZK_IP", "192.168.68.52")
ZK_PORT     = int(os.getenv("ZK_PORT", "4370"))
ZK_PASSWORD = os.getenv("ZK_PASSWORD", None)

DOMAIN         = os.getenv("ZOHO_DOMAIN", "zoho.com")
CLIENT_ID      = os.getenv("ZOHO_CLIENT_ID")
CLIENT_SECRET  = os.getenv("ZOHO_CLIENT_SECRET")
REFRESH_TOKEN  = os.getenv("ZOHO_REFRESH_TOKEN")

BIOMETRIC_TO_ZOHO = {10: "HRM1", 11: "HRM6", 12: "HRM3"}

STATE_FILE    = "next_action.json"
SENT_LOG_FILE = "sent_logs.json"

# ─── Persistence ────────────────────────────────────────────
def load_json_file(filename, default):
    if os.path.exists(filename):
        with open(filename) as f:
            return json.load(f)
    return default

def save_json_file(filename, data):
    with open(filename, "w") as f:
        json.dump(data, f, indent=2)

def load_state(): return load_json_file(STATE_FILE, {})
def save_state(state): save_json_file(STATE_FILE, state)

def load_sent_logs(): return set(tuple(x) for x in load_json_file(SENT_LOG_FILE, []))
def save_sent_logs(logs): save_json_file(SENT_LOG_FILE, list(logs))

# ─── Auth ───────────────────────────────────────────────────
_token_cache = {}
def get_access_token():
    now = time.time()
    info = _token_cache.get("info")
    if info and now < info["fetched"] + info["expires_in"] - 60:
        return info["access_token"]

    r = requests.post(f"https://accounts.{DOMAIN}/oauth/v2/token", data={
        "refresh_token": REFRESH_TOKEN,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "refresh_token"
    })
    r.raise_for_status()
    d = r.json()
    _token_cache["info"] = {
        "access_token": d["access_token"],
        "expires_in": int(d.get("expires_in", 3600)),
        "fetched": now
    }
    return d["access_token"]

# ─── Send to Zoho ───────────────────────────────────────────
def send_to_zoho(emp_id, ts, action):
    token = get_access_token()
    url = f"https://people.{DOMAIN}/people/api/attendance"
    headers = {"Authorization": f"Zoho-oauthtoken {token}"}
    payload = {
        "empId": emp_id,
        "dateFormat": "yyyy-MM-dd HH:mm:ss",
        "checkIn" if action == "checkin" else "checkOut": ts.strftime("%Y-%m-%d %H:%M:%S")
    }
    print(f"📤 [{action.title()}] {emp_id} at {payload.get('checkIn') or payload.get('checkOut')}")
    resp = requests.post(url, headers=headers, data=payload)
    try:
        print("✅", resp.json())
    except:
        print("❌", resp.status_code, resp.text)

# ─── Main ───────────────────────────────────────────────────
def main():
    print("🔄 Starting hybrid sync: real-time + every 1 hour...")
    state = load_state()
    sent_logs = load_sent_logs()

    zk = ZK(ZK_IP, port=ZK_PORT, password=ZK_PASSWORD, timeout=10, force_udp=True)
    conn = zk.connect()
    conn.disable_device()
    print("✅ Connected to ZKTeco device.")

    def is_recent(ts):
        return (datetime.now().date() - ts.date()).days < 3

    def handle_log(log):
        key = (str(log.user_id), log.timestamp.strftime("%Y-%m-%d %H:%M:%S"))
        if not is_recent(log.timestamp) or key in sent_logs:
            return
        try:
            uid = int(log.user_id)
            emp = BIOMETRIC_TO_ZOHO[uid]
        except KeyError:
            print(f"❌ Unmapped UID: {log.user_id}")
            return

        action = state.get(emp, "checkin")
        send_to_zoho(emp, log.timestamp, action)
        state[emp] = "checkout" if action == "checkin" else "checkin"
        sent_logs.add(key)

    try:
        last_seen = set()
        last_batch_time = time.time()

        while True:
            # Real-time new log detection
            for log in conn.get_attendance():
                key = (str(log.user_id), log.timestamp.strftime("%Y-%m-%d %H:%M:%S"))
                if key not in last_seen:
                    last_seen.add(key)
                    handle_log(log)

            # Every 1 hour - recheck recent logs
            if time.time() - last_batch_time > 3600:
                print("⏳ Rechecking last 3 days of logs...")
                for log in conn.get_attendance():
                    handle_log(log)
                last_batch_time = time.time()

            save_state(state)
            save_sent_logs(sent_logs)

    finally:
        conn.enable_device()
        conn.disconnect()

if __name__ == "__main__":
    main()
