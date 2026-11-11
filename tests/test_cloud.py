"""Λογαριασμός και μόνιμη αποθήκευση (cloud) με ψεύτικο Supabase: δεν γίνεται καμία κλήση στο internet."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from davinci import cloud  # noqa: E402
from fake_supabase import FakeSupabase  # noqa: E402


def client(**k):
    srv = FakeSupabase(**k)
    return cloud.Supabase("https://x.supabase.co/", "pk", srv), srv


def test_sign_up_sign_in_and_errors_in_greek():
    c, srv = client()
    s = c.sign_up("a@b.gr", "12345678")
    assert s.email == "a@b.gr" and s.user_id == "u1"
    assert c.sign_in(" a@b.gr ", "12345678").user_id == "u1"
    with pytest.raises(cloud.CloudError, match="Λάθος email ή κωδικός"):
        c.sign_in("a@b.gr", "λάθος")
    url, headers = srv.calls[0][1], srv.calls[0][2]
    assert url == "https://x.supabase.co/auth/v1/signup" and "Authorization" not in headers


def test_sign_up_with_email_confirmation():
    c, srv = client(confirm_email=True)
    assert c.sign_up("a@b.gr", "12345678") is None  # πρώτα επιβεβαίωση
    with pytest.raises(cloud.CloudError, match="δεν έχει επιβεβαιωθεί"):
        c.sign_in("a@b.gr", "12345678")
    with pytest.raises(cloud.CloudError, match="Υπάρχει ήδη λογαριασμός"):
        c.sign_up("a@b.gr", "12345678")


def test_each_user_sees_only_own_measurements_and_same_day_replaces():
    c, srv = client()
    a, b = c.sign_up("a@b.gr", "12345678"), c.sign_up("c@d.gr", "12345678")
    a = c.save(a, {"date": "2026-11-11", "summary": {"weight_kg": 140}})
    a = c.save(a, {"date": "2026-11-11", "summary": {"weight_kg": 139}})
    a = c.save(a, {"date": "2026-10-01", "summary": {"weight_kg": 141}})
    b = c.save(b, {"date": "2026-11-11", "summary": {"weight_kg": 70}})
    rows, a = c.list(a)
    assert [(r["date"], r["summary"]["weight_kg"]) for r in rows] == [("2026-10-01", 141), ("2026-11-11", 139)]
    assert [r["summary"]["weight_kg"] for r in c.list(b)[0]] == [70]
    a = c.delete(a, "2026-11-11")
    assert [r["date"] for r in c.list(a)[0]] == ["2026-10-01"] and len(c.list(b)[0]) == 1
    post = next(x for x in srv.calls if x[0] == "POST" and "/rest/v1/" in x[1])
    assert post[2]["Authorization"].startswith("Bearer at") and "on_conflict=user_id,measured_on" in post[1]


def test_expired_token_is_refreshed_once():
    c, srv = client()
    s = c.sign_up("a@b.gr", "12345678")
    srv.expire_next = True
    rows, s2 = c.list(s)
    assert rows == [] and s2.access_token != s.access_token and s2.user_id == s.user_id


def test_password_recovery_with_code():
    c, srv = client()
    c.sign_up("a@b.gr", "12345678")
    c.recover("a@b.gr")
    with pytest.raises(cloud.CloudError, match="έληξε ή είναι λάθος"):
        c.verify_recovery("a@b.gr", "000000")
    s = c.verify_recovery("a@b.gr", "123456")
    c.set_password(s, "νέος-κωδικός")
    assert c.sign_in("a@b.gr", "νέος-κωδικός").user_id == "u1"


def test_offline_and_secrets():
    c = cloud.Supabase("https://x.supabase.co", "pk", lambda *a: cloud.urllib_transport("GET", "http://127.0.0.1:9", {}, None))
    with pytest.raises(cloud.CloudError, match="Δεν υπάρχει σύνδεση"):
        c.sign_in("a@b.gr", "12345678")
    assert cloud.from_secrets({}) is None and cloud.from_secrets(None) is None
    assert cloud.from_secrets({"supabase": {"url": "http://x", "key": "k"}}) is None
    ok = cloud.from_secrets({"supabase": {"url": "https://nryjgdgcopwcqjfjmetm.supabase.co", "key": "sb_publishable_x"}})
    assert ok.url == "https://nryjgdgcopwcqjfjmetm.supabase.co" and ok.key == "sb_publishable_x"


def test_setup_sql_protects_rows():
    sql = cloud.SETUP_SQL
    assert "enable row level security" in sql and sql.count("(select auth.uid()) = user_id") == 5
    assert "revoke all on public.measurements from anon" in sql and "unique (user_id, measured_on)" in sql


def test_remember_me_uses_refresh_token_not_password():
    c, srv = client()
    s = c.sign_up("a@b.gr", "12345678")
    again = c.remembered(s.refresh_token)
    assert again.user_id == s.user_id and again.email == "a@b.gr" and again.refresh_token != s.refresh_token
    with pytest.raises(cloud.CloudError, match="Η σύνδεση έληξε"):
        c.remembered(s.refresh_token)  # κάθε διακριτικό ανανέωσης ισχύει μία φορά


def test_google_sign_in_with_pkce():
    import urllib.parse
    srv = FakeSupabase()
    assert cloud.Supabase("https://x.supabase.co", "pk", srv).google_url() is None  # χωρίς διεύθυνση εφαρμογής
    c = cloud.Supabase("https://x.supabase.co", "pk", srv, app_url="https://app.streamlit.app/")
    url = c.google_url()
    assert url.startswith("https://x.supabase.co/auth/v1/authorize?provider=google&")
    back = urllib.parse.parse_qs(urllib.parse.urlsplit(srv.google(url, "g@gmail.com")).query)
    assert set(back) == {"dv", "code"}  # ο verifier δεν ταξιδεύει στη διεύθυνση
    s = c.google_finish(back["code"][0], back["dv"][0])
    assert s.email == "g@gmail.com"
    with pytest.raises(cloud.CloudError, match="έληξε"):
        c.google_finish(back["code"][0], back["dv"][0])  # το κλειδί ισχύει μία φορά
    conf = {"supabase": {"url": "https://x.supabase.co", "key": "k", "app_url": "https://app.streamlit.app"}}
    assert cloud.from_secrets(conf).app_url == "https://app.streamlit.app"


def test_unknown_errors_show_supabase_reason():
    # Ο λόγος του Supabase φαίνεται όταν δεν έχουμε δικό μας μήνυμα (π.χ. απόρριψη στην πύλη πριν από το Auth)
    c = cloud.Supabase("https://x.supabase.co", "pk", lambda *a: (401, b'{"message":"Invalid API key"}'))
    with pytest.raises(cloud.CloudError) as e:
        c.sign_in("a@b.gr", "12345678")
    assert "Supabase 401" in str(e.value) and "Invalid API key" in str(e.value)
    assert "POST /auth/v1/token?grant_type=password" in str(e.value)
    html = cloud.Supabase("https://x.supabase.co", "pk", lambda *a: (404, b"<html>no Route matched</html>"))
    with pytest.raises(cloud.CloudError, match="no Route matched"):
        html.recover("a@b.gr")
    odd = cloud.Supabase("https://x.supabase.co", "pk", lambda *a: (200, b"<html>"))
    with pytest.raises(cloud.CloudError, match="όχι JSON"):
        odd.sign_in("a@b.gr", "12345678")
    empty = cloud.Supabase("https://x.supabase.co", "pk", lambda *a: (200, b'{"user": {}}'))
    with pytest.raises(cloud.CloudError, match="πεδία: user"):
        empty.sign_in("a@b.gr", "12345678")
    known = cloud.Supabase("https://x.supabase.co", "pk", lambda *a: (400, b'{"error_code":"invalid_credentials"}'))
    with pytest.raises(cloud.CloudError) as e:
        known.sign_in("a@b.gr", "x")
    assert str(e.value) == "Λάθος email ή κωδικός." and "Supabase 400" in e.value.detail


def test_oauth_error_params():
    assert cloud.oauth_error({}) is None and cloud.oauth_error({"code": "x"}) is None
    msg = cloud.oauth_error({"error": "access_denied", "error_description": "User cancelled"})
    assert msg == "Η σύνδεση με Google απέτυχε: User cancelled (access_denied)."
