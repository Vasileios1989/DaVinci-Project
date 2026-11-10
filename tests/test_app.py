"""Τεστ της εφαρμογής: η λογική (app_logic) με πραγματικά στοιχεία 01–45 και η οθόνη (streamlit_app.py) με
ψεύτικο streamlit, ώστε να ελέγχεται ότι τρέχει όλη η ροή χωρίς σφάλματα.
Η οθόνη ΔΕΝ ελέγχεται εδώ με το πραγματικό Streamlit (δεν ήταν εγκατεστημένο στο περιβάλλον ανάπτυξης)."""

import runpy
import sys
import types
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from davinci import app_logic as al
from davinci import element_01 as e01
from davinci import element_03 as e03
from davinci import element_40 as e40
from davinci import element_42 as e42
from davinci import element_43 as e43
from davinci import element_44 as e44
from davinci import measurement

TODAY = date(2026, 11, 5)
ROOT = Path(__file__).resolve().parents[1]


def inp(**kw) -> al.PlanInput:
    base = dict(birth_date=date(1986, 1, 1), sex="Γυναίκα", height_cm=165.0, weight_kg=72.0, fat_percent=38.0,
                today=TODAY, ancestry="1")
    base.update(kw)
    return al.PlanInput(**base)


# ================================================================ λογική
def test_loss_bmi25_asks_for_aha_and_does_not_choose():
    r = al.plan(inp())
    assert r.presentation is None and r.pending_choice == al.Choice("aha", (500, 750, "30%"), "AHA/ACC/TOS 2013")


def test_bmi_exactly_25_needs_aha_choice():
    p = al.prepare(inp(sex="Άνδρας", height_cm=200.0, weight_kg=100.0, fat_percent=30.0))
    assert p.bmi.value == 25 and p.direction == "loss" and p.choice.kind == "aha"
    below = al.prepare(inp(sex="Άνδρας", height_cm=200.0, weight_kg=99.9, fat_percent=30.0))
    assert below.bmi.value < 25 and below.choice.kind == "rate"


def test_loss_aha_500_matches_the_element_pipeline():
    r = al.plan(inp(aha_deficit=500))
    w = e01.UserCategories(birth_date=date(1986, 1, 1), measurement_date=TODAY, sex="Γυναίκα", height_cm=165.0,
                           ancestry="1")
    tp = e03.weight_target(72, 38, w).points[0]
    p = e42.partition("loss", 72 * 0.38, w, trained=False, bmi=26.4, deficit_kcal_day=500)
    en = e40.assess(w, 72, 1.4, goal="loss", aha_deficit=500, kcal_per_kg=p.e_kcal_per_kg)
    fc = e43.forecast(72, 72 * 0.38, w, trained=False, target_fat_percent=tp.target_fat_percent,
                      target_weight_kg=tp.weight_kg, deficit_kcal_day=500)
    rates = e44.rate_range(500 * 7 / p.e_kcal_per_kg, en.tdee, p.e_kcal_per_kg)
    want = e44.present(w, weight_kg=72, fat_percent=38, start=TODAY, energy=en,
                       macros=None, partition=p, target=tp, forecast=fc, rates=rates)
    got = r.presentation
    assert r.energy.target_intake_kcal == en.target_intake_kcal and got.weeks_to_target == want.weeks_to_target == (12, 28)
    assert [x.name for x in got.parts] == e44.load_data()["parts"]
    assert got.rows == want.rows and got.chart == want.chart
    assert got.parts[2].messages == want.parts[1].messages  # συνοπτική αναφορά


def test_aha_30_percent_uses_30_percent_of_tdee():
    r = al.plan(inp(aha_deficit="30%"))
    en = r.energy
    assert round(en.daily_delta_kcal, 6) == round(-en.tdee * 0.30, 6)
    # ο ίδιος έλλειμμα τροφοδοτεί και την πρόβλεψη και το εύρος εβδομάδων (όχι μόνο τη διατροφή)
    w = e01.UserCategories(birth_date=date(1986, 1, 1), measurement_date=TODAY, sex="Γυναίκα", height_cm=165.0,
                           ancestry="1")
    tp = e03.weight_target(72, 38, w).points[0]
    d = en.tdee * 0.30
    p = e42.partition("loss", 72 * 0.38, w, trained=False, bmi=26.4, deficit_kcal_day=d)
    fc = e43.forecast(72, 72 * 0.38, w, trained=False, target_fat_percent=tp.target_fat_percent,
                      target_weight_kg=tp.weight_kg, deficit_kcal_day=d)
    rates = e44.rate_range(d * 7 / p.e_kcal_per_kg, en.tdee, p.e_kcal_per_kg)
    assert r.presentation.rows == e44.timeline(fc, TODAY, 72, 38, 165.0)
    assert r.presentation.weeks_to_target == e44.weeks_range(72 - tp.weight_kg, rates)
    assert r.presentation.chart == e44.chart(fc, 72, tp.weight_kg, rates)


def test_aha_invalid_choice_is_reported_not_swallowed():
    r = al.plan(inp(aha_deficit=600))
    assert r.presentation is None and r.errors and "Έλλειμμα" in r.errors[0]


def test_rate_path_for_bmi_below_25_and_range_check():
    kw = dict(weight_kg=62.0, height_cm=170.0, fat_percent=34.0)
    r0 = al.plan(inp(**kw))
    assert r0.pending_choice.kind == "rate" and r0.pending_choice.options == (0.5, 1.0)
    ok = al.plan(inp(**kw, rate_percent=0.5))
    assert ok.presentation is not None and not ok.errors
    top = al.plan(inp(**kw, rate_percent=1.0))
    assert top.presentation is not None and not top.errors  # το πάνω όριο του εύρους επιτρέπεται
    bad = al.plan(inp(**kw, rate_percent=1.5))
    assert bad.presentation is None and bad.errors and "εκτός εύρους" in bad.errors[0]


def test_rate_path_matches_the_element_pipeline():
    kw = dict(weight_kg=62.0, height_cm=165.0, fat_percent=40.0)
    r = al.plan(inp(**kw, rate_percent=0.7))
    w = e01.UserCategories(birth_date=date(1986, 1, 1), measurement_date=TODAY, sex="Γυναίκα", height_cm=165.0,
                           ancestry="1")
    assert r.prep.bmi.value < 25 and r.prep.choice.kind == "rate"
    tp = e03.weight_target(62, 40, w).points[0]
    p = e42.partition("loss", 62 * 0.40, w, trained=False, bmi=r.prep.bmi.value, weekly_change_kg=-62 * 0.7 / 100)
    en = e40.assess(w, 62, 1.4, goal="loss", rate_percent=0.7, kcal_per_kg=p.e_kcal_per_kg)
    fc = e43.forecast(62, 62 * 0.40, w, trained=False, target_fat_percent=tp.target_fat_percent,
                      target_weight_kg=tp.weight_kg, rate_percent=0.7)
    rates = e44.rate_range(62 * 0.7 / 100, en.tdee, p.e_kcal_per_kg)
    assert r.presentation.weeks_to_target == e44.weeks_range(62 - tp.weight_kg, rates)
    assert r.presentation.rows == e44.timeline(fc, TODAY, 62, 40, 165.0)
    assert r.energy.target_intake_kcal == en.target_intake_kcal


def test_trained_user_gets_trained_partition_and_macros_use_target_weight():
    r = al.plan(inp(aha_deficit=500, resistance_training=True))
    m42 = e42.load_data()["messages"]
    assert m42["trained"] in r.presentation.parts[0].messages
    assert m42["untrained"] not in r.presentation.parts[0].messages
    plain = al.plan(inp(aha_deficit=500))
    assert m42["untrained"] in plain.presentation.parts[0].messages
    # πρωτεΐνη με βάρος αναφοράς = βάρος-στόχος Υγείας (Στοιχείο 41)
    w = e01.UserCategories(birth_date=date(1986, 1, 1), measurement_date=TODAY, sex="Γυναίκα", height_cm=165.0,
                           ancestry="1")
    tp = e03.weight_target(72, 38, w).points[0]
    from davinci import element_41 as e41
    mac = e41.compute(plain.energy.target_intake_kcal, w, 72, goal="loss", health_target_weight_kg=tp.weight_kg)
    assert mac.reference_weight_kg == tp.weight_kg < 72
    assert plain.presentation.parts[1].lines == e44.macro_lines(mac)


def test_muscular_high_bmi_uses_rate_not_aha():
    # Στοιχείο 40, Κανόνας 13 / Παράδειγμα 2: ΔΜΣ ≥ 25 με λίπος στο υγιές εύρος → ρυθμός %
    p = al.prepare(inp(sex="Άνδρας", height_cm=177.0, weight_kg=85.0, fat_percent=15.0))
    assert p.bmi.value >= 25 and p.fat.in_healthy_range and p.direction == "maintain" and p.choice is None


def test_maintain_inside_range():
    r = al.plan(inp(fat_percent=28.0))
    assert r.prep.direction == "maintain" and [x.name for x in r.presentation.parts][:2] == [
        "Ενεργειακό ισοζύγιο", "Μακροθρεπτικά"]
    assert r.presentation.rows == () and r.presentation.weeks_to_target is None


@pytest.mark.parametrize("kw", [dict(birth_date=date(2010, 1, 1)), dict(pregnant=True), dict(breastfeeding=True)])
def test_no_targets_for_minors_pregnancy_breastfeeding(kw):
    r = al.plan(inp(**kw))
    assert not r.errors and r.pending_choice is None
    assert r.presentation.weeks_to_target is None and r.presentation.rows == () and r.presentation.milestones == ()
    assert r.notes == ("Ανήλικοι, εγκυμοσύνη και θηλασμός: μόνο καταγραφή, χωρίς στόχους.",)


def test_safety_floor_gives_note_and_no_loss():
    r = al.plan(inp(weight_kg=50.0, fat_percent=5.0))
    assert r.prep.direction is None and r.notes == (al.SAFETY_NOTE,) and r.pending_choice is None
    assert r.presentation.weeks_to_target is None


def test_invalid_inputs_become_errors():
    assert al.plan(inp(birth_date=date(2025, 1, 1))).errors == ("Κάτω των 5 ετών: εκτός συστήματος (Ζώνη 0).",)
    assert al.plan(inp(height_cm=50.0)).errors and al.plan(inp(fat_percent=100.0)).errors
    assert al.plan(inp(pregnant=True, sex="Άνδρας")).errors
    assert al.plan(inp(profile="Bodybuilding", birth_date=date(2010, 1, 1))).errors


def test_two_target_profile_note_and_first_point():
    r = al.prepare(inp(profile="Αθλητικό", sex="Άνδρας", height_cm=177.0, weight_kg=95.0, fat_percent=30.0))
    assert r.direction == "loss" and any("δύο σημεία" in n for n in r.notes)
    pts = e03.weight_target(95, 30, r.user).points
    assert len(pts) == 2 and pts[0] != pts[1] and r.target == pts[0]


def test_pal_options_exclude_athlete_only():
    assert set(al.pal_options()) == {"1.3", "1.4", "1.6", "1.8", "2.0"}


def test_allowed_profiles_by_age():
    assert al.allowed_profiles(date(2010, 1, 1), TODAY) == ("Υγεία",)
    assert al.allowed_profiles(date(1990, 1, 1), TODAY) == ("Υγεία", "Αθλητικό", "Bodybuilding")


# ---- κάρτα μέτρησης
WAIST = [(date(2026, 8, 1), 101.0, "μεζούρα", False), (date(2026, 8, 29), 98.5, "μεζούρα", False),
         (date(2026, 9, 26), 97.8, "μεζούρα", False), (date(2026, 10, 24), 95.9, "μεζούρα", False)]


def _man():
    return al.prepare(inp(sex="Άνδρας", height_cm=177.0, weight_kg=90.0, fat_percent=25.0)).user


def test_measurement_card_reproduces_table8():
    c = al.measurement_card("circumference", WAIST, _man(), waist=True)
    assert c.lines()[0] == ("Τρέχον", "95,9 cm") and c.lines()[2] == ("Απόσταση από τον στόχο", "7,4 cm πάνω από το όριο")
    assert c.lines()[3][1].startswith("−1,9 cm (−1,9%) · όριο 4,0 cm") and c.lines()[4][1].endswith("προς τον στόχο")


def test_measurement_card_errors():
    u = _man()
    with pytest.raises(e01.InvalidInput):
        al.measurement_card("weight", WAIST, u)
    with pytest.raises(e01.InvalidInput):
        al.measurement_card("circumference", [(date(2026, 1, 1), 90.0, "", False)], u)
    with pytest.raises(e01.InvalidInput):
        al.measurement_card("circumference", [(date(2026, 1, 1), -1.0, "μεζούρα", False)], u)
    with pytest.raises(e01.InvalidInput):
        al.measurement_card("circumference", [], u)


def test_scale_fat_card_uses_profile_range_only_when_given():
    rows = [(date(2026, 8, 1), 31.4, "ζυγαριά Α", False), (date(2026, 8, 29), 30.6, "ζυγαριά Α", False),
            (date(2026, 9, 26), 29.6, "ζυγαριά Α", False)]
    with_t = al.measurement_card("scale_fat_percent", rows, _man(), scale_fat_range=(21.0, 32.9))
    without = al.measurement_card("scale_fat_percent", rows, _man())
    assert with_t.distance is not None and without.distance is None


def test_clean_rows():
    nan = float("nan")
    recs = [{"Ημερομηνία": pd.Timestamp("2026-08-01"), "Τιμή": 101.0, "Συσκευή / μέθοδος": "μεζούρα", "ISAK": False},
            {"Ημερομηνία": pd.NaT, "Τιμή": nan, "Συσκευή / μέθοδος": "", "ISAK": False}]
    assert al.clean_rows(recs) == [(date(2026, 8, 1), 101.0, "μεζούρα", False)]
    assert al.clean_rows([{"Ημερομηνία": date(2026, 8, 1), "Τιμή": 5, "Συσκευή / μέθοδος": None, "ISAK": None}]) == [
        (date(2026, 8, 1), 5.0, "", False)]
    with pytest.raises(e01.InvalidInput, match="Γραμμή 1"):
        al.clean_rows([{"Ημερομηνία": pd.NaT, "Τιμή": 5.0, "Συσκευή / μέθοδος": "x", "ISAK": False}])
    with pytest.raises(e01.InvalidInput, match="Γραμμή 2"):
        al.clean_rows([{}, {"Ημερομηνία": date(2026, 1, 1), "Τιμή": nan, "Συσκευή / μέθοδος": "x"}])


# ================================================================ οθόνη με ψεύτικο streamlit
class FakeSt:
    """Καταγράφει ό,τι εμφανίζεται και επιστρέφει τις τιμές που δίνει το τεστ (ανά key) ή την προεπιλογή."""

    def __init__(self, values):
        self.values, self.shown, self.errors = values, [], []
        self.column_config = types.SimpleNamespace(**{n: (lambda *a, **k: {"col": n}) for n in
                                                      ("DateColumn", "NumberColumn", "TextColumn", "CheckboxColumn")})

    def _ctx(self):
        return types.SimpleNamespace(__enter__=lambda s: s, __exit__=lambda *a: False)

    def __getattr__(self, name):
        def record(*a, **k):
            self.shown.append((name, a, k))
            if name == "error":
                self.errors.append(a[0])
        return record

    # widgets
    def date_input(self, label, value=None, key=None, **k):
        return self.values.get(key, value)

    def number_input(self, label, key=None, value=None, **k):
        return self.values.get(key, value)

    def radio(self, label, options, key=None, **k):
        return self.values.get(key, options[0])

    def selectbox(self, label, options, key=None, index=0, **k):
        if key in self.values:
            return self.values[key]
        return None if index is None else list(options)[index]

    def checkbox(self, label, key=None, value=False, **k):
        return self.values.get(key, value)

    def data_editor(self, df, key=None, **k):
        return self.values.get(key, df)

    def columns(self, n, **k):
        return [self for _ in range(n)]

    def tabs(self, names):
        return [Ctx() for _ in names]

    def expander(self, *a, **k):
        return Ctx()

    def texts(self):
        out = []
        for name, a, k in self.shown:
            out += [x for x in a if isinstance(x, str)]
        return out


class Ctx:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def run_app(monkeypatch, values):
    fake = FakeSt(values)
    mod = types.ModuleType("streamlit")
    mod.__dict__.update({n: getattr(fake, n) for n in (
        "date_input", "number_input", "radio", "selectbox", "checkbox", "data_editor", "columns", "tabs",
        "expander", "column_config")})
    mod.__getattr__ = lambda name: getattr(fake, name)
    monkeypatch.setitem(sys.modules, "streamlit", mod)
    monkeypatch.setattr(al, "today", lambda: TODAY)
    runpy.run_path(str(ROOT / "streamlit_app.py"), run_name="__main__")
    return fake


WOMAN = {"birth": date(1986, 1, 1), "sex": "Γυναίκα", "height": 165.0, "weight": 72.0, "fat": 38.0,
         "ancestry": "1", "pal": "1.4"}


def test_screen_empty_form_asks_for_input(monkeypatch):
    f = run_app(monkeypatch, {})
    assert not f.errors and any("Συμπλήρωσε" in t for t in f.texts())
    assert not any(t.startswith("Σήμερα:") for t in f.texts())


def test_screen_waits_for_choice(monkeypatch):
    f = run_app(monkeypatch, dict(WOMAN))
    t = f.texts()
    assert not f.errors and "Διάλεξε ρυθμό για να δεις το πλάνο." in t and not any(x.startswith("Σήμερα:") for x in t)


def test_screen_maintain_needs_no_choice(monkeypatch):
    f = run_app(monkeypatch, {**WOMAN, "fat": 28.0})
    t = f.texts()
    assert not f.errors and any(x.startswith("Σήμερα:") for x in t)
    assert "Διάλεξε ρυθμό για να δεις το πλάνο." not in t


def test_screen_full_plan(monkeypatch):
    f = run_app(monkeypatch, {**WOMAN, "aha": 500})
    t = f.texts()
    assert not f.errors
    assert any(x.startswith("Σήμερα: 72 kg") for x in t) and any("12–28 εβδομάδες" in x for x in t)
    assert any(n == "line_chart" for n, a, k in f.shown) and any(n == "dataframe" for n, a, k in f.shown)
    for part in e44.load_data()["parts"]:
        assert part in t


def test_screen_card_tab(monkeypatch):
    rows = pd.DataFrame({"Ημερομηνία": pd.to_datetime([r[0] for r in WAIST]), "Τιμή": [r[1] for r in WAIST],
                         "Συσκευή / μέθοδος": ["μεζούρα"] * 4, "ISAK": [False] * 4})
    vals = {**WOMAN, "sex": "Άνδρας", "height": 177.0, "weight": 90.0, "fat": 25.0, "card_waist": True,
            "card_rows": rows, "aha": 500}
    f = run_app(monkeypatch, vals)
    md = [a[0] for n, a, k in f.shown if n == "markdown"]
    assert not f.errors and "**Τρέχον:** 95,9 cm" in md
    assert any(x.startswith("**Αλλαγή από την αρχική:** −5,1 cm") for x in md)


def test_screen_card_half_row_is_an_error_not_skipped(monkeypatch):
    rows = pd.DataFrame({"Ημερομηνία": pd.to_datetime([None]), "Τιμή": [90.0], "Συσκευή / μέθοδος": ["μεζούρα"],
                         "ISAK": [False]})
    f = run_app(monkeypatch, {**WOMAN, "card_rows": rows, "aha": 500})
    assert any("Γραμμή 1" in e for e in f.errors)


def test_screen_guides_show_numbered_steps(monkeypatch):
    first = measurement.fields()[0]
    f = run_app(monkeypatch, dict(WOMAN))
    steps = measurement.guide(first).steps
    md = [a[0] for n, a, k in f.shown if n == "markdown"]
    assert md.count(f"1. {steps[0]}") == 1 and f"{len(steps)}. {steps[-1]}" in md


def test_files_for_deployment_exist():
    assert (ROOT / "streamlit_app.py").is_file()
    assert (ROOT / "requirements.txt").read_text(encoding="utf-8").startswith("streamlit")


def test_no_removed_streamlit_parameters():
    # «use_container_width» ανακοινώθηκε ότι αφαιρείται από το Streamlit (μετά τις 31/12/2025)
    assert "use_container_width" not in (ROOT / "streamlit_app.py").read_text(encoding="utf-8")


# ================================================================ Δόση 1: καρτέλα «Μετρήσεις» (05, 06, 07)
from davinci import element_06 as e06  # noqa: E402
from davinci import element_07 as e07  # noqa: E402


def man37(**kw):
    base = dict(birth_date=date(1989, 1, 1), sex="Άνδρας", height_cm=177.0, weight_kg=138.9, fat_percent=60.0 / 138.9 * 100,
                today=TODAY, ancestry="1")
    base.update(kw)
    return al.PlanInput(**base)


def sec(inp_, m, title_start):
    secs, errs = al.measurement_sections(inp_, m)
    assert errs == ()
    found = [s for s in secs if s.title.startswith(title_start)]
    return found[0] if found else None


def test_e05_document_table8_bmi_35():
    s = sec(man37(), al.Measures(waist_cm=146.0), "Μέση")
    d = dict(s.lines)
    assert d["Λόγος μέσης/ύψους"] == "0,82" and "Ταξινόμηση" not in d
    assert d["Πότε αρχίζει η ταξινόμηση"] == "Όταν ο ΔΜΣ πέσει κάτω από 35 (βάρος κάτω από ≈ 109,6 kg)"
    assert d["Μέση-στόχος"] == "κάτω από 88,5 cm" and d["Απόσταση από τον στόχο"] == "57,5 cm"
    assert s.messages == (e05_msgs()["bmi_35"],)


def e05_msgs():
    from davinci import element_05 as e05
    return e05.load_data()["messages"]


def test_e05_classification_profile_message_and_target_reached():
    s = sec(man37(weight_kg=80.0, fat_percent=20.0, profile="Αθλητικό"), al.Measures(waist_cm=86.0), "Μέση")
    d = dict(s.lines)
    assert d["Ταξινόμηση"] == "Υγιής κεντρική λιπώδης μάζα — Χωρίς αυξημένο κίνδυνο για την υγεία"
    assert "Απόσταση από τον στόχο" not in d and s.messages == (e05_msgs()["profile_target"],)
    low = sec(man37(weight_kg=60.0, fat_percent=15.0), al.Measures(waist_cm=60.0), "Μέση")
    assert dict(low.lines)["Ταξινόμηση"] == "Κάτω από το εύρος της ταξινόμησης" and low.messages == (e05_msgs()["below_040"],)


def test_e05_pregnancy_no_category_no_target():
    s = sec(man37(sex="Γυναίκα", pregnant=True, weight_kg=70.0, fat_percent=30.0), al.Measures(waist_cm=95.0), "Μέση")
    assert [k for k, _ in s.lines] == ["Περιφέρεια μέσης", "Λόγος μέσης/ύψους"]


def test_below_rounds_down():
    assert al._below(88.65) == "88,6" and al._below(88.5) == "88,5" and al._below(85.1) == "85,1"
    s = sec(man37(height_cm=177.3, weight_kg=80.0, fat_percent=20.0), al.Measures(waist_cm=90.0), "Μέση")
    assert dict(s.lines)["Μέση-στόχος"] == "κάτω από 88,6 cm"


@pytest.mark.parametrize("thigh, est, rng", [(70.0, "398", "350 – 445"), (75.0, "376", "328 – 423"),
                                             (80.0, "354", "306 – 401")])
def test_e06_document_table8(thigh, est, rng):
    s = sec(man37(), al.Measures(waist_cm=146.0, upper_thigh_cm=thigh), "Σπλαχνικό")
    assert s.lines[0] == ("Σπλαχνικό λίπος (Εκτίμηση)", f"≈ {est} cm² (εύρος {rng})")
    assert s.lines[1] == ("Ταξινόμηση", "Αυξημένος κίνδυνος (εκτίμηση)") and s.indicative
    assert s.messages == (e06.load_data()["messages"]["threshold"],)


def test_e06_scale_only_and_missing_thigh_and_scale_recorded():
    m6 = e06.load_data()["messages"]
    s = sec(man37(), al.Measures(scale_visceral_level=12.0), "Σπλαχνικό")
    assert s.lines == (("Σπλαχνικό λίπος (Τιμή ζυγαριάς)", "12,0"),) and s.messages == (m6["scale"],)
    s2 = sec(man37(), al.Measures(waist_cm=100.0), "Σπλαχνικό")
    assert s2.lines == () and s2.messages == (m6["no_thigh"],)
    s3 = sec(man37(), al.Measures(waist_cm=146.0, upper_thigh_cm=70.0, scale_visceral_level=8.0), "Σπλαχνικό")
    assert s3.lines[-1] == ("Τιμή ζυγαριάς (χωρίς μονάδα)", "8,0") and len(s3.lines) == 3
    assert sec(man37(), al.Measures(), "Σπλαχνικό") is None
    minor = sec(man37(birth_date=date(2012, 1, 1), profile="Υγεία"), al.Measures(waist_cm=80.0, upper_thigh_cm=50.0),
                "Σπλαχνικό")
    assert minor.lines == () and minor.messages == (m6["minor"],)
    thigh_only = sec(man37(birth_date=date(2012, 1, 1)), al.Measures(upper_thigh_cm=50.0), "Σπλαχνικό")
    assert thigh_only.messages == (m6["minor"],)


def test_e07_document_table8_and_dry_muscle():
    s = sec(man37(weight_kg=139.1, fat_percent=42.9), al.Measures(scale_muscle_percent=30.0),
            "Σκελετικοί")
    d = dict(s.lines)
    assert d["Σκελετικοί μύες"] == "41,7 kg (ζυγαριά)" and d["% της άλιπης μάζας"] == "52,5%"
    assert d["% του βάρους (πληροφορία)"] == "30,0%" and d["Δείκτης Σκελετικών Μυών (ΔΣΜ)"] == "13,3 kg/m²"
    assert d["Ξηροί μύες (εκτίμηση)"] == "≈ 8,3 kg (εύρος 7,5 – 8,8)" and "Ταξινόμηση" not in d
    m7 = e07.load_data()
    assert m7["messages"]["scale"] in s.messages and m7["messages"]["age_18_59"] in s.messages
    assert m7["messages"]["target"] in s.messages and len(set(s.messages)) == len(s.messages)


def test_e07_target_uses_element03_points():
    inp_ = man37(profile="Αθλητικό", resistance_training=True)
    s = sec(inp_, al.Measures(scale_muscle_percent=30.0), "Σκελετικοί")
    u = al._user(inp_)
    pts = e03.weight_target(inp_.weight_kg, inp_.fat_percent, u).points
    kg = inp_.weight_kg * 0.30
    ts = [e07.target(kg, e03.ffm(inp_.weight_kg, inp_.fat_percent), p.ffm_kg) for p in pts]
    from davinci.fmt import num
    want = " → ".join(f"≈ {num(t.muscle_kg)} kg (ΔΣΜ ≈ {num(t.muscle_kg / 1.77 ** 2)})" for t in ts)
    assert len(pts) == 2 and dict(s.lines)["Ενδεικτικός στόχος μυών"] == want
    assert dict(s.lines)["Ξηροί μύες-στόχος"] == " → ".join(f"≈ {num(t.dry_muscle_kg)} kg" for t in ts)


def test_e07_no_target_when_fat_in_range_minor_or_pregnant():
    for p in (man37(weight_kg=80.0, fat_percent=15.0), man37(birth_date=date(2012, 1, 1)),
              man37(sex="Γυναίκα", breastfeeding=True, weight_kg=70.0, fat_percent=35.0)):
        d = dict(sec(p, al.Measures(scale_muscle_percent=35.0), "Σκελετικοί").lines)
        assert "Ενδεικτικός στόχος μυών" not in d and "Ξηροί μύες-στόχος" not in d


def test_e07_lee_paths():
    m7 = e07.load_data()["messages"]
    obese = sec(man37(), al.Measures(), "Σκελετικοί")  # ΔΜΣ ≥ 30 χωρίς ζυγαριά → καμία τιμή
    assert obese.lines == () and obese.messages[0] == m7["lee_bmi_30"]
    old = sec(man37(birth_date=date(1950, 1, 1), weight_kg=70.0, fat_percent=25.0), al.Measures(), "Σκελετικοί")
    d = dict(old.lines)
    assert d["Σκελετικοί μύες"].endswith("(εξίσωση Lee)") and d["Ταξινόμηση"] in (
        "Φυσιολογική μυϊκή μάζα", "Χαμηλή μυϊκή μάζα", "Πολύ χαμηλή μυϊκή μάζα")
    very_old = sec(man37(birth_date=date(1940, 1, 1), weight_kg=70.0, fat_percent=25.0), al.Measures(), "Σκελετικοί")
    assert dict(very_old.lines)["Ταξινόμηση"].endswith("(Εκτός δεδομένων αναφοράς)") and very_old.indicative


def test_measurement_sections_errors():
    secs, errs = al.measurement_sections(man37(height_cm=50.0), al.Measures(waist_cm=80.0))
    assert secs == () and errs


def test_screen_measures_tab(monkeypatch):
    vals = {"birth": date(1989, 1, 1), "sex": "Άνδρας", "height": 177.0, "weight": 138.9, "fat": 60.0 / 138.9 * 100,
            "ancestry": "1", "pal": "1.4", "m_waist": 146.0, "m_thigh": 70.0, "m_muscle": 30.0, "m_visceral": 8.0}
    f = run_app(monkeypatch, vals)
    md = [a[0] for n, a, k in f.shown if n == "markdown"]
    assert not f.errors
    assert "**Λόγος μέσης/ύψους:** 0,82" in md and "**Σπλαχνικό λίπος (Εκτίμηση):** ≈ 398 cm² (εύρος 350 – 445)" in md
    assert "**Σκελετικοί μύες:** 41,7 kg (ζυγαριά)" in md and "**Τιμή ζυγαριάς (χωρίς μονάδα):** 8,0" in md
    subs = [a[0] for n, a, k in f.shown if n == "subheader"]
    assert {"Μέση (Στοιχείο 05)", "Σπλαχνικό λίπος (Στοιχείο 06)", "Σκελετικοί μύες (Στοιχείο 07)"} <= set(subs)
    assert "Ενδεικτική" in [a[0] for n, a, k in f.shown if n == "warning"]
    steps = measurement.guide("μέση").steps
    assert md.count(f"1. {steps[0]}") >= 1  # οδηγίες δίπλα στο πεδίο


def test_screen_card_starts_empty(monkeypatch):
    f = run_app(monkeypatch, dict(WOMAN))
    assert "Γράψε τουλάχιστον μία μέτρηση." in f.texts()


def test_e07_target_carries_element03_messages():
    m3 = e03.load_data()["messages_k0"]
    # Αθλητικό με λίπος κάτω από το πάνω όριο και προπόνηση: στόχος λίπους πάνω από το σημερινό → Κανόνας 4α του 03
    inp_ = man37(weight_kg=80.0, fat_percent=10.0, profile="Αθλητικό", resistance_training=True)
    s = sec(inp_, al.Measures(scale_muscle_percent=45.0), "Σκελετικοί")
    wt = e03.weight_target(80.0, 10.0, al._user(inp_))
    assert wt.indicative and m3["fat_gain"] in wt.messages
    assert m3["fat_gain"] in s.messages and s.indicative and "Ενδεικτικός στόχος μυών" in dict(s.lines)
    plain = sec(man37(), al.Measures(scale_muscle_percent=30.0), "Σκελετικοί")
    assert not plain.indicative and m3["fat_gain"] not in plain.messages
