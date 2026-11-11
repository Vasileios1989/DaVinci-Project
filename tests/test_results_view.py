"""Παρουσίαση της καρτέλας «Αποτελέσματα» (results_view): μόνο αναδιάταξη, καμία αλλαγή σε τιμές.

Ο βασικός έλεγχος είναι η διατήρηση: κάθε γραμμή, μήνυμα, προειδοποίηση και πίνακας που βγάζει ο
`app_logic.measurement_sections` εμφανίζεται ακριβώς μία φορά στις κάρτες, αυτούσιο (εκτός από την παρένθεση
«(Στοιχείο …)», που δεν εμφανίζεται).
"""

import sys
from collections import Counter
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from davinci import app_logic as al  # noqa: E402
from davinci import results_view as rv  # noqa: E402

TODAY = date(2026, 10, 4)


def person(**k):
    base = dict(birth_date=date(1989, 1, 1), sex="Άνδρας", height_cm=177.0, weight_kg=138.9, fat_percent=43.2,
                today=TODAY, ancestry="1", profile="Αθλητικό", resistance_training=True, pal=1.4, level="Normal")
    return al.PlanInput(**{**base, **k})


FULL = dict(waist_cm=146.0, hip_cm=142.7, neck_cm=44.0, chest_cm=131.5, shoulders_cm=138.0, upper_thigh_cm=80.0,
            scale_muscle_percent=29.9, scale_water_percent=39.0, scale_bone_percent=1.9, scale_visceral_level=18.0,
            arm_relaxed_cm=40.0, biceps_flexed_cm=42.0, forearm_relaxed_cm=32.6, forearm_flexed_cm=34.0,
            wrist_cm=18.6, thigh_cm=74.5, knee_cm=48.0, calf_cm=45.5, ankle_cm=26.5,
            previous_morning_weights=(139.0, 138.8, 139.1), today_morning_weight=138.9, urine_color=3, thirst=2.0)
SF = dict(elbow_cm=7.2, knee_breadths=(10.1, 10.2), sf_isak=True, sf_caliper=al.calipers()[0],
          triceps=al.Skinfold((14.0, 14.2)), subscapular=al.Skinfold((20.0, 20.4)),
          supraspinale=al.Skinfold((15.0, 15.2)), supraspinale_site_confirmed=True,
          calf_skinfold=al.Skinfold((12.0, 12.2)))

CASES = {
    "άνδρας 139 kg, όλα τα πεδία": (person(), al.Measures(**FULL)),
    "άνδρας 139 kg, χωρίς μετρήσεις": (person(), al.Measures()),
    "γυναίκα Υγεία": (person(sex="Γυναίκα", height_cm=165.0, weight_kg=72.0, fat_percent=38.0, profile="Υγεία",
                             resistance_training=False), al.Measures(**{**FULL, "waist_cm": 88.0, "hip_cm": 104.0})),
    "Bodybuilding": (person(weight_kg=90.0, fat_percent=18.0, profile="Bodybuilding"), al.Measures(**FULL)),
    "Professional": (person(weight_kg=82.0, fat_percent=18.0, level="Professional"),
                     al.Measures(**{**FULL, **SF, "waist_cm": 84.0, "hip_cm": 98.0})),
    "70 ετών": (person(birth_date=date(1956, 1, 1), weight_kg=80.0, fat_percent=28.0, profile="Υγεία"),
                al.Measures(**FULL)),
}


def cards(groups):
    return [c for g in groups for c in g.cards]


@pytest.mark.parametrize("name", CASES)
def test_nothing_is_lost_or_changed(name):
    inp, m = CASES[name]
    sections, errors = al.measurement_sections(inp, m)
    assert not errors and len(sections) > 5
    sections = (*rv.start_sections(inp), *sections)
    groups, errors = rv.results(inp, m)
    assert not errors
    cs = cards(groups)
    clean = rv.clean_text
    want_lines = Counter((clean(a), clean(b)) for s in sections for a, b in s.lines)
    got_lines = Counter(x for c in cs for x in (*c.main, *c.targets, *c.details))
    assert got_lines == want_lines
    assert Counter(x for c in cs for x in c.messages) == Counter(clean(x) for s in sections for x in s.messages)
    assert Counter(x for c in cs for x in c.warnings) == Counter(clean(x) for s in sections for x in s.warnings)
    assert Counter(c.table for c in cs if c.table) == Counter(s.table for s in sections if s.table)
    # η σήμανση «Ενδεικτική» (Κ0) ακολουθεί την ενότητά της
    by_title = {rv.clean_title(s.title): s for s in sections}
    assert len(by_title) == len(sections)  # κανένας τίτλος δεν συμπίπτει μετά την αφαίρεση του «(Στοιχείο …)»
    for g in groups:
        assert g.title != rv.OTHER, [c.title for c in g.cards]  # κάθε ενότητα έχει τη θέση της


@pytest.mark.parametrize("name", CASES)
def test_no_element_numbers_in_parentheses(name):
    groups, _ = rv.results(*CASES[name])
    for g in groups:
        texts = [g.title, *(x for line in g.lines for x in line)]
        for c in g.cards:
            texts += [c.title, *c.messages, *c.warnings, *(x for line in (*c.main, *c.targets, *c.details) for x in line)]
        assert not any("Στοιχεί" in t for t in texts), [t for t in texts if "Στοιχεί" in t]


def test_clean_text_removes_only_the_element_reference():
    assert rv.clean_text("Μέση (Στοιχείο 05)") == "Μέση"
    assert rv.clean_text("Εύρη οστών και δερματοπτυχές (Στοιχεία 30, 31, 33–36)") == "Εύρη οστών και δερματοπτυχές"
    assert rv.clean_text("Μεσαίος (από το εύρος αγκώνα, Στοιχείο 32)") == "Μεσαίος (από το εύρος αγκώνα)"
    assert rv.clean_text("με τις εκτιμήσεις των Στοιχείων 15 και 16 (δικέφαλος 34,1 cm, πήχης 30,0 cm), ο λόγος") == \
        "με τις εκτιμήσεις (δικέφαλος 34,1 cm, πήχης 30,0 cm), ο λόγος"
    same = "≈ 98,9 cm (96,0 – 101,9) · κάτω από 88,5 cm (ΛΜΙ: κάτω από 89,0)"
    assert rv.clean_text(same) == same  # αριθμοί και άλλες παρενθέσεις μένουν ανέγγιχτα


def test_order_follows_the_report():
    groups, _ = rv.results(*CASES["άνδρας 139 kg, όλα τα πεδία"])
    assert [g.title for g in groups] == ["Βασικά στοιχεία", "Σύσταση σώματος", "Μετρήσεις κορμού", "Μετρήσεις άκρων",
                                         "Αναλογίες κορμού", "Αναλογίες άκρων", "Σκελετός και δερματοπτυχές",
                                         "Σωματότυπος", "Ενυδάτωση"]
    by = {g.title: [c.title for c in g.cards] for g in groups}
    assert by["Σύσταση σώματος"] == ["Βάρος", "Λίπος", "Σπλαχνικό λίπος", "Άλιπη μάζα", "Σκελετικοί μύες", "Ξηροί μύες",
                                     "Υγρά", "Οστά", "Ανάλυση άλιπης μάζας", "Λόγος μυών / λίπους",
                                     "Λόγος άλιπης / λίπους", "Δείκτης Άλιπης Μάζας (ΔΑΜ)", "ΔΜΣ"]
    assert by["Μετρήσεις κορμού"] == ["Μέση", "Ισχίο", "Λαιμός", "Στήθος", "Ώμοι"]
    assert by["Μετρήσεις άκρων"] == ["Μπράτσο και δικέφαλος", "Πήχης", "Καρπός", "Μηρός", "Πάνω από το γόνατο", "Γάμπα",
                                     "Αστράγαλος"]
    assert by["Αναλογίες κορμού"] == ["Λόγος μέσης / ισχίου", "Λόγος μέσης / ύψους", "Λόγος στήθους / μέσης",
                                      "Λόγος ώμων / μέσης"]
    assert by["Αναλογίες άκρων"] == ["Λόγος πήχη / δικεφάλου", "Λόγος μηρού / γάμπας", "Λόγος καρπού / δικεφάλου",
                                     "Λόγος μηρού / γονάτου", "Λόγος αστραγάλου / γάμπας"]


def test_basics_and_start_values_come_from_the_code():
    inp, m = CASES["άνδρας 139 kg, όλα τα πεδία"]
    groups, _ = rv.results(inp, m)
    assert dict(groups[0].lines) == {"Ηλικία": "37 ετών", "Ύψος": "177,0 cm", "Φύλο": "Άνδρας", "Προφίλ": "Αθλητικό",
                                     "Επίπεδο μέτρησης": "Normal", "Σκελετός": "Δεν έχει οριστεί"}
    c = {x.title: x for x in cards(groups)}
    prep = al.prepare(inp)
    points = al._targets(inp.weight_kg, inp.fat_percent, prep.user)
    assert c["Βάρος"].main == (("Σήμερα", "138,9 kg"),)
    assert c["Βάρος"].targets == (("Βάρος-στόχος (Φάση 1)", "≈ 79,2 kg (−59,7) → ≈ 67,8 kg (−71,1)"),)
    assert [round(p.weight_kg, 1) for p in points] == [79.2, 67.8]  # οι τιμές του Στοιχείου 03, όχι νέος υπολογισμός
    assert c["Λίπος"].main == (("Σήμερα", "43,2% · 60,0 kg"), ("Ταξινόμηση", prep.fat.health_label))
    assert c["Λίπος"].targets == (("Εύρος λίπους του προφίλ", "6,0–13,0%"),)
    assert c["ΔΜΣ"].main == (("Σήμερα", "44,3"), ("Κατηγορία", prep.bmi.category))
    assert c["ΔΜΣ"].targets == (("ΔΜΣ στο βάρος-στόχο", "≈ 25,3 → ≈ 21,6"),)
    assert [round(p.bmi, 1) for p in points] == [25.3, 21.6]


def test_headline():
    c = {x.title: x for x in cards(rv.results(*CASES["άνδρας 139 kg, χωρίς μετρήσεις"])[0])}
    assert rv.headline(c["Βάρος"]) == ("Βάρος", "138,9 kg", ())
    waist_only = {x.title: x for x in cards(rv.results(person(), al.Measures(waist_cm=146.0))[0])}
    v = waist_only["Σπλαχνικό λίπος"]  # λείπει ο άνω μηρός: δεν υπολογίζεται, και ο λόγος μένει στο ⓘ
    assert rv.headline(v) == ("Σπλαχνικό λίπος", rv.NOT_COMPUTED, ()) and v.messages
    full = {x.title: x for x in cards(rv.results(*CASES["άνδρας 139 kg, όλα τα πεδία"])[0])}
    assert rv.headline(full["Ισχίο"]) == ("Ισχίο", "142,7 cm", ())
    assert rv.headline(full["Λόγος μέσης / ισχίου"])[:2] == ("Λόγος μέσης / ισχίου", "1,02")
    title, value, rest = rv.headline(full["Μπράτσο και δικέφαλος"])
    assert value is None and rest[0] == ("Μπράτσο χαλαρό", "40,0 cm")
    assert rv.headline(full["Ανάλυση άλιπης μάζας"]) == ("Ανάλυση άλιπης μάζας", None, ())  # έχει πίνακα
    assert rv.headline(full["Μέση"]) == ("Μέση", "146,0 cm", ())
    assert rv.headline(full["Ξηροί μύες"])[0] == "Ξηροί μύες (εκτίμηση)"  # η λέξη «εκτίμηση» δεν χάνεται
    assert rv.headline(full["Δείκτης Άλιπης Μάζας (ΔΑΜ)"])[:2] == ("Δείκτης Άλιπης Μάζας (ΔΑΜ)", "25,2 kg/m²")
    no_shoulders = {x.title: x for x in cards(rv.results(person(), al.Measures(waist_cm=146.0, chest_cm=131.5))[0])}
    for c in no_shoulders.values():  # «δεν υπολογίστηκε» μόνο όταν η κάρτα δεν έχει καμία γραμμή
        if rv.headline(c)[1] == rv.NOT_COMPUTED:
            assert not (c.main or c.targets or c.details or c.table) and c.messages


def test_error_goes_through_unchanged():
    bad = person(height_cm=20.0)
    assert rv.results(bad, al.Measures()) == ((), al.measurement_sections(bad, al.Measures())[1])
