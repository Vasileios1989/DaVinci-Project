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
