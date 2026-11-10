"""Τεστ Στοιχείων 22–25 (λόγοι περιφερειών). Αναμενόμενες τιμές από τα έγγραφα DaVinci_22 έως DaVinci_25.

Οι τύποι «Έλεγχος ANSUR» των εγγράφων 23–25 υπάρχουν μόνο εδώ, για να ελεγχθεί η στήλη του παραδείγματος·
δεν χρησιμοποιούνται στην εφαρμογή.
"""

import math
from datetime import date

import pytest

from davinci import element_01 as e01
from davinci import element_03 as e03
from davinci import element_14 as e14
from davinci import element_22 as e22
from davinci import element_23 as e23
from davinci import element_24 as e24
from davinci import element_25 as e25
from davinci import ratios
from davinci.fmt import round_half_up as r

TODAY = date(2026, 11, 4)
M22 = e22.load_data()["messages"]
M23 = e23.load_data()["messages"]
M24 = e24.load_data()["messages"]
M25 = e25.load_data()["messages"]

# Οι πέντε περιπτώσεις των παραδειγμάτων, με τη σειρά των εγγράφων.
CASES = (19.9, 13, 6, 16, 10)


def u(age=37, **kw):
    base = dict(birth_date=date(TODAY.year - age, 1, 1), measurement_date=TODAY,
                sex="Άνδρας", height_cm=177.0, ancestry="1")
    base.update(kw)
    return e01.UserCategories(**base)


def target_weight(fat):
    return e03._point(138.9, 60 / 138.9 * 100, fat, u(resistance_training=True)).weight_kg


def close(code, doc, tol=0.1):
    return abs(r(code, 1) - doc) <= tol + 1e-9


# --- Κοινά: λόγος με δύο δεκαδικά, ζώνες εκατοστημορίων -------------------------------------
P = {"5": 1.03, "25": 1.08, "50": 1.13, "75": 1.18, "95": 1.25}


@pytest.mark.parametrize("value, band", [
    (1.02, "κάτω από το 5ο"), (1.03, "5ο–25ο"), (1.07, "5ο–25ο"), (1.08, "25ο–50ό"), (1.13, "50ό–75ο"),
    (1.18, "75ο–95ο"), (1.25, "75ο–95ο"), (1.26, "πάνω από το 95ο"),
])
def test_percentile_band_boundaries(value, band):
    assert ratios.percentile_band(value, P) == band


def test_ratio_is_rounded_to_two_decimals():
    assert ratios.ratio2(146, 142.7) == 1.02
    assert ratios.ratio2(138.0, 146) == 0.95  # 0,9452
    assert ratios.ratio2(27.4, 40) == 0.69  # ακριβώς 0,685· με float θα έβγαινε 0,68
    with pytest.raises(ValueError):
        ratios.ratio2(0, 10)


# --- Στοιχείο 22: Πίνακας 8 ------------------------------------------------------------------
# (αναμενόμενο ισχίο, Ζ, Μ) του εγγράφου
DOC22 = {19.9: (105.0, 94.5, 88.5), 13: (99.0, 89.1, 88.5), 6: (92.1, 82.9, 82.9),
         16: (101.6, 91.4, 88.5), 10: (96.2, 86.6, 86.6)}


def test_e22_today_ratio_and_category():
    res = e22.assess(146, 142.7, u(profile="Αθλητικό"))
    assert res.ratio == 1.02
    assert res.category == "Ουσιαστικά αυξημένος κίνδυνος"
    assert res.messages[0] == M22["U"].replace("είναι Χ,", "είναι 1,02,")
    assert not res.indicative


@pytest.mark.parametrize("fat", CASES)
def test_e22_table8_rows(fat):
    hip, z, m_ = DOC22[fat]
    row = e22.waist_rows(u(), [(target_weight(fat), fat)])[0]
    # Το έγγραφο πολλαπλασίασε το ήδη στρογγυλεμένο ισχίο (π.χ. 0,90 × 99,0 = 89,1)· ο κώδικας με την ακριβή τιμή.
    assert close(row.expected_hip_cm, hip)
    assert close(row.waist_for_whr_cm, z)
    assert row.waist_for_whtr_cm == pytest.approx(88.5)
    assert close(row.waist_for_both_cm, m_)
    assert row.waist_for_both_cm == min(row.waist_for_whr_cm, row.waist_for_whtr_cm)


def test_e22_table8_exact_code_values():
    rows = e22.waist_rows(u(), [(target_weight(f), f) for f in CASES])
    assert [r(x.waist_for_whr_cm, 1) for x in rows] == [94.5, 89.0, 82.8, 91.4, 86.6]
    assert [r(x.waist_for_both_cm, 1) for x in rows] == [88.5, 88.5, 82.8, 88.5, 86.6]


def test_e22_user_display_messages():
    user = u(profile="Αθλητικό")
    res = e22.assess(146, 142.7, user, [(target_weight(13), 13)])
    m = res.messages[1]
    assert "(98,9 cm)" in m and "κάτω από 89,0 cm" in m and "κάτω από 88,5 cm" in m
    assert m.endswith("η μέση πρέπει να είναι κάτω από 88,5 cm.")
    assert res.messages[2:] == (M22["P"], M22["T"])


def test_e22_threshold_is_inclusive_and_on_two_decimals():
    assert e22.assess(90, 100, u()).category == "Ουσιαστικά αυξημένος κίνδυνος"  # 0,90
    assert e22.assess(89.6, 100, u()).category == "Ουσιαστικά αυξημένος κίνδυνος"  # 0,896 → 0,90
    assert e22.assess(89.4, 100, u()).category == "Κάτω από το όριο του ΠΟΥ"  # 0,894 → 0,89
    w = dict(sex="Γυναίκα")
    assert e22.assess(85, 100, u(**w)).category == "Ουσιαστικά αυξημένος κίνδυνος"
    assert e22.assess(84.4, 100, u(**w)).category == "Κάτω από το όριο του ΠΟΥ"
    low = e22.assess(80, 100, u())
    assert low.messages[0] == M22["K"].replace("είναι Χ,", "είναι 0,80,")


def test_e22_no_bmi_restriction_and_health_profile_no_P():
    res = e22.assess(146, 142.7, u())  # ΔΜΣ 44
    assert res.category is not None
    assert M22["P"] not in res.messages and res.messages[-1] == M22["T"]


@pytest.mark.parametrize("anc, key", [("2", "european"), ("3a", "asian"), ("3b", "asian"),
                                      ("4", "european"), ("5", "european"), (None, "european")])
def test_e22_ancestry_indicative(anc, key):
    res = e22.assess(80, 100, u(ancestry=anc))
    assert res.indicative and M22[key] in res.messages


def test_e22_record_only_and_missing():
    assert e22.assess(70, 80, u(age=16)).messages == (M22["record_only"],)
    preg = u(sex="Γυναίκα", age=30, pregnant=True)
    assert e22.assess(70, 80, preg).category is None
    res = e22.assess(None, 142.7, u(), [(target_weight(13), 13)])
    assert res.ratio is None and res.messages[0] == M22["missing"] and len(res.messages) == 3
    with pytest.raises(e01.InvalidInput):
        e22.assess(-1, 100, u())


def test_e22_age_80_label():
    assert e22.assess(80, 100, u(age=82)).out_of_reference_label == e01.zone_for_age(82).label


# --- Στοιχείο 23: Πίνακας 11 -----------------------------------------------------------------
DOC23 = {19.9: (109.5, 1.24), 13: (102.9, 1.16), 6: (95.2, 1.08), 16: (105.8, 1.20), 10: (99.8, 1.13)}


def check23(weight, height, age, sex="Άνδρας"):
    a, b, c = (0.0103, -0.1951, -0.0012) if sex == "Άνδρας" else (-0.0659, -0.1891, -0.0001)
    return math.exp(a + b * math.log(weight / height) + c * age)


def test_e23_today_below_5th():
    res = e23.assess(131.5, 146, u(profile="Αθλητικό"), [target_weight(13)])
    assert res.ratio == 0.90 and res.band == "κάτω από το 5ο"
    assert res.messages[0] == M23["A"].replace("Χο", "κάτω από το 5ο")
    assert res.messages[1] == M23["E"].replace("(Υ cm)", "(102,9 cm)").replace("(Κ cm)", "(88,5 cm)") \
        .replace("τουλάχιστον Λ.", "τουλάχιστον 1,16.")
    assert res.messages[2] == M23["P"] and len(res.messages) == 3 and not res.indicative


@pytest.mark.parametrize("fat", CASES)
def test_e23_table11_rows(fat):
    chest, lam = DOC23[fat]
    row = e23.target_rows(u(), [target_weight(fat)])[0]
    assert r(row.numerator_cm, 1) == chest
    assert row.denominator_cm == pytest.approx(88.5)
    assert r(row.ratio, 2) == lam


def test_e23_check_column():
    assert r(check23(139.1, 177, 37), 2) == 1.01
    # Αθλητικό 6%: ο τύπος με τους συντελεστές του εγγράφου δίνει 1,1656 → 1,17· το έγγραφο γράφει 1,16
    # (πιθανώς από συντελεστές με περισσότερα δεκαδικά). Απόκλιση ≤ 0,01, στη στήλη ελέγχου μόνο.
    doc = [1.10, 1.13, 1.16, 1.12, 1.14]
    got = [check23(target_weight(f), 177, 37) for f in CASES]
    assert all(abs(r(g, 2) - d) <= 0.01 + 1e-9 for g, d in zip(got, doc))
    assert [r(g, 2) for g in got] == [1.10, 1.13, 1.17, 1.12, 1.14]


def test_e23_women_A_and_G_only():
    w = u(sex="Γυναίκα", profile="Bodybuilding")
    res = e23.assess(95, 80, w, [65])
    assert res.messages == (M23["A"].replace("Χο", res.band), M23["G"])


def test_e23_k0():
    res = e23.assess(110, 100, u(ancestry="4"))
    assert res.indicative and M23["ancestry_4_5"] in res.messages
    res = e23.assess(110, 100, u(age=60))
    assert res.indicative and M23["age_59"] in res.messages
    assert e23.assess(110, 100, u(age=17)).messages == (M23["record_only"],)
    miss = e23.assess(None, 100, u())
    assert miss.ratio is None and miss.messages == (M23["missing"],)


# --- Στοιχείο 24: Πίνακας 12 -----------------------------------------------------------------
# Το έγγραφο 24 πήρε τους ώμους από τον τύπο του Πίνακα 9 του Στοιχείου 14, που περιέχει όρο ηλικίας
# (−0,0004 × ηλικία). Ο κώδικας ακολουθεί τον Πίνακα 3 του Στοιχείου 14 (χωρίς όρο ηλικίας) — βλ. NOTES.
DOC24 = {19.9: (119.2, 1.35), 13: (114.7, 1.30), 6: (109.3, 1.24), 16: (116.6, 1.32), 10: (112.5, 1.27)}


def check24(weight, height, age, sex="Άνδρας"):
    a, b, c = (0.0173, -0.3857, -0.0026) if sex == "Άνδρας" else (-0.1320, -0.4116, -0.0021)
    return math.exp(a + b * math.log(weight / height) + c * age)


def test_e24_today_below_5th():
    res = e24.assess(138.0, 146, u(profile="Αθλητικό"), [target_weight(13)])
    assert res.ratio == 0.95 and res.band == "κάτω από το 5ο"
    assert res.messages[0] == M24["A"].replace("Χο", "κάτω από το 5ο")
    # Συμπλήρωμα Α του 14 (όρος ηλικίας): 114,6 cm στο ακριβές βάρος-στόχο 79,25 kg (έγγραφο: 114,7 στα 79,3)
    assert "(114,6 cm)" in res.messages[1] and "τουλάχιστον 1,30." in res.messages[1]
    assert res.messages[2:] == (M24["T"], M24["P"])


@pytest.mark.parametrize("fat", CASES)
def test_e24_table12_document_values(fat):
    # Μετά το Συμπλήρωμα Α του 14 ο κώδικας δίνει τον Πίνακα 12· διαφορές έως 0,1 cm / 0,01 μόνο από
    # το ακριβές βάρος-στόχο και τη στρογγύλευση του εγγράφου (λόγος από στρογγυλεμένους ώμους).
    row = e24.target_rows(u(), [target_weight(fat)])[0]
    shoulders, lam = DOC24[fat]
    assert close(row.numerator_cm, shoulders)
    assert abs(r(row.ratio, 2) - lam) <= 0.01 + 1e-9


def test_e24_check_column():
    assert r(check24(139.1, 177, 37), 2) == 1.01
    got = [r(check24(target_weight(f), 177, 37), 2) for f in CASES]
    assert got == [1.20, 1.26, 1.34, 1.23, 1.29]


def test_e24_women_show_E_T_G():
    w = u(sex="Γυναίκα", profile="Αθλητικό")
    res = e24.assess(105, 80, w, [65])
    assert len(res.messages) == 4
    assert res.messages[2:] == (M24["T"], M24["G"]) and M24["P"] not in res.messages


def test_e24_kilani_shoulders_needed():
    # Το έγγραφο γράφει «περίπου 135,7 cm». 1,53 × 88,5 = 135,4 και 120,0 / 78,2 × 88,5 = 135,8:
    # μικρή απόκλιση στο «περίπου» (βλ. NOTES), όχι τιμή της εφαρμογής.
    assert r(1.53 * 88.5, 1) == 135.4
    assert r(120.0 / 78.2 * 88.5, 1) == 135.8


# --- Στοιχείο 25: Πίνακας 10 -----------------------------------------------------------------
DOC25 = {19.9: (36.5, 31.5, 0.86), 13: (34.1, 30.0, 0.88), 6: (31.3, 28.3, 0.90),
         16: (35.1, 30.7, 0.87), 10: (33.0, 29.4, 0.89)}


def check25(weight, height, age, sex="Άνδρας"):
    a, b, c = (-0.2733, -0.1711, 0.0003) if sex == "Άνδρας" else (-0.2987, -0.2084, -0.0010)
    return math.exp(a + b * math.log(weight / height) + c * age)


@pytest.mark.parametrize("fat", CASES)
def test_e25_table10_rows(fat):
    b, p, lam = DOC25[fat]
    row = e25.target_rows(u(), [target_weight(fat)])[0]
    assert (r(row.denominator_cm, 1), r(row.numerator_cm, 1), r(row.ratio, 2)) == (b, p, lam)


def test_e25_check_column():
    got = [r(check25(target_weight(f), 177, 37), 2) for f in CASES]
    assert got == [0.86, 0.88, 0.91, 0.87, 0.89]


def test_e25_user_display():
    res = e25.assess(30.0, 34.0, u(profile="Αθλητικό"), [target_weight(13)])
    assert res.ratio == 0.88 and res.band == "50ό–75ο"
    assert res.messages == (
        M25["A"].replace("Χο", "50ό–75ο"), M25["L"],
        M25["E"].replace("δικέφαλος Υ cm", "δικέφαλος 34,1 cm").replace("πήχης Ζ cm", "πήχης 30,0 cm")
        .replace("περίπου Λ.", "περίπου 0,88."),
        M25["T"], M25["P"])


def test_e25_women_and_missing_and_injury():
    w = u(sex="Γυναίκα")
    res = e25.assess(26, 30, w, [60])
    assert res.messages[-1] == M25["G"] and M25["P"] not in res.messages
    miss = e25.assess(None, 34.0, u())
    assert miss.ratio is None and miss.messages[0] == M25["missing"] and M25["T"] in miss.messages
    inj = e25.assess(30, 34, u(), [target_weight(13)], injured_or_swollen=True)
    assert inj.band is None and inj.messages == (M25["injury"],)


def test_e25_k0_undeclared_ancestry():
    res = e25.assess(30, 34, u(ancestry=None))
    assert res.indicative and M25["ancestry_4_5"] in res.messages


# --- Μητρώο --------------------------------------------------------------------------------
def test_registry_entries():
    from davinci.registry import ELEMENTS
    for k in ("22", "23", "24", "25"):
        assert ELEMENTS[k]["level"] == "Normal"
