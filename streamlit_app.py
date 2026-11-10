"""DaVinci Fitness — οθόνη της εφαρμογής (Streamlit).

Όλη η λογική είναι στο src/davinci/app_logic.py (με τεστ)· εδώ υπάρχει μόνο η οθόνη.
Εκτέλεση: streamlit run streamlit_app.py
"""

import sys
from dataclasses import replace
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from davinci import app_logic as al  # noqa: E402
from davinci import element_01 as e01  # noqa: E402
from davinci import element_44 as e44  # noqa: E402
from davinci import measurement  # noqa: E402
from davinci.fmt import num  # noqa: E402

st.set_page_config(page_title="DaVinci Fitness", page_icon="💪", layout="centered")
st.title("DaVinci Fitness")
st.caption("Επίπεδο Normal · απώλεια λίπους και συντήρηση. Η αύξηση μυών δεν περιλαμβάνεται ακόμη. "
           "Τα δεδομένα δεν αποθηκεύονται: κλείνοντας τη σελίδα χάνονται.")

TODAY = al.today()


# ------------------------------------------------------------------ στοιχεία χρήστη
def read_inputs() -> al.PlanInput | None:
    with st.expander("Τα στοιχεία σου", expanded=True):
        birth = st.date_input("Ημερομηνία γέννησης", value=None, min_value=date(1900, 1, 1), max_value=TODAY,
                              format="DD/MM/YYYY", key="birth")
        sex = st.radio("Φύλο", e01.load_data()["sexes"], horizontal=True, key="sex")
        c1, c2, c3 = st.columns(3)
        height = c1.number_input("Ύψος (cm)", min_value=90.0, max_value=230.0, value=None, step=0.1, format="%.1f",
                                 key="height")
        weight = c2.number_input("Βάρος (kg)", min_value=0.1, value=None, step=0.1, format="%.1f",
                                 key="weight")
        fat = c3.number_input("Λίπος (%)", min_value=0.1, max_value=99.9, value=None, step=0.1, format="%.1f",
                              key="fat")
        groups = {g["code"]: g["name"] for g in e01.load_data()["ancestry_groups"]}
        ancestry = st.selectbox("Καταγωγή", [None, *groups], format_func=lambda c: "Δεν δηλώνω" if c is None else groups[c],
                                key="ancestry")
        mixed = None
        if ancestry == "5":
            others = [c for c in groups if c != "5"]
            mixed = st.selectbox("Μικτή καταγωγή: ομάδα ενός γονέα (προαιρετικά)", [None, *others],
                                 format_func=lambda c: "Δεν διάλεξα" if c is None else groups[c], key="mixed")
        if birth is None:
            st.info("Συμπλήρωσε ημερομηνία γέννησης, ύψος, βάρος και λίπος.")
            return None
        age = e01.age_in_completed_years(birth, TODAY)
        profiles = al.allowed_profiles(birth, TODAY) or ("Υγεία",)
        profile = st.selectbox("Προφίλ", profiles, key="profile")
        training = st.checkbox("Προπόνηση με βάρη ή μικτή", key="training")
        pregnant = breastfeeding = False
        if e01.pregnancy_fields_visible(sex, age):
            pregnant = st.checkbox("Εγκυμοσύνη", key="pregnant")
            breastfeeding = st.checkbox("Θηλασμός", key="breastfeeding")
        pals = al.pal_options()
        pal = st.selectbox("Επίπεδο δραστηριότητας (PAL)", list(pals), index=None, placeholder="Διάλεξε",
                           format_func=lambda k: f"{k.replace('.', ',')} — {pals[k]}", key="pal")
    if height is None or weight is None or fat is None or pal is None:
        st.info("Συμπλήρωσε ύψος, βάρος, λίπος και επίπεδο δραστηριότητας.")
        return None
    return al.PlanInput(birth_date=birth, sex=sex, height_cm=height, weight_kg=weight, fat_percent=fat, today=TODAY,
                        ancestry=ancestry, mixed_chosen_group=mixed, profile=profile, resistance_training=training,
                        pregnant=pregnant, breastfeeding=breastfeeding, pal=float(pal))


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


# ------------------------------------------------------------------ κάρτα μέτρησης
def tab_card(inp: al.PlanInput) -> None:
    prep = al.prepare(inp)
    if prep.errors:
        st.error(prep.errors[0])
        return
    label = st.selectbox("Τι μετράς;", list(al.CARD_KINDS), key="card_kind")
    kind = al.CARD_KINDS[label]
    waist = kind == "circumference" and st.checkbox("Είναι η περιφέρεια της μέσης (στόχος: λόγος μέσης/ύψους κάτω από 0,50)",
                                                    key="card_waist")
    use_range = kind == "scale_fat_percent" and prep.fat is not None and prep.fat.profile_range is not None and \
        st.checkbox("Με στόχο το εύρος λίπους του προφίλ σου", key="card_range")
    st.write("Γράψε την ίδια μέτρηση σε διαφορετικές ημερομηνίες. Κάθε μέτρηση χρειάζεται συσκευή ή μέθοδο· "
             "αν αλλάξεις συσκευή, η σύγκριση ξεκινά από την αρχή.")
    st.caption("Πάτα το «+» πάνω δεξιά στον πίνακα για νέα γραμμή.")
    rows = st.data_editor(
        pd.DataFrame({"Ημερομηνία": pd.Series(dtype="datetime64[ns]"), "Τιμή": pd.Series(dtype="float64"),
                      "Συσκευή / μέθοδος": pd.Series(dtype="object"), "ISAK": pd.Series(dtype="bool")}),
        num_rows="dynamic", key="card_rows",
        column_config={"Ημερομηνία": st.column_config.DateColumn("Ημερομηνία", format="DD/MM/YYYY"),
                       "Τιμή": st.column_config.NumberColumn("Τιμή", min_value=0.0, format="%.1f"),
                       "Συσκευή / μέθοδος": st.column_config.TextColumn("Συσκευή / μέθοδος"),
                       "ISAK": st.column_config.CheckboxColumn("ISAK", help="Μέτρησε πιστοποιημένος εξεταστής ISAK")})
    records = rows.to_dict("records") if hasattr(rows, "to_dict") else list(rows)
    try:
        clean = al.clean_rows(records)
        if not clean:
            st.info("Γράψε τουλάχιστον μία μέτρηση.")
            return
        card = al.measurement_card(kind, clean, prep.user, waist=bool(waist),
                                   scale_fat_range=prep.fat.profile_range if use_range else None)
    except (e01.InvalidInput, ValueError) as exc:
        st.error(str(exc))
        return
    for name, value in card.lines():
        st.markdown(f"**{name}:** {value}")
    for m in card.messages:
        st.write(m)
    if card.info:
        st.caption(card.info)


# ------------------------------------------------------------------ μετρήσεις (Στοιχεία 05–39, σε δόσεις)
def guide_box(field: str, extra: tuple[str, ...] = ()) -> None:
    g = measurement.guide(field)
    if g is None:
        return
    with st.expander(f"ⓘ {g.title}"):
        for i, step in enumerate(g.steps, start=1):
            st.markdown(f"{i}. {step}")
        for x in extra:
            st.info(x)


def measure_input(label: str, key: str, field: str, *, min_value: float = 0.1, max_value: float | None = None,
                  extra: tuple[str, ...] = ()):
    v = st.number_input(label, min_value=min_value, max_value=max_value, value=None, step=0.1, format="%.1f", key=key)
    guide_box(field, extra)
    return v


def show_section(sec: al.Section) -> None:
    st.subheader(sec.title)
    if sec.indicative:
        st.warning("Ενδεικτική")
    for label, value in sec.lines:
        st.markdown(f"**{label}:** {value}")
    if sec.table:
        head, *body = sec.table
        st.dataframe([dict(zip(head, r)) for r in body], hide_index=True)
    for w in sec.warnings:
        st.warning(w)
    for m in sec.messages:
        st.write(m)


def hydration_inputs() -> dict:
    """Στοιχείο 08, Πίνακας 7: καταγραφή κάθε πρωί, μετά την ούρηση, πριν από φαγητό και ποτό."""
    with st.expander("Ενυδάτωση: έλεγχος Βάρος–Ούρα–Δίψα (18–59 ετών)"):
        st.caption("Καταγραφή κάθε πρωί, μετά την ούρηση, πριν από φαγητό και ποτό.")
        prev = [st.number_input(f"Πρωινό βάρος πριν από {d} {'ημέρα' if d == 1 else 'ημέρες'} (kg)", min_value=0.1,
                                value=None, step=0.1, format="%.1f", key=f"m_prev{d}") for d in (3, 2, 1)]
        today = st.number_input("Πρωινό βάρος σήμερα (kg)", min_value=0.1, value=None, step=0.1, format="%.1f",
                                key="m_today")
        urine = st.selectbox("Χρώμα πρώτων πρωινών ούρων (κλίμακα 1–8)", [None, *range(1, 9)], key="m_urine",
                             format_func=lambda x: "Δεν καταγράφηκε" if x is None else str(x))
        thirst = st.number_input("Δίψα (βαθμός στην κλίμακα)", min_value=0.0, value=None, step=1.0, format="%.0f",
                                 key="m_thirst")
    return dict(previous_morning_weights=tuple(x for x in prev if x is not None), today_morning_weight=today,
                urine_color=urine, thirst=thirst)


def tab_measures(inp: al.PlanInput) -> None:
    st.caption("Συμπλήρωσε όσα έχεις μετρήσει· τα κενά πεδία παραλείπονται. "
               "Σε κάθε πεδίο, το ⓘ δείχνει πώς μετράς.")
    m = al.Measures(
        waist_cm=measure_input("Περιφέρεια μέσης (cm)", "m_waist", "μέση"),
        hip_cm=measure_input("Περιφέρεια ισχίου (cm)", "m_hip", "ισχίο"),
        neck_cm=measure_input("Περιφέρεια λαιμού (cm)", "m_neck", "λαιμός"),
        chest_cm=measure_input("Περιφέρεια στήθους (cm)", "m_chest", "στήθος", extra=al.guide_extra("στήθος", inp)),
        upper_thigh_cm=measure_input("Περιφέρεια άνω μηρού (cm)", "m_thigh", "άνω μηρός"),
        scale_visceral_level=measure_input("Σπλαχνικό λίπος — τιμή ζυγαριάς (χωρίς μονάδα)", "m_visceral",
                                           "επίπεδο σπλαχνικού λίπους (ζυγαριά)", min_value=0.0),
        scale_muscle_percent=measure_input("Μύες % (ζυγαριά)", "m_muscle", "μύες % (ζυγαριά)", max_value=99.9),
        scale_water_percent=measure_input("Υγρά % (ζυγαριά)", "m_water", "υγρά % (ζυγαριά)", max_value=99.9),
        scale_bone_percent=measure_input("Οστά % (ζυγαριά)", "m_bone", "οστά % (ζυγαριά)", max_value=99.9),
        **hydration_inputs(),
    )
    sections, errors = al.measurement_sections(inp, m)
    for e in errors:
        st.error(e)
    for sec in sections:
        show_section(sec)


# ------------------------------------------------------------------ οδηγίες μέτρησης
def tab_guides() -> None:
    field = st.selectbox("Τι θέλεις να μετρήσεις;", list(measurement.fields()), key="guide_field")
    g = measurement.guide(field)
    if g is None:
        st.info("Αυτό το πεδίο είναι δήλωση, όχι μέτρηση.")
        return
    st.subheader(g.title)
    for i, step in enumerate(g.steps, start=1):
        st.markdown(f"{i}. {step}")
    if g.protocol:
        st.caption(g.protocol)


# ------------------------------------------------------------------ σελίδα
inputs = read_inputs()
tab1, tab_m, tab2, tab3 = st.tabs(["Πλάνο", "Μετρήσεις", "Κάρτα μέτρησης", "Οδηγίες μέτρησης"])
with tab1:
    if inputs is not None:
        tab_plan(inputs)
with tab_m:
    if inputs is not None:
        tab_measures(inputs)
with tab2:
    if inputs is not None:
        tab_card(inputs)
with tab3:
    tab_guides()
