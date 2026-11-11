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
    assert Counter(x for c in cs for x in (*c.messages, *c.needs)) == \
        Counter(clean(x) for s in sections for x in s.messages)
    assert Counter(x for c in cs for x in c.warnings) == Counter(clean(x) for s in sections for x in s.warnings)
    assert Counter(c.table for c in cs if c.table) == Counter(s.table for s in sections if s.table)
    # η σήμανση «Ενδεικτική» (Κ0) ακολουθεί την ενότητά της
    by_title = {rv.clean_title(s.title): s for s in sections}
    assert len(by_title) == len(sections)  # κανένας τίτλος δεν συμπίπτει μετά την αφαίρεση του «(Στοιχείο …)»
    known = {c.title for g in groups if g.title != rv.OTHER for c in g.cards}
    other = [c.title for g in groups if g.title == rv.OTHER for c in g.cards]
    assert not known & set(other)
    # κάθε γραμμή του κώδικα φαίνεται: στη γραμμή της οθόνης (τιμή ή δευτερεύουσα γραμμή) ή αυτούσια στο ⓘ
    for c in cs:
        for ln in (*c.main, *c.targets, *c.details):
            assert ln in c.info_lines or any(ln[1] == r.value or ln in r.subs for r in c.rows), (c.title, ln)


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
    assert [g.title for g in groups] == list(rv.TAB_TITLES) == [
        "Σύσταση σώματος", "Κορμός", "Άκρα", "Αναλογίες κορμού", "Αναλογίες άκρων", "Άλλα"]
    body = groups[0]
    assert [(p.key, p.heading, p.fold) for p in body.parts] == [
        ("Βασικά", "Βασικά στοιχεία", False), ("Σύσταση", "Σύσταση σώματος", False),
        ("Ιστοί", "Άλιπη σε ιστούς", True), ("Συστατικά", "Άλιπη σε συστατικά", True), ("Δείκτες", "Δείκτες", False)]
    assert body.part("Σύσταση").cards[-1].title == "Άλιπη μάζα"  # οι αναλύσεις ακριβώς κάτω από την Άλιπη μάζα
    by = {p.key: [r.name for c in p.cards for r in c.rows] for g in groups for p in g.parts}
    assert by["Σύσταση"] == ["Βάρος", "Λίπος", "Σπλαχνικό λίπος (Εκτίμηση)", "Άλιπη μάζα"]
    assert by["Ιστοί"] == ["Σκελετικοί μύες", "Ξηροί μύες (εκτίμηση)", "Λοιποί ιστοί"]
    assert by["Συστατικά"] == ["Νερό", "Ξηρή άλιπη μάζα", "Οστικά μέταλλα", "Λοιπά", "Πρωτεΐνη (τυπική τιμή)",
                                   "Γλυκογόνο (τυπική τιμή)", "Άλλα μέταλλα (τυπική τιμή)", "Διαφορά"]
    assert by["Δείκτες"] == ["Λόγος μυών / λίπους", "Λόγος άλιπης / λίπους", "Δείκτης Άλιπης Μάζας (ΔΑΜ)",
                             "Κανονικοποιημένος ΔΑΜ", "ΔΜΣ"]
    assert by["Κορμός"] == ["Μέση", "Ισχίο", "Λαιμός", "Στήθος", "Ώμοι"]
    assert by["Άκρα"] == ["Μπράτσο χαλαρό", "Δικέφαλος σφιγμένος", "Πήχης χαλαρός", "Πήχης σφιγμένος", "Καρπός",
                          "Μηρός", "Πάνω από το γόνατο", "Γάμπα", "Αστράγαλος"]
    assert by["Αναλογίες κορμού"] == ["Λόγος μέσης / ισχίου", "Λόγος μέσης / ύψους", "Λόγος στήθους / μέσης",
                                      "Λόγος ώμων / μέσης"]
    assert by["Αναλογίες άκρων"] == ["Λόγος πήχη / δικεφάλου", "Λόγος μηρού / γάμπας", "Λόγος καρπού / δικεφάλου",
                                     "Λόγος μηρού / γονάτου", "Λόγος αστραγάλου / γάμπας"]
    assert all(len(g.parts) == 1 and not g.parts[0].fold for g in groups[1:])


def rows_of(groups):
    return {r.name: r for g in groups for c in g.cards for r in c.rows}


def test_rows_values_targets_and_changes():
    groups, _ = rv.results(*CASES["άνδρας 139 kg, όλα τα πεδία"])
    r = rows_of(groups)
    w = r["Βάρος"]
    assert (w.value, w.target_word, w.target) == ("138,9 kg", "Στόχος", "≈ 79,2 kg έως ≈ 67,8 kg")
    assert w.change.parts == (("down", "▼ −59,7 kg έως −71,1 kg, −43,0% έως −51,2%"),)
    fat = r["Λίπος"]  # ποσοστό: η αλλαγή σε ποσοστιαίες μονάδες, χωρίς «% της μέτρησης»
    assert fat.target == "13,0% έως 6,0%" and fat.change.parts == (("down", "▼ −30,2% έως −37,2%"),)
    assert ("Ταξινόμηση", "Παχυσαρκία") in fat.subs
    mus = r["Σκελετικοί μύες"]
    assert mus.note == "52,6% της άλιπης" and mus.target_word == "Ενδεικτικός στόχος"
    assert mus.change.parts[0][0] == "down" and r["Ξηροί μύες (εκτίμηση)"].level == 1
    assert r["Λοιποί ιστοί"].target == rv.NO_TARGET and r["Λοιποί ιστοί"].change is None
    assert r["Νερό"].target_word == "Ενδεικτικός στόχος" and r["Νερό"].value.endswith("(ζυγαριά)")
    assert r["Πρωτεΐνη (τυπική τιμή)"].level == 2 and r["Πρωτεΐνη (τυπική τιμή)"].value.startswith("≈ ")
    up = r["Λόγος στήθους / μέσης"]  # «≥»: πρέπει να ανέβει → πράσινο ▲
    assert up.target_word == "Ελάχιστος λόγος" and all(d == "up" for d, _ in up.change.parts)
    assert r["Ισχίο"].target_word == "Αναμενόμενο"  # εκτίμηση του κώδικα: η λέξη μένει
    assert r["Λόγος μέσης / ύψους"].target == "κάτω από 0,50"
    assert r["Λόγος μέσης / ισχίου"].change is None  # ο στόχος είναι μέση σε cm, όχι λόγος: καμία αλλαγή
    assert r["Λαιμός"].target == rv.NO_TARGET and r["Καρπός"].target_word == "Στόχος"
    dam = r["Δείκτης Άλιπης Μάζας (ΔΑΜ)"]
    pts = al._targets(138.9, 43.2, al.prepare(CASES["άνδρας 139 kg, όλα τα πεδία"][0]).user)
    assert dam.target == " έως ".join(f"≈ {x} kg/m²" for x in (rv.num(p.ffmi, 1) for p in pts))


def test_change_rules():
    assert rv.change("146,0 cm", ["κάτω από 88,5 cm"]).parts == (("down", "▼ −57,5 cm, −39,4%"),)
    assert rv.change("80,0 cm", ["κάτω από 88,5 cm"]) is None  # ήδη κάτω από τον στόχο
    assert rv.change("45,5 cm", ["≥ 37,7 cm", "≥ 35,2 cm"]) is None  # ήδη πάνω από το ελάχιστο
    assert rv.change("30,0 cm", ["≥ 34,1 cm"]).parts == (("up", "▲ +4,1 cm, +13,7%"),)
    assert rv.change("0,69", ["3,5", "8,2"]).parts[0][0] == "up"
    mixed = rv.change("1,50", ["≈ 1,40", "≈ 1,60"]).parts  # ανάμεσα σε δύο στόχους: ένα κομμάτι ανά κατεύθυνση
    assert [d for d, _ in mixed] == ["down", "up"]
    assert rv.change("54,2 kg", ["≈ 54,2 kg"]) is None
    assert rv.change("40,0 cm", ["≈ 0,88"]) is None  # διαφορετική μονάδα: δεν συγκρίνεται
    assert rv._heads("≈ 79,2 kg (−59,7) → ≈ 67,8 kg (−71,1)") == ["≈ 79,2 kg", "≈ 67,8 kg"]
    assert rv._heads("6,0–13,0%") == ["6,0%", "13,0%"] and rv._heads("3,5 – 8,2") == ["3,5", "8,2"]
    assert rv._heads("≥ 60,0 cm (εκτίμηση 58,9, εύρος 57,0 – 60,8)") == ["≥ 60,0 cm"]


def test_missing_lines_say_what_to_fill():
    groups, _ = rv.results(person(), al.Measures())
    g = {p.key: p for x in groups for p in x.parts}
    r = rows_of(groups)
    assert r["Σκελετικοί μύες"].value is None and r["Λοιποί ιστοί"].value is None
    assert g["Ιστοί"].todo == "Για τις γραμμές που λείπουν συμπλήρωσε στη «Μέτρηση» → «Ζυγαριά»: Μύες %."
    assert r["Ξηρή άλιπη μάζα"].value is None and r["Νερό"].value.endswith("(υπολογισμένη)")
    assert g["Συστατικά"].todo.endswith(": Οστά %, Υγρά %.") or g["Συστατικά"].todo.endswith(": Υγρά %, Οστά %.")
    full = {p.key: p for x in rv.results(*CASES["άνδρας 139 kg, όλα τα πεδία"])[0] for p in x.parts}
    assert full["Ιστοί"].todo is None and full["Συστατικά"].todo is None


def test_analysis_message_names_the_screen_headings_without_letters():
    groups, _ = rv.results(*CASES["άνδρας 139 kg, όλα τα πεδία"])
    msgs = [m for g in groups for c in g.cards for m in c.messages]
    two = next(m for m in msgs if m.startswith("Δύο τρόποι ανάλυσης"))
    assert rv._AB_SCREEN in two and " Α " not in two and " Β " not in two and "του Α" not in two
    assert not any(rv._AB_CODE in m for m in msgs)


@pytest.mark.parametrize("name", CASES)
def test_info_has_titled_sections_and_keeps_every_text(name):
    groups, _ = rv.results(*CASES[name])
    for c in cards(groups):
        titles = [t for t, _ in c.info]
        assert set(titles) <= {"Στόχος", "Λεπτομέρειες", "Ενδεικτική", "Προειδοποιήσεις", "Σχόλια"}
        assert all(lines for _, lines in c.info)  # τίτλος χωρίς περιεχόμενο δεν υπάρχει
        assert ("Ενδεικτική" in titles) == c.indicative
        inside = [ln for _, lines in c.info for ln in lines]
        texts = [b for a, b in inside if not a]
        for x in (*c.messages, *c.warnings):  # κάθε σχόλιο και προειδοποίηση μία φορά μέσα στο info
            assert texts.count(x) == 1, (c.title, x)
        assert [ln for ln in inside if ln[0]] == list(c.info_lines) or \
            sorted(ln for ln in inside if ln[0]) == sorted(c.info_lines)


def test_indicative_reason_is_written_inside_the_info():
    inp = person(ancestry=None, profile="Υγεία", resistance_training=False)
    c = {x.title: x for x in cards(rv.results(inp, al.Measures())[0])}
    why = dict(c["Λίπος"].info)["Ενδεικτική"]
    assert any("Δεν δηλώθηκε καταγωγή" in b for _, b in why)
    generic = [x for x in cards(rv.results(*CASES["άνδρας 139 kg, όλα τα πεδία"])[0])
               if x.indicative and dict(x.info)["Ενδεικτική"] == (("", rv.INDICATIVE_GENERIC),)]
    assert all(not any(rv._says_indicative(m) for m in (*x.messages, *x.why)) for x in generic)


def test_health_profile_shows_a_range_like_the_other_profiles():
    inp = person(weight_kg=140.0, fat_percent=42.5, height_cm=180.0, profile="Υγεία", resistance_training=False,
                 birth_date=date(1990, 1, 1))
    w = rows_of(rv.results(inp, al.Measures())[0])["Βάρος"]
    assert w.target == "≈ 84,0 kg έως ≈ 58,8 kg"
    assert w.change.parts == (("down", "▼ −56,0 kg έως −81,2 kg, −40,0% έως −58,0%"),)


def test_basics_and_start_values_come_from_the_code():
    inp, m = CASES["άνδρας 139 kg, όλα τα πεδία"]
    groups, _ = rv.results(inp, m)
    assert dict(groups[0].lines) == {"Ηλικία": "37 ετών", "Ύψος": "177,0 cm", "Φύλο": "Άνδρας", "Προφίλ": "Αθλητικό",
                                     "Επίπεδο μέτρησης": "Normal", "Σκελετός": "Δεν έχει οριστεί"}
    c = {x.title: x for x in cards(groups)}
    prep = al.prepare(inp)
    points = al._targets(inp.weight_kg, inp.fat_percent, prep.user)
    assert c["Βάρος"].main == (("Σήμερα", "138,9 kg"),)
    assert c["Βάρος"].targets == (("Βάρος-στόχος", "≈ 79,2 kg (−59,7) → ≈ 67,8 kg (−71,1)"),)
    assert not any("Φάση 1" in x for card in c.values() for ln in (*card.main, *card.targets, *card.details) for x in ln)
    assert [round(p.weight_kg, 1) for p in points] == [79.2, 67.8]  # οι τιμές του Στοιχείου 03, όχι νέος υπολογισμός
    assert c["Λίπος"].main == (("Σήμερα", "43,2% · 60,0 kg"), ("Ταξινόμηση", prep.fat.health_label))
    assert c["Λίπος"].targets == (("Εύρος λίπους του προφίλ", "6,0–13,0%"),)
    assert c["ΔΜΣ"].main == (("Σήμερα", "44,3"), ("Κατηγορία", prep.bmi.category))
    assert c["ΔΜΣ"].targets == (("ΔΜΣ στο βάρος-στόχο", "≈ 25,3 → ≈ 21,6"),)
    assert [round(p.bmi, 1) for p in points] == [25.3, 21.6]


def test_headline_for_cards_without_row_spec():
    c = {x.title: x for g in rv.results(*CASES["Professional"])[0] for x in g.cards}
    assert rv.headline(c["Σκελετός"]) == ("Σκελετός", None, c["Σκελετός"].main)  # μόνο τίτλος, γραμμές από κάτω
    sk = c["Σκελετός"].rows[0]
    assert sk.value is None and sk.missing == "" and ("Σκελετός", "Μεσαίος") in sk.subs
    assert rv.headline(c["Εκτομορφία"])[:2] == ("Εκτομορφία", c["Εκτομορφία"].main[0][1])
    assert rv.headline(rv.Card("Χ"))[1] == rv.NOT_COMPUTED


def test_error_goes_through_unchanged():
    bad = person(height_cm=20.0)
    assert rv.results(bad, al.Measures()) == ((), al.measurement_sections(bad, al.Measures())[1])


def test_no_calculation_module_changed():
    # η παρουσίαση δεν γράφει σε κανένα module υπολογισμού: δεν εισάγεται από αυτά
    src = Path(__file__).resolve().parents[1] / "src" / "davinci"
    for f in src.glob("*.py"):
        if f.name not in ("results_view.py", "history.py"):
            assert "results_view" not in f.read_text(encoding="utf-8"), f.name
