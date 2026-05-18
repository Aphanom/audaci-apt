import requests
try:
    res = requests.get("http://127.0.0.1:8080/api/sync/SYNC-C7B187", timeout=5, proxies={"http": None, "https": None})
    print("STATUS:", res.status_code)
    print("JSON:", res.json())
except Exception as e:
    print("ERROR:", e)
