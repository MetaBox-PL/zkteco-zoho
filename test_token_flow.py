# test_token_flow.py

from get_access_token import get_access_token

def test_get_token():
    print("🧪 Testing token flow...")
    token = get_access_token()
    if token:
        print("✅ Got valid access token!")
        print("🔑 Token:", token[:10] + "..." + token[-5:])
        return token
    else:
        print("❌ Failed to get access token")
        return None

if __name__ == "__main__":
    test_get_token()
