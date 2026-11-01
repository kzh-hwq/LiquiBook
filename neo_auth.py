"""Xac thuc NEO API (JWT) voi tu dong lam moi token.
 
Luu y: anh tai lieu khong cho biet 2 chi tiet, hay kiem tra lai tren trang docs:
  1) Body gui dang JSON hay form  -> doi BODY_AS_JSON
  2) Tham so lam moi token        -> sua ham _refresh()
"""
import json
import os
import subprocess
import time
import threading
from pathlib import Path
from urllib.parse import urlencode
 
from dotenv import load_dotenv
 
# Doc .env nam canh file code, bat ke chay tu thu muc nao
load_dotenv(Path(__file__).resolve().parent / ".env")
 
BODY_AS_JSON = True      # doi thanh False neu docs yeu cau form-urlencoded
EXPIRY_MARGIN = 300      # lam moi som 5 phut truoc khi het han (token song 10800s)
 
 
class NeoAuth:
    def __init__(self):
        self.url = os.getenv("NEO_AUTH_URL", "https://external.vpbanks.com.vn/auth/token")
        self.username = os.environ["NEO_USERNAME"]
        self.password = os.environ["NEO_PASSWORD"]
        self.access_token = None
        self.refresh_token = None
        self.expires_at = 0.0
        self._lock = threading.Lock()
 
    def _post(self, payload: dict) -> dict:
        """Goi bang `curl` thay vi `requests`: Cloudflare cua VPBankS chan dau van ket noi cua
        thu vien Python (403) nhung chap nhan curl. Mat khau di qua stdin, khong lo trong `ps`."""
        if BODY_AS_JSON:
            ctype, body = "application/json", json.dumps(payload)
        else:
            ctype, body = "application/x-www-form-urlencoded", urlencode(payload)
        cmd = ["curl", "-sS", "--max-time", "15", "-X", "POST", self.url,
               "-H", f"Content-Type: {ctype}", "-H", "Accept: application/json",
               "-d", "@-", "-w", "\n%{http_code}"]
        res = subprocess.run(cmd, input=body, capture_output=True, text=True)
        if res.returncode != 0:
            raise RuntimeError(f"curl loi ({res.returncode}): {res.stderr.strip()[:200]}")
        out, _, code = res.stdout.rpartition("\n")
        if code.strip() != "200":
            raise RuntimeError(f"HTTP {code.strip()}: {out[:300]}")
        try:
            return json.loads(out)
        except json.JSONDecodeError:
            raise RuntimeError(f"Phan hoi khong phai JSON: {out[:200]}")
 
    def _store(self, data: dict) -> None:
        # Co the token nam trong data["data"]; xu ly ca hai truong hop.
        body = data.get("data", data) if isinstance(data, dict) else data
        if not isinstance(body, dict) or "access_token" not in body:
            info = {k: data.get(k) for k in ("status", "code", "message") if isinstance(data, dict) and k in data}
            if isinstance(body, dict):
                info["data"] = {k: v for k, v in body.items() if "token" not in k.lower()}
            raise RuntimeError(f"May chu khong tra access_token. Phan hoi: {info}")
        self.access_token = body["access_token"]
        self.refresh_token = body.get("refresh_token", self.refresh_token)
        self.expires_at = time.time() + int(body.get("expires_in", 10800))
 
    def login(self) -> None:
        self._store(self._post({"username": self.username, "password": self.password}))
 
    def _refresh(self) -> None:
        # TODO: kiem tra docs xem refresh can truong nao (vd grant_type, refresh_token).
        try:
            self._store(self._post({"grant_type": "refresh_token",
                                    "refresh_token": self.refresh_token}))
        except Exception:  # noqa: BLE001
            self.login()  # du phong: dang nhap lai
 
    def token(self) -> str:
        with self._lock:
            if not self.access_token:
                self.login()
            elif time.time() > self.expires_at - EXPIRY_MARGIN:
                self._refresh()
            return self.access_token
 
    def headers(self) -> dict:
        return {"Authorization": f"Bearer {self.token()}"}
 
 
if __name__ == "__main__":
    # Kiem tra nhanh: chi in do dai token, khong in token.
    auth = NeoAuth()
    tok = auth.token()
    print(f"Dang nhap OK. Do dai token: {len(tok)}, het han sau {int(auth.expires_at - time.time())}s")
 