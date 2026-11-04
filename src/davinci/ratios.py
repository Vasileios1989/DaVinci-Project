"""Κοινά εργαλεία για τους λόγους περιφερειών (Στοιχεία 22–29).

- Λόγος με δύο δεκαδικά: η σύγκριση γίνεται με τη στρογγυλεμένη τιμή, ώστε η τιμή που βλέπει ο χρήστης
  να συμφωνεί με την κατηγορία ή τη ζώνη (σύμβαση του Στοιχείου 22, Πίνακας 2· εφαρμόζεται σε όλους τους λόγους).
- Εκατοστημόριο σε ζώνες (Στοιχεία 23–29): κάτω από το 5ο · 5ο–25ο · 25ο–50ό · 50ό–75ο · 75ο–95ο · πάνω από το 95ο.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from davinci import element_01 as e01
from davinci.fmt import num

BANDS = ("κάτω από το 5ο", "5ο–25ο", "25ο–50ό", "50ό–75ο", "75ο–95ο", "πάνω από το 95ο")


def ratio2(numerator: float, denominator: float) -> float:
    """Λόγος στα δύο δεκαδικά (μισό προς τα πάνω), με δεκαδική διαίρεση των τιμών όπως καταχωρήθηκαν:
    27,4 / 40 = 0,685 → 0,69 (η διαίρεση με float θα έδινε 0,68499… → 0,68)."""
    if numerator <= 0 or denominator <= 0:
        raise ValueError("Οι περιφέρειες πρέπει να είναι θετικές.")
    q = Decimal(repr(numerator)) / Decimal(repr(denominator))
    return float(q.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def percentile_band(value: float, percentiles: dict) -> str:
    """percentiles: {"5": .., "25": .., "50": .., "75": .., "95": ..}.

    Σύμβαση συστήματος: τιμή ίση με ένα εκατοστημόριο ανήκει στη ζώνη από πάνω του
    (π.χ. ακριβώς στο 5ο → «5ο–25ο»), εκτός από το 95ο, που ανήκει στη ζώνη «75ο–95ο».
    """
    p = [percentiles[k] for k in ("5", "25", "50", "75", "95")]
    if value < p[0]:
        return BANDS[0]
    if value > p[4]:
        return BANDS[5]
    for i in range(1, 4):
        if value < p[i]:
            return BANDS[i]
    return BANDS[4]


# --- Κοινή αξιολόγηση των λόγων με εκατοστημόρια ANSUR II (Στοιχεία 23–25) -----------------

@dataclass(frozen=True)
class TargetRow:
    weight_kg: float
    numerator_cm: float  # αναμενόμενο στήθος / ώμοι / πήχης
    denominator_cm: float  # μέση-στόχος / αναμενόμενος δικέφαλος
    ratio: float  # ακριβής· εμφάνιση με δύο δεκαδικά


@dataclass(frozen=True)
class PercentileResult:
    ratio: float | None  # δύο δεκαδικά
    band: str | None
    rows: tuple[TargetRow, ...] = ()
    indicative: bool = False
    messages: tuple[str, ...] = ()


def assess_percentile(d: dict, numerator: float | None, denominator: float | None,
                      user: e01.UserCategories, rows: tuple[TargetRow, ...], fill_e,
                      exclusion: tuple[str, str] | None = None) -> PercentileResult:
    """d: δεδομένα του στοιχείου· fill_e(μήνυμα Ε, πρώτη γραμμή) → κείμενο.

    exclusion: («record», μήνυμα) → ο λόγος καταγράφεται χωρίς σύγκριση· («skip», μήνυμα) → δεν υπολογίζεται.
    Ποια μηνύματα εμφανίζονται ορίζει ο πίνακας «Τι εμφανίζεται» (d["show"]).

    Σύμβαση συστήματος: όταν λείπει ένα πεδίο, εμφανίζονται το μήνυμα «missing» και τα μηνύματα
    που δεν εξαρτώνται από τη μέτρηση· χωρίς Α, Υ και Κ0, που αφορούν τη θέση.
    """
    m, show = d["messages"], d["show"]
    for v in (numerator, denominator):
        if v is not None and v <= 0:
            raise e01.InvalidInput("Οι περιφέρειες πρέπει να είναι θετικές.")
    have = numerator is not None and denominator is not None
    ratio = ratio2(numerator, denominator) if have else None

    if user.age < d["min_age"] or user.pregnant_or_breastfeeding:
        return PercentileResult(ratio, None, messages=(m["record_only"],))
    if exclusion is not None:
        kind, text = exclusion
        return PercentileResult(ratio if kind == "record" else None, None, messages=(text,))

    group = "athletic" if user.profile in show["athletic_profiles"] else "health"
    keys = show[user.sex][group]
    msgs: list[str] = []
    band = None
    indicative = False
    if have:
        band = percentile_band(ratio, d["percentiles"][user.sex])
    else:
        msgs.append(m["missing"])
    for k in keys:
        if k == "A":
            if have:
                msgs.append(m["A"].replace("Χο", band))
        elif k == "E":
            if rows:
                msgs.append(fill_e(m["E"], rows[0]))
        else:
            msgs.append(m[k])
    if have:
        mx = d.get("maximum")
        if mx and ratio > mx[user.sex]:
            msgs.append(m["U"])
        if (user.effective_group or "5") in d["no_data_ancestries"]:
            msgs.append(m["ancestry_4_5"])
            indicative = True
        if user.age > d["age_range"][1]:
            msgs.append(m["age_59"])
            indicative = True
    return PercentileResult(ratio, band, rows, indicative, tuple(msgs))


def fmt_ratio(x: float) -> str:
    return num(x, 2)
