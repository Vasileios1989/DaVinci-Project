"""Τεστ της εφαρμογής: η λογική (app_logic) με πραγματικά στοιχεία 01–45 και η οθόνη (streamlit_app.py) με
ψεύτικο streamlit, ώστε να ελέγχεται ότι τρέχει όλη η ροή χωρίς σφάλματα.
Η οθόνη ΔΕΝ ελέγχεται εδώ με το πραγματικό Streamlit (δεν ήταν εγκατεστημένο στο περιβάλλον ανάπτυξης)."""

import importlib
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
        self.inputs, self.expanders, self.group, self.options, self.placeholders = [], [], None, {}, {}
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
        self.inputs.append((self.group, label))
        self.placeholders[label] = k.get("placeholder")
        return self.values.get(key, value)

    def radio(self, label, options, key=None, index=0, **k):
        return self.values.get(key, list(options)[index])

    def selectbox(self, label, options, key=None, index=0, **k):
        self.options[key] = list(options)
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

    def expander(self, label, *a, **k):
        self.expanders.append(label)
        fake = self

        class Group:
            def __enter__(self):
                self.prev, fake.group = fake.group, (label if fake.group is None else fake.group)
                return self

            def __exit__(self, *a):
                fake.group = self.prev
                return False
        return Group()

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
    # μία φορά στο ⓘ του πεδίου «Ύψος» και μία στην καρτέλα «Οδηγίες μέτρησης»
    assert md.count(f"1. {steps[0]}") == 2 and f"{len(steps)}. {steps[-1]}" in md


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


# ================================================================ Δόση 2: 03 (ΔΑΜ, ανάλυση), 08, 09, 10
from davinci import element_08 as e08  # noqa: E402
from davinci import element_09 as e09  # noqa: E402
from davinci import element_10 as e10  # noqa: E402

SCALE = dict(scale_muscle_percent=30.0, scale_water_percent=39.2, scale_bone_percent=1.9)


def man139(**kw):  # το παράδειγμα των εγγράφων 07–10 (22/09/2026, ζυγαριά)
    return man37(weight_kg=139.1, fat_percent=42.9, **kw)


def lines(s):
    return dict(s.lines)


def test_e03_ffmi_document_examples():
    s = sec(man37(profile="Αθλητικό", resistance_training=True), al.Measures(), "Άλιπη μάζα")
    d = lines(s)
    assert d["Άλιπη μάζα"] == "78,9 kg" and d["Κανονικοποιημένος ΔΑΜ"] == "25,4"  # Πίνακας 7: 25,4
    assert d["Άλιπη μάζα-στόχος (Φάση 1)"] == "≈ 69,0 kg (−9,9) → ≈ 63,7 kg (−15,2)"  # Πίνακες 7, Β2
    m3 = e03.load_data()
    assert d["Ένδειξη"] == f'{m3["indications_men"][0]["label"]} · {m3["indication_high_with_excess_fat"]}'
    assert "Φυσιολογικό εύρος (πληροφορία)" not in d  # μόνο προφίλ Υγεία


def test_e03_ffmi_health_reference_range_and_minor():
    s = sec(man139(), al.Measures(), "Άλιπη μάζα")
    hr = e03.load_data()["health_reference_range"]
    assert lines(s)["Φυσιολογικό εύρος (πληροφορία)"] == f'16,7 – 19,8 · {hr["labels"]["above"]}'  # Πίνακας Ε4
    assert hr["messages"]["high_with_bmi_25"] in s.messages and hr["messages"]["activity"] in s.messages
    minor = sec(man37(birth_date=date(2012, 1, 1), weight_kg=60.0, fat_percent=30.0), al.Measures(), "Άλιπη μάζα")
    assert [k for k, _ in minor.lines] == ["Άλιπη μάζα", "ΔΑΜ", "Κανονικοποιημένος ΔΑΜ"] and minor.messages == ()
    woman = sec(man37(sex="Γυναίκα", weight_kg=70.0, fat_percent=30.0), al.Measures(), "Άλιπη μάζα")
    assert "Κανονικοποιημένος ΔΑΜ" not in lines(woman)


def test_e08_document_table12():
    s = sec(man139(), al.Measures(**SCALE), "Υγρά")
    d, m8 = lines(s), e08.load_data()["messages"]
    assert d["Υγρά"] == "54,5 kg (ζυγαριά)" and d["Αναλογία νερού / άλιπη μάζα"] == "0,687 — Ασυνήθιστη αναλογία"
    assert d["% του βάρους (πληροφορία)"] == "39,2%" and s.indicative
    assert [m8["scale_no_hydration"], m8["bmi_out_of_range"], m8["unusual_ratio"]] == list(s.messages[:3])
    assert d["Ενδεικτικός στόχος υγρών"].startswith("≈ ")  # Υγεία, λίπος πάνω από το εύρος: υπάρχει στόχος
    t = sec(man139(profile="Αθλητικό", resistance_training=True), al.Measures(**SCALE), "Υγρά")
    pts = e03.weight_target(139.1, 42.9, al._user(man139(profile="Αθλητικό", resistance_training=True))).points
    from davinci.fmt import num
    assert lines(t)["Ενδεικτικός στόχος υγρών"] == " → ".join(f"≈ {num(0.73 * p.ffm_kg)} kg" for p in pts)
    assert m8["target"] in t.messages


def test_e08_target_and_computed_water():
    s = sec(man37(weight_kg=80.0, fat_percent=30.0), al.Measures(), "Υγρά")
    d, m8 = lines(s), e08.load_data()["messages"]
    assert d["Υγρά"].endswith("(υπολογισμένη)") and d["Αναλογία νερού / άλιπη μάζα"].startswith("0,730")
    assert m8["computed"] in s.messages and d["Ενδεικτικός στόχος υγρών"].startswith("≈ ")
    old = sec(man37(birth_date=date(1940, 1, 1), weight_kg=70.0, fat_percent=25.0), al.Measures(), "Υγρά")
    assert lines(old)["Ηλικία"] == "Εκτός δεδομένων αναφοράς"


def test_e08_hydration():
    m8 = e08.load_data()["messages"]
    none = sec(man37(), al.Measures(), "Ενυδάτωση")
    assert none.lines == () and none.messages == (m8["baseline_missing"],)
    full = sec(man37(), al.Measures(previous_morning_weights=(100.0, 100.0, 100.0), today_morning_weight=98.0,
                                    urine_color=6, thirst=5.0), "Ενυδάτωση")
    assert lines(full) == {"Ενυδάτωση (Βάρος–Ούρα–Δίψα)": "Πιθανή αφυδάτωση",
                           "Θετικές ενδείξεις": "3 από 3 (Βάρος, Ούρα, Δίψα)"}
    part = sec(man37(), al.Measures(urine_color=3), "Ενυδάτωση")
    assert lines(part)["Θετικές ενδείξεις"] == "0 από 1 (Ούρα)" and part.messages == (m8["baseline_missing"],)
    old = sec(man37(birth_date=date(1950, 1, 1)), al.Measures(urine_color=7), "Ενυδάτωση")
    assert old.lines == () and old.messages == (m8["age_60_no_blood"],)
    minor_inp = man37(birth_date=date(2012, 1, 1))
    assert e08.assess_hydration(al._user(minor_inp)).messages == (m8["minor"],)
    assert m8["minor"] in sec(minor_inp, al.Measures(), "Υγρά").messages
    # Δόση 8: μια ενότητα που θα έμενε χωρίς μήνυμα κρατά το πρώτο της, ακόμη κι αν εμφανίστηκε πιο πάνω
    assert sec(minor_inp, al.Measures(), "Ενυδάτωση").messages == (m8["minor"],)


def test_e09_document_table11_and_typical():
    m9 = e09.load_data()["messages"]
    s = sec(man139(), al.Measures(**SCALE), "Οστά")
    assert lines(s) == {"Οστικά μέταλλα": "2,6 kg (Εκτίμηση ζυγαριάς άγνωστης ακρίβειας)",
                        "% της άλιπης μάζας": "3,3%", "% του βάρους (πληροφορία)": "1,9%"}
    assert s.messages == (m9["scale"], m9["target"], m9["weight_loss"], m9["no_dxa"])
    t = sec(man139(), al.Measures(), "Οστά")
    assert lines(t)["Οστικά μέταλλα"] == "≈ 4,5 kg (Τυπική τιμή)"
    assert m9["typical"].replace("[X]", "4,5").replace("[Y]", "79,4") in t.messages
    maint = sec(man37(weight_kg=80.0, fat_percent=15.0), al.Measures(), "Οστά")
    assert m9["weight_loss"] not in maint.messages and m9["target"] in maint.messages
    for p in (man37(sex="Γυναίκα", breastfeeding=True, weight_kg=70.0, fat_percent=35.0),
              man37(birth_date=date(2012, 1, 1))):
        x = sec(p, al.Measures(), "Οστά")
        assert m9["target"] not in x.messages and m9["weight_loss"] not in x.messages


def test_e10_document_tables_7_8():
    m10 = e10.load_data()["messages"]
    s = sec(man139(profile="Αθλητικό"), al.Measures(**SCALE), "Λόγοι")
    assert lines(s) == {"Λόγος άλιπης / λίπους": "1,33", "Σύγκριση με το όριο (χωρίς οστά)": "1,29",
                        "Ένδειξη": "Αυξημένος μεταβολικός κίνδυνος", "Λόγος μυών / λίπους": "0,70",
                        "Στόχος άλιπης / λίπους (προφίλ)": "6,7 – 15,7", "Στόχος μυών / λίπους (προφίλ)": "3,5 – 8,2"}
    assert s.messages == (m10["below_threshold"],) and s.indicative
    h = sec(man139(), al.Measures(), "Λόγοι")  # χωρίς οστά ζυγαριάς: όχι η τυπική τιμή
    d = lines(h)
    assert "Σύγκριση με το όριο (χωρίς οστά)" not in d and d["Στόχος άλιπης / λίπους (προφίλ)"] == "4,0 – 11,5"
    assert m10["no_bone"] in h.messages
    old = sec(man37(birth_date=date(1955, 1, 1), weight_kg=80.0, fat_percent=25.0), al.Measures(), "Λόγοι")
    assert m10["age_65"] in old.messages and "Ένδειξη" not in lines(old)
    minor = sec(man37(birth_date=date(2012, 1, 1)), al.Measures(), "Λόγοι")
    assert "Στόχος άλιπης / λίπους (προφίλ)" not in lines(minor) and m10["minor"] in minor.messages


def test_e10_muscle_ratio_needs_muscle():
    s = sec(man37(), al.Measures(), "Λόγοι")  # ΔΜΣ ≥ 30 χωρίς ζυγαριά → καμία τιμή μυών (Στοιχείο 07)
    assert "Λόγος μυών / λίπους" not in lines(s) and e10.load_data()["messages"]["no_muscle"] in s.messages


def test_e03_analysis_document_table_g2():
    s = sec(man139(), al.Measures(**SCALE), "Ανάλυση")
    assert s.table == (
        ("Γραμμή", "kg", "% άλιπης", "% βάρους"), ("Άλιπη μάζα", "79,4", "100,0%", "57,1%"),
        ("Α. Από τι υλικό", "", "", ""),
        ("Νερό (υγρά)", "54,5", "68,7%", "39,2%"), ("Ξηρή άλιπη μάζα", "24,9", "31,3%", "17,9%"),
        ("Οστικά μέταλλα", "2,6", "3,3%", "1,9%"), ("Λοιπά", "22,3", "28,0%", "16,0%"),
        ("Πρωτεΐνη (τυπική τιμή)", "≈ 15,9", "20,0%", "11,4%"), ("Γλυκογόνο (τυπική τιμή)", "≈ 0,7", "0,9%", "0,5%"),
        ("Άλλα μέταλλα (τυπική τιμή)", "≈ 1,0", "1,2%", "0,7%"), ("Διαφορά", "4,7", "5,9%", "3,4%"),
        ("Β. Από ποιους ιστούς", "", "", ""), ("Σκελετικοί μύες", "41,7", "52,5%", "30,0%"),
        ("Ξηροί μύες (εκτίμηση)", "≈ 8,3", "10,5%", "6,0%"), ("Λοιποί ιστοί", "37,7", "47,5%", "27,1%"))
    g = e03.load_data()["dry_mass"]
    assert len(s.warnings) == 1 and s.warnings[0].startswith("Διαφορά 4,7 kg") and "0,687" in s.warnings[0]
    assert e03.load_data()["analysis"]["note_two_ways"] in s.messages
    assert g["msg_typical"].replace("[Y]", "79,4") in s.messages


def test_e03_analysis_without_water_and_typical_bone_message_once():
    secs, _ = al.measurement_sections(man139(), al.Measures(scale_muscle_percent=30.0))
    a = [x for x in secs if x.title.startswith("Ανάλυση")][0]
    names = [r[0] for r in a.table]
    assert "Νερό (υγρά)" not in names and "Λοιπά" not in names and "Οστικά μέταλλα (τυπική τιμή)" in names
    typical = e09.load_data()["messages"]["typical"].replace("[X]", "4,5").replace("[Y]", "79,4")
    allmsgs = [m for x in secs for m in x.messages]
    assert allmsgs.count(typical) == 1  # δεν επαναλαμβάνεται σε δεύτερη ενότητα
    assert len(allmsgs) == len(set(allmsgs))
    assert e03.load_data()["dry_mass"]["msg_no_water"] in a.messages


def test_screen_batch2(monkeypatch):
    vals = {"birth": date(1989, 1, 1), "sex": "Άνδρας", "height": 177.0, "weight": 139.1, "fat": 42.9,
            "ancestry": "1", "pal": "1.4", "m_muscle": 30.0, "m_water": 39.2, "m_bone": 1.9,
            "m_prev3": 100.0, "m_prev2": 100.0, "m_prev1": 100.0, "m_today": 98.0, "m_urine": 6, "m_thirst": 5.0}
    f = run_app(monkeypatch, vals)
    md = [a[0] for n, a, k in f.shown if n == "markdown"]
    assert not f.errors
    assert "**Αναλογία νερού / άλιπη μάζα:** 0,687 — Ασυνήθιστη αναλογία" in md
    assert "**Ενυδάτωση (Βάρος–Ούρα–Δίψα):** Πιθανή αφυδάτωση" in md and "**Λόγος άλιπης / λίπους:** 1,33" in md
    tables = [a[0] for n, a, k in f.shown if n == "dataframe" and a and isinstance(a[0], list) and a[0]
              and "Γραμμή" in a[0][0]]
    assert tables and tables[0][0] == {"Γραμμή": "Άλιπη μάζα", "kg": "79,4", "% άλιπης": "100,0%", "% βάρους": "57,1%"}
    assert any(a[0].startswith("Διαφορά 4,7 kg") for n, a, k in f.shown if n == "warning")


# ================================================================ Δόση 3: 11, 12, 13
from davinci import element_11 as e11  # noqa: E402
from davinci import element_12 as e12  # noqa: E402
from davinci import element_13 as e13  # noqa: E402

ATH = dict(profile="Αθλητικό", resistance_training=True)  # Πίνακας 7 του 03: 79,3 / 67,8 kg


def test_e11_document_table8():
    s = sec(man37(**ATH), al.Measures(hip_cm=142.7), "Ισχίο")
    m11 = e11.load_data()["messages"]
    assert s.lines == (("Μέτρηση", "142,7 cm"),
                       ("Αναμενόμενο ισχίο στα 79,3 kg (λίπος 13,0%)", "≈ 98,9 cm (96,0 – 101,9)"),
                       ("Αναμενόμενο ισχίο στα 67,8 kg (λίπος 6,0%)", "≈ 92,0 cm (89,3 – 94,8)"))
    b = m11["B"].replace("Χ cm", "98,9 cm").replace("Υ–Ζ", "96,0–101,9")
    assert s.messages == (m11["A"], b) and not s.indicative  # 99,0 στο έγγραφο: βλ. NOTES (στρογγυλεμένο βάρος)


def test_e11_cases():
    m11 = e11.load_data()["messages"]
    assert sec(man37(weight_kg=80.0, fat_percent=15.0), al.Measures(), "Ισχίο") is None  # ούτε μέτρηση ούτε εκτίμηση
    est_only = sec(man37(), al.Measures(), "Ισχίο")
    assert m11["no_hip"] in est_only.messages and est_only.lines[0][0].startswith("Αναμενόμενο ισχίο")
    bb = sec(man37(profile="Bodybuilding", ancestry="4"), al.Measures(hip_cm=120.0), "Ισχίο")
    assert m11["C"] in bb.messages and m11["ancestry"] in bb.messages and bb.indicative
    minor = sec(man37(birth_date=date(2012, 1, 1)), al.Measures(hip_cm=90.0), "Ισχίο")
    assert minor.lines == (("Μέτρηση", "90,0 cm"),) and m11["record_only"] in minor.messages
    old = sec(man37(birth_date=date(1940, 1, 1)), al.Measures(hip_cm=110.0), "Ισχίο")
    assert ("Ηλικία", "Εκτός δεδομένων αναφοράς") in old.lines


def test_e12_document_table6_and_cases():
    m12 = e12.load_data()["messages"]
    s = sec(man139(profile="Αθλητικό"), al.Measures(neck_cm=44.0), "Λαιμός")
    assert s.lines == (("Μέτρηση", "44,0 cm"), ("Όριο STOP-Bang", "στο όριο ή πάνω (≥ 43 cm)"))
    assert s.messages == (m12["A"], m12["B"]) and not s.indicative  # χωρίς Γ: λίπος εκτός εύρους
    lean = sec(man37(weight_kg=80.0, fat_percent=10.0, profile="Αθλητικό"), al.Measures(neck_cm=40.0), "Λαιμός")
    assert ("Όριο STOP-Bang", "κάτω από το όριο (43 cm)") in lean.lines and m12["C"] in lean.messages
    w = sec(man37(sex="Γυναίκα", weight_kg=70.0, fat_percent=30.0, ancestry="3b"), al.Measures(neck_cm=41.0),
            "Λαιμός")
    assert ("Όριο STOP-Bang", "στο όριο ή πάνω (≥ 41 cm)") in w.lines and m12["ancestry_3b"] in w.messages
    assert w.indicative
    preg = sec(man37(sex="Γυναίκα", pregnant=True, weight_kg=70.0, fat_percent=30.0), al.Measures(neck_cm=45.0),
               "Λαιμός")
    assert preg.lines == (("Μέτρηση", "45,0 cm"),) and m12["record_only"] in preg.messages
    assert sec(man37(), al.Measures(), "Λαιμός") is None
    old = sec(man37(birth_date=date(1940, 1, 1)), al.Measures(neck_cm=40.0), "Λαιμός")
    assert ("Ηλικία", "Εκτός δεδομένων αναφοράς") in old.lines


def test_e13_document_table9():
    m13 = e13.load_data()["messages"]
    s = sec(man37(**ATH), al.Measures(chest_cm=131.5), "Στήθος")
    assert s.lines == (("Μέτρηση", "131,5 cm"), ("Αναμενόμενο στήθος στα 79,3 kg", "≈ 102,9 cm (100,1 – 105,8)"),
                       ("Αναμενόμενο στήθος στα 67,8 kg", "≈ 95,2 cm (92,6 – 97,9)"))
    assert s.messages == (m13["A"], m13["B"]) and not s.indicative


def test_e13_cases_and_women_info():
    m13 = e13.load_data()["messages"]
    old = sec(man37(birth_date=date(1960, 1, 1), ancestry="5"), al.Measures(chest_cm=120.0), "Στήθος")
    assert m13["age_59"] in old.messages and m13["ancestry_4_5"] in old.messages and old.indicative
    no = sec(man37(), al.Measures(), "Στήθος")
    assert m13["no_chest"] in no.messages and no.messages[0] == m13["A"]
    assert sec(man37(weight_kg=80.0, fat_percent=15.0), al.Measures(), "Στήθος") is None
    minor = sec(man37(birth_date=date(2012, 1, 1)), al.Measures(chest_cm=80.0), "Στήθος")
    assert minor.lines == (("Μέτρηση", "80,0 cm"),) and m13["record_only"] in minor.messages
    assert al.guide_extra("στήθος", "Γυναίκα") == (m13["women_info"],)
    assert al.guide_extra("στήθος", "Άνδρας") == () and al.guide_extra("μέση", "Γυναίκα") == ()


def test_screen_batch3(monkeypatch):
    vals = {"birth": date(1989, 1, 1), "sex": "Γυναίκα", "height": 165.0, "weight": 72.0, "fat": 38.0,
            "ancestry": "1", "pal": "1.4", "m_hip": 110.0, "m_neck": 36.0, "m_chest": 100.0}
    f = run_app(monkeypatch, vals)
    md = [a[0] for n, a, k in f.shown if n == "markdown"]
    subs = [a[0] for n, a, k in f.shown if n == "subheader"]
    assert not f.errors and {"Ισχίο (Στοιχείο 11)", "Λαιμός (Στοιχείο 12)", "Στήθος (Στοιχείο 13)"} <= set(subs)
    assert "**Όριο STOP-Bang:** κάτω από το όριο (41 cm)" in md
    infos = [a[0] for n, a, k in f.shown if n == "info"]
    assert e13.load_data()["messages"]["women_info"] in infos  # μέσα στο ⓘ του στήθους


def test_screen_inputs_grouped_in_categories(monkeypatch):
    f = run_app(monkeypatch, {})
    top = ["1. Προσωπικά στοιχεία", "2. Σύσταση σώματος (ζυγαριά)", "3. Περιφέρειες κορμού (μεζούρα)",
           "4. Περιφέρειες άκρων (μεζούρα)", "5. Ενυδάτωση: έλεγχος Βάρος–Ούρα–Δίψα (18–59 ετών)"]
    assert [e for e in f.expanders if e[:2] in ("1.", "2.", "3.", "4.", "5.")] == top
    where = {label: g for g, label in f.inputs}
    assert where["Ύψος (cm)"] == top[0]
    assert {where[x] for x in ("Βάρος (kg)", "Λίπος %", "Μύες %", "Υγρά %", "Οστά %")} == {top[1]}
    assert {where[x] for x in ("Λαιμός (cm)", "Στήθος (cm)", "Μέση (cm)", "Ισχίο (cm)")} == {top[2]}
    assert where["Άνω μηρός — ακριβώς κάτω από τη γλουτιαία πτυχή (cm)"] == top[3] and where["Πρωινό βάρος σήμερα (kg)"] == top[4]


def test_screen_missing_fields_listed(monkeypatch):
    f = run_app(monkeypatch, {"birth": date(1990, 1, 1), "height": 170.0})
    assert "Συμπλήρωσε: βάρος, λίπος, επίπεδο δραστηριότητας." in f.texts()


def test_screen_missing_birth_and_profiles_by_age(monkeypatch):
    f = run_app(monkeypatch, {"height": 170.0, "weight": 70.0, "fat": 25.0, "pal": "1.4"})
    assert "Συμπλήρωσε: ημερομηνία γέννησης." in f.texts() and not f.errors
    assert f.options["profile"] == ["Υγεία", "Αθλητικό", "Bodybuilding"]
    minor = run_app(monkeypatch, {"birth": date(2012, 1, 1)})
    assert minor.options["profile"] == ["Υγεία"]



# ================================================================ Normal / Professional (Στοιχείο 46) και «Προαιρετικό»
from davinci import element_06 as e06m  # noqa: E402
from davinci import element_46 as e46  # noqa: E402

PRO = dict(level="Professional")


def test_required_fields_have_no_placeholder_optional_do(monkeypatch):
    f = run_app(monkeypatch, {})
    ph = f.placeholders
    assert ph["Ύψος (cm)"] is None and ph["Βάρος (kg)"] is None and ph["Λίπος %"] is None
    for label in ("Μύες %", "Υγρά %", "Οστά %", "Μέση (cm)", "Άνω μηρός — ακριβώς κάτω από τη γλουτιαία πτυχή (cm)", "Πρωινό βάρος σήμερα (kg)",
                  "Σπλαχνικό λίπος — μόνο αν το δείχνει η ζυγαριά σου (χωρίς μονάδα)"):
        assert ph[label] == "Προαιρετικό"


def test_normal_hides_professional_categories(monkeypatch):
    f = run_app(monkeypatch, dict(WOMAN))
    assert not any(e.startswith(("6.", "7.")) for e in f.expanders)
    assert any(t.startswith("Όργανα: ") and "Δερματοπτυχόμετρο" not in t for t in f.texts())
    p = run_app(monkeypatch, {**WOMAN, "level": "Professional", "x_meno": "Ναι"})
    assert [e for e in p.expanders if e.startswith(("6.", "7."))] == [
        "6. Όργανα Professional (δερματοπτυχόμετρο, παχύμετρο οστών)", "7. Ιατρικές εξετάσεις (προαιρετικά)"]
    assert e46.load_data()["messages"]["N3"] in p.texts() and e46.medical_entry_message() in p.texts()
    assert p.options["x_meno"] == ["Ναι", "Όχι"] and not p.errors


def test_normal_rejects_medical_values():
    secs, errs = al.measurement_sections(man37(), al.Measures(medical_muscle_kg=40.0))
    assert secs == () and errs and "Professional" in errs[0]


def test_pro_visceral_ct_and_volume_and_n4():
    n4 = e46.load_data()["messages"]["N4"]
    s = sec(man37(**PRO), al.Measures(ct_visceral_cm2=120.0, waist_cm=146.0, upper_thigh_cm=70.0), "Σπλαχνικό")
    assert s.lines[:2] == (("Σπλαχνικό λίπος (Μέτρηση, τομογραφία)", "120,0 cm²"), ("Ταξινόμηση", "Αυξημένος κίνδυνος"))
    assert n4 in s.messages
    v = sec(man37(**PRO), al.Measures(visceral_volume=1500.0), "Σπλαχνικό")
    assert v.lines == (("Σπλαχνικό λίπος (Μέτρηση, DXA ή μαγνητική)", "1.500,0 (μονάδα της γνωμάτευσης)"),)
    assert e06m.load_data()["messages"]["volume"] in v.messages and n4 not in v.messages
    one = sec(man37(**PRO), al.Measures(ct_visceral_cm2=80.0), "Σπλαχνικό")
    assert n4 not in one.messages and one.lines[1] == ("Ταξινόμηση", "Κάτω από το όριο κινδύνου")


def test_pro_muscle_water_bone_medical_with_n4():
    n4 = e46.load_data()["messages"]["N4"]
    m = al.Measures(medical_muscle_kg=40.0, scale_muscle_percent=30.0, isotope_water_kg=57.0, scale_water_percent=39.2,
                    dxa_bone_kg=3.4, scale_bone_percent=1.9)
    secs, errs = al.measurement_sections(man139(**PRO), m)
    assert errs == ()
    get = {x.title.split(" (")[0]: x for x in secs}
    assert dict(get["Σκελετικοί μύες"].lines)["Σκελετικοί μύες"] == "40,0 kg (ιατρική μέτρηση)"
    assert dict(get["Υγρά"].lines)["Υγρά"] == "57,0 kg (ιατρική μέτρηση)"
    assert dict(get["Οστά"].lines)["Οστικά μέταλλα"] == "3,4 kg"
    assert n4 in get["Σκελετικοί μύες"].messages  # εμφανίζεται μία φορά (αφαίρεση διπλών)
    rows = {r[0]: r[1] for r in get["Ανάλυση άλιπης μάζας"].table}
    assert rows["Νερό (υγρά)"] == "57,0" and rows["Οστικά μέταλλα"] == "3,4" and rows["Σκελετικοί μύες"] == "40,0"
    assert dict(get["Λόγοι άλιπης / λίπους και μυών / λίπους"].lines)["Σύγκριση με το όριο (χωρίς οστά)"] == \
        _n2((79.4261 - 3.4) / (139.1 - 79.4261))


def _n2(x):
    from davinci.fmt import num
    return num(x, 2)


def test_pro_bone_health_dxa():
    m9 = e09.load_data()["messages"]
    man = sec(man37(**PRO), al.Measures(t_score=-2.7), "Οστά")  # άνδρας 37: Z-score (Πίνακας 6)
    assert "Υγεία οστών (Z-score, DXA)" not in dict(man.lines)
    z = sec(man37(**PRO), al.Measures(z_score=-2.3), "Οστά")
    assert dict(z.lines)["Υγεία οστών (Z-score, DXA)"] == "Κάτω από το αναμενόμενο για την ηλικία"
    w = sec(man37(sex="Γυναίκα", weight_kg=70.0, fat_percent=30.0, **PRO),
            al.Measures(t_score=-2.7, menopause=True), "Οστά")
    assert dict(w.lines)["Υγεία οστών (T-score, DXA)"] == "Οστεοπόρωση (κατά την πυκνότητα)"
    nm = sec(man37(sex="Γυναίκα", weight_kg=70.0, fat_percent=30.0, **PRO), al.Measures(t_score=-1.5), "Οστά")
    assert m9["menopause_missing"] in nm.messages and dict(nm.lines)["Υγεία οστών (T-score, DXA)"].startswith("Χαμηλή")


def test_pro_hydration_blood():
    old = dict(birth_date=date(1950, 1, 1), **PRO)
    s = sec(man37(**old), al.Measures(serum_osmolality=305.0), "Ενυδάτωση")
    assert s.lines == (("Ωσμωτικότητα ορού (μετρημένη)", "305,0 mOsm/kg · όριο > 300"),
                       ("Ενυδάτωση (εξέταση αίματος)", "Αφυδάτωση από χαμηλή πρόσληψη υγρών"))
    ok = sec(man37(**old), al.Measures(serum_osmolality=290.0), "Ενυδάτωση")
    assert ok.lines[1] == ("Ενυδάτωση (εξέταση αίματος)", "κάτω από το όριο")
    from davinci.fmt import num
    low = sec(man37(**old), al.Measures(osmolality_inputs=(140.0, 4.0, 5.0, 6.0)), "Ενυδάτωση")
    assert low.lines == (("Υπολογισμένη ωσμωτικότητα", f"{num(1.86 * 144 + 1.15 * 5 + 6 + 14)} mmol/L · όριο > 295"),
                         ("Ενυδάτωση (εξέταση αίματος)", "κάτω από το όριο"))  # 293,6
    high = sec(man37(**old), al.Measures(osmolality_inputs=(145.0, 4.0, 5.0, 6.0)), "Ενυδάτωση")
    assert high.lines == (("Υπολογισμένη ωσμωτικότητα", "302,9 mmol/L · όριο > 295"),
                          ("Ενυδάτωση (εξέταση αίματος)", "Ένδειξη για έλεγχο από γιατρό"))


def test_screen_professional_values_reach_results(monkeypatch):
    vals = {**WOMAN, "level": "Professional", "x_muscle": 25.0, "x_na": 140.0, "x_k": 4.0, "x_glu": 5.0}
    f = run_app(monkeypatch, vals)
    md = [a[0] for n, a, k in f.shown if n == "markdown"]
    assert "**Σκελετικοί μύες:** 25,0 kg (ιατρική μέτρηση)" in md and not f.errors
    assert not any(x.startswith("**Υπολογισμένη ωσμωτικότητα") for x in md)  # λείπει η ουρία
    g = run_app(monkeypatch, {**vals, "x_urea": 6.0, "birth": date(1950, 1, 1)})
    assert any(x.startswith("**Υπολογισμένη ωσμωτικότητα:**") for x in
               [a[0] for n, a, k in g.shown if n == "markdown"])


def test_pro_n4_needs_two_real_sources_and_menopause_choice(monkeypatch):
    n4 = e46.load_data()["messages"]["N4"]
    s = sec(man37(**PRO), al.Measures(ct_visceral_cm2=120.0, waist_cm=146.0), "Σπλαχνικό")  # χωρίς άνω μηρό
    assert n4 not in s.messages
    w = dict(sex="Γυναίκα", weight_kg=70.0, fat_percent=30.0, **PRO)
    pre = sec(man37(**w), al.Measures(t_score=-2.7, menopause=False), "Οστά")  # πριν την εμμηνόπαυση: Z-score
    assert not any(k.startswith("Υγεία οστών") for k, _ in pre.lines)
    vals = {**WOMAN, "level": "Professional", "x_t": -2.7}
    yes = run_app(monkeypatch, {**vals, "x_meno": "Ναι"})
    no = run_app(monkeypatch, {**vals, "x_meno": "Όχι"})
    md_yes = [a[0] for n, a, k in yes.shown if n == "markdown"]
    md_no = [a[0] for n, a, k in no.shown if n == "markdown"]
    assert "**Υγεία οστών (T-score, DXA):** Οστεοπόρωση (κατά την πυκνότητα)" in md_yes
    assert not any(x.startswith("**Υγεία οστών") for x in md_no)


# ================================================================ Δόση 4: 14, 15, 16
from davinci import element_14 as e14  # noqa: E402
from davinci import element_15 as e15  # noqa: E402
from davinci import element_16 as e16  # noqa: E402


def test_e14_document_table9():
    m14 = e14.load_data()["messages"]
    s = sec(man37(**ATH), al.Measures(shoulders_cm=138.0), "Ώμοι")
    # Ο Πίνακας 9 βγαίνει με τον όρο ηλικίας που ο Πίνακας 3 παραλείπει (εύρημα στο NOTES): 114,7 → ο κώδικας 116,3
    assert s.lines == (("Μέτρηση", "138,0 cm"), ("Αναμενόμενοι ώμοι στα 79,3 kg", "≈ 116,3 cm (113,1 – 119,7)"),
                       ("Αναμενόμενοι ώμοι στα 67,8 kg", "≈ 110,9 cm (107,8 – 114,1)"))
    assert s.messages == (m14["A"], m14["B"]) and not s.indicative
    assert sec(man37(weight_kg=80.0, fat_percent=15.0), al.Measures(), "Ώμοι") is None
    no = sec(man37(), al.Measures(), "Ώμοι")
    assert m14["no_value"] in no.messages and no.lines[0][0].startswith("Αναμενόμενοι ώμοι")
    minor = sec(man37(birth_date=date(2012, 1, 1)), al.Measures(shoulders_cm=90.0), "Ώμοι")
    assert minor.lines == (("Μέτρηση", "90,0 cm"),) and m14["record_only"] in minor.messages


def test_e15_document_table11():
    m15 = e15.load_data()["messages"]
    s = sec(man139(**ATH), al.Measures(arm_relaxed_cm=40.0, biceps_flexed_cm=40.0), "Μπράτσο")
    d = dict(s.lines)
    assert d["Μπράτσο χαλαρό"] == "40,0 cm" and d["Διορθωμένο για τον ΔΜΣ"] == "30,0 cm"
    assert d["Ταξινόμηση"] == "Φυσιολογικό" and d["Ελάχιστο για «Φυσιολογικό» σήμερα"] == "≥ 38,0 cm"
    assert d["Αναμενόμενο στο σημερινό βάρος"] == "46,2 cm (43,9 – 48,5)"
    assert m15["O"] in s.messages and m15["C"] in s.messages and s.indicative  # ΔΜΣ 44,4 > 43,5
    pts = e03.weight_target(139.1, 42.9, al._user(man139(**ATH))).points
    flx = e15.assess_flexed(40.0, 139.1, al._user(man139(**ATH)), [p.weight_kg for p in pts])
    assert flx.is_minimum and [k for k, _ in s.lines][-2:] == [f"Αναμενόμενος δικέφαλος στα {_n1(p.weight_kg)} kg"
                                                               for p in pts]
    assert all(v.startswith("≥ ") and "(εύρος " in v for k, v in s.lines if k.startswith("Αναμενόμενος δικέφαλος"))


def _n1(x):
    from davinci.fmt import num
    return num(x)


def test_e15_doc_targets_with_doc_weights():
    # Πίνακας 11: Αθλητικό 13% (79,3 kg) → ≥ 34,1 cm (εύρος 32,4 – 35,8)
    s = sec(man37(**ATH), al.Measures(biceps_flexed_cm=36.0), "Μπράτσο")
    assert ("Αναμενόμενος δικέφαλος στα 79,3 kg", "≥ 34,1 cm (εύρος 32,4 – 35,8)") in s.lines
    h = sec(man37(resistance_training=True), al.Measures(biceps_flexed_cm=36.0), "Μπράτσο")  # Υγεία: πληροφορία
    assert ("Αναμενόμενος δικέφαλος στα 90,0 kg", "≈ 36,5 cm (34,7 – 38,3)") in h.lines


def test_e15_cases():
    m15 = e15.load_data()["messages"]
    low = sec(man37(weight_kg=95.0, fat_percent=30.0), al.Measures(arm_relaxed_cm=33.0), "Μπράτσο")  # ΔΜΣ 30,3
    assert dict(low.lines)["Διορθωμένο για τον ΔΜΣ"] == "26,0 cm" and dict(low.lines)["Ταξινόμηση"] == "Χαμηλό"
    thin = sec(man37(weight_kg=55.0, fat_percent=10.0), al.Measures(arm_relaxed_cm=25.0), "Μπράτσο")  # ΔΜΣ 17,6
    assert m15["relaxed_low_bmi"] in thin.messages and dict(thin.lines)["Ταξινόμηση"] == "Πολύ χαμηλό"
    minor = sec(man37(birth_date=date(2012, 1, 1)), al.Measures(arm_relaxed_cm=25.0), "Μπράτσο")
    assert minor.lines == (("Μπράτσο χαλαρό", "25,0 cm"),) and m15["record_only"] in minor.messages
    assert sec(man37(weight_kg=80.0, fat_percent=15.0), al.Measures(), "Μπράτσο") is None
    only_flexed = sec(man37(weight_kg=80.0, fat_percent=15.0), al.Measures(biceps_flexed_cm=36.0), "Μπράτσο")
    assert ("Δικέφαλος σφιγμένος", "36,0 cm") in only_flexed.lines
    asian = sec(man37(weight_kg=80.0, fat_percent=15.0, ancestry="3a"), al.Measures(arm_relaxed_cm=33.0), "Μπράτσο")
    assert m15["relaxed_ancestry"] in asian.messages and asian.indicative


def test_e16_document_table10_and_cases():
    m16 = e16.load_data()["messages"]
    s = sec(man139(**ATH), al.Measures(forearm_relaxed_cm=32.6), "Πήχης")
    d = dict(s.lines)
    assert d["Πήχης χαλαρός"] == "32,6 cm" and d["Ταξινόμηση"] == "Φυσιολογικό (όριο 24,9 cm)"
    assert m16["O"] in s.messages and m16["relaxed_bmi_30"] in s.messages and m16["no_flexed"] in s.messages
    assert s.indicative  # από τον χαλαρό πήχη (ΔΜΣ ≥ 30), όχι από τον σφιγμένο
    assert "Αναμενόμενο στο σημερινό βάρος" not in d  # χωρίς σφιγμένο: καμία σύγκριση
    doc = sec(man37(**ATH), al.Measures(forearm_flexed_cm=30.0), "Πήχης")
    assert ("Αναμενόμενος πήχης στα 79,3 kg", "≥ 30,0 cm (εύρος 28,9 – 31,3)") in doc.lines
    today = sec(man139(**ATH), al.Measures(forearm_flexed_cm=30.0), "Πήχης")
    assert ("Αναμενόμενο στο σημερινό βάρος", "37,1 cm (35,6 – 38,6)") in today.lines and m16["C"] in today.messages
    w = sec(man37(sex="Γυναίκα", weight_kg=60.0, fat_percent=28.0), al.Measures(forearm_relaxed_cm=21.0), "Πήχης")
    assert dict(w.lines)["Ταξινόμηση"] == "Χαμηλό (όριο 21,7 cm)" and w.messages[0] == m16["X"]
    minor = sec(man37(birth_date=date(2012, 1, 1)), al.Measures(forearm_relaxed_cm=20.0), "Πήχης")
    assert minor.lines == (("Πήχης χαλαρός", "20,0 cm"),) and m16["record_only"] in minor.messages


def test_screen_batch4(monkeypatch):
    vals = {**WOMAN, "m_shoulders": 100.0, "m_arm_rel": 30.0, "m_biceps": 31.0, "m_fore_rel": 24.0, "m_fore_flx": 25.0}
    f = run_app(monkeypatch, vals)
    subs = [a[0] for n, a, k in f.shown if n == "subheader"]
    assert not f.errors
    assert {"Ώμοι (Στοιχείο 14)", "Μπράτσο και δικέφαλος (Στοιχείο 15)", "Πήχης (Στοιχείο 16)"} <= set(subs)
    md = [a[0] for n, a, k in f.shown if n == "markdown"]
    assert "**Μπράτσο χαλαρό:** 30,0 cm" in md and "**Πήχης σφιγμένος:** 25,0 cm" in md
    where = {label: g for g, label in f.inputs}
    assert where["Ώμοι (cm)"].startswith("3.") and where["Μπράτσο χαλαρό (cm)"].startswith("4.")
    assert where["Πήχης σφιγμένος (cm)"].startswith("4.") and f.placeholders["Ώμοι (cm)"] == "Προαιρετικό"


# ================================================================ Δόση 5: 17, 18, 19
from davinci import element_17 as e17  # noqa: E402
from davinci import element_18 as e18  # noqa: E402
from davinci import element_19 as e19  # noqa: E402


def test_e17_document_table8():
    m17 = e17.load_data()["messages"]
    s = sec(man139(), al.Measures(wrist_cm=18.6), "Καρπός")
    assert s.lines == (("Μέτρηση", "18,6 cm"), ("Σκελετός", "Δεν έχει οριστεί"))
    assert s.messages == (m17["A"], m17["B"], m17["S"])
    lean = sec(man37(weight_kg=70.0, fat_percent=15.0), al.Measures(wrist_cm=17.0), "Καρπός")  # ΔΜΣ 22,3: χωρίς Β
    assert lean.messages == (m17["A"], m17["S"])
    minor = sec(man37(birth_date=date(2012, 1, 1)), al.Measures(wrist_cm=15.0), "Καρπός")
    assert minor.lines == (("Μέτρηση", "15,0 cm"),) and minor.messages == (m17["record_only"],)
    assert sec(man37(), al.Measures(), "Καρπός") is None


def test_e18_document_table10():
    m18 = e18.load_data()["messages"]
    s = sec(man37(**ATH), al.Measures(thigh_cm=74.5), "Μηρός")
    d = dict(s.lines)
    assert d["Ταξινόμηση"] == "Πάνω από το όριο (60 cm · από μία μελέτη, προς επιβεβαίωση)"
    assert d["Αναμενόμενος μηρός στα 79,3 kg"] == "≥ 60,0 cm (εκτίμηση 58,9, εύρος 57,0 – 60,8)"  # έγγραφο 57,1: βλ. NOTES
    assert d["Αναμενόμενος μηρός στα 67,8 kg"] == "≥ 60,0 cm (εκτίμηση 53,6, εύρος 51,9 – 55,4)"
    assert m18["O"] in s.messages and m18["D"] in s.messages and m18["C"] in s.messages and s.indicative
    today = e18.estimate(138.9, al._user(man37(**ATH)))
    assert d["Αναμενόμενο στο σημερινό βάρος"] == f"{_n1(today.value_cm)} cm ({_n1(today.range_cm[0])} – {_n1(today.range_cm[1])})"
    bb = sec(man37(profile="Bodybuilding", resistance_training=True), al.Measures(), "Μηρός")
    assert dict(bb.lines)["Αναμενόμενος μηρός στα 83,9 kg"].startswith("≥ 60,9 cm (εκτίμηση 60,9")


def test_e18_health_profile_and_cases():
    m18 = e18.load_data()["messages"]
    h = sec(man37(resistance_training=True), al.Measures(thigh_cm=58.0), "Μηρός")
    d = dict(h.lines)
    assert d["Ταξινόμηση"].startswith("Κάτω από το όριο") and m18["X"] in h.messages
    assert d["Αναμενόμενος μηρός στα 90,0 kg"].startswith("≈ 63,")  # Υγεία: πληροφορία, χωρίς «≥»
    young = sec(man37(birth_date=date(2000, 1, 1), weight_kg=70.0, fat_percent=15.0), al.Measures(thigh_cm=58.0),
                "Μηρός")
    assert m18["threshold_age"] in young.messages and young.indicative
    minor = sec(man37(birth_date=date(2012, 1, 1)), al.Measures(thigh_cm=50.0), "Μηρός")
    assert minor.lines == (("Μέτρηση", "50,0 cm"),) and m18["record_only"] in minor.messages
    no = sec(man37(), al.Measures(), "Μηρός")
    assert m18["no_value"] in no.messages and "Αναμενόμενο στο σημερινό βάρος" not in dict(no.lines)


def test_e19_document_table9_and_swollen():
    m19 = e19.load_data()["messages"]
    s = sec(man37(**ATH), al.Measures(knee_cm=48.0), "Πάνω από το γόνατο")
    assert s.lines[0] == ("Μέτρηση", "48,0 cm") and s.messages == (m19["A"],)
    assert s.lines[1][0] == "Αναμενόμενο πάνω από το γόνατο στα 79,3 kg" and s.lines[1][1].startswith("≈ 39,")
    sw = sec(man37(**ATH), al.Measures(knee_cm=48.0, knee_swollen=True), "Πάνω από το γόνατο")
    assert sw.lines == (("Μέτρηση", "48,0 cm"),) and sw.messages == (m19["swollen"],)
    assert sec(man37(weight_kg=80.0, fat_percent=15.0), al.Measures(), "Πάνω από το γόνατο") is None
    est_only = sec(man37(), al.Measures(), "Πάνω από το γόνατο")  # χωρίς μέτρηση, με εκτίμηση
    assert m19["no_value"] in est_only.messages and est_only.lines[0][0].startswith("Αναμενόμενο πάνω")


def test_screen_batch5(monkeypatch):
    vals = {**WOMAN, "m_wrist": 15.5, "m_thigh18": 58.0, "m_knee": 42.0, "m_knee_swollen": True}
    f = run_app(monkeypatch, vals)
    md = [a[0] for n, a, k in f.shown if n == "markdown"]
    subs = [a[0] for n, a, k in f.shown if n == "subheader"]
    assert not f.errors and {"Καρπός (Στοιχείο 17)", "Μηρός (Στοιχείο 18)", "Πάνω από το γόνατο (Στοιχείο 19)"} <= set(subs)
    assert "**Μέτρηση:** 58,0 cm" in md and e19.load_data()["messages"]["swollen"] in f.texts()
    where = {label: g for g, label in f.inputs}
    assert all(where[x].startswith("4.") for x in ("Καρπός (cm)", "Μηρός — 1 cm κάτω από τη γλουτιαία πτυχή (cm)",
                                                    "Πάνω από το γόνατο (cm)"))


# ---- Δόση 6: Στοιχεία 20 (γάμπα), 21 (αστράγαλος) ----
from davinci import element_20 as e20  # noqa: E402
from davinci import element_21 as e21  # noqa: E402


def test_e20_document_table11():
    m20 = e20.load_data()["messages"]
    s = sec(man139(**ATH), al.Measures(calf_cm=45.5), "Γάμπα")
    d = dict(s.lines)
    assert d["Μέτρηση"] == "45,5 cm" and d["Διορθωμένη για τον ΔΜΣ"] == "33,5 cm"
    assert d["Ταξινόμηση"] == "Μέτρια χαμηλή" and d["Τιμή για «φυσιολογική» σήμερα"] == "≥ 46,0 cm"
    assert d["Αναμενόμενο στο σημερινό βάρος"] == "48,3 cm (46,4 – 50,2)"
    assert m20["M"] in s.messages and m20["C"] in s.messages
    secs, _ = al.measurement_sections(man139(**ATH), al.Measures(calf_cm=45.5))
    assert any(m20["A"] in x.messages for x in secs)  # κοινό μήνυμα ANSUR: εμφανίζεται μία φορά
    assert s.indicative  # ΔΜΣ σήμερα εκτός εύρους ANSUR II
    t = sec(man37(**ATH), al.Measures(calf_cm=45.5), "Γάμπα")  # στόχος 79,3 kg όπως στο έγγραφο
    assert dict(t.lines)["Αναμενόμενη γάμπα στα 79,3 kg"] == (
        "≥ 37,7 cm (εκτίμηση 37,7, εύρος 36,2 – 39,2 · για «φυσιολογική» ≥ 37,0 cm)")
    assert dict(t.lines)["Αναμενόμενη γάμπα στα 67,8 kg"] == (
        "≥ 35,2 cm (εκτίμηση 35,2, εύρος 33,8 – 36,6 · για «φυσιολογική» ≥ 34,0 cm)")
    lean = dict(sec(man37(weight_kg=77.0, fat_percent=15.0), al.Measures(calf_cm=36.0), "Γάμπα").lines)  # ΔΜΣ 24,6
    assert lean["Τιμή για «φυσιολογική» σήμερα"] == "≥ 34,0 cm" and lean["Διορθωμένη για τον ΔΜΣ"] == "36,0 cm"


def test_e20_minimum_is_normal_value_when_higher():
    s = sec(man37(**ATH), al.Measures(), "Γάμπα")
    for (label, value), est, normal in zip(
            [x for x in s.lines if x[0].startswith("Αναμενόμενη")],
            e20.assess(None, 138.9, al._user(man37(**ATH)), [79.3, 67.8]).estimates, (37.0, 34.0)):
        assert value.startswith(f"≥ {_n1(max(est.value_cm, normal))} cm")


def test_e20_health_cases():
    m20 = e20.load_data()["messages"]
    h = sec(man37(), al.Measures(calf_cm=40.0), "Γάμπα")  # Υγεία: «≈», χωρίς «≥»
    assert all(v.startswith("≈ ") for k, v in h.lines if k.startswith("Αναμενόμενη"))
    assert "Αναμενόμενη γάμπα στα 81,5 kg" in dict(h.lines)
    ed = sec(man37(), al.Measures(calf_cm=45.5, leg_edema=True), "Γάμπα")
    assert ed.lines == (("Μέτρηση", "45,5 cm"),) and ed.messages == (m20["edema"],) and not ed.indicative
    minor = sec(man37(birth_date=date(2012, 1, 1)), al.Measures(calf_cm=35.0), "Γάμπα")
    assert minor.lines == (("Μέτρηση", "35,0 cm"),) and minor.messages == (m20["record_only"],)
    no = sec(man37(), al.Measures(), "Γάμπα")
    d = dict(no.lines)
    assert m20["no_value"] in no.messages and "Ταξινόμηση" not in d and "Αναμενόμενο στο σημερινό βάρος" not in d
    assert "Τιμή για «φυσιολογική» σήμερα" not in d
    assert sec(man37(weight_kg=80.0, fat_percent=15.0), al.Measures(), "Γάμπα") is None


def test_e21_document_table10():
    m21 = e21.load_data()["messages"]
    s = sec(man139(**ATH), al.Measures(ankle_cm=26.5), "Αστράγαλος")
    d = dict(s.lines)
    # έγγραφο 25,5 – 27,8: το έγγραφο στρογγύλεψε πρώτα την εκτίμηση (βλ. NOTES, Στοιχείο 21)
    assert d["Μέτρηση"] == "26,5 cm" and d["Αναμενόμενο στο σημερινό βάρος"] == "26,6 cm (25,5 – 27,7)"
    t = dict(sec(man37(**ATH), al.Measures(ankle_cm=26.5), "Αστράγαλος").lines)
    assert t["Αναμενόμενος αστράγαλος στα 79,3 kg"] == "≈ 22,2 cm (21,2 – 23,1)"
    assert m21["A"] in s.messages and m21["T"] not in s.messages and s.indicative
    assert al.ankle_field_note() == m21["T"]


def test_e21_edema_injury_and_cases():
    m21 = e21.load_data()["messages"]
    x = sec(man37(), al.Measures(ankle_cm=26.5, leg_edema=True, ankle_injured=True), "Αστράγαλος")
    assert x.lines == (("Μέτρηση", "26,5 cm"),) and x.messages == (m21["edema"], m21["injury"])
    inj = sec(man37(), al.Measures(ankle_cm=26.5, ankle_injured=True), "Αστράγαλος")
    assert m21["injury"] in inj.messages and m21["edema"] not in inj.messages
    minor = sec(man37(birth_date=date(2012, 1, 1)), al.Measures(ankle_cm=22.0), "Αστράγαλος")
    assert minor.lines == (("Μέτρηση", "22,0 cm"),) and minor.messages == (m21["record_only"],)
    no = sec(man37(), al.Measures(), "Αστράγαλος")
    assert m21["no_value"] in no.messages and no.lines[0][0] == "Αναμενόμενο στο σημερινό βάρος"
    assert sec(man37(weight_kg=80.0, fat_percent=15.0), al.Measures(), "Αστράγαλος") is None


def test_screen_batch6(monkeypatch):
    vals = {**WOMAN, "m_calf": 36.0, "m_ankle": 21.5, "m_edema": True}
    f = run_app(monkeypatch, vals)
    subs = [a[0] for n, a, k in f.shown if n == "subheader"]
    assert not f.errors and {"Γάμπα (Στοιχείο 20)", "Αστράγαλος (Στοιχείο 21)"} <= set(subs)
    assert e20.load_data()["messages"]["edema"] in f.texts() and e21.load_data()["messages"]["edema"] in f.texts()
    assert e21.load_data()["messages"]["T"] in f.texts()  # δίπλα στο πεδίο
    where = {label: g for g, label in f.inputs}
    assert where["Γάμπα (cm)"].startswith("4.") and where["Αστράγαλος (cm)"].startswith("4.")
    f2 = run_app(monkeypatch, {**WOMAN, "m_ankle": 21.5, "m_ankle_injured": True})
    assert e21.load_data()["messages"]["injury"] in f2.texts() and e20.load_data()["messages"]["edema"] not in f2.texts()


# ---- Δόση 7: Στοιχεία 22–25 (λόγοι) ----
from davinci import element_22 as e22  # noqa: E402
from davinci import element_23 as e23  # noqa: E402
from davinci import element_24 as e24  # noqa: E402
from davinci import element_25 as e25  # noqa: E402

DOC = dict(waist_cm=146.0, hip_cm=142.7, chest_cm=131.5, shoulders_cm=138.0)


def test_e22_document_table8():
    m22 = e22.load_data()["messages"]
    s = sec(man37(**ATH), al.Measures(**DOC), "Λόγος μέσης / ισχίου")
    d = dict(s.lines)
    assert d["Λόγος μέσης / ισχίου"] == "1,02" and d["Ταξινόμηση"] == "Ουσιαστικά αυξημένος κίνδυνος"
    # έγγραφο 99,0 / 89,1 και 92,1 / 82,9 από στρογγυλεμένο ισχίο (βλ. NOTES, Στοιχεία 11 και 22)· η Μ ίδια
    assert d["Μέση στα 79,3 kg (λίπος 13,0%)"] == (
        "κάτω από 88,5 cm (ΛΜΙ: κάτω από 89,0 · μέση/ύψος: κάτω από 88,5 · ισχίο ≈ 98,9)")
    assert d["Μέση στα 67,8 kg (λίπος 6,0%)"].startswith("κάτω από 82,8 cm (ΛΜΙ: κάτω από 82,8 ·")
    assert s.messages[0] == m22["U"].replace("είναι Χ,", "είναι 1,02,")
    assert m22["P"] in s.messages and m22["T"] in s.messages and not s.indicative and "Ηλικία" not in d
    assert any("κάτω από 89,0 cm" in x for x in s.messages)  # μήνυμα Μ με την πρώτη γραμμή


def test_e22_cases():
    m22 = e22.load_data()["messages"]
    h = sec(man37(weight_kg=80.0, fat_percent=15.0, ancestry="3a"), al.Measures(waist_cm=80.0, hip_cm=95.0),
            "Λόγος μέσης / ισχίου")
    assert dict(h.lines) == {"Λόγος μέσης / ισχίου": "0,84", "Ταξινόμηση": "Κάτω από το όριο του ΠΟΥ"}
    assert m22["asian"] in h.messages and h.indicative and m22["P"] not in h.messages
    w = sec(man37(), al.Measures(waist_cm=100.0), "Λόγος μέσης / ισχίου")
    assert m22["missing"] in w.messages and "Λόγος μέσης / ισχίου" not in dict(w.lines)
    minor = sec(man37(birth_date=date(2012, 1, 1)), al.Measures(waist_cm=70.0, hip_cm=80.0), "Λόγος μέσης / ισχίου")
    assert minor.lines == (("Λόγος μέσης / ισχίου", "0,88"),) and minor.messages == (m22["record_only"],)
    old = sec(man37(birth_date=date(1940, 1, 1), weight_kg=80.0, fat_percent=15.0),
              al.Measures(waist_cm=90.0, hip_cm=100.0), "Λόγος μέσης / ισχίου")
    assert dict(old.lines)["Ηλικία"] == "Εκτός δεδομένων αναφοράς"
    assert sec(man37(weight_kg=80.0, fat_percent=15.0), al.Measures(), "Λόγος μέσης / ισχίου") is None


def test_e23_document_table11():
    m23 = e23.load_data()["messages"]
    s = sec(man37(**ATH), al.Measures(**DOC), "Λόγος στήθους / μέσης")
    d = dict(s.lines)
    assert d["Λόγος στήθους / μέσης"] == "0,90" and d["Εκατοστημόριο ANSUR II"] == "κάτω από το 5ο"
    assert d["Ελάχιστος λόγος στα 79,3 kg"] == "≥ 1,16 (στήθος ≈ 102,9 cm · μέση κάτω από 88,5 cm)"
    assert d["Ελάχιστος λόγος στα 67,8 kg"] == "≥ 1,08 (στήθος ≈ 95,2 cm · μέση κάτω από 88,5 cm)"
    assert s.messages[0] == m23["A"].replace("Χο", "κάτω από το 5ο") and m23["P"] in s.messages
    assert any("τουλάχιστον 1,16." in x for x in s.messages)


def test_e23_women_no_target_rows_and_cases():
    m23 = e23.load_data()["messages"]
    w = sec(man37(sex="Γυναίκα", height_cm=165.0, weight_kg=90.0, fat_percent=40.0),
            al.Measures(chest_cm=100.0, waist_cm=90.0), "Λόγος στήθους / μέσης")
    assert [k for k, v in w.lines] == ["Λόγος στήθους / μέσης", "Εκατοστημόριο ANSUR II"]  # Πίνακας 7: χωρίς Ε
    assert m23["G"] in w.messages and not any("τουλάχιστον" in x for x in w.messages)
    one = sec(man37(), al.Measures(chest_cm=110.0), "Λόγος στήθους / μέσης")
    assert m23["missing"] in one.messages and "Εκατοστημόριο ANSUR II" not in dict(one.lines)
    nd = sec(man37(ancestry="5", birth_date=date(1960, 1, 1)), al.Measures(chest_cm=120.0, waist_cm=110.0),
             "Λόγος στήθους / μέσης")
    assert m23["ancestry_4_5"] in nd.messages and m23["age_59"] in nd.messages and nd.indicative


def test_e24_document_table12():
    m24 = e24.load_data()["messages"]
    s = sec(man37(**ATH), al.Measures(**DOC), "Λόγος ώμων / μέσης")
    d = dict(s.lines)
    assert d["Λόγος ώμων / μέσης"] == "0,95" and d["Εκατοστημόριο ANSUR II"] == "κάτω από το 5ο"
    # έγγραφο 114,7 / 1,30 με τον όρο ηλικίας του 14 (βλ. NOTES, Στοιχεία 14 και 24)
    assert d["Ελάχιστος λόγος στα 79,3 kg"] == "≥ 1,31 (ώμοι ≈ 116,3 cm · μέση κάτω από 88,5 cm)"
    assert d["Ελάχιστος λόγος στα 67,8 kg"] == "≥ 1,25 (ώμοι ≈ 110,9 cm · μέση κάτω από 88,5 cm)"
    for k in ("T", "P"):
        assert m24[k] in s.messages
    w = sec(man37(sex="Γυναίκα", height_cm=165.0, weight_kg=90.0, fat_percent=40.0),
            al.Measures(shoulders_cm=105.0, waist_cm=90.0), "Λόγος ώμων / μέσης")
    assert any(k.startswith("Ελάχιστος λόγος") for k, v in w.lines) and m24["G"] in w.messages  # Πίνακας 8: Ε


def test_e25_document_table10_and_cases():
    m25 = e25.load_data()["messages"]
    s = sec(man37(**ATH), al.Measures(biceps_flexed_cm=40.0, forearm_flexed_cm=33.0), "Λόγος πήχη / δικεφάλου")
    d = dict(s.lines)
    assert d["Λόγος πήχη / δικεφάλου (σφιγμένοι)"] == "0,83" and d["Εκατοστημόριο ANSUR II"] == "5ο–25ο"
    assert d["Αναμενόμενος λόγος στα 79,3 kg"] == "≈ 0,88 (πήχης 30,0 cm · δικέφαλος 34,1 cm)"
    assert d["Αναμενόμενος λόγος στα 67,8 kg"] == "≈ 0,90 (πήχης 28,3 cm · δικέφαλος 31,3 cm)"
    assert m25["L"] in s.messages and m25["P"] in s.messages and m25["T"] not in s.messages
    assert al.arm_field_note() == m25["T"]
    relaxed = sec(man37(), al.Measures(arm_relaxed_cm=40.0, forearm_relaxed_cm=32.6), "Λόγος πήχη / δικεφάλου")
    assert m25["missing"] in relaxed.messages and "Εκατοστημόριο ANSUR II" not in dict(relaxed.lines)
    inj = sec(man37(), al.Measures(biceps_flexed_cm=40.0, forearm_flexed_cm=33.0, arm_injured=True),
              "Λόγος πήχη / δικεφάλου")
    assert inj.lines == (("Λόγος πήχη / δικεφάλου (σφιγμένοι)", "0,83"),) and inj.messages == (m25["injury"],)
    assert sec(man37(weight_kg=80.0, fat_percent=15.0), al.Measures(), "Λόγος πήχη / δικεφάλου") is None


def test_screen_batch7(monkeypatch):
    vals = {**WOMAN, "m_waist": 90.0, "m_hip": 105.0, "m_chest": 100.0, "m_shoulders": 105.0,
            "m_biceps": 31.0, "m_fore_flx": 26.0}
    f = run_app(monkeypatch, vals)
    subs = [a[0] for n, a, k in f.shown if n == "subheader"]
    assert not f.errors and {"Λόγος μέσης / ισχίου (Στοιχείο 22)", "Λόγος στήθους / μέσης (Στοιχείο 23)",
                             "Λόγος ώμων / μέσης (Στοιχείο 24)", "Λόγος πήχη / δικεφάλου (Στοιχείο 25)"} <= set(subs)
    assert e25.load_data()["messages"]["T"] in f.texts()  # δίπλα στα πεδία
    md = [a[0] for n, a, k in f.shown if n == "markdown"]
    assert "**Λόγος μέσης / ισχίου:** 0,86" in md and "**Ταξινόμηση:** Ουσιαστικά αυξημένος κίνδυνος" in md
    f2 = run_app(monkeypatch, {**vals, "m_arm_injured": True})
    assert e25.load_data()["messages"]["injury"] in f2.texts()


def test_ratios_shown_without_measurements_when_targets_exist():
    m22, m24 = e22.load_data()["messages"], e24.load_data()["messages"]
    s = sec(man37(), al.Measures(), "Λόγος μέσης / ισχίου")  # Υγεία, στόχος 81,5 kg: μόνο η πληροφορία μέσης
    assert m22["missing"] in s.messages and s.lines[0][0].startswith("Μέση στα 81,5 kg")
    one = sec(man37(), al.Measures(shoulders_cm=130.0), "Λόγος ώμων / μέσης")
    assert m24["missing"] in one.messages and "Εκατοστημόριο ANSUR II" not in dict(one.lines)
    lean = sec(man37(weight_kg=80.0, fat_percent=15.0), al.Measures(shoulders_cm=120.0), "Λόγος ώμων / μέσης")
    assert lean.lines == () and lean.messages[0] == m24["missing"]  # χωρίς στόχο, μόνο ένα πεδίο


# ---- Δόση 8: Στοιχεία 26–29 (λόγοι άκρων) ----
from davinci import element_26 as e26  # noqa: E402
from davinci import element_27 as e27  # noqa: E402
from davinci import element_28 as e28  # noqa: E402
from davinci import element_29 as e29  # noqa: E402

LIMBS = dict(thigh_cm=60.0, calf_cm=40.0, wrist_cm=18.0, biceps_flexed_cm=38.0, ankle_cm=23.0, knee_cm=40.0)


def test_e26_to_e29_document_examples():
    m = al.Measures(**LIMBS)
    exp = {  # Πίνακες 9 (26), 11 (27), 11 (28), 11 (29): Αθλητικό 13% και 6%
        "Λόγος μηρού / γάμπας": ("1,50", "5ο–25ο", "≈ 1,56 (μηρός 58,9 cm · γάμπα 37,7 cm)",
                                 "≈ 1,52 (μηρός 53,6 cm · γάμπα 35,2 cm)"),
        "Λόγος καρπού / δικεφάλου": ("0,47", "25ο–50ό", "≈ 0,51 (καρπός 17,4 cm · δικέφαλος 34,1 cm)",
                                     "≈ 0,54 (καρπός 16,9 cm · δικέφαλος 31,3 cm)"),
        "Λόγος αστραγάλου / γάμπας": ("0,58", "25ο–50ό", "≈ 0,59 (αστράγαλος 22,2 cm · γάμπα 37,7 cm)",
                                      "≈ 0,60 (αστράγαλος 21,1 cm · γάμπα 35,2 cm)"),
        # έγγραφο 39,3 / 36,5: διαφορά 0,1 από το ακριβές βάρος-στόχο, όπως στο 19 (βλ. NOTES)· ο λόγος ίδιος
        "Λόγος μηρού / γονάτου": ("1,50", "25ο–50ό", "≈ 1,50 (μηρός 58,9 cm · πάνω από το γόνατο 39,2 cm)",
                                  "≈ 1,47 (μηρός 53,6 cm · πάνω από το γόνατο 36,4 cm)"),
    }
    for title, (ratio, band, r1, r2) in exp.items():
        s = sec(man37(**ATH), m, title)
        assert s.lines[0][1] == ratio and dict(s.lines)["Εκατοστημόριο ANSUR II"] == band, title
        assert s.lines[2] == ("Αναμενόμενος λόγος στα 79,3 kg", r1) and s.lines[3][1] == r2, title
    m26, m27, m28 = e26.load_data()["messages"], e27.load_data()["messages"], e28.load_data()["messages"]
    s26 = sec(man37(**ATH), m, "Λόγος μηρού / γάμπας")
    assert m26["P"] in s26.messages and m26["T"] not in s26.messages
    s27 = sec(man37(**ATH), m, "Λόγος καρπού / δικεφάλου")
    assert m27["S"] in s27.messages and m27["P"] in s27.messages and m27["T"] not in s27.messages
    s28 = sec(man37(**ATH), m, "Λόγος αστραγάλου / γάμπας")
    assert m28["S"] in s28.messages and m28["N"] in s28.messages and m28["T"] not in s28.messages
    s29 = sec(man37(**ATH), m, "Λόγος μηρού / γονάτου")
    assert e29.load_data()["messages"]["T"] not in s29.messages and e29.load_data()["messages"]["S"] in s29.messages
    for k in (26, 27, 28, 29):
        assert al.field_note(k) == importlib.import_module(f"davinci.element_{k}").load_data()["messages"]["T"]


def test_e26_e28_leg_exclusions():
    m26, m28 = e26.load_data()["messages"], e28.load_data()["messages"]
    ed = al.Measures(**LIMBS, leg_edema=True)
    assert sec(man37(), ed, "Λόγος μηρού / γάμπας").lines == () and \
        sec(man37(), ed, "Λόγος μηρού / γάμπας").messages == (m26["edema"],)
    assert sec(man37(), ed, "Λόγος αστραγάλου / γάμπας").messages == (m28["edema"],)
    for flag in ("leg_injured", "ankle_injured"):
        inj = al.Measures(**LIMBS, **{flag: True})
        s26 = sec(man37(), inj, "Λόγος μηρού / γάμπας")
        assert s26.lines == (("Λόγος μηρού / γάμπας", "1,50"),) and s26.messages == (m26["injury"],), flag
        assert sec(man37(), inj, "Λόγος αστραγάλου / γάμπας").lines == (), flag  # 28: δεν υπολογίζεται
    lip = sec(man37(sex="Γυναίκα", height_cm=165.0, weight_kg=90.0, fat_percent=40.0),
              al.Measures(**LIMBS, lipedema=True), "Λόγος αστραγάλου / γάμπας")
    assert lip.lines == (("Λόγος αστραγάλου / γάμπας", "0,58"),) and lip.messages == (m28["lipedema"],)
    both = sec(man37(), al.Measures(**LIMBS, lipedema=True, leg_edema=True), "Λόγος αστραγάλου / γάμπας")
    assert both.messages == (m28["edema"],)  # προηγείται το οίδημα (σύμβαση του 28)
    high = sec(man37(), al.Measures(ankle_cm=30.0, calf_cm=40.0), "Λόγος αστραγάλου / γάμπας")
    assert m28["U"] in high.messages  # 0,75 > 0,68


def test_e27_e29_exclusions_and_missing():
    m27, m29 = e27.load_data()["messages"], e29.load_data()["messages"]
    inj = sec(man37(), al.Measures(**LIMBS, arm_injured=True), "Λόγος καρπού / δικεφάλου")
    assert inj.lines == (("Λόγος καρπού / δικεφάλου (σφιγμένος)", "0,47"),) and inj.messages == (m27["injury"],)
    knee = sec(man37(), al.Measures(**LIMBS, knee_swollen=True), "Λόγος μηρού / γονάτου")
    assert knee.lines == () and knee.messages == (m29["knee"],)
    lip = sec(man37(sex="Γυναίκα", height_cm=165.0, weight_kg=90.0, fat_percent=40.0),
              al.Measures(**LIMBS, lipedema=True), "Λόγος μηρού / γονάτου")
    assert lip.messages == (m29["lipedema"],) and lip.lines == (("Λόγος μηρού / γονάτου", "1,50"),)
    relaxed = sec(man37(), al.Measures(wrist_cm=18.0, arm_relaxed_cm=40.0), "Λόγος καρπού / δικεφάλου")
    assert m27["missing"] in relaxed.messages and "Εκατοστημόριο ANSUR II" not in dict(relaxed.lines)
    lean = al.Measures(knee_cm=40.0)
    one = sec(man37(weight_kg=80.0, fat_percent=15.0), lean, "Λόγος μηρού / γονάτου")
    assert one.lines == () and one.messages[0] == m29["missing"]
    for title in ("Λόγος μηρού / γάμπας", "Λόγος καρπού / δικεφάλου", "Λόγος αστραγάλου / γάμπας",
                  "Λόγος μηρού / γονάτου"):
        assert sec(man37(weight_kg=80.0, fat_percent=15.0), al.Measures(), title) is None, title
        assert sec(man37(), al.Measures(), title).lines[0][0].startswith("Αναμενόμενος λόγος"), title


def test_e26_e28_e29_single_field_shows_missing():
    lean = dict(weight_kg=80.0, fat_percent=15.0)
    for title, field, msgs in (("Λόγος μηρού / γάμπας", "calf_cm", e26), ("Λόγος αστραγάλου / γάμπας", "ankle_cm", e28),
                               ("Λόγος μηρού / γονάτου", "thigh_cm", e29), ("Λόγος καρπού / δικεφάλου", "wrist_cm", e27)):
        s = sec(man37(**lean), al.Measures(**{field: 30.0}), title)
        assert s.messages[0] == msgs.load_data()["messages"]["missing"], title


def test_screen_batch8(monkeypatch):
    vals = {**WOMAN, "m_thigh18": 60.0, "m_calf": 38.0, "m_wrist": 15.5, "m_biceps": 30.0, "m_ankle": 22.0,
            "m_knee": 40.0}
    f = run_app(monkeypatch, vals)
    subs = [a[0] for n, a, k in f.shown if n == "subheader"]
    assert not f.errors and {"Λόγος μηρού / γάμπας (Στοιχείο 26)", "Λόγος καρπού / δικεφάλου (Στοιχείο 27)",
                             "Λόγος αστραγάλου / γάμπας (Στοιχείο 28)", "Λόγος μηρού / γονάτου (Στοιχείο 29)"} <= set(subs)
    for k in (26, 27, 28, 29):
        assert al.field_note(k) in f.texts(), k
    f2 = run_app(monkeypatch, {**vals, "m_lipedema": True, "m_leg_injured": True})
    assert e29.load_data()["messages"]["lipedema"] in f2.texts() and e26.load_data()["messages"]["injury"] in f2.texts()
    man = run_app(monkeypatch, {**vals, "sex": "Άνδρας", "m_lipedema": True})  # το πεδίο μόνο στις γυναίκες
    assert e29.load_data()["messages"]["lipedema"] not in man.texts()


# ---- Δόση 9: Στοιχεία 30, 31, 32 (Professional) ----
from davinci import element_30 as e30  # noqa: E402
from davinci import element_31 as e31  # noqa: E402
from davinci import element_32 as e32  # noqa: E402


def test_e30_e32_document_table10():
    m30, p = e30.load_data()["messages"], e32.load_data()["messages"]["P"]
    s = sec(man139(**PRO), al.Measures(elbow_cm=7.4), "Σκελετός — εύρος αγκώνα")
    assert s.lines == (("Εύρος αγκώνα", "7,4 cm"), ("Σκελετός", "Μεσαίος"),
                       ("Όρια (NHANES III)", "Μικρός ≤ 6,9 · Μεσαίος · Μεγάλος ≥ 7,9 cm"))
    assert s.messages == (p.replace("[κατηγορία]", "Μεσαίος"), m30["HP1"]) and s.indicative
    t = sec(man139(**PRO), al.Measures(elbow_cm=7.0), "Σκελετός — εύρος αγκώνα")
    assert dict(t.lines)["Σκελετός (Δαλματία)"] == "Μικρός"
    assert t.messages[1:] == (m30["HP1"], m30["D"].replace("[κατηγορία]", "Μικρός"), m30["O"])
    forty = sec(man139(birth_date=date(1985, 1, 1), **PRO), al.Measures(elbow_cm=7.4), "Σκελετός — εύρος αγκώνα")
    assert dict(forty.lines)["Όρια (NHANES III)"] == "Μικρός ≤ 7,0 · Μεσαίος · Μεγάλος ≥ 7,9 cm"  # από τα 40
    none = sec(man139(**PRO), al.Measures(), "Σκελετός — εύρος αγκώνα")
    assert none.lines == (("Σκελετός", "Δεν έχει οριστεί"),) and none.messages == (m30["S"],) and not none.indicative


def test_e30_cases_and_normal_level():
    m30 = e30.load_data()["messages"]
    w = sec(man37(sex="Γυναίκα", height_cm=165.0, ancestry="3a", birth_date=date(2007, 6, 1), **PRO),
            al.Measures(elbow_cm=7.0, elbow_left_arm=True), "Σκελετός — εύρος αγκώνα")
    assert dict(w.lines)["Σκελετός"] == "Μεγάλος" and "Σκελετός (Δαλματία)" not in dict(w.lines)
    for k in ("HP2", "E", "Y", "A"):
        assert m30[k] in w.messages, k
    old = sec(man37(ancestry="2", birth_date=date(1940, 1, 1), weight_kg=80.0, fat_percent=20.0, **PRO),
              al.Measures(elbow_cm=7.5), "Σκελετός — εύρος αγκώνα")
    assert m30["X"] in old.messages and dict(old.lines)["Όρια (NHANES III)"] == "Μικρός ≤ 7,0 · Μεσαίος · Μεγάλος ≥ 7,9 cm"
    cond = sec(man37(**PRO), al.Measures(elbow_cm=7.4, elbow_condition=True), "Σκελετός — εύρος αγκώνα")
    assert cond.lines == (("Εύρος αγκώνα", "7,4 cm"), ("Σκελετός", "Δεν έχει οριστεί")) and cond.messages == (m30["T"],)
    minor = sec(man37(birth_date=date(2012, 1, 1), **PRO), al.Measures(elbow_cm=6.0), "Σκελετός — εύρος αγκώνα")
    assert minor.messages == (m30["R"],)
    assert sec(man37(), al.Measures(elbow_cm=7.4), "Σκελετός — εύρος αγκώνα") is None  # Normal
    assert sec(man37(), al.Measures(knee_breadths=(10.0, 10.1)), "Εύρος γονάτου") is None


def test_e17_frame_from_elbow():
    s17 = e32.load_data()["messages"]["S"]
    w = sec(man37(**PRO), al.Measures(wrist_cm=18.6, elbow_cm=7.4), "Καρπός")
    assert dict(w.lines)["Σκελετός"] == "Μεσαίος (από το εύρος αγκώνα, Στοιχείο 32)" and s17 not in w.messages
    n = sec(man37(), al.Measures(wrist_cm=18.6, elbow_cm=7.4), "Καρπός")  # Normal: ο αγκώνας δεν μετράει
    assert dict(n.lines)["Σκελετός"] == "Δεν έχει οριστεί" and s17 in n.messages
    c = sec(man37(**PRO), al.Measures(wrist_cm=18.6, elbow_cm=7.4, elbow_condition=True), "Καρπός")
    assert dict(c.lines)["Σκελετός"] == "Δεν έχει οριστεί"


def test_e31_knee_breadth():
    m31 = e31.load_data()["messages"]
    s = sec(man139(**PRO), al.Measures(knee_breadths=(10.0, 10.1)), "Εύρος γονάτου")
    assert s.lines == (("Μετρήσεις", "10,0 · 10,1 cm"), ("Τιμή για τη Μεσομορφία", "10,05 cm"),
                       ("Ποιος μέτρησε · πλευρά", "Άλλο άτομο · δεξί πόδι"))
    assert s.messages == (m31["normal"], m31["high_bmi"])
    three = sec(man37(weight_kg=80.0, fat_percent=15.0, **PRO),
                al.Measures(knee_breadths=(10.0, 10.5, 10.2), knee_measured_by="Ο ίδιος", knee_side="αριστερό",
                            knee_breadth_edema=True), "Εύρος γονάτου")
    assert dict(three.lines)["Τιμή για τη Μεσομορφία"] == "10,2 cm (αβέβαιη)"
    assert dict(three.lines)["Ποιος μέτρησε · πλευρά"] == "Ο ίδιος · αριστερό πόδι"
    assert three.messages == (m31["normal"], m31["self"], m31["edema"])
    far = sec(man37(**PRO), al.Measures(knee_breadths=(10.0, 10.5)), "Εύρος γονάτου")
    assert far.messages == (m31["third"],) and len(far.lines) == 1
    one = sec(man37(**PRO), al.Measures(knee_breadths=(10.0,)), "Εύρος γονάτου")
    assert one.lines == (("Μέτρηση", "10,0 cm"),) and one.warnings and one.warnings[0].startswith("Χρειάζονται δύο")
    out = sec(man37(**PRO), al.Measures(knee_breadths=(1.0, 1.0)), "Εύρος γονάτου")
    assert out.messages == (m31["out_of_range"],)
    inj = sec(man37(**PRO), al.Measures(knee_breadths=(10.0, 10.0), knee_breadth_injured=True), "Εύρος γονάτου")
    assert inj.messages == (m31["injury"],)
    left = sec(man37(**PRO), al.Measures(knee_breadths=(10.0, 10.0), knee_breadth_injured=True, knee_side="αριστερό"),
               "Εύρος γονάτου")
    assert dict(left.lines)["Τιμή για τη Μεσομορφία"] == "10,0 cm (αβέβαιη)"
    preg = sec(man37(sex="Γυναίκα", height_cm=165.0, pregnant=True, **PRO), al.Measures(knee_breadths=(9.0, 9.0)),
               "Εύρος γονάτου")
    assert m31["pregnancy"] in preg.messages
    none = sec(man37(**PRO), al.Measures(), "Εύρος γονάτου")
    assert none.lines == () and none.messages == (m31["not_measured"],)


def test_screen_batch9(monkeypatch):
    vals = {**WOMAN, "level": "Professional", "p_elbow": 6.5, "p_knee1": 9.0, "p_knee2": 9.1}
    f = run_app(monkeypatch, vals)
    subs = [a[0] for n, a, k in f.shown if n == "subheader"]
    assert not f.errors and {"Σκελετός — εύρος αγκώνα (Στοιχεία 30, 32)", "Εύρος γονάτου (Στοιχείο 31)"} <= set(subs)
    md = [a[0] for n, a, k in f.shown if n == "markdown"]
    assert "**Σκελετός:** Μεσαίος" in md and "**Ποιος μέτρησε · πλευρά:** Άλλο άτομο · δεξί πόδι" in md
    where = {label: g for g, label in f.inputs}
    assert where["Εύρος αγκώνα (cm)"].startswith("6.") and where["Εύρος γονάτου — 1η μέτρηση (cm)"].startswith("6.")
    assert "ⓘ " + e30.info()["info_title"] in f.expanders and "ⓘ " + e31.info()["info_title"] in f.expanders
    f2 = run_app(monkeypatch, {**vals, "p_knee_by": "Ο ίδιος", "p_elbow_left": True})
    assert e31.load_data()["messages"]["self"] in f2.texts() and e30.load_data()["messages"]["A"] in f2.texts()
    normal = run_app(monkeypatch, {**WOMAN, "p_elbow": 6.5})
    assert "Εύρος αγκώνα (cm)" not in {label for g, label in normal.inputs}


# ---- Δόση 10: Στοιχεία 33–36 (δερματοπτυχές, Professional) ----
from davinci import element_33 as e33  # noqa: E402
from davinci import element_34 as e34  # noqa: E402
from davinci import element_35 as e35  # noqa: E402
from davinci import element_36 as e36  # noqa: E402

SF = al.Skinfold
HARP = dict(sf_isak=True, sf_caliper="Harpenden / Holtain")


def man30(**kw):  # τα παραδείγματα των εγγράφων 33 και 36: άνδρας 30 ετών, 178 cm, ΔΜΣ 24
    return man37(birth_date=date(1996, 1, 1), height_cm=178.0, weight_kg=76.0, fat_percent=15.0, **PRO, **kw)


def test_e33_e36_document_examples():
    m = al.Measures(**HARP, triceps=SF((10.2, 10.6)), calf_skinfold=SF((7.0, 7.2)), calf_cm=38.0)
    t = sec(man30(), m, "Δερματοπτυχή τρικεφάλου")
    d = dict(t.lines)
    assert d["Τιμή"] == "10,4 mm" and d["Εκατοστημόριο (ΗΠΑ 2007–2010, 30–39 ετών)"] == "28ο" and t.indicative
    m33 = e33.load_data()["messages"]
    assert t.messages[1] == m33["indicative"].replace("[λόγος]", "ISAK έναντι πρωτοκόλλου NHANES")
    assert t.table[1] == ("Βαλένθια (10ο / 50ό / 90ό)", "5,2 / 8,0 / 13,0 mm", "Garrido-Chamorro 2012")
    assert "Εκατοστημόριο ανά καταγωγή (λευκοί μη ισπανόφωνοι, 20–39 ετών)" in d
    c = sec(man30(), m, "Δερματοπτυχή γάμπας")
    dc = dict(c.lines)
    assert dc["Τιμή"] == "7,1 mm" and dc["Εκατοστημόριο (Καναδάς 2007–2009, ΔΜΣ κάτω από 30, 20–39 ετών)"] == "37ο"
    assert dc["Μέσος όρος (Ιταλία 2024, 30–34 ετών)"] == "8,4 ± 5,0 mm" and dc["Διορθωμένη περιφέρεια γάμπας"] == "37,29 cm"
    assert any("1,3 mm κάτω από τον μέσο όρο" in x for x in c.messages)


def test_e34_e35_display():
    m = al.Measures(**HARP, subscapular=SF((12.0, 12.0)), supraspinale=SF((9.0, 9.0)), supraspinale_site_confirmed=True)
    s = sec(man30(), m, "Δερματοπτυχή υποπλάτιου")
    assert dict(s.lines)["Εκατοστημόριο (ΗΠΑ 2007–2010, 30–39 ετών)"] == "17ο" and s.table[0][0].startswith("Αθλητές")
    p = sec(man30(), m, "Δερματοπτυχή υπερακάνθιου")
    assert dict(p.lines)["Μέσος όρος (Ιταλία 2024, 30–34 ετών)"] == "15,6 ± 8,4 mm"
    assert not any(k.startswith("Εκατοστημόριο") for k, v in p.lines)  # Στοιχείο 35: χωρίς εκατοστημόριο
    unknown = sec(man30(), al.Measures(**HARP, supraspinale=SF((9.0, 9.0))), "Δερματοπτυχή υπερακάνθιου")
    assert any(e35.load_data()["reasons"]["site_unknown"] in x for x in unknown.messages)


def test_skinfold_input_cases():
    m33 = e33.load_data()["messages"]
    third = sec(man30(), al.Measures(**HARP, triceps=SF((10.0, 11.0))), "Δερματοπτυχή τρικεφάλου")
    assert third.lines == (("Μετρήσεις", "10,0 · 11,0 mm"),) and third.messages == (m33["third"],)
    three = sec(man30(), al.Measures(**HARP, triceps=SF((10.0, 11.0, 10.6))), "Δερματοπτυχή τρικεφάλου")
    assert dict(three.lines)["Τιμή"] == "10,5 mm"
    odd = sec(man30(), al.Measures(**HARP, triceps=SF((60.0, 60.0))), "Δερματοπτυχή τρικεφάλου")
    assert odd.messages == (m33["unusual"].replace("[X]", "60,0"),)
    ok = sec(man30(), al.Measures(**HARP, triceps=SF((60.0, 60.0), confirmed=True)), "Δερματοπτυχή τρικεφάλου")
    assert dict(ok.lines)["Εκατοστημόριο (ΗΠΑ 2007–2010, 30–39 ετών)"] == "πάνω από το 95ο · αβέβαιη"
    no_cal = sec(man30(), al.Measures(sf_isak=True, triceps=SF((10.0, 10.0))), "Δερματοπτυχή τρικεφάλου")
    assert no_cal.warnings and no_cal.warnings[0].startswith("Δαγκάνα:")
    one = sec(man30(), al.Measures(**HARP, triceps=SF((10.0,))), "Δερματοπτυχή τρικεφάλου")
    assert one.warnings[0].startswith("Χρειάζονται δύο μετρήσεις") and one.lines == (("Μετρήσεις", "10,0 mm"),)
    nm = sec(man30(), al.Measures(**HARP, triceps=SF(not_measured=True)), "Δερματοπτυχή τρικεφάλου")
    assert nm.lines == () and nm.messages == (m33["not_measured"],)
    assert sec(man30(), al.Measures(**HARP), "Δερματοπτυχή τρικεφάλου") is None
    assert sec(man30(), al.Measures(calf_skinfold=SF(not_measured=True)), "Δερματοπτυχή γάμπας") is None  # 36: χωρίς μήνυμα
    normal = man37(birth_date=date(1996, 1, 1), height_cm=178.0, weight_kg=76.0, fat_percent=15.0)
    assert sec(normal, al.Measures(**HARP, triceps=SF((10.0, 10.0))), "Δερματοπτυχή τρικεφάλου") is None


def test_skinfold_indicative_reasons_and_special_cases():
    m33, m36 = e33.load_data()["messages"], e36.load_data()["messages"]
    lange = sec(man30(ancestry="3a"), al.Measures(sf_isak=None, sf_caliper="Lange", triceps=SF((10.0, 10.0), left_side=True,
                                                                                               edema=True)),
                "Δερματοπτυχή τρικεφάλου")
    text = " ".join(lange.messages)
    for reason in ("η μέτρηση δεν έγινε με το πρωτόκολλο ISAK", "δαγκάνα Lange", "μέτρηση στο αριστερό χέρι"):
        assert reason in text, reason
    assert m33["ancestry"] in lange.messages and m33["edema"] in lange.messages
    assert not any(k.startswith("Εκατοστημόριο ανά καταγωγή") for k, v in lange.lines)
    preg = sec(man37(sex="Γυναίκα", height_cm=165.0, pregnant=True, **PRO),
               al.Measures(**HARP, triceps=SF((20.0, 20.0)), postpartum_recent=True), "Δερματοπτυχή τρικεφάλου")
    assert preg.lines == (("Μετρήσεις", "20,0 · 20,0 mm"), ("Τιμή", "20,0 mm")) and preg.messages == (m33["pregnancy"],)
    post = sec(man37(sex="Γυναίκα", height_cm=165.0, **PRO), al.Measures(**HARP, triceps=SF((20.0, 20.0)),
                                                                       postpartum_recent=True), "Δερματοπτυχή τρικεφάλου")
    assert m33["postpartum"] in post.messages
    child = sec(man37(birth_date=date(2012, 1, 1), **PRO), al.Measures(**HARP, triceps=SF((10.0, 10.0))),
                "Δερματοπτυχή τρικεφάλου")
    assert m33["child"] in child.messages and child.table == () and "14 ετών" in child.lines[2][0]
    heavy = sec(man37(**PRO), al.Measures(**HARP, calf_skinfold=SF((20.0, 20.0)), calf_cm=45.0,
                                          calf_skinfold_at_max_girth=False, calf_varicose=True),
                "Δερματοπτυχή γάμπας")
    assert m36["bmi_30"] in heavy.messages and m36["varicose"] in heavy.messages
    assert dict(heavy.lines)["Διορθωμένη περιφέρεια γάμπας"] == (
        "43,00 cm (ενδεικτική: η δερματοπτυχή δεν μετρήθηκε στο ύψος της μέγιστης περιφέρειας)")
    assert any("μέτρηση στο αριστερό πόδι" in x for x in heavy.messages)  # κιρσοί → αριστερό πόδι
    ed = sec(man30(), al.Measures(**HARP, calf_skinfold=SF((7.0, 7.0), edema=True)), "Δερματοπτυχή γάμπας")
    assert m36["edema"] in ed.messages


def test_screen_batch10(monkeypatch):
    vals = {**WOMAN, "level": "Professional", "p_caliper": "Harpenden / Holtain", "p_isak": "Ναι",
            "p_tri1": 20.0, "p_tri2": 20.4, "p_sub1": 15.0, "p_sub2": 15.2, "p_sup1": 12.0, "p_sup2": 12.2,
            "p_sup_site": "Ναι", "p_calf1": 15.0, "p_calf2": 15.0, "m_calf": 37.0}
    f = run_app(monkeypatch, vals)
    subs = [a[0] for n, a, k in f.shown if n == "subheader"]
    assert not f.errors and {"Δερματοπτυχή τρικεφάλου (Στοιχείο 33)", "Δερματοπτυχή υποπλάτιου (Στοιχείο 34)",
                             "Δερματοπτυχή υπερακάνθιου (Στοιχείο 35)", "Δερματοπτυχή γάμπας (Στοιχείο 36)"} <= set(subs)
    assert e35.before_message() in f.texts() and e36.before_message() in f.texts()
    where = {label: g for g, label in f.inputs}
    assert where["Τρικέφαλος — 1η μέτρηση (mm)"].startswith("6.")
    for t in ("τρικεφάλου", "υποπλάτιου", "υπερακάνθιου", "γάμπας"):
        assert any(x.startswith("ⓘ") and t in x for x in f.expanders), t
    assert any(n == "dataframe" for n, a, k in f.shown)  # πίνακας αθλητών
    odd = run_app(monkeypatch, {**vals, "p_tri1": 60.0, "p_tri2": 60.0})
    assert e33.load_data()["messages"]["unusual"].replace("[X]", "60,0") in odd.texts()
    ok = run_app(monkeypatch, {**vals, "p_tri1": 60.0, "p_tri2": 60.0, "p_tri_ok": True})
    assert e33.load_data()["messages"]["unusual"].replace("[X]", "60,0") not in ok.texts()


def test_screen_batch10_defaults_and_options(monkeypatch):
    base = {**WOMAN, "level": "Professional", "p_caliper": "Harpenden / Holtain", "p_tri1": 20.0, "p_tri2": 20.0,
            "p_sup1": 12.0, "p_sup2": 12.0, "p_calf1": 15.0, "p_calf2": 15.0, "m_calf": 37.0}
    f = run_app(monkeypatch, base)  # προεπιλογές: ISAK «Δεν ξέρω», σημείο υπερακάνθιας «Δεν ξέρω»
    text = " ".join(f.texts())
    assert "η μέτρηση δεν έγινε με το πρωτόκολλο ISAK" in text and e35.load_data()["reasons"]["site_unknown"] in text
    g = run_app(monkeypatch, {**base, "p_isak": "Ναι", "p_sup_site": "Ναι", "p_calf_atmax": False,
                              "p_calf_varicose": True})
    text = " ".join(g.texts())
    assert "η μέτρηση δεν έγινε με το πρωτόκολλο ISAK" not in text and e35.load_data()["reasons"]["site_unknown"] not in text
    assert e36.load_data()["reasons"]["not_at_max_girth"] in text and e36.load_data()["messages"]["varicose"] in text
    nm = run_app(monkeypatch, {**WOMAN, "level": "Professional", "p_tri_nm": True})
    assert e33.load_data()["messages"]["not_measured"] in nm.texts()
