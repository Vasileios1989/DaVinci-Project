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
/* ⓘ info των «Αποτελεσμάτων»: ανοίγει / κλείνει· γράμματα με πατούρες, κανονικό μέγεθος, γκριζωπά, πυκνές γραμμές */
details.dv-info {background: #262B42; border: 1px solid rgba(255,255,255,.10); border-radius: 14px;
  margin: .1rem 0 .9rem 0; padding: 0;}
details.dv-info > summary {cursor: pointer; padding: .45rem .9rem; font-size: .92rem; font-weight: 600;
  color: rgba(242,243,247,.85); list-style: none;}
details.dv-info > summary::-webkit-details-marker {display: none;}
details.dv-info > summary::before {content: "▸"; display: inline-block; width: 1.1rem; opacity: .7;}
details.dv-info[open] > summary::before {content: "▾";}
details.dv-info[open] > summary {border-bottom: 1px solid rgba(255,255,255,.10);}
.dv-info-body {padding: .55rem .95rem .7rem .95rem; font-family: Georgia, "Noto Serif", "Times New Roman", serif;
  font-size: .95rem; line-height: 1.4; color: #C5C8D3;}
.dv-info-body p {margin: 0 0 .3rem 0; font-size: .95rem; line-height: 1.4;}
.dv-info-title {font-size: 1.02rem; font-weight: 700; color: #E6E8EF; margin: 0 0 .3rem 0;}
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


def sign_in_done(s: cloud.Session) -> None:
    st.session_state.update(session=s, mode="account", history=[], _cloud_loaded=False)
    st.rerun()


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
        if st.button("Σύνδεση", key="li_go", type="primary"):
            s = cloud_call(lambda: CLOUD.sign_in(email or "", pw or ""))
            if s:
                sign_in_done(s)
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


if CLOUD is not None and not st.session_state.get("mode"):
    entry_screen()

st.title("DaVinci Fitness")
if CLOUD is not None:
    if session() is not None:
        st.caption(f"Συνδεδεμένος: {session().email}")
        if st.button("Αποσύνδεση", key="logout"):
            CLOUD.sign_out(session())
            for k in ("session", "mode", "history", "_cloud_loaded"):
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
AREAS = (("Προσωπικά", "1. Προσωπικά στοιχεία"), ("Ζυγαριά", "2. Σύσταση σώματος (ζυγαριά)"),
         ("Κορμός", "3. Περιφέρειες κορμού (μεζούρα)"), ("Άκρα", "4. Περιφέρειες άκρων (μεζούρα)"),
         ("Ενυδάτωση", "5. Ενυδάτωση: έλεγχος Βάρος–Ούρα–Δίψα (18–59 ετών)"))
PRO_AREAS = (("Όργανα", "6. Όργανα Professional (δερματοπτυχόμετρο, παχύμετρο οστών)"),
             ("Εξετάσεις", "7. Ιατρικές εξετάσεις (προαιρετικά)"))


def read_inputs() -> tuple[al.PlanInput | None, al.Measures, str | None]:
    """Όλα τα πεδία, σε περιοχές που διαλέγεις από πάνω. Επιστρέφει και το μήνυμα «Συμπλήρωσε: …» (ή None)."""
    # Το επίπεδο διαλέγεται μέσα στην πρώτη περιοχή· οι περιοχές 6–7 υπάρχουν μόνο στο Professional (Στοιχείο 46).
    pro = st.session_state.get("level") == "Professional"
    areas = AREAS + (PRO_AREAS if pro else ())
    tabs = dict(zip((a[0] for a in areas), st.tabs([a[0] for a in areas])))

    with tabs["Προσωπικά"]:
        st.caption(AREAS[0][1])
        mdate = st.date_input("Ημερομηνία μέτρησης", value=TODAY, min_value=date(1900, 1, 1), max_value=TODAY,
                              format="DD/MM/YYYY", key="mdate") or TODAY
        birth = st.date_input("Ημερομηνία γέννησης", value=None, min_value=date(1900, 1, 1), max_value=TODAY,
                              format="DD/MM/YYYY", key="birth")
        sex = st.radio("Φύλο", e01.load_data()["sexes"], horizontal=True, key="sex")
        level = st.radio("Επίπεδο μέτρησης", e46_levels(), horizontal=True, key="level")
        for x in al.level_info(level):
            st.caption(x)
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
        training = st.checkbox("Προπόνηση με βάρη ή μικτή", key="training")
        pregnant = breastfeeding = False
        if birth and e01.pregnancy_fields_visible(sex, e01.age_in_completed_years(birth, mdate)):
            pregnant = st.checkbox("Εγκυμοσύνη", key="pregnant")
            breastfeeding = st.checkbox("Θηλασμός", key="breastfeeding")
        pals = al.pal_options()
        pal = st.selectbox("Επίπεδο δραστηριότητας (PAL)", list(pals), index=None, placeholder="Διάλεξε",
                           format_func=lambda k: f"{k.replace('.', ',')} — {pals[k]}", key="pal")

    with tabs["Ζυγαριά"]:
        st.caption(AREAS[1][1])
        weight = measure_input("Βάρος (kg)", "weight", "βάρος", optional=False)
        fat = measure_input("Λίπος %", "fat", "λίπος % (ζυγαριά)", max_value=99.9, optional=False)
        muscle = measure_input("Μύες %", "m_muscle", "μύες % (ζυγαριά)", max_value=99.9)
        water = measure_input("Υγρά %", "m_water", "υγρά % (ζυγαριά)", max_value=99.9)
        bone = measure_input("Οστά %", "m_bone", "οστά % (ζυγαριά)", max_value=99.9)
        visceral = measure_input("Σπλαχνικό λίπος — μόνο αν το δείχνει η ζυγαριά σου (χωρίς μονάδα)", "m_visceral",
                                 "επίπεδο σπλαχνικού λίπους (ζυγαριά)", min_value=0.0)
        amputation = st.checkbox("Ακρωτηριασμός (αλλάζει το βάρος)", key="m_amputation")

    with tabs["Κορμός"]:
        st.caption(AREAS[2][1])
        neck = measure_input("Λαιμός (cm)", "m_neck", "λαιμός")
        chest = measure_input("Στήθος (cm)", "m_chest", "στήθος", extra=al.guide_extra("στήθος", sex))
        waist = measure_input("Μέση (cm)", "m_waist", "μέση")
        hip = measure_input("Ισχίο (cm)", "m_hip", "ισχίο")
        shoulders = measure_input("Ώμοι (cm)", "m_shoulders", "ώμοι")

    with tabs["Άκρα"]:
        st.caption(AREAS[3][1])
        arm_rel = measure_input("Μπράτσο χαλαρό (cm)", "m_arm_rel", "δικέφαλος χαλαρός")
        biceps = measure_input("Δικέφαλος σφιγμένος (cm)", "m_biceps", "δικέφαλος σφιγμένος")
        fore_rel = measure_input("Πήχης χαλαρός (cm)", "m_fore_rel", "πήχης")
        fore_flx = measure_input("Πήχης σφιγμένος (cm)", "m_fore_flx", "πήχης σφιγμένος")
        st.caption(al.arm_field_note())
        wrist = measure_input("Καρπός (cm)", "m_wrist", "καρπός")
        st.caption(al.field_note(27))
        arm_injured = st.checkbox("Τραυματισμός ή πρήξιμο στο δεξί χέρι ή στον καρπό", key="m_arm_injured")
        thigh = measure_input("Άνω μηρός — ακριβώς κάτω από τη γλουτιαία πτυχή (cm)", "m_thigh", "άνω μηρός")
        thigh18 = measure_input("Μηρός — 1 cm κάτω από τη γλουτιαία πτυχή (cm)", "m_thigh18", "μηρός")
        knee = measure_input("Πάνω από το γόνατο (cm)", "m_knee", "γόνατο")
        st.caption(al.field_note(29))
        swollen = st.checkbox("Το γόνατο είναι πρησμένο ή τραυματισμένο", key="m_knee_swollen")
        calf = measure_input("Γάμπα (cm)", "m_calf", "γάμπα")
        st.caption(al.field_note(26))
        ankle = measure_input("Αστράγαλος (cm)", "m_ankle", "αστράγαλος")
        st.caption(al.ankle_field_note())
        st.caption(al.field_note(28))
        edema = st.checkbox("Πρήξιμο (οίδημα) στα πόδια ή στον αστράγαλο", key="m_edema")
        injured = st.checkbox("Ο αστράγαλος είναι τραυματισμένος (π.χ. διάστρεμμα)", key="m_ankle_injured")
        leg_injured = st.checkbox("Τραυματισμός στο δεξί πόδι (μηρός ή γάμπα)", key="m_leg_injured")
        lipedema = (st.checkbox("Έχω διάγνωση λιποιδήματος από γιατρό", key="m_lipedema")
                    if sex == "Γυναίκα" else False)

    with tabs["Ενυδάτωση"]:
        st.caption(AREAS[4][1])
        hydration = hydration_inputs()
    medical = professional_inputs(sex, birth, tabs["Όργανα"], tabs["Εξετάσεις"]) if pro else {}
    m = al.Measures(waist_cm=waist, upper_thigh_cm=thigh, scale_visceral_level=visceral, scale_muscle_percent=muscle,
                    scale_water_percent=water, scale_bone_percent=bone, hip_cm=hip, neck_cm=neck, chest_cm=chest,
                    shoulders_cm=shoulders, arm_relaxed_cm=arm_rel, biceps_flexed_cm=biceps,
                    forearm_relaxed_cm=fore_rel, forearm_flexed_cm=fore_flx, wrist_cm=wrist, thigh_cm=thigh18,
                    knee_cm=knee, knee_swollen=swollen, calf_cm=calf, ankle_cm=ankle, leg_edema=edema,
                    ankle_injured=injured, arm_injured=arm_injured, leg_injured=leg_injured, lipedema=lipedema, amputation=amputation,
                    **hydration, **medical)

    missing = [n for n, v in (("ημερομηνία γέννησης", birth), ("ύψος", height), ("βάρος", weight), ("λίπος", fat),
                              ("επίπεδο δραστηριότητας", pal)) if v is None]
    if missing:
        return None, m, "Συμπλήρωσε: " + ", ".join(missing) + "."
    inp = al.PlanInput(birth_date=birth, sex=sex, height_cm=height, weight_kg=weight, fat_percent=fat, today=mdate,
                       ancestry=ancestry, mixed_chosen_group=mixed, profile=profile, resistance_training=training,
                       pregnant=pregnant, breastfeeding=breastfeeding, pal=float(pal), level=level)
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
        st.caption(PRO_AREAS[0][1])
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
        st.caption(PRO_AREAS[1][1])
        st.caption(al.medical_message())
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
                knee_breadth_edema=knee_edema, knee_breadth_injured=knee_inj, **sf, ct_visceral_cm2=ct, visceral_volume=vol, medical_muscle_kg=mus, isotope_water_kg=wat,
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
def guide_box(field: str | None, extra: tuple[str, ...] = ()) -> None:
    if field is None:
        return
    g = measurement.guide(field)
    if g is None:
        return
    with st.expander(f"ⓘ {g.title}"):
        for i, step in enumerate(g.steps, start=1):
            st.markdown(f"{i}. {step}")
        for x in extra:
            st.info(x)
        if g.protocol:
            st.caption(g.protocol)


OPTIONAL = "Προαιρετικό"
SKINFOLD_RANGE = (2, 50)  # Στοιχεία 33–36: τιμή κάτω από 2 ή πάνω από 50 mm ζητά επιβεβαίωση


def measure_input(label: str, key: str, field: str | None, *, min_value: float | None = 0.1,
                  max_value: float | None = None, extra: tuple[str, ...] = (), optional: bool = True):
    """Τα προαιρετικά πεδία δείχνουν αχνό «Προαιρετικό» μέσα στο κουτί, που χάνεται όταν γράψεις τιμή."""
    v = st.number_input(label, min_value=min_value, max_value=max_value, value=None, step=0.1, format="%.1f", key=key,
                        placeholder=OPTIONAL if optional else None)
    guide_box(field, extra)
    return v


BR = "  \n"  # αλλαγή γραμμής μέσα στην ίδια παράγραφο (markdown)


def _pair(label: str, value: str, cls: str = "dv-v") -> str:
    return f'<b>{escape(label)}</b>: <span class="{cls}">{escape(value)}</span>'


def row_html(r: rv.Row) -> str:
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
    out = [head] + [f'<div class="dv-sub">{_pair(a, b)}</div>' for a, b in r.subs]
    if r.target_word:
        out.append(f'<div class="dv-target">({escape(r.target_word)}: {escape(r.target)})</div>')
    return f'<div class="dv-row dv-l{r.level}">' + "".join(out) + "</div>"


def info_html(cards) -> str:
    """Το «ⓘ info»: ανοίγει και κλείνει. Μέσα, ανά κάρτα: τίτλος το όνομα του στοιχείου και από κάτω οι ενότητες
    (Στόχος · Λεπτομέρειες · Ενδεικτική · Προειδοποιήσεις · Σχόλια). «» όταν δεν υπάρχει τίποτα να γραφτεί."""
    blocks = []
    for card in cards:
        if not card.info:
            continue
        h = f'<div class="dv-info-title">{escape(card.title)}</div>'
        for title, lines in card.info:
            h += f'<div class="dv-info-h">{escape(title)}</div>'
            h += "".join(f"<p>{(f'<b>{escape(a)}:</b> ' if a else '')}{escape(b)}</p>" for a, b in lines)
        blocks.append(h)
    if not blocks:
        return ""
    return ('<details class="dv-info"><summary>ⓘ info</summary><div class="dv-info-body">' + "".join(blocks)
            + "</div></details>")


def show_card(card: rv.Card, small: bool = False) -> None:
    """Οι γραμμές της κάρτας και ό,τι λείπει ορατά· όλα τα κείμενα (σχόλια, «Ενδεικτική», προειδοποιήσεις) στο ⓘ.
    small: μέσα σε ανάλυση που ανοίγει / κλείνει — μικρότερα γράμματα, και το ⓘ ένα, στο τέλος της ανάλυσης."""
    rows = "".join(row_html(r) for r in card.rows)
    st.markdown(f'<div class="dv-small">{rows}</div>' if small else rows, unsafe_allow_html=True)
    if card.table and card.show_table:  # ο πίνακας της ανάλυσης άλιπης μάζας φαίνεται ως γραμμές
        head, *body = card.table
        st.dataframe([dict(zip(head, r)) for r in body], hide_index=True)
    for n in card.needs:
        st.info(n)
    if not small and card.info:
        st.markdown(info_html([card]), unsafe_allow_html=True)


def show_part(part: rv.Part) -> None:
    if part.todo:
        st.info(part.todo)
    if part.lines:
        st.markdown(BR.join(f"**{label}:** {v}" for label, v in part.lines))
    for card in part.cards:
        show_card(card, small=part.fold)
    if part.fold:
        info = info_html(part.cards)
        if info:
            st.markdown(info, unsafe_allow_html=True)


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
            st.session_state.update(history=hist.ordered(rows), session=s, _cloud_loaded=True)
    return st.session_state.setdefault("history", [])


def store(entry: dict) -> bool:
    """Με λογαριασμό: αποθήκευση και στη βάση. False αν η βάση δεν δέχτηκε την εγγραφή."""
    s = session()
    if CLOUD is None or s is None:
        return True
    s = cloud_call(lambda: CLOUD.save(s, entry))
    if s is None:
        return False
    st.session_state["session"] = s
    return True


def unstore(day: str) -> bool:
    s = session()
    if CLOUD is None or s is None:
        return True
    s = cloud_call(lambda: CLOUD.delete(s, day))
    if s is None:
        return False
    st.session_state["session"] = s
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
            cards = [hist.card_from(c) for c in p["cards"]]
            for card in cards:
                rows = "".join(row_html(r) for r in card.rows)
                st.markdown(f'<div class="dv-small">{rows}</div>' if p["fold"] else rows, unsafe_allow_html=True)
                if not p["fold"] and card.info:
                    st.markdown(info_html([card]), unsafe_allow_html=True)
            if p["fold"] and info_html(cards):
                st.markdown(info_html(cards), unsafe_allow_html=True)


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
