"""Τεστ για τις διορθώσεις του ελέγχου κώδικα–εγγράφων (11/11/2026).
02 Κανόνας 11 · 07 Συμπλήρωμα Α · 40 Κανόνας 17 · 42 Κανόνας 12 και Παράδειγμα 1 · 43 Κανόνας 16.
"""

from datetime import date

import pytest

from davinci import element_01 as e01
from davinci import element_02 as e02
from davinci import element_07 as e07
from davinci import element_40 as e40
from davinci import element_42 as e42
from davinci import element_43 as e43
from davinci.fmt import round_half_up as r

TODAY = date(2026, 11, 4)


def u(age=30, sex="Γυναίκα", height=165.0, **kw):
    base = dict(birth_date=date(TODAY.year - age, 1, 1), measurement_date=TODAY, sex=sex,
                height_cm=height, ancestry="1")
    base.update(kw)
    return e01.UserCategories(**base)


def _points(rate_kg_week, start=72.0, days=28):
    return [(d, start + rate_kg_week * d / 7) for d in range(days)]


# --- 02, Κανόνας 11: «≤ 3 μονάδες από όριο ταξινόμησης» και στους 6–17 -------------------------------
@pytest.mark.parametrize("sex", ["Άνδρας", "Γυναίκα"])
@pytest.mark.parametrize("age", [6, 10, 17])
def test_e02_rule_11_minors(sex, age):
    lo, _hi, high_from, very_from = e02.load_data()["children_tables"][sex][str(age)]
    kid = u(age=age, sex=sex, height=140.0)
    for b in (lo, high_from, very_from):
        assert e02.assess(b, kid).near_boundary
        assert e02.assess(b + 3.0, kid).near_boundary
    assert not e02.assess(very_from + 3.1, kid).near_boundary
    mid = (lo + high_from) / 2
    if min(mid - lo, high_from - mid) > 3.0:
        assert not e02.assess(mid, kid).near_boundary


def test_e02_rule_11_age_5_no_classification():
    assert not e02.assess(20.0, u(age=5, height=110.0)).near_boundary


# --- 07, Συμπλήρωμα Α: «Ανήλικοι / εγκυμοσύνη: καμία τιμή / μόνο καταγραφή» -------------------------
@pytest.mark.parametrize("flag", ["pregnant", "breastfeeding"])
def test_e07_no_dry_muscle_in_pregnancy_or_breastfeeding(flag):
    res = e07.assess(72.0, 38.0, u(**{flag: True}))
    assert res.muscle_kg is not None  # καταγραφή
    assert res.dry_muscle_kg is None and res.dry_muscle_range_kg is None and res.category is None
    dm = e07.load_data()["dry_muscle"]["messages"]
    assert not any(m in res.messages for m in dm.values())
    assert e07.assess(72.0, 38.0, u()).dry_muscle_kg is not None


# --- 40, Κανόνας 17: καμία πρόταση ελλείμματος στην εγκυμοσύνη ---------------------------------------
def test_e40_rule_17_pregnant_without_trimester_no_deficit():
    res = e40.assess(u(age=40, pregnant=True), 72.0, 1.4, goal="loss", aha_deficit=500)
    assert res.goal == "maintain" and res.daily_delta_kcal is None
    assert res.target_intake_kcal == res.tdee and res.indicative


def test_e40_rule_17_with_trimester_unchanged():
    res = e40.assess(u(age=40, pregnant=True), 72.0, 1.4, goal="loss", aha_deficit=500, trimester=2,
                     pre_pregnancy_weight_kg=68.0)
    assert res.goal == "maintain" and res.target_intake_kcal == res.tdee


# --- 42, Κανόνας 12: απώλεια στον θηλασμό μόνο με ≥ 4 εβδομάδες από τον τοκετό ----------------------
def test_e42_rule_12_breastfeeding_without_weeks_not_allowed():
    m = e42.load_data()["messages"]
    p = e42.partition("loss", 27.36, u(age=30, breastfeeding=True), trained=False, bmi=26.4, deficit_kcal_day=500)
    assert not p.allowed and p.messages == (m["lactation_no"],) and p.weekly_change_kg is None
    ok = e42.partition("loss", 27.36, u(age=30, breastfeeding=True), trained=False, bmi=26.4, deficit_kcal_day=500,
                       lactation_weeks_postpartum=6)
    assert ok.allowed and m["lactation_ok"] in ok.messages and ok.weekly_change_kg >= -0.5


def test_e42_example_1_exact_fat_mass():
    """Έγγραφο 42, Παράδειγμα 1: 72 kg × 38% = 27,36 kg («27,4») → f 27,5% · E 7.341 · 0,48 kg · με 750 kcal 0,72 kg."""
    f = e42.ffm_fraction_loss(72 * 0.38, False)
    e = e42.energy_per_kg(f)
    assert r(f * 100, 1) == 27.5 and r(e, 0) == 7341
    assert r(500 * 7 / e, 2) == 0.48 and r(750 * 7 / e, 2) == 0.72


# --- 43, Κανόνας 16: εγκυμοσύνη και κάτω των 18: καμία διόρθωση προς έλλειμμα ------------------------
@pytest.mark.parametrize("who", [dict(age=30, pregnant=True), dict(age=16, height=160.0)])
def test_e43_rule_16_no_correction_towards_deficit(who):
    res = e43.correct(2000, -0.48, 7341, _points(-0.10), u(**who), goal="loss")
    assert not res.changed and res.new_intake_kcal == 2000 and res.delta_kcal == 0.0


def test_e43_rule_16_adult_and_upward_correction_unchanged():
    adult = e43.correct(2000, -0.48, 7341, _points(-0.10), u(), goal="loss")
    assert adult.changed and adult.new_intake_kcal < 2000
    up = e43.correct(2000, -0.48, 7341, _points(-0.80), u(age=30, pregnant=True), goal="loss")
    assert up.changed and up.new_intake_kcal > 2000  # προς τα πάνω επιτρέπεται
