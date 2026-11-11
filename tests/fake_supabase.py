"""Ψεύτικο Supabase για τα τεστ: Auth (εγγραφή, σύνδεση, ανανέωση, ανάκτηση) και πίνακας `measurements` με τον
κανόνα «κάθε χρήστης μόνο τις δικές του γραμμές» (όπως το Row Level Security του `cloud.SETUP_SQL`)."""

import json
import urllib.parse


class FakeSupabase:
    def __init__(self, confirm_email=False):
        self.users = {}  # email → {"id", "password", "confirmed"}
        self.tokens = {}  # access token → user id
        self.refresh = {}  # refresh token → user id
        self.rows = []  # {"user_id", "measured_on", "data"}
        self.confirm_email, self.calls, self.n = confirm_email, [], 0
        self.otp = {}  # email → κωδικός ανάκτησης
        self.expire_next = False  # η επόμενη κλήση στον πίνακα απαντά 401 (έληξε το διακριτικό)

    def _issue(self, uid):
        self.n += 1
        a, r = f"at{self.n}", f"rt{self.n}"
        self.tokens[a], self.refresh[r] = uid, r and uid
        email = next(e for e, u in self.users.items() if u["id"] == uid)
        return {"access_token": a, "refresh_token": r, "user": {"id": uid, "email": email}}

    @staticmethod
    def _err(status, code, msg="x"):
        return status, json.dumps({"code": status, "error_code": code, "msg": msg}).encode()

    def __call__(self, method, url, headers, body):
        self.calls.append((method, url, headers, body))
        assert headers["apikey"] == "pk"
        u = urllib.parse.urlsplit(url)
        q = urllib.parse.parse_qs(u.query)
        d = json.loads(body) if body else {}
        if u.path == "/auth/v1/signup":
            if d["email"] in self.users:
                return 200, json.dumps({"id": "fake", "identities": []}).encode()
            uid = f"u{len(self.users) + 1}"
            self.users[d["email"]] = {"id": uid, "password": d["password"], "confirmed": not self.confirm_email}
            if self.confirm_email:
                return 200, json.dumps({"id": uid, "identities": [{"id": "i"}]}).encode()
            return 200, json.dumps(self._issue(uid)).encode()
        if u.path == "/auth/v1/token" and q["grant_type"] == ["password"]:
            usr = self.users.get(d["email"])
            if not usr or usr["password"] != d["password"]:
                return self._err(400, "invalid_credentials")
            if not usr["confirmed"]:
                return self._err(400, "email_not_confirmed")
            return 200, json.dumps(self._issue(usr["id"])).encode()
        if u.path == "/auth/v1/token" and q["grant_type"] == ["refresh_token"]:
            uid = self.refresh.pop(d["refresh_token"], None)
            if uid is None:
                return self._err(400, "refresh_token_not_found")
            return 200, json.dumps(self._issue(uid)).encode()
        if u.path == "/auth/v1/recover":
            if d["email"] in self.users:
                self.otp[d["email"]] = "123456"
            return 200, b"{}"
        if u.path == "/auth/v1/verify":
            if self.otp.get(d["email"]) != d["token"]:
                return self._err(403, "otp_expired")
            return 200, json.dumps(self._issue(self.users[d["email"]]["id"])).encode()
        uid = self.tokens.get(headers.get("Authorization", "").removeprefix("Bearer "))
        if u.path == "/auth/v1/user" and method == "PUT":
            email = next(e for e, x in self.users.items() if x["id"] == uid)
            self.users[email]["password"] = d["password"]
            return 200, b"{}"
        if u.path == "/auth/v1/logout":
            return 204, b""
        assert u.path == "/rest/v1/measurements"
        if uid is None or self.expire_next:
            self.expire_next = False
            return 401, json.dumps({"code": "PGRST301", "message": "JWT expired"}).encode()
        mine = [r for r in self.rows if r["user_id"] == uid]  # Row Level Security
        if method == "GET":
            return 200, json.dumps(sorted(({"measured_on": r["measured_on"], "data": r["data"]} for r in mine),
                                          key=lambda r: r["measured_on"])).encode()
        if method == "POST":
            if d["user_id"] != uid:
                return 403, json.dumps({"code": "42501", "message": "row-level security"}).encode()
            self.rows = [r for r in self.rows if not (r["user_id"] == uid and r["measured_on"] == d["measured_on"])]
            self.rows.append(d)
            return 201, b""
        if method == "DELETE":
            day = q["measured_on"][0].removeprefix("eq.")
            self.rows = [r for r in self.rows if not (r["user_id"] == uid and r["measured_on"] == day)]
            return 204, b""
        raise AssertionError((method, url))
