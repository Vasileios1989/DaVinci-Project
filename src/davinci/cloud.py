"""Λογαριασμός χρήστη και μόνιμη αποθήκευση του ιστορικού στο Supabase (απόφαση του χρήστη 11/11/2026).

Δεν υπολογίζει τίποτα. Μιλά με δύο υπηρεσίες του Supabase μέσω HTTPS (μόνο με τη βασική βιβλιοθήκη της Python):
- Auth (`/auth/v1`): εγγραφή, σύνδεση με email και κωδικό, ανάκτηση κωδικού, ανανέωση της σύνδεσης.
- Πίνακας `measurements` (`/rest/v1`): μία γραμμή ανά χρήστη και ημερομηνία· στη στήλη `data` η εγγραφή του
  `history.snapshot` όπως είναι.

Ασφάλεια: η εφαρμογή έχει μόνο το δημόσιο κλειδί (publishable). Κάθε ανάγνωση και εγγραφή γίνεται με το διακριτικό
του συνδεδεμένου χρήστη, και ο κανόνας του πίνακα (Row Level Security, βλ. `SETUP_SQL`) επιτρέπει μόνο τις γραμμές
του ίδιου χρήστη. Ο κωδικός δεν αποθηκεύεται πουθενά από την εφαρμογή.
"""

from __future__ import annotations

import base64
import hashlib
import json
import secrets as _secrets
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Callable

TABLE = "measurements"

SETUP_SQL = """\
-- DaVinci Fitness: πίνακας μετρήσεων. Τρέχει μία φορά στο Supabase → SQL Editor → Run.
create table if not exists public.measurements (
  id bigint generated always as identity primary key,
  user_id uuid not null default auth.uid() references auth.users (id) on delete cascade,
  measured_on date not null,
  data jsonb not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (user_id, measured_on)
);

alter table public.measurements enable row level security;

create policy "own rows: select" on public.measurements
  for select to authenticated using ((select auth.uid()) = user_id);
create policy "own rows: insert" on public.measurements
  for insert to authenticated with check ((select auth.uid()) = user_id);
create policy "own rows: update" on public.measurements
  for update to authenticated using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
create policy "own rows: delete" on public.measurements
  for delete to authenticated using ((select auth.uid()) = user_id);

create or replace function public.measurements_touch() returns trigger
  language plpgsql set search_path = '' as $$
begin
  new.updated_at := now();
  return new;
end;
$$;
create trigger measurements_touch before update on public.measurements
  for each row execute function public.measurements_touch();

revoke all on public.measurements from anon;
grant select, insert, update, delete on public.measurements to authenticated;
"""

# Μηνύματα για τους κωδικούς σφάλματος του Supabase Auth (ό,τι δεν είναι εδώ: γενικό μήνυμα).
MESSAGES = {
    "invalid_credentials": "Λάθος email ή κωδικός.",
    "email_not_confirmed": "Το email δεν έχει επιβεβαιωθεί. Άνοιξε τον σύνδεσμο που σου στάλθηκε και ξαναδοκίμασε.",
    "user_already_exists": "Υπάρχει ήδη λογαριασμός με αυτό το email. Συνδέσου ή ζήτησε νέο κωδικό.",
    "email_exists": "Υπάρχει ήδη λογαριασμός με αυτό το email. Συνδέσου ή ζήτησε νέο κωδικό.",
    "weak_password": "Ο κωδικός είναι αδύναμος. Χρησιμοποίησε τουλάχιστον 8 χαρακτήρες.",
    "validation_failed": "Έλεγξε το email και τον κωδικό.",
    "email_address_invalid": "Το email δεν είναι έγκυρο.",
    "over_email_send_rate_limit": "Στάλθηκαν πολλά email σε λίγο χρόνο. Δοκίμασε ξανά σε λίγα λεπτά.",
    "over_request_rate_limit": "Πολλές προσπάθειες σε λίγο χρόνο. Δοκίμασε ξανά σε λίγα λεπτά.",
    "signup_disabled": "Οι νέες εγγραφές είναι κλειστές.",
    "refresh_token_not_found": "Η σύνδεση έληξε. Συνδέσου ξανά.",
    "session_expired": "Η σύνδεση έληξε. Συνδέσου ξανά.",
    "otp_expired": "Ο κωδικός έληξε ή είναι λάθος. Ζήτησε νέο.",
    "same_password": "Ο νέος κωδικός είναι ίδιος με τον παλιό.",
    "provider_disabled": "Η σύνδεση με Google δεν έχει ενεργοποιηθεί στο Supabase.",
    "flow_state_not_found": "Η σύνδεση με Google έληξε. Δοκίμασε ξανά.",
    "flow_state_expired": "Η σύνδεση με Google έληξε. Δοκίμασε ξανά.",
    "bad_code_verifier": "Η σύνδεση με Google δεν ολοκληρώθηκε. Δοκίμασε ξανά.",
}
GENERIC = "Η υπηρεσία αποθήκευσης δεν απάντησε σωστά. Δοκίμασε ξανά."
OFFLINE = "Δεν υπάρχει σύνδεση με την υπηρεσία αποθήκευσης. Έλεγξε το internet ή δοκίμασε σε λίγο."
PAUSED_HINT = " Αν το project του Supabase είναι σε παύση, πάτα «Resume» στη σελίδα του."


class CloudError(Exception):
    def __init__(self, message: str, code: str | None = None, status: int | None = None, detail: str = ""):
        super().__init__(message)
        self.code, self.status, self.detail = code, status, detail


@dataclass(frozen=True)
class Session:
    access_token: str
    refresh_token: str
    user_id: str
    email: str


# Μεταφορά: (μέθοδος, url, κεφαλίδες, σώμα) → (κωδικός HTTP, σώμα). Στα τεστ αντικαθίσταται.
Transport = Callable[[str, str, dict, bytes | None], tuple[int, bytes]]


def urllib_transport(method: str, url: str, headers: dict, body: bytes | None) -> tuple[int, bytes]:
    req = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        detail = f"{type(e).__name__}: {getattr(e, 'reason', e)}"[:200]
        print(f"[DaVinci/Supabase] {method} {url.split('?')[0]} → {detail}", file=sys.stderr)
        raise CloudError(f"{OFFLINE}{PAUSED_HINT} ({detail})", detail=detail) from e


def _error(status: int, raw: bytes) -> CloudError:
    try:
        d = json.loads(raw or b"{}")
    except ValueError:
        d = {}
    code = d.get("error_code") or d.get("code") or d.get("error")
    if code == "invalid_grant" and "confirm" in str(d.get("error_description", "")).lower():
        code = "email_not_confirmed"
    if code == "invalid_grant":
        code = "invalid_credentials"
    # Ο λόγος όπως τον έδωσε το Supabase (χωρίς κλειδιά ή διακριτικά): φαίνεται όταν δεν έχουμε δικό μας μήνυμα
    text = d.get("msg") or d.get("message") or d.get("error_description") or d.get("hint") or ""
    if not text and not d:
        text = (raw or b"").decode("utf-8", "replace").strip()
    detail = " · ".join(str(x) for x in (f"Supabase {status}", code, text) if x)[:240]
    print(f"[DaVinci/Supabase] {detail}", file=sys.stderr)  # στα logs του Streamlit (Manage app)
    known = MESSAGES.get(str(code))
    msg = known or f"{GENERIC}{PAUSED_HINT if status in (502, 503, 504, 540) else ''} ({detail})"
    return CloudError(msg, str(code) if code else None, status, detail)


# Σύνδεση με Google (PKCE): ο «verifier» μένει στον διακομιστή της εφαρμογής μέχρι να γυρίσει ο χρήστης από τη
# Google· στη διεύθυνση επιστροφής ταξιδεύει μόνο ένα τυχαίο κλειδί (dv) που τον βρίσκει.
_PKCE: dict[str, str] = {}
_PKCE_MAX = 500
OAUTH_EXPIRED = ("Η σύνδεση με Google έληξε (η εφαρμογή ξεκίνησε ξανά ή ο σύνδεσμος χρησιμοποιήθηκε ήδη). "
                 "Δοκίμασε ξανά.")
OAUTH_NO_KEY = ("Η Google σε επέστρεψε στην εφαρμογή χωρίς το κλειδί της σύνδεσης. Στο Supabase → Authentication → "
                "URL Configuration → Redirect URLs πρόσθεσε τη διεύθυνση της εφαρμογής με /** στο τέλος "
                "(π.χ. https://….streamlit.app/**) και δοκίμασε ξανά.")


def oauth_error(params) -> str | None:
    """Η Google ή το Supabase γύρισαν με ?error=…: το μήνυμα για την οθόνη (None αν δεν υπάρχει σφάλμα)."""
    err = params.get("error") or params.get("error_code")
    if not err:
        return None
    desc = params.get("error_description") or ""
    return f"Η σύνδεση με Google απέτυχε: {desc or err} ({err})."[:300]


class Supabase:
    def __init__(self, url: str, key: str, transport: Transport = urllib_transport, app_url: str | None = None):
        self.url, self.key, self.transport = url.rstrip("/"), key, transport
        self.app_url = app_url.rstrip("/") if app_url else None  # η διεύθυνση της εφαρμογής (για το Google)

    # --- κλήσεις ---
    def _call(self, method: str, path: str, body=None, token: str | None = None, extra: dict | None = None):
        headers = {"apikey": self.key, "Content-Type": "application/json", "Accept": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        headers.update(extra or {})
        data = None if body is None else json.dumps(body, ensure_ascii=False).encode()
        status, raw = self.transport(method, self.url + path, headers, data)
        if status >= 400:
            e = _error(status, raw)
            e.detail = f"{method} {path.split('?')[0]}{'?' + path.split('?')[1].split('&')[0] if '?' in path else ''} → {e.detail}"
            if not MESSAGES.get(str(e.code)):
                e.args = (f"{GENERIC} ({e.detail})",)
            raise e
        try:
            return json.loads(raw) if raw else None
        except ValueError as exc:
            detail = f"{method} {path.split('?')[0]} → {status}, όχι JSON: {raw[:120]!r}"
            print(f"[DaVinci/Supabase] {detail}", file=sys.stderr)
            raise CloudError(f"{GENERIC} ({detail})", status=status, detail=detail) from exc

    @staticmethod
    def _session(d: dict) -> Session:
        if not isinstance(d, dict) or not d.get("access_token") or not d.get("refresh_token"):
            keys = ", ".join(sorted(d)) if isinstance(d, dict) else type(d).__name__
            raise CloudError(f"{GENERIC} (η απάντηση δεν είχε σύνδεση· πεδία: {keys})", detail=keys)
        u = d.get("user") or {}
        return Session(d["access_token"], d["refresh_token"], u.get("id", ""), u.get("email", ""))

    # --- λογαριασμός ---
    def sign_up(self, email: str, password: str) -> Session | None:
        """Νέος λογαριασμός. None = πρέπει πρώτα να επιβεβαιωθεί το email (στάλθηκε σύνδεσμος)."""
        d = self._call("POST", "/auth/v1/signup", {"email": email.strip(), "password": password})
        if d and d.get("access_token"):
            return self._session(d)
        user = (d or {}).get("user") or d or {}
        if user.get("identities") == []:
            # με επιβεβαίωση email, το Supabase απαντά με κενά identities όταν το email υπάρχει ήδη
            raise CloudError(MESSAGES["user_already_exists"], "user_already_exists")
        return None

    def sign_in(self, email: str, password: str) -> Session:
        return self._session(self._call("POST", "/auth/v1/token?grant_type=password",
                                        {"email": email.strip(), "password": password}))

    def refresh(self, s: Session) -> Session:
        return self._session(self._call("POST", "/auth/v1/token?grant_type=refresh_token",
                                        {"refresh_token": s.refresh_token}))

    def recover(self, email: str) -> None:
        self._call("POST", "/auth/v1/recover", {"email": email.strip()})

    def verify_recovery(self, email: str, code: str) -> Session:
        """Ο κωδικός μίας χρήσης του email «Reset password» → σύνδεση (για να οριστεί νέος κωδικός)."""
        return self._session(self._call("POST", "/auth/v1/verify",
                                        {"type": "recovery", "email": email.strip(), "token": code.strip()}))

    def set_password(self, s: Session, password: str) -> None:
        self._call("PUT", "/auth/v1/user", {"password": password}, s.access_token)

    def remembered(self, refresh_token: str) -> Session:
        """«Να με θυμάσαι»: νέα σύνδεση από το διακριτικό ανανέωσης που κρατά η συσκευή (όχι ο κωδικός)."""
        return self.refresh(Session("", refresh_token, "", ""))

    def google_url(self) -> str | None:
        """Η διεύθυνση του κουμπιού «Σύνδεση με Google»· None αν δεν έχει οριστεί η διεύθυνση της εφαρμογής."""
        if not self.app_url:
            return None
        nonce, verifier = _secrets.token_urlsafe(16), _secrets.token_urlsafe(48)
        while len(_PKCE) >= _PKCE_MAX:
            _PKCE.pop(next(iter(_PKCE)))
        _PKCE[nonce] = verifier
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
        q = urllib.parse.urlencode({"provider": "google", "redirect_to": f"{self.app_url}/?dv={nonce}",
                                    "code_challenge": challenge, "code_challenge_method": "s256"})
        return f"{self.url}/auth/v1/authorize?{q}"

    def google_finish(self, code: str, nonce: str) -> Session:
        """Ο χρήστης γύρισε από τη Google με ?code=…&dv=…: ανταλλαγή του κωδικού με σύνδεση."""
        verifier = _PKCE.pop(nonce, None)
        if verifier is None:
            raise CloudError(OAUTH_EXPIRED)
        return self._session(self._call("POST", "/auth/v1/token?grant_type=pkce",
                                        {"auth_code": code, "code_verifier": verifier}))

    def sign_out(self, s: Session) -> None:
        try:
            self._call("POST", "/auth/v1/logout", {}, s.access_token)
        except CloudError:
            pass  # η αποσύνδεση στην εφαρμογή γίνεται ούτως ή άλλως

    # --- μετρήσεις (με αυτόματη ανανέωση της σύνδεσης μία φορά) ---
    def _as_user(self, s: Session, fn):
        """(αποτέλεσμα, σύνδεση): αν το διακριτικό έληξε, ανανεώνεται και η κλήση ξαναγίνεται μία φορά."""
        try:
            return fn(s), s
        except CloudError as e:
            if e.status != 401 and e.code not in ("bad_jwt", "PGRST301", "PGRST303"):
                raise
        s = self.refresh(s)
        return fn(s), s

    def list(self, s: Session) -> tuple[list[dict], Session]:
        q = f"/rest/v1/{TABLE}?select=measured_on,data&order=measured_on.asc"
        rows, s = self._as_user(s, lambda x: self._call("GET", q, token=x.access_token))
        return [r["data"] for r in rows or ()], s

    def save(self, s: Session, entry: dict) -> Session:
        """Νέα μέτρηση ή αντικατάσταση της μέτρησης της ίδιας ημερομηνίας."""
        q = f"/rest/v1/{TABLE}?on_conflict=user_id,measured_on"
        hdr = {"Prefer": "resolution=merge-duplicates,return=minimal"}
        return self._as_user(s, lambda x: self._call(
            "POST", q, {"user_id": x.user_id, "measured_on": entry["date"], "data": entry},
            x.access_token, hdr))[1]

    def delete(self, s: Session, day: str) -> Session:
        q = f"/rest/v1/{TABLE}?measured_on=eq.{urllib.parse.quote(day)}"
        return self._as_user(s, lambda x: self._call("DELETE", q, token=x.access_token,
                                                     extra={"Prefer": "return=minimal"}))[1]


def from_secrets(secrets) -> Supabase | None:
    """Από τα Secrets του Streamlit: [supabase] url = "…", key = "…" και, για το Google, app_url = "…".
    None αν δεν έχουν οριστεί."""
    try:
        conf = secrets["supabase"]
        url, key = str(conf["url"]).strip(), str(conf["key"]).strip()
    except Exception:
        return None
    if not url.startswith("https://") or not key:
        return None
    try:
        app_url = str(conf["app_url"]).strip()
    except Exception:
        app_url = ""
    return Supabase(url, key, app_url=app_url if app_url.startswith("https://") else None)
