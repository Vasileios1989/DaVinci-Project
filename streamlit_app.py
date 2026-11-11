"""DaVinci Fitness — οθόνη της εφαρμογής (Streamlit).

Όλη η λογική είναι στο src/davinci/app_logic.py (με τεστ)· εδώ υπάρχει μόνο η οθόνη.
Εκτέλεση: streamlit run streamlit_app.py
"""

import sys
from dataclasses import replace
from datetime import date
from html import escape
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

import streamlit as st  # noqa: E402

from davinci import app_logic as al  # noqa: E402
from davinci import cloud  # noqa: E402
from davinci import element_01 as e01  # noqa: E402
from davinci import element_44 as e44  # noqa: E402
from davinci import history as hist  # noqa: E402
from davinci import measurement  # noqa: E402
from davinci import results_view as rv  # noqa: E402
from davinci.fmt import num  # noqa: E402

st.set_page_config(page_title="DaVinci Fitness", page_icon="💪", layout="centered")

# Εμφάνιση (σύμβαση συστήματος): σκούρο θέμα με κάρτες· τα χρώματα ορίζονται στο .streamlit/config.toml.
# Το CSS αλλάζει μόνο την όψη (καρτέλες, κάρτες, κουμπιά)· δεν αγγίζει υπολογισμούς ή κείμενα.
STYLE = """
<style>
.block-container {padding-top: 2.2rem; max-width: 46rem;}
/* πάνω καρτέλες: Μέτρηση · Αποτελέσματα · Πλάνο */
.stTabs [data-baseweb="tab-list"] {gap: 1.4rem; border-bottom: 1px solid rgba(255,255,255,.08);}
.stTabs [data-baseweb="tab"] {height: 3rem; padding: 0 .1rem; background: transparent;}
.stTabs [data-baseweb="tab"] p {font-size: 1.05rem; font-weight: 600; opacity: .6;}
.stTabs [data-baseweb="tab"][aria-selected="true"] p {opacity: 1;}
.stTabs [data-baseweb="tab-highlight"] {height: 3px; border-radius: 3px;}
/* δεύτερη σειρά: περιοχές μέτρησης, σε σχήμα χαπιού */
.stTabs .stTabs [data-baseweb="tab-list"] {gap: .5rem; border-bottom: 0; padding: .35rem 0 .6rem;}
.stTabs .stTabs [data-baseweb="tab"] {height: 2.3rem; padding: 0 1rem; border-radius: 999px;
    background: #262B42; border: 1px solid rgba(255,255,255,.08);}
.stTabs .stTabs [data-baseweb="tab"] p {font-size: .92rem; font-weight: 500; opacity: .85;}
.stTabs .stTabs [data-baseweb="tab"][aria-selected="true"] {background: #FF7043; border-color: #FF7043;}
.stTabs .stTabs [data-baseweb="tab"][aria-selected="true"] p {color: #14172B; opacity: 1; font-weight: 700;}
.stTabs .stTabs [data-baseweb="tab-highlight"], .stTabs .stTabs [data-baseweb="tab-border"] {display: none;}
/* κάρτες */
[data-testid="stVerticalBlockBorderWrapper"], [data-testid="stExpander"] details {
    border-radius: 16px; border-color: rgba(255,255,255,.08);}
[data-testid="stVerticalBlockBorderWrapper"] {background: #1E2238;}
[data-testid="stExpander"] details {background: #262B42;}
/* πεδία και κουμπιά */
.stButton button, .stDownloadButton button {border-radius: 999px; font-weight: 700; letter-spacing: .04em;}
[data-baseweb="input"], [data-baseweb="select"] > div {border-radius: 12px;}
h1 {font-weight: 800; letter-spacing: -.01em;}
/* «Αποτελέσματα»: γραμμές μέτρησης, αλλαγή προς τον στόχο, στόχος */
.dv-row {margin: .15rem 0 .7rem 0; line-height: 1.45;}
.dv-l1 {margin-left: 1.3rem;} .dv-l2 {margin-left: 2.6rem;}
.dv-note, .dv-missing {opacity: .75;}
.dv-down {color: #FF6B6B; font-weight: 700;}
.dv-up {color: #4ADE80; font-weight: 700;}
.dv-sub {font-size: .92rem; opacity: .9;}
.dv-target {font-size: .85rem; color: rgba(242,243,247,.55);}
h3 {font-size: 1.15rem;}
/* «ⓘ info»: μικρό κουμπί δίπλα στο στοιχείο· ανοίγει παράθυρο πάνω στην οθόνη, που κυλά και κλείνει (✕ ή έξω) */
details.dv-info {display: inline-block; margin: 0 0 0 .45rem; vertical-align: baseline;}
details.dv-info > summary {display: inline-block; cursor: pointer; list-style: none; white-space: nowrap;
  font-size: .74rem; font-weight: 600; line-height: 1.2; color: #FFB199; background: rgba(255,112,67,.14);
  border: 1px solid rgba(255,112,67,.35); border-radius: 999px; padding: .08rem .5rem;}
details.dv-info > summary::-webkit-details-marker {display: none;}
details.dv-info[open] > summary::before {content: ""; position: fixed; inset: 0; background: rgba(0,0,0,.62);
  z-index: 1000000; cursor: default;}
details.dv-info[open] > summary::after {content: "✕"; position: fixed; z-index: 1000002; top: calc(10vh + .55rem);
  right: calc(max(5vw, 50vw - 300px) + .7rem); font-size: 1.05rem; line-height: 1; color: #F2F3F7;
  background: #2F3550; border-radius: 999px; padding: .35rem .5rem;}
details.dv-info > .dv-info-body {position: fixed; z-index: 1000001; top: 10vh; left: max(5vw, 50vw - 300px);
  right: max(5vw, 50vw - 300px); max-height: 76vh; overflow-y: auto; -webkit-overflow-scrolling: touch;
  overscroll-behavior: contain; background: #1E2238; border: 1px solid rgba(255,255,255,.14); border-radius: 16px;
  box-shadow: 0 18px 50px rgba(0,0,0,.55); padding: 1rem 1.1rem 1.1rem 1.1rem; white-space: normal; text-align: left;
  font-family: Georgia, "Noto Serif", "Times New Roman", serif; font-size: .95rem; font-weight: 400;
  line-height: 1.4; color: #C5C8D3;}
.dv-info-body p {margin: 0 0 .3rem 0; font-size: .95rem; line-height: 1.4;}
.dv-info-body ol {margin: 0 0 .4rem 0; padding-left: 1.3rem;} .dv-info-body li {margin: 0 0 .25rem 0; font-size: .95rem;}
.dv-info-body p.dv-info-small {font-size: .8rem; opacity: .75; margin-top: .5rem;}
.dv-label {font-size: .9rem; margin: .35rem 0 .2rem 0;}
.dv-label-strong {font-size: 1.02rem; font-weight: 700; margin-top: 1rem;}
.dv-info-title {font-size: 1.05rem; font-weight: 700; color: #E6E8EF; margin: 0 2.2rem .4rem 0;}
.dv-info-title + .dv-info-title, .dv-info-body p + .dv-info-title {margin-top: .8rem;}
.dv-info-h {font-size: .88rem; font-weight: 700; color: #DADDE6; margin: .55rem 0 .15rem 0;}
/* αναλύσεις της άλιπης μάζας (μέσα στο κουτί που ανοίγει): μικρότερα γράμματα */
.dv-small .dv-row {font-size: .9rem; margin-bottom: .5rem;}
.dv-small .dv-sub {font-size: .84rem;} .dv-small .dv-target {font-size: .8rem;}
.dv-logo {font-size: 2.4rem; font-weight: 800; letter-spacing: -.02em; margin: 1.2rem 0 .2rem 0;}
.dv-logo span {color: #FF7043;}
</style>
"""
st.markdown(STYLE, unsafe_allow_html=True)


# ------------------------------------------------------------------ είσοδος: χωρίς λογαριασμό ή με email και κωδικό
# Μόνο όταν έχουν οριστεί τα Secrets του Supabase· αλλιώς η εφαρμογή ανοίγει όπως πριν (χωρίς λογαριασμό).
CLOUD = cloud.from_secrets(getattr(st, "secrets", None))


def session() -> cloud.Session | None:
    return st.session_state.get("session")


def cloud_call(fn):
    """Κλήση στο Supabase· σφάλμα → μήνυμα στην οθόνη και None."""
    try:
        return fn()
    except cloud.CloudError as e:
        st.error(str(e))
        return None


# «Να με θυμάσαι»: η συσκευή κρατά σε cookie μόνο το διακριτικό ανανέωσης της σύνδεσης (όχι τον κωδικό).
COOKIE, COOKIE_DAYS = "dv_rt", 60
try:
    import streamlit.components.v1 as components
except Exception:  # χωρίς components (π.χ. στα τεστ) δεν γράφεται cookie
    components = None


def write_cookie(value: str | None) -> None:
    """Γράφει (ή σβήνει, με None) το cookie στον browser. Κρατά και αντίγραφο στη συνεδρία, για έλεγχο."""
    st.session_state["_cookie"] = value
    if components is None:
        return
    age = COOKIE_DAYS * 86400 if value else 0
    components.html(f"<script>try{{window.parent.document.cookie='{COOKIE}={value or ''}; path=/; max-age={age}; "
                    "SameSite=Lax; Secure';}catch(e){}</script>", height=0)


def read_cookie() -> str | None:
    try:
        return st.context.cookies.get(COOKIE) or None
    except Exception:
        return None


def keep(s: cloud.Session) -> None:
    """Νέα ή ανανεωμένη σύνδεση: στη συνεδρία και, με «Να με θυμάσαι», στο cookie (το διακριτικό αλλάζει κάθε φορά)."""
    if st.session_state.get("session") == s:
        return
    st.session_state["session"] = s
    if st.session_state.get("remember"):
        write_cookie(s.refresh_token)


def sign_in_done(s: cloud.Session, remember: bool = False, rerun: bool = True) -> None:
    st.session_state.update(mode="account", history=[], _cloud_loaded=False, remember=remember)
    st.session_state.pop("session", None)
    keep(s)
    if rerun:
        st.rerun()


def resume() -> None:
    """Πριν από την οθόνη εισόδου: επιστροφή από τη Google (?code=…&dv=…) ή «Να με θυμάσαι» (cookie).
    Κάθε αποτυχία γράφει τον λόγο στην οθόνη (και στα logs του Streamlit)."""
    qp = getattr(st, "query_params", None)
    params = {k: qp.get(k) for k in ("code", "dv", "error", "error_code", "error_description")} if qp is not None else {}
    code, nonce = params.get("code"), params.get("dv")
    failed = cloud.oauth_error(params)
    if failed:  # η Google ή το Supabase αρνήθηκαν
        qp.clear()
        st.error(failed)
    elif code and session() is not None:  # ο ίδιος κωδικός ξανά (διπλή εκτέλεση): είσαι ήδη συνδεδεμένος
        qp.clear()
        return
    elif code and not nonce:
        qp.clear()
        st.error(cloud.OAUTH_NO_KEY)
    elif code and nonce:
        s = cloud_call(lambda: CLOUD.google_finish(code, nonce))
        qp.clear()
        if s:
            sign_in_done(s, remember=True, rerun=False)
            return
    token = read_cookie()
    if token and not st.session_state.get("_cookie_tried"):
        st.session_state["_cookie_tried"] = True
        try:
            s = CLOUD.remembered(token)
        except cloud.CloudError as e:
            print(f"[DaVinci] «Να με θυμάσαι»: {e.detail or e}", file=sys.stderr)
            write_cookie(None)  # έληξε: ζητείται ξανά σύνδεση, χωρίς μήνυμα λάθους
        else:
            sign_in_done(s, remember=True, rerun=False)


def entry_screen() -> None:
    st.markdown('<div class="dv-logo">DaVinci <span>Fitness</span></div>', unsafe_allow_html=True)
    st.caption("Σύσταση σώματος, αναλογίες και πλάνο, με βάση την επιστημονική βιβλιογραφία.")
    if st.button("Συνέχεια χωρίς λογαριασμό", key="guest"):
        st.session_state["mode"] = "guest"
        st.rerun()
    st.caption("Χωρίς λογαριασμό οι μετρήσεις κρατιούνται μόνο με αρχείο αντιγράφου.")
    st.divider()
    login, signup, reset = st.tabs(["Σύνδεση", "Νέος λογαριασμός", "Ξέχασα τον κωδικό"])
    with login:
        email = st.text_input("Email", key="li_email")
        pw = st.text_input("Κωδικός", type="password", key="li_pw")
        remember = st.checkbox("Να με θυμάσαι", value=True, key="li_remember")
        if st.button("Σύνδεση", key="li_go", type="primary"):
            s = cloud_call(lambda: CLOUD.sign_in(email or "", pw or ""))
            if s:
                sign_in_done(s, remember)
        if CLOUD.app_url:
            if "_google_url" not in st.session_state:
                st.session_state["_google_url"] = CLOUD.google_url()
            st.link_button("Σύνδεση με Google", st.session_state["_google_url"])
    with signup:
        email = st.text_input("Email", key="su_email")
        pw = st.text_input("Κωδικός (τουλάχιστον 8 χαρακτήρες)", type="password", key="su_pw")
        pw2 = st.text_input("Ξανά ο κωδικός", type="password", key="su_pw2")
        if st.button("Δημιουργία λογαριασμού", key="su_go", type="primary"):
            if (pw or "") != (pw2 or ""):
                st.error("Οι δύο κωδικοί δεν είναι ίδιοι.")
            elif len(pw or "") < 8:
                st.error(cloud.MESSAGES["weak_password"])
            else:
                try:
                    s = CLOUD.sign_up(email or "", pw)
                except cloud.CloudError as e:
                    st.error(str(e))
                else:
                    if s is not None:
                        sign_in_done(s)
                    st.success("Σου στείλαμε email επιβεβαίωσης. Άνοιξε τον σύνδεσμο και μετά συνδέσου.")
    with reset:
        email = st.text_input("Email", key="rs_email")
        if st.button("Στείλε μου κωδικό", key="rs_send"):
            if cloud_call(lambda: CLOUD.recover(email or "") or True):
                st.success("Αν υπάρχει λογαριασμός, στάλθηκε email με κωδικό μίας χρήσης.")
        code = st.text_input("Κωδικός από το email", key="rs_code")
        new = st.text_input("Νέος κωδικός (τουλάχιστον 8 χαρακτήρες)", type="password", key="rs_new")
        if st.button("Αλλαγή κωδικού", key="rs_go", type="primary"):
            if len(new or "") < 8:
                st.error(cloud.MESSAGES["weak_password"])
            else:
                s = cloud_call(lambda: CLOUD.verify_recovery(email or "", code or ""))
                if s and cloud_call(lambda: CLOUD.set_password(s, new) or True):
                    sign_in_done(s)
    st.stop()


if CLOUD is not None and (not st.session_state.get("mode") or st.query_params.get("code")):
    resume()
if CLOUD is not None and not st.session_state.get("mode"):
    entry_screen()

st.title("DaVinci Fitness")
if CLOUD is not None:
    if session() is not None:
        st.caption(f"Συνδεδεμένος: {session().email}")
        if st.button("Αποσύνδεση", key="logout"):
            CLOUD.sign_out(session())
            write_cookie(None)
            for k in ("session", "mode", "history", "_cloud_loaded", "remember", "_google_url"):
                st.session_state.pop(k, None)
            st.rerun()
    elif st.button("Σύνδεση ή νέος λογαριασμός", key="to_login"):
        st.session_state.pop("mode", None)
        st.rerun()
st.caption("Επίπεδο Normal · απώλεια λίπους και συντήρηση. Η αύξηση μυών δεν περιλαμβάνεται ακόμη. "
           "Αποθηκευμένες μετρήσεις: στο «Ιστορικό».")

TODAY = al.today()


# ------------------------------------------------------------------ στοιχεία χρήστη (όλα τα πεδία, σε περιοχές)
# Περιοχές της καρτέλας «Μέτρηση»: (σύντομο όνομα καρτέλας, πλήρης τίτλος μέσα στην περιοχή).
# Περιοχές της «Μέτρησης» (απόφαση του χρήστη 11/11/2026, 6η): η ζυγαριά μέσα στα «Προσωπικά»·
# η ενυδάτωση μόνο στο Professional. Χωρίς γκρι γραμμές-τίτλους.
AREAS = ("Προσωπικά", "Κορμός", "Άκρα")
PRO_AREAS = ("Ενυδάτωση", "Όργανα", "Εξετάσεις")

# Θερμίδες που καίει ο χρήστης: ή επίπεδο δραστηριότητας (PAL) ή δηλωμένες θερμίδες (απόφαση του χρήστη 11/11/2026).
MODES = ("Δραστηριότητα", "Σταθερό", "Εβδομαδιαίο", "Διαφοροποιημένο")
KCAL_NOTE = ("Γράψε τις συνολικές θερμίδες όλης της ημέρας, όχι μόνο της προπόνησης.",
             "Ο υπολογισμός χρησιμοποιεί τον μέσο όρο των ημερών.",
             "Το ρολόι ή η εφαρμογή δίνει εκτίμηση, όχι μέτρηση.")
MODE_INFO = {
    "Δραστηριότητα": ("Για όποιον δεν ξέρει πόσες θερμίδες καίει.",
                      "Διάλεξε το επίπεδο που σου ταιριάζει.",
                      "Θερμίδες ημέρας = βασικός μεταβολισμός × επίπεδο δραστηριότητας (PAL)."),
    "Σταθερό": ("Ίδιες θερμίδες κάθε μέρα.", *KCAL_NOTE),
    "Εβδομαδιαίο": ("Θερμίδες για κάθε ημέρα της εβδομάδας.", "Το πρόγραμμα επαναλαμβάνεται κάθε εβδομάδα.",
                    *KCAL_NOTE),
    "Διαφοροποιημένο": ("Γράψε πόσες ημέρες έχει το πρόγραμμά σου και τις θερμίδες κάθε ημέρας.",
                        "Μετά την τελευταία ημέρα ξεκινά πάλι από την πρώτη.", *KCAL_NOTE),
}
TRAINING_INFO = ("Αλλάζει τον υπολογισμό: πόση άλιπη μάζα αναμένεται να χαθεί μαζί με το λίπος.",
                 "Επηρεάζει το βάρος-στόχο και το πλάνο.")
VISCERAL_SCALE_INFO = ("Μόνο αν το δείχνει η ζυγαριά σου.", "Γράψε τον αριθμό όπως τον δείχνει, χωρίς μονάδα.")
WEEKDAYS = ("Δευτέρα", "Τρίτη", "Τετάρτη", "Πέμπτη", "Παρασκευή", "Σάββατο", "Κυριακή")
CYCLE_DAYS = (2, 90)  # «Διαφοροποιημένο»: πόσες ημέρες μπορεί να έχει το πρόγραμμα (σύμβαση συστήματος)


def pop_html(title: str, lines=(), steps=(), small: str | None = None, cls: str = "dv-info dv-guide") -> str:
    """Το «ⓘ info» δίπλα σε ένα στοιχείο: πατάς και ανοίγει παράθυρο πάνω στην οθόνη, που κυλά και κλείνει (✕)."""
    body = f'<div class="dv-info-title">{escape(title)}</div>'
    if steps:
        body += "<ol>" + "".join(f"<li>{escape(x)}</li>" for x in steps) + "</ol>"
    body += "".join(f"<p>{escape(x)}</p>" for x in lines)
    if small:
        body += f'<p class="dv-info-small">{escape(small)}</p>'
    return f'<details class="{cls}"><summary>ⓘ info</summary><div class="dv-info-body">{body}</div></details>'


def guide_html(field: str | None, extra: tuple[str, ...] = ()) -> str:
    """Οι οδηγίες μέτρησης ενός πεδίου ως «ⓘ info»· «» όταν δεν υπάρχουν."""
    g = measurement.guide(field) if field else None
    if g is None:
        return pop_html("Σημείωση", extra) if extra else ""
    return pop_html(g.title, extra, g.steps, g.protocol)


def field_label(text: str, popup: str = "", strong: bool = False) -> None:
    """Η ετικέτα ενός πεδίου με το «ⓘ info» στην ίδια γραμμή."""
    cls = "dv-label dv-label-strong" if strong else "dv-label"
    st.markdown(f'<div class="{cls}">{escape(text)}{popup}</div>', unsafe_allow_html=True)


def fill_days(keys: tuple[str, ...]) -> None:
    """«Ίδια τιμή σε όλες»: η τιμή της πρώτης ημέρας αντιγράφεται στις υπόλοιπες."""
    first = st.session_state.get(keys[0])
    if first is not None:
        for k in keys[1:]:
            st.session_state[k] = first


def kcal_input(label: str, key: str):
    return st.number_input(label, min_value=500.0, max_value=10000.0, value=None, step=10.0, format="%.0f", key=key)


def activity_inputs():
    """(κλειδί PAL ή None, μέσος όρος θερμίδων ανά ημέρα ή None, τι λείπει ή None)."""
    field_label("Θερμίδες που καίω", strong=True)
    mode = st.radio("Θερμίδες που καίω", MODES, horizontal=True, key="act_mode", label_visibility="collapsed")
    field_label(mode, pop_html(mode, MODE_INFO[mode]))
    if mode == "Δραστηριότητα":
        pals = al.pal_options()
        pal = st.selectbox("Επίπεδο δραστηριότητας (PAL)", list(pals), index=None, placeholder="Διάλεξε",
                           format_func=lambda k: f"{k.replace('.', ',')} — {pals[k]}", key="pal",
                           label_visibility="collapsed")
        return pal, None, None if pal else "επίπεδο δραστηριότητας"
    if mode == "Σταθερό":
        days = [kcal_input("Θερμίδες την ημέρα (kcal)", "kcal_fixed")]
    else:
        if mode == "Εβδομαδιαίο":
            names = WEEKDAYS
            keys = tuple(f"kcal_w{i}" for i in range(7))
        else:
            n = st.number_input("Ημέρες προγράμματος", min_value=CYCLE_DAYS[0], max_value=CYCLE_DAYS[1], value=None,
                                step=1, key="kcal_n")
            if n is None:
                return None, None, "ημέρες προγράμματος"
            names = tuple(f"Ημέρα {i}" for i in range(1, int(n) + 1))
            keys = tuple(f"kcal_d{i}" for i in range(1, int(n) + 1))
        days = [kcal_input(f"{name} (kcal)", key) for name, key in zip(names, keys)]
        st.button("Ίδια τιμή σε όλες", key="kcal_fill", on_click=fill_days, args=(keys,))
    if any(x is None for x in days):
        return None, None, "θερμίδες" if len(days) == 1 else "θερμίδες κάθε ημέρας"
    return None, al.kcal_average(days), None


def read_inputs() -> tuple[al.PlanInput | None, al.Measures, str | None]:
    """Όλα τα πεδία, σε περιοχές που διαλέγεις από πάνω. Επιστρέφει και το μήνυμα «Συμπλήρωσε: …» (ή None)."""
    # Το επίπεδο διαλέγεται μέσα στην πρώτη περιοχή· οι περιοχές του Professional υπάρχουν μόνο εκεί (Στοιχείο 46).
    pro = st.session_state.get("level") == "Professional"
    areas = AREAS + (PRO_AREAS if pro else ())
    tabs = dict(zip(areas, st.tabs(list(areas))))

    with tabs["Προσωπικά"]:
        mdate = st.date_input("Ημερομηνία μέτρησης", value=TODAY, min_value=date(1900, 1, 1), max_value=TODAY,
                              format="DD/MM/YYYY", key="mdate") or TODAY
        birth = st.date_input("Ημερομηνία γέννησης", value=None, min_value=date(1900, 1, 1), max_value=TODAY,
                              format="DD/MM/YYYY", key="birth")
        sex = st.radio("Φύλο", e01.load_data()["sexes"], horizontal=True, key="sex")
        chosen = st.session_state.get("level") or e46_levels()[0]
        field_label("Επίπεδο μέτρησης", pop_html(f"Επίπεδο {chosen}", al.level_info(chosen)))
        level = st.radio("Επίπεδο μέτρησης", e46_levels(), horizontal=True, key="level", label_visibility="collapsed")
        height = measure_input("Ύψος (cm)", "height", "ύψος", min_value=90.0, max_value=230.0, optional=False)
        groups = {g["code"]: g["name"] for g in e01.load_data()["ancestry_groups"]}
        ancestry = st.selectbox("Καταγωγή", [None, *groups], format_func=lambda c: "Δεν δηλώνω" if c is None else groups[c],
                                key="ancestry")
        mixed = None
        if ancestry == "5":
            others = [c for c in groups if c != "5"]
            mixed = st.selectbox("Μικτή καταγωγή: ομάδα ενός γονέα (προαιρετικά)", [None, *others],
                                 format_func=lambda c: "Δεν διάλεξα" if c is None else groups[c], key="mixed")
        profiles = (al.allowed_profiles(birth, mdate) or ("Υγεία",)) if birth else e01.load_data()["profiles"]
        profile = st.selectbox("Προφίλ", profiles, key="profile")
        pregnant = breastfeeding = False
        if birth and e01.pregnancy_fields_visible(sex, e01.age_in_completed_years(birth, mdate)):
            pregnant = st.checkbox("Εγκυμοσύνη", key="pregnant")
            breastfeeding = st.checkbox("Θηλασμός", key="breastfeeding")

        # Ζυγαριά: όλα υποχρεωτικά· οι οδηγίες μία φορά, στην επικεφαλίδα
        field_label("Ζυγαριά", guide_html("λίπος % (ζυγαριά)"), strong=True)
        weight = measure_input("Βάρος (kg)", "weight", None, optional=False)
        fat = measure_input("Λίπος %", "fat", None, max_value=99.9, optional=False)
        muscle = measure_input("Μύες %", "m_muscle", None, max_value=99.9, optional=False)
        water = measure_input("Υγρά %", "m_water", None, max_value=99.9, optional=False)
        bone = measure_input("Οστά %", "m_bone", None, max_value=99.9, optional=False)

        pal, kcal_day, activity_missing = activity_inputs()
        field_label("Προπόνηση με βάρη ή μικτή", pop_html("Προπόνηση με βάρη ή μικτή", TRAINING_INFO))
        training = st.checkbox("Ναι", key="training")

    with tabs["Κορμός"]:
        neck = measure_input("Λαιμός (cm)", "m_neck", "λαιμός")
        chest = measure_input("Στήθος (cm)", "m_chest", "στήθος", extra=al.guide_extra("στήθος", sex))
        waist = measure_input("Μέση (cm)", "m_waist", "μέση")
        hip = measure_input("Ισχίο (cm)", "m_hip", "ισχίο")
        shoulders = measure_input("Ώμοι (cm)", "m_shoulders", "ώμοι")

    with tabs["Άκρα"]:
        arm_rel = measure_input("Μπράτσο χαλαρό (cm)", "m_arm_rel", "δικέφαλος χαλαρός")
        biceps = measure_input("Δικέφαλος σφιγμένος (cm)", "m_biceps", "δικέφαλος σφιγμένος")
        fore_rel = measure_input("Πήχης χαλαρός (cm)", "m_fore_rel", "πήχης")
        fore_flx = measure_input("Πήχης σφιγμένος (cm)", "m_fore_flx", "πήχης σφιγμένος",
                                 extra=(al.arm_field_note(),))
        wrist = measure_input("Καρπός (cm)", "m_wrist", "καρπός", extra=(al.field_note(27),))
        arm_injured = st.checkbox("Τραυματισμός ή πρήξιμο στο δεξί χέρι ή στον καρπό", key="m_arm_injured")
        thigh = measure_input("Άνω μηρός — ακριβώς κάτω από τη γλουτιαία πτυχή (cm)", "m_thigh", "άνω μηρός")
        thigh18 = measure_input("Μηρός — 1 cm κάτω από τη γλουτιαία πτυχή (cm)", "m_thigh18", "μηρός")
        knee = measure_input("Πάνω από το γόνατο (cm)", "m_knee", "γόνατο", extra=(al.field_note(29),))
        swollen = st.checkbox("Το γόνατο είναι πρησμένο ή τραυματισμένο", key="m_knee_swollen")
        calf = measure_input("Γάμπα (cm)", "m_calf", "γάμπα", extra=(al.field_note(26),))
        ankle = measure_input("Αστράγαλος (cm)", "m_ankle", "αστράγαλος",
                              extra=(al.ankle_field_note(), al.field_note(28)))
        edema = st.checkbox("Πρήξιμο (οίδημα) στα πόδια ή στον αστράγαλο", key="m_edema")
        injured = st.checkbox("Ο αστράγαλος είναι τραυματισμένος (π.χ. διάστρεμμα)", key="m_ankle_injured")
        leg_injured = st.checkbox("Τραυματισμός στο δεξί πόδι (μηρός ή γάμπα)", key="m_leg_injured")
        lipedema = (st.checkbox("Έχω διάγνωση λιποιδήματος από γιατρό", key="m_lipedema")
                    if sex == "Γυναίκα" else False)

    hydration = {}
    if pro:  # η ενυδάτωση (έλεγχος Βάρος–Ούρα–Δίψα) μόνο στο Professional
        with tabs["Ενυδάτωση"]:
            hydration = hydration_inputs()
    medical = professional_inputs(sex, birth, tabs["Όργανα"], tabs["Εξετάσεις"]) if pro else {}
    m = al.Measures(waist_cm=waist, upper_thigh_cm=thigh, scale_muscle_percent=muscle,
                    scale_water_percent=water, scale_bone_percent=bone, hip_cm=hip, neck_cm=neck, chest_cm=chest,
                    shoulders_cm=shoulders, arm_relaxed_cm=arm_rel, biceps_flexed_cm=biceps,
                    forearm_relaxed_cm=fore_rel, forearm_flexed_cm=fore_flx, wrist_cm=wrist, thigh_cm=thigh18,
                    knee_cm=knee, knee_swollen=swollen, calf_cm=calf, ankle_cm=ankle, leg_edema=edema,
                    ankle_injured=injured, arm_injured=arm_injured, leg_injured=leg_injured, lipedema=lipedema,
                    **hydration, **medical)

    missing = [n for n, v in (("ημερομηνία γέννησης", birth), ("ύψος", height), ("βάρος", weight), ("λίπος", fat),
                              ("μύες", muscle), ("υγρά", water), ("οστά", bone)) if v is None]
    if activity_missing:
        missing.append(activity_missing)
    if missing:
        return None, m, "Συμπλήρωσε: " + ", ".join(missing) + "."
    if kcal_day is not None:
        try:
            pal = al.pal_from_kcal(kcal_day, birth_date=birth, today=mdate, sex=sex, height_cm=height,
                                   weight_kg=weight)
        except al.KcalOutOfRange as e:
            return None, m, str(e)
    inp = al.PlanInput(birth_date=birth, sex=sex, height_cm=height, weight_kg=weight, fat_percent=fat, today=mdate,
                       ancestry=ancestry, mixed_chosen_group=mixed, profile=profile, resistance_training=training,
                       pregnant=pregnant, breastfeeding=breastfeeding, pal=float(pal), level=level,
                       kcal_day=kcal_day)
    return inp, m, None


def e46_levels() -> list[str]:
    from davinci import element_46 as e46
    return list(e46.levels())


def e31_options() -> list[str]:
    from davinci import element_31 as e31
    return list(e31.load_data()["measured_by"])


ISAK = {"Ναι": True, "Όχι": False, "Δεν ξέρω": None}


def skinfold(name: str, key: str, field: str, left_label: str, edema_label: str) -> al.Skinfold:
    """Μία δερματοπτυχή σε mm (Στοιχεία 33–36): 2 μετρήσεις και 3η όταν διαφέρουν πάνω από 5%."""
    st.markdown(f"**{name}**")
    vals = [measure_input(f"{name} — 1η μέτρηση (mm)", f"{key}1", field),
            measure_input(f"{name} — 2η μέτρηση (mm)", f"{key}2", None),
            measure_input(f"{name} — 3η μέτρηση, μόνο αν οι δύο διαφέρουν πάνω από 5% (mm)", f"{key}3", None)]
    mm = tuple(x for x in vals if x is not None)
    not_measured = False if mm else st.checkbox("Δεν μετρήθηκε (η πτυχή δεν πιάνεται ή ξεπερνά τη δαγκάνα)",
                                                key=f"{key}_nm")
    left = st.checkbox(left_label, key=f"{key}_left")
    edema = st.checkbox(edema_label, key=f"{key}_edema")
    lo, hi = SKINFOLD_RANGE
    confirmed = (st.checkbox("Επιβεβαιώνω ότι η τιμή είναι σε χιλιοστά (mm)", key=f"{key}_ok")
                 if any(x < lo or x > hi for x in mm) else False)
    return al.Skinfold(mm, not_measured, left, edema, confirmed)


def skinfold_inputs(sex: str) -> dict:
    st.markdown("**Δερματοπτυχές (mm)**")
    isak = st.radio("Ο εξεταστής ακολούθησε το πρωτόκολλο ISAK;", list(ISAK), index=2, horizontal=True, key="p_isak")
    caliper = st.selectbox("Δαγκάνα", al.calipers(), index=None, placeholder="Επίλεξε δαγκάνα", key="p_caliper")
    tri = skinfold("Τρικέφαλος", "p_tri", "δερματοπτυχή τρικεφάλου", "Μέτρηση στο αριστερό χέρι",
                   "Οίδημα ή λεμφοίδημα στο χέρι")
    post = (st.checkbox("Πρώτες εβδομάδες μετά τον τοκετό", key="p_postpartum") if sex == "Γυναίκα" else False)
    sub = skinfold("Υποπλάτιος", "p_sub", "δερματοπτυχή υποπλάτιου", "Μέτρηση στην αριστερή πλευρά", "Οίδημα")
    st.caption(al.skinfold_notes()["35"])
    site = st.radio("Μέτρησες την υπερακάνθια μπροστά, πάνω από τη λεκάνη;",
                    ["Ναι", "Δεν ξέρω", "Όχι, στο πλάι (λαγόνια ακρολοφία)"], index=1, horizontal=True,
                    key="p_sup_site")
    sup = skinfold("Υπερακάνθιος", "p_sup", "δερματοπτυχή υπερακάνθιου", "Μέτρηση στην αριστερή πλευρά", "Οίδημα")
    st.caption(al.skinfold_notes()["36"])
    calf = skinfold("Γάμπα (δερματοπτυχή)", "p_calf", "δερματοπτυχή γάμπας", "Μέτρηση στο αριστερό πόδι",
                    "Πρήξιμο ή κυτταρίτιδα στη γάμπα")
    at_max = st.checkbox("Η δερματοπτυχή μετρήθηκε στο ύψος της μέγιστης περιφέρειας γάμπας", value=True,
                         key="p_calf_atmax")
    varicose = st.checkbox("Κιρσοί στη δεξιά γάμπα (μέτρηση στην αριστερή)", key="p_calf_varicose")
    cmax = st.checkbox("Μία από τις πτυχές τρικεφάλου, υποπλάτιου ή υπερακάνθιου έφτασε το μέγιστο άνοιγμα της "
                       "δαγκάνας", key="p_caliper_max")
    return dict(sf_isak=ISAK[isak], sf_caliper=caliper, triceps=tri, postpartum_recent=post, subscapular=sub,
                supraspinale=sup, supraspinale_site_confirmed=True if site == "Ναι" else None, calf_skinfold=calf,
                calf_skinfold_at_max_girth=at_max, calf_varicose=varicose, supraspinale_is_iliac=site.startswith("Όχι"),
                sf_caliper_max=cmax)


def professional_inputs(sex: str, birth, tab_tools, tab_medical) -> dict:
    """Περιοχές 6 και 7: μόνο στο επίπεδο Professional (Στοιχείο 46)."""
    with tab_tools:
        elbow = measure_input("Εύρος αγκώνα (cm)", "p_elbow", "εύρος αγκώνα")
        elbow_left = st.checkbox("Μέτρηση στο αριστερό χέρι (το δεξί δεν μπορεί να μετρηθεί)", key="p_elbow_left")
        elbow_cond = st.checkbox("Κάταγμα, φλεγμονή ή οίδημα στον αγκώνα", key="p_elbow_cond")
        knee = [measure_input("Εύρος γονάτου — 1η μέτρηση (cm)", "p_knee1", "εύρος γονάτου"),
                measure_input("Εύρος γονάτου — 2η μέτρηση (cm)", "p_knee2", None),
                measure_input("Εύρος γονάτου — 3η μέτρηση, μόνο αν οι δύο διαφέρουν πάνω από 0,2 cm (cm)",
                              "p_knee3", None)]
        by = e31_options()
        measured_by = st.radio("Ποιος μέτρησε το γόνατο", by, index=by.index("Άλλο άτομο"), horizontal=True,
                               key="p_knee_by")
        side = st.radio("Πόδι", ["δεξί", "αριστερό"], horizontal=True, key="p_knee_side")
        knee_edema = st.checkbox("Πρήξιμο ή μώλωπας στο γόνατο", key="p_knee_edema")
        knee_inj = st.checkbox("Τραυματισμός, πρόθεση ή αρθρίτιδα στο δεξί γόνατο", key="p_knee_inj")
        sf = skinfold_inputs(sex)
    with tab_medical:
        st.caption(al.medical_message())
        visceral = measure_input("Σπλαχνικό λίπος — ζυγαριά", "m_visceral", "επίπεδο σπλαχνικού λίπους (ζυγαριά)",
                                 min_value=0.0, extra=VISCERAL_SCALE_INFO)
        ct = measure_input("Σπλαχνικό λίπος — αξονική ή μαγνητική τομογραφία (cm²)", "x_ct", None)
        vol = measure_input("Σπλαχνικό λίπος — DXA ή μαγνητική: όγκος ή μάζα (μονάδα της γνωμάτευσης)", "x_vol", None)
        mus = measure_input("Σκελετικοί μύες — ιατρική μέτρηση (kg)", "x_muscle", None)
        wat = measure_input("Υγρά — αραίωση ισοτόπων (kg)", "x_water", None)
        osm = measure_input("Ωσμωτικότητα ορού, μετρημένη (mOsm/kg)", "x_osm", None)
        st.caption("Αν δεν υπάρχει μετρημένη ωσμωτικότητα: Na, K, γλυκόζη και ουρία (mmol/L), για υπολογισμό.")
        calc = [measure_input(n + " (mmol/L)", "x_" + k, None) for n, k in
                (("Νάτριο (Na)", "na"), ("Κάλιο (K)", "k"), ("Γλυκόζη", "glu"), ("Ουρία", "urea"))]
        bone = measure_input("Οστικά μέταλλα — DXA (kg)", "x_bone", None)
        t = measure_input("T-score (DXA)", "x_t", None, min_value=None)
        z = measure_input("Z-score (DXA)", "x_z", None, min_value=None)
        meno = None
        if sex == "Γυναίκα":
            meno = st.selectbox("Έχεις περάσει την εμμηνόπαυση;", ["Ναι", "Όχι"], index=None, placeholder=OPTIONAL,
                                key="x_meno")
    return dict(elbow_cm=elbow, elbow_left_arm=elbow_left, elbow_condition=elbow_cond,
                knee_breadths=tuple(x for x in knee if x is not None), knee_measured_by=measured_by, knee_side=side,
                knee_breadth_edema=knee_edema, knee_breadth_injured=knee_inj, **sf, scale_visceral_level=visceral,
                ct_visceral_cm2=ct, visceral_volume=vol, medical_muscle_kg=mus, isotope_water_kg=wat,
                serum_osmolality=osm, osmolality_inputs=tuple(calc) if all(x is not None for x in calc) else None,
                dxa_bone_kg=bone, t_score=t, z_score=z, menopause=None if meno is None else meno == "Ναι")


# ------------------------------------------------------------------ πλάνο
def show_start(prep: al.Prep, inp: al.PlanInput) -> None:
    st.subheader("Αφετηρία")
    if prep.bmi and prep.bmi.category:
        st.markdown(f"**ΔΜΣ:** {num(prep.bmi.value, 1)} — {prep.bmi.category}")
    if prep.fat and (prep.fat.health_label or prep.fat.health_category):
        st.markdown(f"**Λίπος:** {num(inp.fat_percent, 1)}% — {prep.fat.health_label or prep.fat.health_category}")
    if prep.fat and prep.fat.profile_range:
        lo, hi = prep.fat.profile_range
        st.markdown(f"**Εύρος λίπους του προφίλ:** {num(lo, 1)}–{num(hi, 1)}%")


def choose(prep: al.Prep, inp: al.PlanInput) -> al.PlanInput | None:
    ch = prep.choice
    if ch is None:
        return inp
    st.subheader("Ρυθμός απώλειας")
    if ch.kind == "aha":
        st.write("ΔΜΣ 25 και πάνω: το έλλειμμα ορίζεται σε kcal (" + ch.source + "). Διάλεξε ένα.")
        pick = st.selectbox("Ημερήσιο έλλειμμα", list(ch.options), index=None, placeholder="Διάλεξε",
                            format_func=lambda x: "30% της ημερήσιας δαπάνης" if x == "30%" else f"{x} kcal την ημέρα",
                            key="aha")
        return None if pick is None else replace(inp, aha_deficit=pick)
    lo, hi = ch.options
    steps, x = [], lo
    while x <= hi + 1e-9:
        steps.append(round(x, 2))
        x += 0.1
    st.write(f"Εύρος: {num(lo, 1)}–{num(hi, 1)}% του βάρους την εβδομάδα ({ch.source}). Διάλεξε ένα.")
    pick = st.selectbox("Εβδομαδιαίος ρυθμός", steps, index=None, placeholder="Διάλεξε", key="rate",
                        format_func=lambda r: f"{num(r, 1)}% την εβδομάδα (≈ {num(inp.weight_kg * r / 100, 2)} kg)")
    return None if pick is None else replace(inp, rate_percent=pick)


def show_presentation(pres: e44.Presentation) -> None:
    for m in pres.before:
        st.warning(m)
    if pres.indicative:
        st.warning("Ενδεικτική")
    for part in pres.parts:
        st.subheader(part.name)
        for m in part.messages:
            st.write(m)
        for label, value in part.lines:
            st.markdown(f"**{label}:** {value}")
        if part.name == e44.load_data()["parts"][3]:
            show_timeline(pres)
    if pres.info:
        st.caption(pres.info)


def show_timeline(pres: e44.Presentation) -> None:
    if pres.chart:
        st.line_chart({"πρόβλεψη (kg)": [p.predicted_kg for p in pres.chart],
                       "γρήγορος ρυθμός (kg)": [p.band_low_kg for p in pres.chart],
                       "αργός ρυθμός (kg)": [p.band_high_kg for p in pres.chart]})
        st.caption("Οριζόντιος άξονας: εβδομάδες από σήμερα. Το εύρος ανάμεσα στον αργό και τον γρήγορο ρυθμό.")
    if pres.rows:
        st.dataframe([{"εβδομάδα": r.week, "ημερομηνία": e44.day_text(r.day), **r.cells} for r in pres.rows],
                     hide_index=True)


def tab_plan(inp: al.PlanInput) -> None:
    prep = al.prepare(inp)
    if prep.errors:
        for e in prep.errors:
            st.error(e)
        return
    show_start(prep, inp)
    full = choose(prep, inp)
    if full is None:
        st.info("Διάλεξε ρυθμό για να δεις το πλάνο.")
        return
    res = al.plan(full)
    for e in res.errors:
        st.error(e)
    for n in res.notes:
        st.info(n)
    for m in res.messages:
        st.write(m)
    if res.presentation is not None:
        show_presentation(res.presentation)


# ------------------------------------------------------------------ μετρήσεις (Στοιχεία 05–39, σε δόσεις)
OPTIONAL = "Προαιρετικό"
SKINFOLD_RANGE = (2, 50)  # Στοιχεία 33–36: τιμή κάτω από 2 ή πάνω από 50 mm ζητά επιβεβαίωση


def measure_input(label: str, key: str, field: str | None, *, min_value: float | None = 0.1,
                  max_value: float | None = None, extra: tuple[str, ...] = (), optional: bool = True):
    """Ετικέτα με το «ⓘ info» (οδηγίες μέτρησης) στην ίδια γραμμή και από κάτω το πεδίο.
    Τα προαιρετικά πεδία δείχνουν αχνό «Προαιρετικό» μέσα στο κουτί, που χάνεται όταν γράψεις τιμή."""
    field_label(label, guide_html(field, tuple(x for x in extra if x)))
    return st.number_input(label, min_value=min_value, max_value=max_value, value=None, step=0.1, format="%.1f",
                           key=key, placeholder=OPTIONAL if optional else None, label_visibility="collapsed")


BR = "  \n"  # αλλαγή γραμμής μέσα στην ίδια παράγραφο (markdown)


def _pair(label: str, value: str, cls: str = "dv-v") -> str:
    return f'<b>{escape(label)}</b>: <span class="{cls}">{escape(value)}</span>'


def row_html(r: rv.Row, popup: str = "") -> str:
    """Μία γραμμή: όνομα και μέτρηση (κανονικό χρώμα), αλλαγή προς τον στόχο (κόκκινο ▼ / πράσινο ▲),
    δευτερεύουσες γραμμές, και από κάτω (Στόχος: …) με μικρά γκρι γράμματα."""
    if r.value is not None:
        head = _pair(r.name, r.value)
    elif r.missing:
        head = _pair(r.name, r.missing, "dv-v dv-missing")
    else:
        head = f"<b>{escape(r.name)}</b>"
    if r.note:
        head += f' <span class="dv-note">· {escape(r.note)}</span>'
    if r.change:
        head += "".join(f' <span class="dv-{d}">{escape(t)}</span>' for d, t in r.change.parts)
    out = [head + popup] + [f'<div class="dv-sub">{_pair(a, b)}</div>' for a, b in r.subs]
    if r.target_word:
        out.append(f'<div class="dv-target">({escape(r.target_word)}: {escape(r.target)})</div>')
    return f'<div class="dv-row dv-l{r.level}">' + "".join(out) + "</div>"


def info_html(card) -> str:
    """Το «ⓘ info» ενός στοιχείου των «Αποτελεσμάτων», δίπλα στο όνομά του: παράθυρο που κυλά και κλείνει.
    Μέσα: τίτλος το όνομα του στοιχείου και οι ενότητες (Στόχος · Λεπτομέρειες · Ενδεικτική · Προειδοποιήσεις ·
    Σχόλια). «» όταν δεν υπάρχει τίποτα να γραφτεί."""
    if not card.info:
        return ""
    h = f'<div class="dv-info-title">{escape(card.title)}</div>'
    for title, lines in card.info:
        h += f'<div class="dv-info-h">{escape(title)}</div>'
        h += "".join(f"<p>{(f'<b>{escape(a)}:</b> ' if a else '')}{escape(b)}</p>" for a, b in lines)
    return f'<details class="dv-info"><summary>ⓘ info</summary><div class="dv-info-body">{h}</div></details>'


def card_html(card, small: bool = False) -> str:
    """Οι γραμμές μιας κάρτας· το «ⓘ info» στην πρώτη γραμμή, δίπλα στο στοιχείο."""
    rows = "".join(row_html(r, info_html(card) if i == 0 else "") for i, r in enumerate(card.rows))
    return f'<div class="dv-small">{rows}</div>' if small else rows


def show_card(card: rv.Card, small: bool = False) -> None:
    """Οι γραμμές της κάρτας και ό,τι λείπει ορατά· όλα τα κείμενα (σχόλια, «Ενδεικτική», προειδοποιήσεις) στο ⓘ.
    small: μέσα σε ανάλυση που ανοίγει / κλείνει — μικρότερα γράμματα."""
    st.markdown(card_html(card, small), unsafe_allow_html=True)
    if card.table and card.show_table:  # ο πίνακας της ανάλυσης άλιπης μάζας φαίνεται ως γραμμές
        head, *body = card.table
        st.dataframe([dict(zip(head, r)) for r in body], hide_index=True)
    for n in card.needs:
        st.info(n)


def show_part(part: rv.Part) -> None:
    if part.todo:
        st.info(part.todo)
    if part.lines:
        st.markdown(BR.join(f"**{label}:** {v}" for label, v in part.lines))
    for card in part.cards:
        show_card(card, small=part.fold)


def show_group(group: rv.Group) -> None:
    """Κάθε μέρος σε δικό του πλαίσιο με επικεφαλίδα· τα μέρη που ανοίγουν / κλείνουν (αναλύσεις της άλιπης
    μάζας) μπαίνουν στο τέλος του προηγούμενου πλαισίου, δηλαδή κάτω από την Άλιπη μάζα."""
    parts, i = group.parts, 0
    while i < len(parts):
        j = i + 1
        while j < len(parts) and parts[j].fold:
            j += 1
        with st.container(border=True):
            st.subheader(parts[i].heading)
            show_part(parts[i])
            for fold in parts[i + 1:j]:
                with st.expander(fold.heading):
                    show_part(fold)
        i = j
    if not (group.cards or group.lines):
        st.info("Δεν υπάρχουν αποτελέσματα εδώ: συμπλήρωσε τις μετρήσεις αυτής της κατηγορίας στη «Μέτρηση».")


def hydration_inputs() -> dict:
    """Στοιχείο 08, Πίνακας 7: καταγραφή κάθε πρωί, μετά την ούρηση, πριν από φαγητό και ποτό."""
    st.caption("Καταγραφή κάθε πρωί, μετά την ούρηση, πριν από φαγητό και ποτό.")
    prev = [measure_input(f"Πρωινό βάρος πριν από {d} {'ημέρα' if d == 1 else 'ημέρες'} (kg)", f"m_prev{d}", None)
            for d in (3, 2, 1)]
    today = measure_input("Πρωινό βάρος σήμερα (kg)", "m_today", None)
    urine = st.selectbox("Χρώμα πρώτων πρωινών ούρων (κλίμακα 1–8)", list(range(1, 9)), index=None,
                         placeholder=OPTIONAL, key="m_urine")
    thirst = measure_input("Δίψα (βαθμός στην κλίμακα)", "m_thirst", None, min_value=0.0)
    return dict(previous_morning_weights=tuple(x for x in prev if x is not None), today_morning_weight=today,
                urine_color=urine, thirst=thirst)


def tab_results(inp: al.PlanInput, m: al.Measures) -> tuple:
    st.caption("Αποτελέσματα από όσα συμπλήρωσες στην καρτέλα «Μέτρηση»· τα κενά πεδία παραλείπονται.")
    st.caption("▼ κόκκινο = πρέπει να πέσει · ▲ πράσινο = πρέπει να ανέβει · ⓘ info = στόχος, σχόλια και λεπτομέρειες")
    groups, errors = rv.results(inp, m)
    for e in errors:
        st.error(e)
    if not groups:
        return ()
    # Κάθε κατηγορία σε δικό της κουμπί (απόφαση του χρήστη 11/11/2026)· η σειρά είναι πάντα η ίδια.
    for tab, group in zip(st.tabs([g.title for g in groups]), groups):
        with tab:
            show_group(group)
    return groups


# ------------------------------------------------------------------ ιστορικό (απόφαση του χρήστη 11/11/2026)
def history() -> list[dict]:
    """Οι μετρήσεις. Με λογαριασμό διαβάζονται από τη βάση μία φορά ανά συνεδρία."""
    s = session()
    if CLOUD is not None and s is not None and not st.session_state.get("_cloud_loaded"):
        got = cloud_call(lambda: CLOUD.list(s))
        if got is not None:
            rows, s = got
            st.session_state.update(history=hist.ordered(rows), _cloud_loaded=True)
            keep(s)
    return st.session_state.setdefault("history", [])


def store(entry: dict) -> bool:
    """Με λογαριασμό: αποθήκευση και στη βάση. False αν η βάση δεν δέχτηκε την εγγραφή."""
    s = session()
    if CLOUD is None or s is None:
        return True
    s = cloud_call(lambda: CLOUD.save(s, entry))
    if s is None:
        return False
    keep(s)
    return True


def unstore(day: str) -> bool:
    s = session()
    if CLOUD is None or s is None:
        return True
    s = cloud_call(lambda: CLOUD.delete(s, day))
    if s is None:
        return False
    keep(s)
    return True


def save_box(inp: al.PlanInput, m: al.Measures, groups, key: str) -> None:
    """Κουμπί αποθήκευσης της τρέχουσας μέτρησης (στο τέλος των «Αποτελεσμάτων» και στην αρχή του «Ιστορικού»)."""
    if st.button(f"Αποθήκευση μέτρησης {hist.day_text(inp.today.isoformat())}", key=key, type="primary"):
        entry = hist.snapshot(inp, m, groups)
        if not store(entry):
            return
        new, replaced = hist.add(history(), entry)
        st.session_state["history"] = new
        st.success("Η μέτρηση αντικατέστησε την προηγούμενη της ίδιας ημερομηνίας." if replaced
                   else "Η μέτρηση αποθηκεύτηκε στο «Ιστορικό».")


def show_entry(entry: dict) -> None:
    """Το αποτέλεσμα όπως αποθηκεύτηκε: όλες οι ενότητες κάθετα, με το «ⓘ info» κάθε στοιχείου."""
    for g in entry["results"]:
        st.markdown(f"#### {escape(g['title'])}")
        for p in g["parts"]:
            if len(g["parts"]) > 1 or p["heading"] != g["title"]:
                st.markdown(f"**{escape(p['heading'])}**")
            if p["lines"]:
                st.markdown(BR.join(f"**{a}:** {b}" for a, b in p["lines"]))
            for c in p["cards"]:
                st.markdown(card_html(hist.card_from(c), p["fold"]), unsafe_allow_html=True)


def tab_history(inp: al.PlanInput | None, m: al.Measures, groups) -> None:
    st.caption("Κάθε μέτρηση κρατά τα αποτελέσματα όπως βγήκαν εκείνη την ημέρα. Μία μέτρηση ανά ημερομηνία.")
    if inp is not None and groups:
        save_box(inp, m, groups, "save_hist")
    entries = hist.ordered(history())
    if not entries:
        st.info("Δεν υπάρχουν αποθηκευμένες μετρήσεις. Συμπλήρωσε τη «Μέτρηση» και πάτα «Αποθήκευση μέτρησης».")
    for i, entry in enumerate(entries, start=1):
        with st.container(border=True):
            left, right = st.columns([8, 1], vertical_alignment="center")
            left.markdown(f"**{escape(hist.label(i, entry))}**")
            with right.popover("⋯"):
                st.download_button("Εξαγωγή σε docx", hist.to_docx(entry, i), file_name=hist.docx_name(entry),
                                   mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                   key=f"docx_{entry['date']}")
                if st.button("Διαγραφή", key=f"del_{entry['date']}") and unstore(entry["date"]):
                    st.session_state["history"] = hist.remove(history(), entry["date"])
                    st.rerun()
            with st.expander("Αποτελέσματα"):
                show_entry(entry)
    st.divider()
    st.markdown("**Αντίγραφο**")
    if session() is not None:
        st.caption("Οι μετρήσεις σου αποθηκεύονται στον λογαριασμό σου. Το αντίγραφο είναι προαιρετικό.")
    else:
        st.caption("Χωρίς λογαριασμό οι μετρήσεις κρατιούνται μόνο όσο είναι ανοιχτή η σελίδα. "
                   "Κατέβασε αντίγραφο μετά από κάθε αποθήκευση και φόρτωσέ το την επόμενη φορά.")
    if entries:
        st.download_button("Λήψη αντιγράφου", hist.to_json(entries), file_name="DaVinci_Istoriko.json",
                           mime="application/json", key="backup_down")
    up = st.file_uploader("Φόρτωση αντιγράφου (.json)", type=["json"], key="backup_up")
    if up is not None and st.session_state.get("_loaded") != up.name:
        try:
            loaded = hist.from_json(up.getvalue())
            if all(store(e) for e in loaded):  # με λογαριασμό: και στη βάση
                st.session_state["history"] = hist.merge(history(), loaded)
                st.session_state["_loaded"] = up.name
                st.rerun()
        except hist.BadBackup as e:
            st.error(str(e))


# ------------------------------------------------------------------ σελίδα
# Σειρά καρτελών (απόφαση του χρήστη, 11/11/2026): Μέτρηση → Αποτελέσματα → Πλάνο.
# Οι οδηγίες μέτρησης βρίσκονται μόνο στο ⓘ κάθε πεδίου· η κάρτα μέτρησης (Στοιχείο 45) δεν εμφανίζεται.
tab_in, tab_res, tab_pl, tab_hist = st.tabs(["Μέτρηση", "Αποτελέσματα", "Πλάνο", "Ιστορικό"])
with tab_in:
    inputs, measures, todo = read_inputs()
    if todo:
        st.info(todo)
groups = ()
with tab_res:
    if inputs is not None:
        groups = tab_results(inputs, measures)
        if groups:
            save_box(inputs, measures, groups, "save_res")
    else:
        st.info(todo)
with tab_pl:
    if inputs is not None:
        tab_plan(inputs)
    else:
        st.info(todo)
with tab_hist:
    tab_history(inputs, measures, groups)
