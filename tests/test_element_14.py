"""Τεστ Στοιχείου 14 (ώμοι)."""

import math
from datetime import date

import pytest

from davinci import element_01 as e01
from davinci import element_03 as e03
from davinci import element_14 as e14
from davinci.fmt import round_half_up as r1

TODAY = date(2026, 11, 4)
M = e14.load_data()["messages"]


def u(age=37, **kw):
    base = dict(birth_date=date(TODAY.year - age, 1, 1), measurement_date=TODAY,
                sex="Άνδρας", height_cm=177.0, ancestry="1")
    base.update(kw)
    return e01.UserCategories(**base)


def target_weight(fat):
    return e03._point(138.9, 60 / 138.9 * 100, fat, u(resistance_training=True)).weight_kg


# --- Πίνακας 9 του εγγράφου (Συμπλήρωμα Α, 10/11/2026) ---------------------------------
# Οι a και b του Πίνακα 3 βγαίνουν από το μοντέλο ΜΕ ηλικία (επανυπολογισμός από τα αρχεία ANSUR II,
# tools/check_ansur_models.py)· ο όρος ηλικίας εφαρμόζεται, οπότε ο κώδικας δίνει τον Πίνακα 9 ακριβώς.
# Πριν από τη διόρθωση ο κώδικας έδινε 138,1 · 120,9 · 116,4 · 110,9 · 118,4 · 114,2 cm.
@pytest.mark.parametrize("fat, doc, rng", [
    ("today", 136.1, None), (19.9, 119.2, (115.8, 122.6)), (13.0, 114.7, (111.4, 118.0)),
    (6.0, 109.3, (106.3, 112.5)), (16.0, 116.6, (113.4, 120.0)), (10.0, 112.5, (109.4, 115.8)),
])
def test_document_table_9(fat, doc, rng):
    w = 139.1 if fat == "today" else round(target_weight(fat), 1)
    e = e14.estimate(w, u())
    assert r1(e.value_cm) == doc
    if rng:
        assert abs(r1(e.range_cm[0]) - rng[0]) <= 0.1 + 1e-9 and abs(r1(e.range_cm[1]) - rng[1]) <= 0.1 + 1e-9


def test_today_measured_plus_1_4_percent():
    e = e14.estimate(139.1, u())
    assert r1((138.0 / e.value_cm - 1) * 100) == 1.4  # Πίνακας 9: «+1,4%, μέσα στο σφάλμα»


def test_today_measured_within_error():
    e = e14.estimate(139.1, u())
    assert e.range_cm[0] <= 138.0 <= e.range_cm[1]


# --- Τύποι ------------------------------------------------------------------------
def test_formula_women():
    user = u(sex="Γυναίκα", height_cm=165)
    expected = math.exp(4.9025 + 0.2886 * math.log(65 / 165) - 0.0006 * 37)
    e = e14.estimate(65, user)
    assert e.value_cm == pytest.approx(expected)
    assert e.range_cm == pytest.approx((expected * math.exp(-0.0299), expected * math.exp(0.0299)))


def test_age_term():
    """−0,0004 ανά έτος στους άνδρες, −0,0006 στις γυναίκες (Συμπλήρωμα Α)."""
    assert e14.estimate(80, u(age=55)).value_cm == pytest.approx(e14.estimate(80, u(age=20)).value_cm
                                                                 * math.exp(-0.0004 * 35))
    w = dict(sex="Γυναίκα", height_cm=165)
    assert e14.estimate(65, u(age=50, **w)).value_cm == pytest.approx(e14.estimate(65, u(age=20, **w)).value_cm
                                                                      * math.exp(-0.0006 * 30))


@pytest.mark.parametrize("anc, delta", [("1", 0), ("2", 0.0131), ("3a", -0.0020), ("3b", -0.0020),
                                        ("4", 0), ("5", 0), (None, 0)])
def test_ancestry_delta(anc, delta):
    base = e14.estimate(80, u()).value_cm
    assert e14.estimate(80, u(ancestry=anc)).value_cm == pytest.approx(base * math.exp(delta))


# --- Μηνύματα -------------------------------------------------------------------
def test_messages_by_profile():
    assert e14.assess(u(), 120, [80]).messages == (M["A"],)
    assert e14.assess(u(profile="Αθλητικό"), 120, [80]).messages == (M["A"], M["B"])


@pytest.mark.parametrize("kw, msg", [(dict(age=60), "age_59"), (dict(ancestry="4"), "ancestry_4_5"),
                                     (dict(ancestry=None), "ancestry_4_5")])
def test_k0(kw, msg):
    r = e14.assess(u(**kw), 120, [80])
    assert r.indicative and M[msg] in r.messages


def test_bmi_out_of_range_and_record_only():
    assert M["bmi_out_of_range"] in e14.assess(u(), 120, [140]).messages  # ΔΜΣ 44,7
    kid = e01.UserCategories(birth_date=date(2012, 1, 1), measurement_date=TODAY,
                             sex="Άνδρας", height_cm=165, ancestry="1")
    r = e14.assess(kid, 100, [55])
    assert r.estimates == () and M["record_only"] in r.messages
    assert M["no_value"] in e14.assess(u(), None, [80]).messages
