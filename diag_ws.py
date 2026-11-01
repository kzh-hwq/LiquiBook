"""Chan doan ket noi WebSocket NEO API (khong luu du lieu, khong in token/mat khau).

Thu cac bien the: co/khong header Origin; in ma trang thai bat tay, phan hoi dau tien.
"""
import json
import os
import time
from pathlib import Path

import certifi
import websocket
from dotenv import load_dotenv

from neo_auth import NeoAuth

load_dotenv(Path(__file__).resolve().parent / ".env")
URL = os.getenv("NEO_WS_URL", "wss://neoapi.vpbanks.com.vn/stock-stream/broker")
ORIGIN = "https://neoinvest.vpbanks.com.vn"

token = NeoAuth().token()
print("Da lay token (do dai", len(token), ")\n")


def listen(ws, seconds, label):
    ws.settimeout(1)
    end, got = time.time() + seconds, 0
    while time.time() < end:
        try:
            msg = ws.recv()
        except websocket.WebSocketTimeoutException:
            continue
        except Exception as e:  # noqa: BLE001
            print(f"   {label}: loi/dong ket noi: {type(e).__name__}: {e}")
            return got
        got += 1
        print(f"   {label}: nhan duoc: {str(msg)[:300]}")
        if got >= 3:
            break
    return got


def trial(name, **kw):
    print(f"=== {name} ===")
    try:
        ws = websocket.create_connection(URL, timeout=10, sslopt={"ca_certs": certifi.where()}, **kw)
    except Exception as e:  # noqa: BLE001
        print("   Khong ket noi duoc:", type(e).__name__, e, "\n")
        return
    print("   Bat tay OK, ma trang thai:", getattr(ws, "getstatus", lambda: "?")())
    n = listen(ws, 3, "truoc khi gui")
    ws.send(json.dumps({"action": "auth", "data": token}))
    print("   Da gui lenh auth, cho 12 giay...")
    n += listen(ws, 12, "sau khi gui")
    if n == 0:
        try:
            ws.ping()
            print("   Khong co thong diep nao. Ping gui duoc (ket noi con song).")
        except Exception as e:  # noqa: BLE001
            print("   Ket noi da chet:", type(e).__name__, e)
    ws.close()
    print()


trial("A: khong Origin")
trial("B: co Origin", origin=ORIGIN)
