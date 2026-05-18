import asyncio
import sys
import os
import urllib.request
import requests
import websockets

async def run_diagnostics():
    print("=" * 60)
    print("AUDACI CONNECTION DIAGNOSTICS")
    print("=" * 60)
    
    # 1. Print Env Proxies
    print("\n[1] Checking System and Env Proxies:")
    print(f"  urllib.request proxies: {urllib.request.getproxies()}")
    for env in ["HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy", "NO_PROXY", "no_proxy"]:
        print(f"  Env variable {env}: {os.environ.get(env)}")

    # Test targets
    targets = [
        ("127.0.0.1:8080", "127.0.0.1"),
        ("localhost:8080", "localhost"),
    ]

    for label, host in targets:
        print(f"\n" + "-" * 50)
        print(f"TESTING TARGET: {label}")
        print("-" * 50)

        # 2. HTTP GET test with requests (default)
        print(f"\n[*] testing HTTP GET http://{host}:8080/api/bot/info (requests)...")
        try:
            r = requests.get(f"http://{host}:8080/api/bot/info", timeout=3)
            print(f"  SUCCESS! Status: {r.status_code}")
            print(f"  Response: {r.json()}")
        except Exception as e:
            print(f"  FAILED: {e}")

        # 3. HTTP GET test with requests (bypassing proxies)
        print(f"\n[*] testing HTTP GET http://{host}:8080/api/bot/info (requests, proxies bypassed)...")
        try:
            r = requests.get(f"http://{host}:8080/api/bot/info", timeout=3, proxies={"http": None, "https": None})
            print(f"  SUCCESS! Status: {r.status_code}")
            print(f"  Response: {r.json()}")
        except Exception as e:
            print(f"  FAILED: {e}")

        # 4. WebSocket connect
        ws_url = f"ws://{label}/api/ws/sync/TEST-DIAGNOSTIC-CODE"
        print(f"\n[*] testing WebSocket connection to {ws_url}...")
        try:
            async with websockets.connect(ws_url, open_timeout=3) as ws:
                print("  SUCCESS! WebSocket connection established and accepted.")
        except Exception as e:
            print(f"  FAILED: {type(e).__name__}: {e}")
            if hasattr(e, "status_code"):
                print(f"    Status Code: {e.status_code}")
            if hasattr(e, "headers"):
                print(f"    Headers: {dict(e.headers)}")

if __name__ == "__main__":
    asyncio.run(run_diagnostics())
