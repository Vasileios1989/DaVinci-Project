"""Παρουσίαση της καρτέλας «Αποτελέσματα»: ομάδες και κάρτες (σύμβαση συστήματος, απόφαση του χρήστη 11/11/2026).

Δεν υπολογίζει τίποτα. Παίρνει τις ενότητες του `app_logic.measurement_sections` και την αφετηρία του
`app_logic.prepare` όπως είναι και τις μοιράζει σε κάρτες, με τη σειρά της «Αναφοράς Σωματικής Σύνθεσης»:
Βασικά στοιχεία · Σύσταση σώματος · Μετρήσεις κορμού · Μετρήσεις άκρων · Αναλογίες κορμού · Αναλογίες άκρων
και, μετά, ό,τι άλλο βγάζει ο κώδικας (σκελετός, δερματοπτυχές, σωματότυπος, ενυδάτωση).

Κάθε κάρτα δείχνει: τη μέτρηση (και την ταξινόμησή της), τις γραμμές στόχου ή εκτίμησης στο βάρος-στόχο (🎯),
και μέσα στο ⓘ όλες τις άλλες γραμμές και τα σχόλια. Οι ετικέτες και οι τιμές μένουν αυτολεξεί: όπου ο κώδικας
γράφει «Αναμενόμενο», η κάρτα δεν το μετονομάζει σε «Στόχο». Καμία γραμμή, μήνυμα ή προειδοποίηση δεν χάνεται:
ό,τι δεν ταιριάζει σε κάρτα πηγαίνει στην ομάδα «Άλλα». Η μόνη αλλαγή στα κείμενα: οι αναφορές σε αριθμούς
στοιχείων («(Στοιχείο 05)», «των Στοιχείων 15 και 16») δεν εμφανίζονται (`clean_text`).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from davinci import app_logic as al
from davinci import element_01 as e01
from davinci.fmt import num

Line = tuple[str, str]


@dataclass(frozen=True)
class Card:
    title: str
    main: tuple[Line, ...] = ()  # μέτρηση και ταξινόμηση
    targets: tuple[Line, ...] = ()  # στόχος ή εκτίμηση στο βάρος-στόχο
    details: tuple[Line, ...] = ()  # οι υπόλοιπες γραμμές της ενότητας (μέσα στο ⓘ)
    messages: tuple[str, ...] = ()  # σχόλια (μέσα στο ⓘ)
    warnings: tuple[str, ...] = ()  # προειδοποιήσεις (μένουν ορατές)
    indicative: bool = False
    table: tuple[tuple[str, ...], ...] = ()


@dataclass(frozen=True)
class Group:
    title: str
    cards: tuple[Card, ...] = ()
    lines: tuple[Line, ...] = ()  # μόνο στα «Βασικά στοιχεία»


@dataclass(frozen=True)
class Spec:
    """Μία κάρτα: από ποια ενότητα παίρνει γραμμές και ποιες.
    Η κάρτα-ιδιοκτήτης (owner) παίρνει και ό,τι περισσεύει από την ενότητα, τα σχόλια, τις προειδοποιήσεις και
    τον πίνακα. Οι άλλες κάρτες παίρνουν μόνο τις γραμμές που ονομάζουν."""
    title: str
    source: tuple[str, ...]  # τίτλος ενότητας χωρίς το «(Στοιχείο …)»· περισσότερα από ένα = εναλλακτικοί
    main: tuple[str, ...] = ()  # αρχή της ετικέτας
    targets: tuple[str, ...] | None = None  # None = όλες οι γραμμές στόχου που δεν πήρε άλλη κάρτα
    owner: bool = True


_ELEMENT = re.compile(r"\s*\(Στοιχεί[οα] [^)]*\)$")
_ELEMENT_ANYWHERE = re.compile(r"\s*\(Στοιχεί[οα] [^)]*\)")
_ELEMENT_IN_LIST = re.compile(r", Στοιχεί[οα] [^,)]*(?=\))")
_ELEMENTS_GENITIVE = re.compile(r" των Στοιχείων \d+ και \d+| του Στοιχείου \d+")
GENERIC_LABELS = ("Μέτρηση", "Σήμερα", "Περιφέρεια μέσης")  # η τιμή γράφεται δίπλα στον τίτλο της κάρτας
NOT_COMPUTED = "δεν υπολογίστηκε"
# Γραμμές στόχου ή εκτίμησης στο βάρος-στόχο, όπως τις ονομάζει ο κώδικας.
_TARGET = re.compile(r"[σΣ]τόχος|στο βάρος-στόχο|^Απόσταση από τον στόχο|^Αναμενόμεν\S+ .*στα \S+ kg"
                     r"|^Ελάχιστος λόγος στα |^Μέση στα |^Εύρος λίπους του προφίλ")
_MAIN_ALWAYS = ("Μέτρηση", "Μετρήσεις", "Ταξινόμηση")

WEIGHT, FAT, BMI = "Βάρος", "Λίπος", "ΔΜΣ"
_FFMI = "Άλιπη μάζα και ΔΑΜ"
_MUSCLE = "Σκελετικοί μύες"
_RATIOS = "Λόγοι άλιπης / λίπους και μυών / λίπους"

LAYOUT: tuple[tuple[str, tuple[Spec, ...]], ...] = (
    ("Σύσταση σώματος", (
        Spec(WEIGHT, (WEIGHT,), ("Σήμερα",)),
        Spec(FAT, (FAT,), ("Σήμερα",)),
        Spec("Σπλαχνικό λίπος", ("Σπλαχνικό λίπος",), ("Σπλαχνικό λίπος",)),
        Spec("Άλιπη μάζα", (_FFMI,), ("Άλιπη μάζα",), ("Άλιπη μάζα-στόχος",), owner=False),
        Spec(_MUSCLE, (_MUSCLE,), ("Σκελετικοί μύες",)),
        Spec("Ξηροί μύες", (_MUSCLE,), ("Ξηροί μύες (εκτίμηση)",), ("Ξηροί μύες-στόχος",), owner=False),
        Spec("Υγρά", ("Υγρά",), ("Υγρά",)),
        Spec("Οστά", ("Οστά",), ("Οστικά μέταλλα", "Υγεία οστών")),
        Spec("Ανάλυση άλιπης μάζας", ("Ανάλυση άλιπης μάζας",)),
        Spec("Λόγος μυών / λίπους", (_RATIOS,), ("Λόγος μυών / λίπους",), ("Στόχος μυών / λίπους",), owner=False),
        Spec("Λόγος άλιπης / λίπους", (_RATIOS,), ("Λόγος άλιπης / λίπους", "Ένδειξη")),
        Spec("Δείκτης Άλιπης Μάζας (ΔΑΜ)", (_FFMI,), ("ΔΑΜ", "Κανονικοποιημένος ΔΑΜ", "Ένδειξη")),
        Spec(BMI, (BMI,), ("Σήμερα", "Κατηγορία")),
    )),
    ("Μετρήσεις κορμού", (
        Spec("Μέση", ("Μέση",), ("Περιφέρεια μέσης",)),
        Spec("Ισχίο", ("Ισχίο",)),
        Spec("Λαιμός", ("Λαιμός",), ("Όριο STOP-Bang",)),
        Spec("Στήθος", ("Στήθος",)),
        Spec("Ώμοι", ("Ώμοι",)),
    )),
    ("Μετρήσεις άκρων", (
        Spec("Μπράτσο και δικέφαλος", ("Μπράτσο και δικέφαλος",), ("Μπράτσο χαλαρό", "Δικέφαλος σφιγμένος")),
        Spec("Πήχης", ("Πήχης",), ("Πήχης χαλαρός", "Πήχης σφιγμένος")),
        Spec("Καρπός", ("Καρπός",)),
        Spec("Μηρός", ("Μηρός",)),
        Spec("Πάνω από το γόνατο", ("Πάνω από το γόνατο",)),
        Spec("Γάμπα", ("Γάμπα",)),
        Spec("Αστράγαλος", ("Αστράγαλος",)),
    )),
    ("Αναλογίες κορμού", (
        Spec("Λόγος μέσης / ισχίου", ("Λόγος μέσης / ισχίου",), ("Λόγος",)),
        Spec("Λόγος μέσης / ύψους", ("Μέση",), ("Λόγος μέσης/ύψους", "Ταξινόμηση", "Πότε αρχίζει η ταξινόμηση"), (),
             owner=False),
        Spec("Λόγος στήθους / μέσης", ("Λόγος στήθους / μέσης",), ("Λόγος",)),
        Spec("Λόγος ώμων / μέσης", ("Λόγος ώμων / μέσης",), ("Λόγος",)),
    )),
    ("Αναλογίες άκρων", (
        Spec("Λόγος πήχη / δικεφάλου", ("Λόγος πήχη / δικεφάλου",), ("Λόγος",)),
        Spec("Λόγος μηρού / γάμπας", ("Λόγος μηρού / γάμπας",), ("Λόγος",)),
        Spec("Λόγος καρπού / δικεφάλου", ("Λόγος καρπού / δικεφάλου",), ("Λόγος",)),
        Spec("Λόγος μηρού / γονάτου", ("Λόγος μηρού / γονάτου",), ("Λόγος",)),
        Spec("Λόγος αστραγάλου / γάμπας", ("Λόγος αστραγάλου / γάμπας",), ("Λόγος",)),
    )),
    ("Σκελετός και δερματοπτυχές", (
        Spec("Σκελετός", ("Σκελετός", "Σκελετός — εύρος αγκώνα"), ("Σκελετός", "Εύρος αγκώνα")),
        Spec("Εύρος γονάτου", ("Εύρος γονάτου",)),
        Spec("Δερματοπτυχή τρικεφάλου", ("Δερματοπτυχή τρικεφάλου",)),
        Spec("Δερματοπτυχή υποπλάτιου", ("Δερματοπτυχή υποπλάτιου",)),
        Spec("Δερματοπτυχή υπερακάνθιου", ("Δερματοπτυχή υπερακάνθιου",)),
        Spec("Δερματοπτυχή γάμπας", ("Δερματοπτυχή γάμπας",)),
        Spec("Εύρη οστών και δερματοπτυχές", ("Εύρη οστών και δερματοπτυχές",)),
    )),
    ("Σωματότυπος", (
        Spec("Ενδομορφία", ("Ενδομορφία",), ("Ενδομορφία",)),
        Spec("Μεσομορφία", ("Μεσομορφία",), ("Μεσομορφία",)),
        Spec("Ενδομορφία και μεσομορφία", ("Ενδομορφία και μεσομορφία",)),
        Spec("Εκτομορφία", ("Εκτομορφία",), ("Εκτομορφία", "Κλίμακα Heath-Carter")),
    )),
    ("Ενυδάτωση", (
        Spec("Ενυδάτωση", ("Ενυδάτωση",), ("Ενυδάτωση",)),
    )),
)
OTHER = "Άλλα"


def clean_title(title: str) -> str:
    """«Μέση (Στοιχείο 05)» → «Μέση»."""
    return _ELEMENT.sub("", title)


def clean_text(text: str) -> str:
    """Κείμενο όπως εμφανίζεται στα «Αποτελέσματα»: χωρίς τις παρενθέσεις «(Στοιχείο …)»."""
    text = _ELEMENT_ANYWHERE.sub("", text)
    text = _ELEMENT_IN_LIST.sub("", text)  # «(από το εύρος αγκώνα, Στοιχείο 32)» → «(από το εύρος αγκώνα)»
    return _ELEMENTS_GENITIVE.sub("", text)  # «με τις εκτιμήσεις των Στοιχείων 15 και 16 (…)» → «με τις εκτιμήσεις (…)»


def _clean_lines(lines) -> tuple[Line, ...]:
    return tuple((clean_text(a), clean_text(b)) for a, b in lines)


def headline(card: "Card") -> tuple[str, str | None, tuple[Line, ...]]:
    """(τίτλος, τιμή δίπλα στον τίτλο ή None, υπόλοιπες κύριες γραμμές).
    Η τιμή μπαίνει δίπλα στον τίτλο όταν η πρώτη κύρια γραμμή λέγεται «Μέτρηση» ή «Σήμερα», όπως η κάρτα
    (τότε ο τίτλος γράφεται όπως η γραμμή, π.χ. «Ξηροί μύες (εκτίμηση)»), ή είναι η συντομογραφία του τίτλου
    («ΔΑΜ»). Κάρτα χωρίς καμία γραμμή και χωρίς πίνακα: «δεν υπολογίστηκε» (ο λόγος είναι στο ⓘ)."""
    if not card.main:
        empty = not (card.targets or card.details or card.table)
        return card.title, (NOT_COMPUTED if empty else None), ()
    label, value = card.main[0]
    if label in GENERIC_LABELS or f"({label})" in card.title:
        return card.title, value, card.main[1:]
    if label.startswith(card.title):
        return label, value, card.main[1:]
    return card.title, None, card.main


def _starts(label: str, prefixes: tuple[str, ...]) -> bool:
    return any(label.startswith(p) for p in prefixes)


# --- ενότητες αφετηρίας: ό,τι δείχνει ήδη το «Πλάνο» (Στοιχεία 02, 03, 04), χωρίς νέο υπολογισμό ------------
def start_sections(inp: al.PlanInput) -> tuple[al.Section, ...]:
    """Βάρος, Λίπος και ΔΜΣ ως ενότητες· () όταν η αφετηρία έχει σφάλμα (το δείχνουν οι μετρήσεις)."""
    prep = al.prepare(inp)
    if prep.errors or prep.user is None:
        return ()
    points = al._targets(inp.weight_kg, inp.fat_percent, prep.user)
    w = inp.weight_kg
    lines: list[Line] = [("Σήμερα", f"{num(w, 1)} kg")]
    if points:
        lines.append(("Βάρος-στόχος (Φάση 1)", " → ".join(
            f"≈ {num(p.weight_kg, 1)} kg ({al._signed(p.weight_kg - w)})" for p in points)))
    out = [al.Section(WEIGHT, tuple(lines))]

    fat, bmi = prep.fat, prep.bmi
    if fat is not None:
        lines = [("Σήμερα", f"{num(fat.fat_percent, 1)}% · {num(fat.fat_kg, 1)} kg")]
        label = fat.health_label or fat.health_category
        if label:
            lines.append(("Ταξινόμηση", label))
        if fat.profile_range:
            lo, hi = fat.profile_range
            lines.append(("Εύρος λίπους του προφίλ", f"{num(lo, 1)}–{num(hi, 1)}%"))
        out.append(al.Section(FAT, tuple(lines), tuple(fat.messages), fat.indicative))
    if bmi is not None:
        lines = [("Σήμερα", num(bmi.value, 1))]
        if bmi.category:
            lines.append(("Κατηγορία", bmi.category))
        if points:
            lines.append(("ΔΜΣ στο βάρος-στόχο", " → ".join(f"≈ {num(p.bmi, 1)}" for p in points)))
        out.append(al.Section(BMI, tuple(lines), tuple(bmi.messages), bmi.indicative))
    return tuple(out)


def basics(inp: al.PlanInput, sections: tuple[al.Section, ...]) -> tuple[Line, ...]:
    """Βασικά στοιχεία: όσα δήλωσε ο χρήστης, και ο σκελετός όπως τον δίνει ο κώδικας."""
    age = e01.age_in_completed_years(inp.birth_date, inp.today)
    lines: list[Line] = [("Ηλικία", f"{age} ετών"), ("Ύψος", f"{num(inp.height_cm, 1)} cm"), ("Φύλο", inp.sex),
                         ("Προφίλ", inp.profile), ("Επίπεδο μέτρησης", inp.level)]
    for sec in sections:
        if clean_title(sec.title).startswith("Σκελετός"):
            lines += [line for line in sec.lines if line[0] == "Σκελετός"][:1]
    return tuple(lines)


# --- κάρτες ----------------------------------------------------------------------------------------------
def _cards(specs: tuple[Spec, ...], by_title: dict[str, al.Section], taken: dict[str, set[int]]) -> list[Card]:
    cards = []
    for spec in specs:
        name = next((s for s in spec.source if s in by_title), None)
        if name is None:
            continue
        sec, used = by_title[name], taken.setdefault(name, set())
        free = [(i, line) for i, line in enumerate(sec.lines) if i not in used]
        if spec.owner:
            # ό,τι ονόμασαν οι άλλες κάρτες της ίδιας ενότητας δεν το παίρνει ο ιδιοκτήτης
            others = [s for _, ss in LAYOUT for s in ss if not s.owner and name in s.source]
            free = [(i, line) for i, line in free if not any(_claims(o, line[0]) for o in others)]
        main, targets, details = [], [], []
        for i, line in free:
            label = line[0]
            if spec.targets is not None and _starts(label, spec.targets):
                targets.append(line)
            elif _starts(label, spec.main) or (spec.owner and label in _MAIN_ALWAYS):
                main.append(line)
            elif spec.targets is None and _TARGET.search(label):
                targets.append(line)
            elif spec.owner:
                details.append(line)
            else:
                continue
            used.add(i)
        if spec.owner and not main and details and not sec.table:
            main.append(details.pop(0))  # ενότητα χωρίς γνωστή γραμμή μέτρησης: η πρώτη της γραμμή
        if not spec.owner and not (main or targets):
            continue
        cards.append(Card(spec.title, _clean_lines(main), _clean_lines(targets), _clean_lines(details),
                          tuple(map(clean_text, sec.messages)) if spec.owner else (),
                          tuple(map(clean_text, sec.warnings)) if spec.owner else (),
                          sec.indicative, sec.table if spec.owner else ()))
    return cards


def _claims(spec: Spec, label: str) -> bool:
    return _starts(label, spec.main) or (spec.targets is not None and _starts(label, spec.targets))


def results(inp: al.PlanInput, m: al.Measures) -> tuple[tuple[Group, ...], tuple[str, ...]]:
    """Ομάδες καρτών της καρτέλας «Αποτελέσματα» και σφάλματα. Οι τιμές είναι του `app_logic`, αυτούσιες."""
    measured, errors = al.measurement_sections(inp, m)
    sections = (*start_sections(inp), *measured)
    by_title = {clean_title(s.title): s for s in sections}
    taken: dict[str, set[int]] = {}
    groups = []
    if not errors:
        groups.append(Group("Βασικά στοιχεία", lines=basics(inp, sections)))
    for title, specs in LAYOUT:
        cards = _cards(specs, by_title, taken)
        if cards:
            groups.append(Group(title, tuple(cards)))
    known = {s for _, specs in LAYOUT for spec in specs if spec.owner for s in spec.source}
    rest = tuple(Card(clean_title(s.title), _clean_lines(s.lines[:1]), (), _clean_lines(s.lines[1:]),
                      tuple(map(clean_text, s.messages)), tuple(map(clean_text, s.warnings)), s.indicative,
                      s.table) for s in sections if clean_title(s.title) not in known)
    if rest:
        groups.append(Group(OTHER, rest))
    return tuple(groups), errors
