"""Παρουσίαση της καρτέλας «Αποτελέσματα» (σύμβαση συστήματος, αποφάσεις του χρήστη 11/11/2026).

Δεν αλλάζει κανέναν υπολογισμό. Παίρνει τις ενότητες του `app_logic.measurement_sections` και την αφετηρία του
`app_logic.prepare` όπως είναι και τις μοιράζει σε καρτέλες (κουμπιά), με τη σειρά:
Βασικά · Σύσταση · Ιστοί (Α) · Συστατικά (Β) · Δείκτες · Κορμός · Άκρα · Αναλογίες κορμού · Αναλογίες άκρων · Άλλα.

Κάθε κάρτα έχει δύο όψεις:
- την πλήρη καταγραφή (`main`, `targets`, `details`, `messages`, `warnings`, `table`): κάθε γραμμή του κώδικα
  ακριβώς μία φορά, αυτούσια (έλεγχος: tests/test_results_view.py)·
- τις γραμμές της οθόνης (`rows`): μέτρηση, αλλαγή προς τον στόχο (▼ / ▲) και, από κάτω, (Στόχος: …).

Η αλλαγή προς τον στόχο είναι η μόνη νέα πράξη: στόχος μείον μέτρηση, και η ίδια διαφορά ως % της μέτρησης.
Γίνεται με τις τιμές όπως εμφανίζονται, ώστε μέτρηση + αλλαγή = στόχος στην οθόνη (σύμβαση συστήματος).
Οι στόχοι είναι μόνο όσοι δίνει ο κώδικας· όπου δεν δίνει, γράφεται «—». Όπου ο κώδικας λέει «Αναμενόμενο»
(εκτίμηση, όχι στόχος), η λέξη μένει.

Αλλαγές στα κείμενα: οι αναφορές σε αριθμούς στοιχείων («(Στοιχείο 05)», «των Στοιχείων 15 και 16») δεν
εμφανίζονται, και στο μήνυμα της ανάλυσης άλιπης μάζας τα γράμματα Α / Β ακολουθούν τις επικεφαλίδες της οθόνης
(Α = ιστοί, Β = συστατικά) (`clean_text`).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from davinci import app_logic as al
from davinci import element_01 as e01
from davinci.fmt import num

Line = tuple[str, str]
NOT_COMPUTED = "δεν υπολογίστηκε"
NOT_MEASURED = "δεν μετρήθηκε"
NO_TARGET = "—"
DOWN, UP = "down", "up"


# --- κείμενα ----------------------------------------------------------------------------------------------
_ELEMENT = re.compile(r"\s*\(Στοιχεί[οα] [^)]*\)$")
_ELEMENT_ANYWHERE = re.compile(r"\s*\(Στοιχεί[οα] [^)]*\)")
_ELEMENT_IN_LIST = re.compile(r", Στοιχεί[οα] [^,)]*(?=\))")
_ELEMENTS_GENITIVE = re.compile(r" των Στοιχείων \d+ και \d+| του Στοιχείου \d+")
# Στοιχείο 03, μήνυμα της ανάλυσης: στην οθόνη Α = ιστοί, Β = συστατικά (απόφαση του χρήστη 11/11/2026)
_AB_CODE = "Ο Α δείχνει από τι υλικό αποτελείται και ο Β από ποιους ιστούς"
_AB_SCREEN = "Ο Α δείχνει από ποιους ιστούς αποτελείται και ο Β από τι υλικό"


def clean_title(title: str) -> str:
    """«Μέση (Στοιχείο 05)» → «Μέση»."""
    return _ELEMENT.sub("", title)


def clean_text(text: str) -> str:
    """Κείμενο όπως εμφανίζεται στα «Αποτελέσματα»: χωρίς αναφορές σε αριθμούς στοιχείων."""
    text = _ELEMENT_ANYWHERE.sub("", text)
    text = _ELEMENT_IN_LIST.sub("", text)  # «(από το εύρος αγκώνα, Στοιχείο 32)» → «(από το εύρος αγκώνα)»
    text = _ELEMENTS_GENITIVE.sub("", text)  # «με τις εκτιμήσεις των Στοιχείων 15 και 16 (…)» → «με τις εκτιμήσεις (…)»
    return text.replace(_AB_CODE, _AB_SCREEN)


def _clean_lines(lines) -> tuple[Line, ...]:
    return tuple((clean_text(a), clean_text(b)) for a, b in lines)


# --- δομές -----------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Change:
    """Αλλαγή προς τον στόχο: ένα κομμάτι ανά κατεύθυνση (συνήθως ένα)."""
    parts: tuple[tuple[str, str], ...]  # (DOWN | UP, κείμενο)


@dataclass(frozen=True)
class Row:
    """Μία γραμμή της οθόνης."""
    name: str
    value: str | None  # None → δεν υπολογίστηκε / δεν μετρήθηκε
    missing: str = NOT_COMPUTED  # «» = κάρτα με μόνο τίτλο (οι τιμές είναι στις γραμμές από κάτω)
    note: str | None = None  # π.χ. «52,6% της άλιπης»
    change: Change | None = None
    target_word: str | None = None  # None → καμία γραμμή στόχου (κάρτες χωρίς στόχους, «Άλλα»)
    target: str = NO_TARGET
    subs: tuple[Line, ...] = ()  # δευτερεύουσες γραμμές κάτω από τη μέτρηση (ταξινόμηση κ.λπ.)
    level: int = 0  # εσοχή: 1 = μέρος της από πάνω γραμμής


@dataclass(frozen=True)
class Card:
    title: str
    main: tuple[Line, ...] = ()  # μέτρηση και ταξινόμηση
    targets: tuple[Line, ...] = ()  # στόχος ή εκτίμηση στο βάρος-στόχο
    details: tuple[Line, ...] = ()  # οι υπόλοιπες γραμμές της ενότητας
    messages: tuple[str, ...] = ()  # σχόλια (μέσα στο ⓘ)
    warnings: tuple[str, ...] = ()  # προειδοποιήσεις (μένουν ορατές)
    indicative: bool = False
    table: tuple[tuple[str, ...], ...] = ()
    rows: tuple[Row, ...] = ()
    needs: tuple[str, ...] = ()  # σχόλια «χρειάζεται …» μιας κάρτας χωρίς τιμή: ορατά, όχι στο ⓘ
    info_lines: tuple[Line, ...] = ()  # γραμμές του ⓘ (όσες δεν φαίνονται αυτούσιες στις γραμμές της οθόνης)
    show_table: bool = True  # False: ο πίνακας φαίνεται ως γραμμές (ανάλυση άλιπης μάζας)


@dataclass(frozen=True)
class Group:
    """Μία καρτέλα (κουμπί) των «Αποτελεσμάτων»."""
    title: str  # σύντομο όνομα κουμπιού
    heading: str = ""
    cards: tuple[Card, ...] = ()
    lines: tuple[Line, ...] = ()  # μόνο στα «Βασικά»
    todo: str | None = None  # «Συμπλήρωσε …» για γραμμές που δεν υπολογίστηκαν


@dataclass(frozen=True)
class R:
    """Προδιαγραφή μίας γραμμής της οθόνης.
    value: ετικέτα της γραμμής του κώδικα με την τιμή (ίδια, ή η ίδια συνέχεια με « (…)»)· table: όνομα γραμμής
    του πίνακα της ανάλυσης άλιπης μάζας. targets: αρχή της ετικέτας των γραμμών στόχου. delta: αν η αλλαγή
    προς τον στόχο έχει νόημα (ίδιο μέγεθος στη μέτρηση και στον στόχο)."""
    name: str
    value: str | None = None
    targets: tuple[str, ...] = ()
    word: str = "Στόχος"
    delta: bool = True
    subs: tuple[str, ...] = ()
    level: int = 0
    table: str | None = None
    pct: str | None = None  # γραμμή του πίνακα με το «% άλιπης» για τη σημείωση
    pct_line: str | None = None  # ή γραμμή της κάρτας με το «% της άλιπης μάζας»
    show_label: bool = True  # όνομα = ετικέτα του κώδικα (π.χ. «Ξηροί μύες (εκτίμηση)»)
    missing: str = NOT_COMPUTED
    fixed: str | None = None  # στόχος που δεν είναι γραμμή της ενότητας (βλ. `_fixed_targets`)


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
    rows: tuple[R, ...] | None = None  # None = γενική γραμμή (τίτλος, τιμή, οι υπόλοιπες κύριες γραμμές)
    always: bool = False  # η κάρτα εμφανίζεται και χωρίς ενότητα / γραμμές (με «δεν υπολογίστηκε»)


# Γραμμές στόχου ή εκτίμησης στο βάρος-στόχο, όπως τις ονομάζει ο κώδικας.
_TARGET = re.compile(r"[σΣ]τόχος|στο βάρος-στόχο|^Απόσταση από τον στόχο|^Αναμενόμεν\S+ .*στα \S+ kg"
                     r"|^Ελάχιστος λόγος στα |^Μέση στα |^Εύρος λίπους του προφίλ")
_MAIN_ALWAYS = ("Μέτρηση", "Μετρήσεις", "Ταξινόμηση")
GENERIC_LABELS = ("Μέτρηση", "Σήμερα", "Περιφέρεια μέσης")  # η τιμή γράφεται δίπλα στον τίτλο της κάρτας

WEIGHT, FAT, BMI = "Βάρος", "Λίπος", "ΔΜΣ"
_FFMI = "Άλιπη μάζα και ΔΑΜ"
_MUSCLE = "Σκελετικοί μύες"
_RATIOS = "Λόγοι άλιπης / λίπους και μυών / λίπους"
_ANALYSIS = "Ανάλυση άλιπης μάζας"
_EXP = "Αναμενόμενο"


def _ratio(title: str, word: str = _EXP, prefix: str = "Αναμενόμενος λόγος") -> Spec:
    return Spec(title, (title,), ("Λόγος",), rows=(R(title, title, (prefix,), word, show_label=False),))


def _girth(title: str, prefix: str, subs: tuple[str, ...] = ()) -> Spec:
    return Spec(title, (title,), rows=(R(title, "Μέτρηση", (prefix,) if prefix else (), _EXP if prefix else "Στόχος",
                                         subs=subs, show_label=False),))


TABS: tuple[tuple[str, str, tuple[Spec, ...]], ...] = (
    ("Σύσταση", "Σύσταση σώματος", (
        Spec(WEIGHT, (WEIGHT,), ("Σήμερα",), rows=(R(WEIGHT, "Σήμερα", ("Βάρος-στόχος",), show_label=False),)),
        Spec(FAT, (FAT,), ("Σήμερα",), rows=(R(FAT, "Σήμερα", ("Εύρος λίπους του προφίλ",), subs=("Ταξινόμηση",),
                                               show_label=False),)),
        Spec("Σπλαχνικό λίπος", ("Σπλαχνικό λίπος",), ("Σπλαχνικό λίπος",), always=True,
             rows=(R("Σπλαχνικό λίπος", "Σπλαχνικό λίπος", subs=("Ταξινόμηση", "Τιμή ζυγαριάς")),)),
        Spec("Άλιπη μάζα", (_FFMI,), ("Άλιπη μάζα",), ("Άλιπη μάζα-στόχος",), owner=False,
             rows=(R("Άλιπη μάζα", "Άλιπη μάζα", ("Άλιπη μάζα-στόχος",)),)),
    )),
    ("Ιστοί (Α)", "Α. Άλιπη μάζα σε ιστούς", (
        Spec(_MUSCLE, (_MUSCLE,), ("Σκελετικοί μύες",), always=True, rows=(
            R(_MUSCLE, _MUSCLE, ("Ενδεικτικός στόχος μυών",), "Ενδεικτικός στόχος", subs=("Ταξινόμηση",),
              pct=_MUSCLE),
            R("Ξηροί μύες", "Ξηροί μύες (εκτίμηση)", ("Ξηροί μύες-στόχος",), level=1, pct="Ξηροί μύες"))),
        Spec("Λοιποί ιστοί", (_ANALYSIS,), owner=False, always=True,
             rows=(R("Λοιποί ιστοί", table="Λοιποί ιστοί"),)),
    )),
    ("Συστατικά (Β)", "Β. Άλιπη μάζα σε συστατικά", (
        Spec("Νερό", ("Υγρά",), ("Υγρά",), rows=(
            R("Νερό", "Υγρά", ("Ενδεικτικός στόχος υγρών",), "Ενδεικτικός στόχος", pct="Νερό", show_label=False),)),
        Spec("Ξηρή άλιπη μάζα", (_ANALYSIS,), owner=False, always=True,
             rows=(R("Ξηρή άλιπη μάζα", table="Ξηρή άλιπη μάζα"),)),
        Spec("Οστικά μέταλλα", ("Οστά",), ("Οστικά μέταλλα", "Υγεία οστών"), rows=(
            R("Οστικά μέταλλα", "Οστικά μέταλλα", subs=("Υγεία οστών",), level=1, pct_line="% της άλιπης μάζας"),)),
        Spec("Λοιπά", (_ANALYSIS,), always=True, rows=(
            R("Λοιπά", table="Λοιπά", level=1),
            R("Πρωτεΐνη", table="Πρωτεΐνη", level=2), R("Γλυκογόνο", table="Γλυκογόνο", level=2),
            R("Άλλα μέταλλα", table="Άλλα μέταλλα", level=2), R("Διαφορά", table="Διαφορά", level=2))),
    )),
    ("Δείκτες", "Δείκτες", (
        Spec("Λόγος μυών / λίπους", (_RATIOS,), ("Λόγος μυών / λίπους",), ("Στόχος μυών / λίπους",), owner=False,
             rows=(R("Λόγος μυών / λίπους", "Λόγος μυών / λίπους", ("Στόχος μυών / λίπους",)),)),
        Spec("Λόγος άλιπης / λίπους", (_RATIOS,), ("Λόγος άλιπης / λίπους", "Ένδειξη"),
             rows=(R("Λόγος άλιπης / λίπους", "Λόγος άλιπης / λίπους", ("Στόχος άλιπης / λίπους",),
                     subs=("Ένδειξη",)),)),
        Spec("Δείκτης Άλιπης Μάζας (ΔΑΜ)", (_FFMI,), ("ΔΑΜ", "Κανονικοποιημένος ΔΑΜ", "Ένδειξη"), rows=(
            R("Δείκτης Άλιπης Μάζας (ΔΑΜ)", "ΔΑΜ", subs=("Ένδειξη",), show_label=False, fixed="ffmi"),
            R("Κανονικοποιημένος ΔΑΜ", "Κανονικοποιημένος ΔΑΜ", level=1, fixed="normalized_ffmi"))),
        Spec(BMI, (BMI,), ("Σήμερα", "Κατηγορία"), rows=(
            R(BMI, "Σήμερα", ("ΔΜΣ στο βάρος-στόχο",), "ΔΜΣ στο βάρος-στόχο", subs=("Κατηγορία",),
              show_label=False),)),
    )),
    ("Κορμός", "Μετρήσεις κορμού", (
        Spec("Μέση", ("Μέση",), ("Περιφέρεια μέσης",),
             rows=(R("Μέση", "Περιφέρεια μέσης", ("Μέση-στόχος",), show_label=False),)),
        _girth("Ισχίο", "Αναμενόμενο ισχίο"),
        Spec("Λαιμός", ("Λαιμός",), ("Όριο STOP-Bang",),
             rows=(R("Λαιμός", "Μέτρηση", subs=("Όριο STOP-Bang",), show_label=False),)),
        _girth("Στήθος", "Αναμενόμενο στήθος"),
        _girth("Ώμοι", "Αναμενόμενοι ώμοι"),
    )),
    ("Άκρα", "Μετρήσεις άκρων", (
        Spec("Μπράτσο και δικέφαλος", ("Μπράτσο και δικέφαλος",), ("Μπράτσο χαλαρό", "Δικέφαλος σφιγμένος"), rows=(
            R("Μπράτσο χαλαρό", "Μπράτσο χαλαρό", subs=("Ταξινόμηση",), missing=NOT_MEASURED),
            R("Δικέφαλος σφιγμένος", "Δικέφαλος σφιγμένος", ("Αναμενόμενος δικέφαλος",), _EXP,
              missing=NOT_MEASURED))),
        Spec("Πήχης", ("Πήχης",), ("Πήχης χαλαρός", "Πήχης σφιγμένος"), rows=(
            R("Πήχης χαλαρός", "Πήχης χαλαρός", subs=("Ταξινόμηση",), missing=NOT_MEASURED),
            R("Πήχης σφιγμένος", "Πήχης σφιγμένος", ("Αναμενόμενος πήχης",), _EXP, missing=NOT_MEASURED))),
        _girth("Καρπός", ""),
        _girth("Μηρός", "Αναμενόμενος μηρός", ("Ταξινόμηση",)),
        _girth("Πάνω από το γόνατο", "Αναμενόμενο πάνω από το γόνατο στα"),
        _girth("Γάμπα", "Αναμενόμενη γάμπα", ("Ταξινόμηση",)),
        _girth("Αστράγαλος", "Αναμενόμενος αστράγαλος"),
    )),
    ("Αναλογίες κορμού", "Αναλογίες κορμού", (
        Spec("Λόγος μέσης / ισχίου", ("Λόγος μέσης / ισχίου",), ("Λόγος",), rows=(
            R("Λόγος μέσης / ισχίου", "Λόγος μέσης / ισχίου", ("Μέση στα",), "Μέση", delta=False,
              subs=("Ταξινόμηση",), show_label=False),)),
        Spec("Λόγος μέσης / ύψους", ("Μέση",), ("Λόγος μέσης/ύψους", "Ταξινόμηση", "Πότε αρχίζει η ταξινόμηση"), (),
             owner=False, rows=(R("Λόγος μέσης / ύψους", "Λόγος μέσης/ύψους",
                                  subs=("Ταξινόμηση", "Πότε αρχίζει η ταξινόμηση"), show_label=False,
                                  fixed="whtr"),)),
        _ratio("Λόγος στήθους / μέσης", "Ελάχιστος λόγος", "Ελάχιστος λόγος"),
        _ratio("Λόγος ώμων / μέσης", "Ελάχιστος λόγος", "Ελάχιστος λόγος"),
    )),
    ("Αναλογίες άκρων", "Αναλογίες άκρων", (
        _ratio("Λόγος πήχη / δικεφάλου"), _ratio("Λόγος μηρού / γάμπας"), _ratio("Λόγος καρπού / δικεφάλου"),
        _ratio("Λόγος μηρού / γονάτου"), _ratio("Λόγος αστραγάλου / γάμπας"),
    )),
    ("Άλλα", "Σκελετός, δερματοπτυχές, σωματότυπος, ενυδάτωση", (
        Spec("Σκελετός", ("Σκελετός", "Σκελετός — εύρος αγκώνα"), ("Σκελετός", "Εύρος αγκώνα")),
        Spec("Εύρος γονάτου", ("Εύρος γονάτου",)),
        Spec("Δερματοπτυχή τρικεφάλου", ("Δερματοπτυχή τρικεφάλου",)),
        Spec("Δερματοπτυχή υποπλάτιου", ("Δερματοπτυχή υποπλάτιου",)),
        Spec("Δερματοπτυχή υπερακάνθιου", ("Δερματοπτυχή υπερακάνθιου",)),
        Spec("Δερματοπτυχή γάμπας", ("Δερματοπτυχή γάμπας",)),
        Spec("Εύρη οστών και δερματοπτυχές", ("Εύρη οστών και δερματοπτυχές",)),
        Spec("Ενδομορφία", ("Ενδομορφία",), ("Ενδομορφία",)),
        Spec("Μεσομορφία", ("Μεσομορφία",), ("Μεσομορφία",)),
        Spec("Ενδομορφία και μεσομορφία", ("Ενδομορφία και μεσομορφία",)),
        Spec("Εκτομορφία", ("Εκτομορφία",), ("Εκτομορφία", "Κλίμακα Heath-Carter")),
        Spec("Ενυδάτωση", ("Ενυδάτωση",), ("Ενυδάτωση",)),
    )),
)
BASICS, OTHER = "Βασικά", "Άλλα"
TAB_TITLES = (BASICS, *(t for t, _, _ in TABS))
TODO = {  # γραμμές που δεν υπολογίστηκαν → πεδία της «Μέτρησης» (περιοχή «Ζυγαριά»)
    _MUSCLE: "Μύες %", "Ξηροί μύες": "Μύες %", "Λοιποί ιστοί": "Μύες %",
    "Ξηρή άλιπη μάζα": "Υγρά %", "Λοιπά": "Υγρά %, Οστά %", "Διαφορά": "Υγρά %, Οστά %",
}


def _starts(label: str, prefixes: tuple[str, ...]) -> bool:
    return any(label.startswith(p) for p in prefixes)


def _is(label: str, value: str) -> bool:
    """Η ετικέτα είναι η ζητούμενη, ή η ίδια με συμπλήρωμα σε παρένθεση («Ξηροί μύες (εκτίμηση)»)."""
    return label == value or label.startswith(value + " (")


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
            lines += [clean_line for clean_line in _clean_lines(sec.lines) if clean_line[0] == "Σκελετός"][:1]
    return tuple(lines)


# --- αριθμοί όπως εμφανίζονται ------------------------------------------------------------------------------
_NUM = re.compile(r"([−-]?)(\d+(?:\.\d{3})*)(?:,(\d+))?")
_UNIT = re.compile(r"\s*(kg/m²|cm²|kg|cm|mm|%)")
_CMP = (("κάτω από", "<"), ("<", "<"), ("≥", "≥"), ("≈", "≈"))


@dataclass(frozen=True)
class Num:
    value: float
    decimals: int
    unit: str
    cmp: str = ""  # «<» (κάτω από), «≥», «≈» ή «»
    text: str = ""  # όπως εμφανίζεται


def parse_num(text: str) -> Num | None:
    """Ο πρώτος αριθμός ενός κειμένου του κώδικα, με τη μονάδα και το σύμβολο σύγκρισης που προηγείται."""
    t = text.strip()
    cmp = next((sym for word, sym in _CMP if t.startswith(word)), "")
    m = _NUM.search(t)
    if m is None:
        return None
    sign, whole, frac = m.groups()
    value = float(whole.replace(".", "") + ("." + frac if frac else ""))
    unit = _UNIT.match(t[m.end():])
    return Num(-value if sign else value, len(frac or ""), unit.group(1) if unit else "", cmp, t)


def _heads(value: str) -> list[str]:
    """«≈ 79,2 kg (−59,7) → ≈ 67,8 kg (−71,1)» → ["≈ 79,2 kg", "≈ 67,8 kg"] · «6,0–13,0%» → ["6,0%", "13,0%"]."""
    out = []
    for part in value.split(" → "):
        head = part.split(" (")[0].strip()
        rng = re.fullmatch(r"(\S+)\s*–\s*(\S+?)(%?)", head)
        if rng and parse_num(rng.group(1)) and parse_num(rng.group(2)):
            out += [rng.group(1) + rng.group(3), rng.group(2) + rng.group(3)]
        else:
            out.append(head)
    return out


def _signed(x: float, decimals: int) -> str:
    s = num(abs(x), decimals)
    return s if float(s.replace(".", "").replace(",", ".")) == 0 else ("−" if x < 0 else "+") + s


def change(now: str, targets: list[str]) -> Change | None:
    """Αλλαγή από τη μέτρηση στον στόχο, με τις τιμές όπως εμφανίζονται.
    «κάτω από Χ»: μόνο αν η μέτρηση δεν είναι ήδη κάτω · «≥ Χ»: μόνο αν είναι ήδη κάτω από Χ · αλλιώς Χ − μέτρηση.
    Το % (διαφορά / μέτρηση) παραλείπεται όταν η μέτρηση είναι ήδη ποσοστό. Διαφορετικές μονάδες: καμία αλλαγή."""
    v = parse_num(now)
    if v is None or v.value == 0:
        return None
    deltas: list[tuple[float, int]] = []
    for t in targets:
        n = parse_num(t)
        if n is None or n.unit != v.unit:
            return None
        d = n.value - v.value
        if (n.cmp == "<" and d > 0) or (n.cmp == "≥" and d < 0):
            continue  # ο στόχος έχει ήδη επιτευχθεί
        dec = max(n.decimals, v.decimals)
        if float(num(abs(d), dec).replace(".", "").replace(",", ".")) == 0:
            continue
        deltas.append((d, dec))
    if not deltas:
        return None
    unit = f" {v.unit}" if v.unit and v.unit != "%" else v.unit
    parts = []
    for direction in (DOWN, UP):
        ds = [(d, dec) for d, dec in deltas if (d < 0) == (direction == DOWN)]
        if not ds:
            continue
        text = " έως ".join(_signed(d, dec) + unit for d, dec in ds)
        if v.unit != "%":
            text += ", " + " έως ".join(_signed(d / v.value * 100, 1) + "%" for d, _ in ds)
        parts.append((direction, ("▼ " if direction == DOWN else "▲ ") + text))
    return Change(tuple(parts))


# --- κάρτες ----------------------------------------------------------------------------------------------
def _cards(specs: tuple[Spec, ...], by_title: dict[str, al.Section], taken: dict[str, set[int]],
           every: tuple[Spec, ...]) -> list[tuple[Spec, Card]]:
    cards = []
    for spec in specs:
        name = next((s for s in spec.source if s in by_title), None)
        if name is None:
            if spec.always:
                cards.append((spec, Card(spec.title)))
            continue
        sec, used = by_title[name], taken.setdefault(name, set())
        free = [(i, line) for i, line in enumerate(sec.lines) if i not in used]
        if spec.owner:
            # ό,τι ονόμασαν οι άλλες κάρτες της ίδιας ενότητας δεν το παίρνει ο ιδιοκτήτης
            others = [s for s in every if not s.owner and name in s.source]
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
        if not spec.owner and not (main or targets) and not spec.always:
            continue
        cards.append((spec, Card(spec.title, _clean_lines(main), _clean_lines(targets), _clean_lines(details),
                                 tuple(map(clean_text, sec.messages)) if spec.owner else (),
                                 tuple(map(clean_text, sec.warnings)) if spec.owner else (),
                                 sec.indicative,
                                 sec.table if spec.owner else ())))
    return cards


def _claims(spec: Spec, label: str) -> bool:
    return _starts(label, spec.main) or (spec.targets is not None and _starts(label, spec.targets))


def headline(card: Card) -> tuple[str, str | None, tuple[Line, ...]]:
    """(τίτλος, τιμή δίπλα στον τίτλο ή None, υπόλοιπες κύριες γραμμές) για τις κάρτες χωρίς προδιαγραφή γραμμών.
    Η τιμή μπαίνει δίπλα στον τίτλο όταν η πρώτη κύρια γραμμή λέγεται «Μέτρηση» ή «Σήμερα», όπως η κάρτα
    (τότε ο τίτλος γράφεται όπως η γραμμή), ή είναι η συντομογραφία του τίτλου («ΔΑΜ»).
    Κάρτα χωρίς καμία γραμμή και χωρίς πίνακα: «δεν υπολογίστηκε» (ο λόγος είναι στο ⓘ)."""
    if not card.main:
        empty = not (card.targets or card.details or card.table)
        return card.title, (NOT_COMPUTED if empty else None), ()
    label, value = card.main[0]
    if label in GENERIC_LABELS or f"({label})" in card.title:
        return card.title, value, card.main[1:]
    if label.startswith(card.title):
        return label, value, card.main[1:]
    return card.title, None, card.main


def _table_rows(table) -> dict[str, tuple[str, ...]]:
    """Γραμμές του πίνακα της ανάλυσης άλιπης μάζας, με το όνομα χωρίς « (τυπική τιμή)» / « (εκτίμηση)»."""
    return {r[0].split(" (")[0]: r for r in table[1:] if len(r) == 4 and r[1]}


def _pct_note(pct: str) -> str:
    return f"{pct} της άλιπης"


def _rows(spec: Spec, card: Card, table: dict[str, tuple[str, ...]], fixed: dict[str, str]
          ) -> tuple[tuple[Row, ...], set[Line]]:
    """Γραμμές της οθόνης και οι γραμμές του κώδικα που φαίνονται αυτούσιες (δεν επαναλαμβάνονται στο ⓘ)."""
    lines = (*card.main, *card.targets, *card.details)
    shown: set[Line] = set()
    if spec.rows is None:  # γενική: τίτλος, τιμή, οι υπόλοιπες κύριες γραμμές και οι στόχοι αυτούσιοι
        title, value, rest = headline(card)
        if card.main:
            shown.add(card.main[0])
        shown.update(rest)
        shown.update(card.targets)
        missing = NOT_COMPUTED if value == NOT_COMPUTED else ""  # «» = μόνο τίτλος, οι γραμμές από κάτω
        return (Row(title, None if value == NOT_COMPUTED else value, missing, subs=(*rest, *card.targets)),), shown
    out = []
    for r in spec.rows:
        value_line = next((ln for ln in lines if r.value and _is(ln[0], r.value)), None)
        name, value, note = r.name, None, None
        if value_line is not None:
            shown.add(value_line)
            name = value_line[0] if r.show_label else r.name
            value = value_line[1]
        elif r.table and r.table in table:
            row = table[r.table]
            name, value, note = row[0], f"{row[1]} kg", _pct_note(row[2])
        if r.pct and r.pct in table and value is not None:
            note = _pct_note(table[r.pct][2])
        if r.pct_line:
            pl = next((ln for ln in lines if ln[0] == r.pct_line), None)
            if pl is not None and value is not None:
                note = _pct_note(pl[1])
        subs = tuple(ln for ln in lines if _starts(ln[0], r.subs) and ln is not value_line) if value else ()
        shown.update(subs)
        tlines = [ln for ln in lines if _starts(ln[0], r.targets)] if r.targets else []
        heads = list(dict.fromkeys(h for _, v in tlines for h in _heads(v)))  # ίδια τιμή δύο φορές → μία
        if r.fixed and r.fixed in fixed:
            heads = _heads(fixed[r.fixed])
        target = " έως ".join(heads) if heads else NO_TARGET
        if len(heads) == 2 and "–" in "".join(v for _, v in tlines) and value is not None:
            # εύρος του προφίλ («6,0–13,0%»): πρώτα το πιο κοντινό άκρο, όπως τα σημεία-στόχοι
            v = parse_num(value)
            if v is not None:
                heads.sort(key=lambda h: abs(parse_num(h).value - v.value))
                target = " έως ".join(heads)
        word = "Μέση στο βάρος-στόχο" if r.word == "Μέση" else r.word
        if not heads:
            word = "Στόχος"  # χωρίς στόχο από τον κώδικα: «(Στόχος: —)»
        ch = change(value, heads) if (value is not None and heads and r.delta) else None
        out.append(Row(name, value, r.missing, note, ch, word, target, subs, r.level))
    return tuple(out), shown


def _fixed_targets(inp: al.PlanInput, by_title: dict[str, al.Section]) -> dict[str, str]:
    """Στόχοι που ο κώδικας υπολογίζει αλλά δεν γράφει ως γραμμή της ενότητας:
    ΔΑΜ και κανονικοποιημένος ΔΑΜ στα σημεία-στόχους (Στοιχείο 03, Φάση 1) · λόγος μέσης/ύψους «κάτω από 0,50»
    (Στοιχείο 05, target_ratio), μόνο όταν η ενότητα «Μέση» δίνει μέση-στόχο."""
    from davinci import element_05 as e05
    out: dict[str, str] = {}
    prep = al.prepare(inp)
    if not prep.errors and prep.user is not None:
        points = al._targets(inp.weight_kg, inp.fat_percent, prep.user)
        if points:
            out["ffmi"] = " → ".join(f"≈ {num(p.ffmi, 1)} kg/m²" for p in points)
            out["normalized_ffmi"] = " → ".join(f"≈ {num(p.normalized_ffmi, 1)}" for p in points)
    waist = by_title.get("Μέση")
    if waist is not None and any(label == "Μέση-στόχος" for label, _ in waist.lines):
        out["whtr"] = f"κάτω από {num(e05.load_data()['target_ratio'], 2)}"
    return out


def _needs(card: Card, rows: tuple[Row, ...]) -> tuple[str, ...]:
    """Σχόλια «χρειάζεται …» κάρτας που δεν υπολογίστηκε: φαίνονται, γιατί λένε τι να συμπληρώσεις."""
    if any(r.value is not None for r in rows):
        return ()
    return tuple(m for m in card.messages if "ρειάζ" in m)  # «χρειάζεται», «Χρειάζονται»


def results(inp: al.PlanInput, m: al.Measures) -> tuple[tuple[Group, ...], tuple[str, ...]]:
    """Καρτέλες των «Αποτελεσμάτων» και σφάλματα. Οι τιμές είναι του `app_logic`, αυτούσιες."""
    measured, errors = al.measurement_sections(inp, m)
    if errors:
        return (), errors
    sections = (*start_sections(inp), *measured)
    by_title = {clean_title(s.title): s for s in sections}
    analysis = by_title.get(_ANALYSIS)
    table = _table_rows(analysis.table) if analysis is not None else {}
    fixed = _fixed_targets(inp, by_title)
    every = tuple(s for _, _, specs in TABS for s in specs)
    taken: dict[str, set[int]] = {}
    groups = [Group(BASICS, "Βασικά στοιχεία", lines=basics(inp, sections))]
    known = {s for spec in every if spec.owner for s in spec.source}
    for title, heading, specs in TABS:
        cards = []
        for spec, card in _cards(specs, by_title, taken, every):
            rows, shown = _rows(spec, card, table, fixed)
            needs = _needs(card, rows)
            info = tuple(ln for ln in (*card.main, *card.targets, *card.details) if ln not in shown)
            if spec.rows is not None:  # οι στόχοι φαίνονται συμπτυγμένοι· αυτούσιοι στο ⓘ
                info = (*info, *(ln for ln in card.targets if ln not in info))
            cards.append(Card(card.title, card.main, card.targets, card.details,
                              tuple(x for x in card.messages if x not in needs), card.warnings, card.indicative,
                              card.table, rows, needs, info, spec.rows is None))
        if title == OTHER:
            for s in sections:
                if clean_title(s.title) not in known:  # ό,τι δεν έχει θέση: κρατιέται, δεν χάνεται
                    lines = _clean_lines(s.lines)
                    cards.append(Card(clean_title(s.title), lines[:1], (), lines[1:],
                                      tuple(map(clean_text, s.messages)), tuple(map(clean_text, s.warnings)),
                                      s.indicative, s.table,
                                      (Row(clean_title(s.title), lines[0][1] if lines else None),), (),
                                      lines[1:]))
        missing = sorted({TODO[r.name] for c in cards for r in c.rows if r.value is None and r.name in TODO})
        todo = None
        if missing:
            fields = ", ".join(dict.fromkeys(f.strip() for x in missing for f in x.split(",")))
            todo = f"Για τις γραμμές που λείπουν συμπλήρωσε στη «Μέτρηση» → «Ζυγαριά»: {fields}."
        groups.append(Group(title, heading, tuple(cards), todo=todo))
    return tuple(groups), ()
