"""Τεστ Στοιχείου 03. Αναμενόμενες τιμές από τα παραδείγματα του εγγράφου DaVinci_03."""

from datetime import date

import pytest

from davinci import element_01 as e01
from davinci import element_03 as e03
from davinci.fmt import round_half_up as r1

TODAY = date(2026, 11, 4)
D = e03.load_data()


def u(age=37, **kw):
    base = dict(birth_date=date(TODAY.year - age, 1, 1), measurement_date=TODAY,
                sex="Άνδρας", height_cm=177.0, ancestry="1")
    base.update(kw)
    return e01.UserCategories(**base)


# Πίνακας 7: άνδρας 37, 177 cm, 138,9 kg, λίπος 60,0 kg, άλιπη 78,9 kg
W7, FAT7 = 138.9, 60.0 / 138.9 * 100


# --- Πίνακας 7 -----------------------------------------------------------------
@pytest.mark.parametrize("target, w_no, w_tr, ffm_tr, bmi, nffmi", [
    (19.9, 81.5, 90.0, 72.1, 28.7, 23.2),
    (13.0, 67.8, 79.3, 69.0, 25.3, 22.2),
    (10.0, 61.3, 74.6, 67.1, 23.8, 21.6),
    (6.0, 51.0, 67.8, 63.7, 21.6, 20.5),
])
def test_document_table_7(target, w_no, w_tr, ffm_tr, bmi, nffmi):
    no = e03._point(W7, FAT7, target, u(resistance_training=False))
    tr = e03._point(W7, FAT7, target, u(resistance_training=True))
    assert no.k == 1.0 and tr.k == 0.543
    assert (r1(no.weight_kg), r1(tr.weight_kg), r1(tr.ffm_kg)) == (w_no, w_tr, ffm_tr)
    assert (r1(tr.bmi), r1(tr.normalized_ffmi)) == (bmi, nffmi)


def test_document_today_normalized_ffmi():
    assert r1(e03.normalized_ffmi(e03.ffmi(78.9, 177), 177)) == 25.4


def test_forbes_fat_matches_target_percent():
    ffm_t = e03.expected_ffm(78.9, 60.0, 13.0, 0.543)
    w = ffm_t / 0.87
    assert (w - ffm_t) / w == pytest.approx(0.13)


# --- Κανόνες 1, 2, 4, 4α, 8 -------------------------------------------------------
def test_athletic_range_two_points():
    r = e03.weight_target(W7, FAT7, u(profile="Αθλητικό", resistance_training=True))
    assert r.status == "υπολογίστηκε"
    assert [r1(p.weight_kg) for p in r.points] == [79.3, 67.8]  # «≈ 68 – 79 kg»
    assert r.messages == ()  # ο χρήστης είναι υπέρβαρος: δεν εμφανίζεται το μήνυμα «αδύνατου»


def test_health_above_range_targets_both_ends_of_the_range():
    # σύμβαση συστήματος (απόφαση του χρήστη 11/11/2026): εύρος και στην Υγεία, όπως στα άλλα προφίλ·
    # πρώτο σημείο το ανώτατο υγιές λίπος (ό,τι έδινε πριν ο Κανόνας 1), δεύτερο το κατώτατο
    r = e03.weight_target(W7, FAT7, u(resistance_training=True))
    assert [p.target_fat_percent for p in r.points] == [19.9, 8.0]
    assert r1(r.points[0].weight_kg) == 90.0  # το πρώτο σημείο δεν άλλαξε
    assert r.points[1].weight_kg < r.points[0].weight_kg
    same = e03._point(W7, FAT7, 8.0, u(resistance_training=True))  # ίδιος τύπος με τα άλλα προφίλ
    assert r.points[1] == same


def test_health_within_range_achieved():
    assert e03.weight_target(75, 15, u()).status == "επιτεύχθηκε"


def test_health_below_range_targets_lower_bound_with_k1():
    r = e03.weight_target(60, 6, u(resistance_training=True))
    p = r.points[0]
    assert p.target_fat_percent == 8.0 and p.k == 1.0 and p.weight_kg > 60
    assert D["messages_k0"]["fat_gain"] in r.messages and r.indicative


def test_lean_user_training_message():
    r = e03.weight_target(72, 15, u(profile="Αθλητικό", resistance_training=True))  # ΔΜΣ 23
    assert D["messages_k0"]["lean_training"] in r.messages


@pytest.mark.parametrize("training, losing, k", [(True, True, 0.543), (True, False, 1.0),
                                                 (False, True, 1.0), (False, False, 1.0)])
def test_k_factor(training, losing, k):
    assert e03.k_factor(training, losing) == k


def test_minor_and_pregnancy_no_target():
    kid = e01.UserCategories(birth_date=date(2012, 1, 1), measurement_date=TODAY,
                             sex="Άνδρας", height_cm=165, ancestry="1")
    assert e03.weight_target(60, 25, kid).status == "δεν εφαρμόζεται"
    assert e03.weight_target(70, 30, u(sex="Γυναίκα", pregnant=True)).status == "δεν εφαρμόζεται"


def test_rule_5_low_ffmi_at_target():
    p = e03._point(50, 30, 21.0, u(sex="Γυναίκα", height_cm=170))
    assert p.ffmi < 15 and p.low_ffmi


# --- Πίνακες 2, 4 και Συμπληρώματα Ε/Ζ ---------------------------------------------
def test_today_ffmi_example_E4():
    r = e03.assess_ffmi(139.1, 42.9, u())
    # Έγγραφο: 79,4 / 1,77² = 25,3 (με στρογγυλεμένη άλιπη). Ακριβώς: 79,4261 / 1,77² = 25,35 → 25,4.
    assert r1(r.ffmi) == 25.4
    assert r1(79.4 / 1.77 ** 2) == 25.3
    assert r.reference_range == (16.7, 19.8)
    assert r.reference_label == "Πάνω από το εύρος ατόμων με φυσιολογικό βάρος"
    hr = D["health_reference_range"]["messages"]
    assert hr["high_with_bmi_25"] in r.messages
    assert hr["age_40"] not in r.messages  # 37 ετών
    assert D["indication_high_with_excess_fat"] in r.indications


@pytest.mark.parametrize("sex, ffmi_value, low", [("Άνδρας", 16.99, True), ("Άνδρας", 17.0, False),
                                                  ("Γυναίκα", 14.99, True), ("Γυναίκα", 15.0, False)])
def test_low_ffmi(sex, ffmi_value, low):
    h = 1.70
    w = 80.0
    fat = (1 - ffmi_value * h * h / w) * 100
    assert e03.assess_ffmi(w, fat, u(sex=sex, height_cm=170)).low is low


def test_men_indications_normalized():
    # 180 cm → κανονικοποιημένος = ΔΑΜ
    ind = e03.assess_ffmi(100, 100 - 28.5 * 3.24, u(height_cm=180, profile="Bodybuilding")).indications
    assert "Σπάνια τιμή χωρίς αναβολικά" in ind
    assert "Πάνω από το πρακτικό ανώτατο όριο — ελέγξτε τη μέτρηση" in ind


@pytest.mark.parametrize("anc, rng, msg", [
    ("1", (16.7, 19.8), None), ("2", (17.5, 20.6), "Z2"), ("3a", (15.2, 18.3), "Z3"),
    ("3b", (15.2, 18.3), "Z3"), ("4", (16.7, 19.8), "Z45"), (None, (16.7, 19.8), "Z45"),
])
def test_ancestry_reference_ranges(anc, rng, msg):
    assert e03.health_reference_range(u(ancestry=anc)) == (rng, msg)


def test_Z2_ranges_equal_shifted_kyle_range():
    kyle = {"Άνδρας": (16.7, 19.8), "Γυναίκα": (14.6, 16.8)}
    shift = {"2": {"Άνδρας": 0.849, "Γυναίκα": 0.850}, "3a": {"Άνδρας": -1.505, "Γυναίκα": -1.505}}
    ranges = D["health_reference_range"]["ranges"]
    for g, s in shift.items():
        for sex in kyle:
            assert tuple(ranges[g][sex]) == tuple(r1(x + s[sex]) for x in kyle[sex])


def test_reference_range_only_for_health_profile():
    r = e03.assess_ffmi(80, 15, u(profile="Αθλητικό"))
    assert r.reference_range is None and r.reference_label is None


# --- Συμπλήρωμα Δ: Φάση 2 (Πίνακας Δ7) ---------------------------------------------
def _ffm_end(target):
    return e03._point(W7, FAT7, target, u(resistance_training=True)).ffm_kg


# Το έγγραφο (Πίνακας Δ7) υπολόγισε με ενδιάμεσες τιμές ήδη στρογγυλεμένες (π.χ. 77,7 / 0,9 = 86,3),
# ενώ ο κανόνας Β-7 ορίζει ακριβείς τιμές. Γι' αυτό κρατάμε και τα δύο: την τιμή του κώδικα
# (ακριβής) και την τιμή του εγγράφου, που πρέπει να απέχει ≤ 0,1 kg ή ≤ 1 εβδομάδα.
@pytest.mark.parametrize("profile, fat, status, ffm_t, gain, weight, weeks, doc_weight, doc_weeks", [
    ("Υγεία", 19.9, "διατήρηση", None, 0.0, 90.0, None, 90.0, None),
    ("Αθλητικό", 13.0, "διατήρηση", None, 0.0, 79.3, None, 79.3, None),
    ("Αθλητικό", 6.0, "αύξηση", 66.8, 3.1, 71.0, 26.3, 71.0, 27),
    ("Bodybuilding", 16.0, "αύξηση", 77.7, 7.3, 92.5, 62.5, 92.5, 63),
    ("Bodybuilding", 10.0, "αύξηση", 77.7, 10.6, 86.4, 90.9, 86.3, 91),
])
def test_document_table_D7(profile, fat, status, ffm_t, gain, weight, weeks, doc_weight, doc_weeks):
    r = e03.phase2(_ffm_end(fat), fat, u(profile=profile))
    assert r.status == status
    assert r1(r.gain_kg) == gain and r1(r.weight_kg) == weight
    assert abs(r.weight_kg - doc_weight) <= 0.1
    if ffm_t is not None:
        assert r1(r.ffm_target_kg) == ffm_t
        assert r1(r.min_weeks) == weeks
        assert abs(r.min_weeks - doc_weeks) <= 1


def test_phase2_messages():
    m = D["phase2"]["messages"]
    r = e03.phase2(55, 20, u(age=45, sex="Γυναίκα", height_cm=165, profile="Bodybuilding", ancestry="2"))
    assert set(r.messages) == {m["age_40"], m["ancestry_2_5"], m["women_bodybuilding"], m["scale"]}
    assert e03.phase2(60, 13, u(sex="Γυναίκα", pregnant=True)).messages == (m["not_applicable"],)


def test_phase2_women_use_raw_ffmi():
    r = e03.phase2(40, 20, u(sex="Γυναίκα", height_cm=160, profile="Αθλητικό"))
    assert r.ffm_target_kg == pytest.approx(17.9 * 1.6 ** 2)


# --- Συμπληρώματα Β και Γ: ανάλυση (Πίνακες Β3α και Γ2) -----------------------------
def example_analysis(**kw):
    w = 139.1
    args = dict(water_kg=e03.scale_kg(w, 39.2), bone_kg=e03.scale_kg(w, 1.9), muscle_kg=e03.scale_kg(w, 30.0))
    args.update(kw)
    return e03.analysis(w, 42.9, u(), **args)


def test_document_table_B3a_and_G2():
    a = example_analysis()
    m = {ln.name: ln.kg for ln in a.material}
    t = {ln.name: ln.kg for ln in a.tissues}
    assert r1(a.ffm_kg) == 79.4 and r1(139.1 - a.ffm_kg) == 59.7
    assert [r1(m[k]) for k in ("Νερό (υγρά)", "Ξηρή άλιπη μάζα", "Οστικά μέταλλα", "Λοιπά",
                               "Πρωτεΐνη", "Γλυκογόνο", "Άλλα μέταλλα", "Διαφορά")] == \
        [54.5, 24.9, 2.6, 22.3, 15.9, 0.7, 1.0, 4.7]
    assert [r1(t[k]) for k in ("Σκελετικοί μύες", "Ξηροί μύες", "Λοιποί ιστοί")] == [41.7, 8.3, 37.7]
    assert r1(a.pct_of_ffm(m["Νερό (υγρά)"])) == 68.7 and r1(a.pct_of_ffm(t["Σκελετικοί μύες"])) == 52.5
    assert a.warnings == ("Διαφορά 4,7 kg: οι τιμές της ζυγαριάς δεν συμφωνούν με τις τυπικές τιμές. "
                          "Συνήθης αιτία είναι χαμηλή τιμή νερού (αναλογία 0,687). Με την τυπική αναλογία "
                          "0,73 το νερό θα ήταν περίπου 58,0 kg.",)
    assert ("Η πρωτεΐνη, το γλυκογόνο και τα άλλα μέταλλα είναι τυπικές τιμές για άλιπη μάζα 79,4 kg, "
            "όχι μετρήσεις. Η ζυγαριά δεν τα μετράει. Το γλυκογόνο αλλάζει με τη διατροφή.") in a.messages


def test_sums_are_exact_B1():
    a = example_analysis()
    m = {ln.name: ln.kg for ln in a.material}
    t = {ln.name: ln.kg for ln in a.tissues}
    assert m["Νερό (υγρά)"] + m["Ξηρή άλιπη μάζα"] == pytest.approx(a.ffm_kg)
    assert m["Οστικά μέταλλα"] + m["Λοιπά"] == pytest.approx(m["Ξηρή άλιπη μάζα"])
    assert m["Πρωτεΐνη"] + m["Γλυκογόνο"] + m["Άλλα μέταλλα"] + m["Διαφορά"] == pytest.approx(m["Λοιπά"])
    assert t["Σκελετικοί μύες"] + t["Λοιποί ιστοί"] == pytest.approx(a.ffm_kg)


def test_missing_water():
    a = example_analysis(water_kg=None)
    names = [ln.name for ln in a.material]
    assert "Λοιπά" not in names and "Διαφορά" not in names and "Ξηρή άλιπη μάζα" not in names
    assert D["dry_mass"]["msg_no_water"] in a.messages
    assert "Η ανάλυση υλικού είναι ελλιπής, γιατί δεν υπάρχει τιμή για νερό. Τα λοιπά δεν υπολογίζονται." in a.messages


def test_missing_muscle():
    a = example_analysis(muscle_kg=None)
    assert a.tissues == ()
    assert {ln.name: ln.kg for ln in a.material}["Γλυκογόνο"] == 0.6
    assert D["analysis"]["msg_no_muscle"] in a.messages


def test_inconsistent_values():
    a = example_analysis(water_kg=80.0)
    assert D["analysis"]["msg_inconsistent"] in a.warnings and a.difference_kg is None


def test_difference_ok_message():
    a = example_analysis(water_kg=0.73 * 79.4261)
    assert abs(a.difference_kg) <= 1.5 and a.warnings == ()


def test_minor_no_typical_values():
    kid = e01.UserCategories(birth_date=date(2012, 1, 1), measurement_date=TODAY,
                             sex="Άνδρας", height_cm=165, ancestry="1")
    a = e03.analysis(55, 20, kid, water_kg=33, bone_kg=1.5, muscle_kg=20)
    assert not any(ln.typical for ln in a.material)
    assert D["dry_mass"]["msg_minor"] in a.messages
