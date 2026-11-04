"""Κοινή λογική για τις δερματοπτυχές (Στοιχεία 33–36): είσοδος σε mm, εκατοστημόριο NHANES 2007–2010
με γραμμική παρεμβολή, δεύτερη ένδειξη ανά καταγωγή, μηνύματα. Χωρίς στόχο.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path

from davinci import element_01 as e01
from davinci import element_46 as e46
from davinci.fmt import num, round_half_up

ROOT = Path(__file__).resolve().parents[2]


def load_tables(d: dict) -> dict:
    return json.loads((ROOT / d["tables_file"]).read_text(encoding="utf-8"))


def decade_row(age: int) -> str:
    if age >= 80:
        return "80+"
    lo = age // 10 * 10
    return f"{lo}–{lo + 9}"


def race_band(age: int) -> str:
    return "20–39" if age < 40 else "40–59" if age < 60 else "60+"


@dataclass(frozen=True)
class Position:
    percentile: float | None  # παρεμβολή· None όταν είναι εκτός πίνακα
    below: str | None = None  # «5» ή «10» (πρώτο διαθέσιμο)
    above: bool = False

    @property
    def label(self) -> str:
        if self.below:
            return f"κάτω από το {self.below}ο"
        if self.above:
            return "πάνω από το 95ο"
        return f"{round_half_up(self.percentile, 0):.0f}ο"

    @property
    def uncertain_from(self) -> float:
        return 95.0 if self.above else (self.percentile or 0.0)


def position(value_mm: float, p: dict) -> Position:
    """Γραμμική παρεμβολή ανάμεσα στα διαθέσιμα εκατοστημόρια (σύμβαση συστήματος).
    Σε επίπεδο τμήμα (ίσες τιμές) δίνεται το χαμηλότερο εκατοστημόριο."""
    pts = [(float(k), Decimal(repr(v))) for k, v in p.items() if v is not None]
    v = Decimal(repr(value_mm))
    if v < pts[0][1]:
        return Position(None, below=f"{pts[0][0]:.0f}")
    if v > pts[-1][1]:
        return Position(None, above=True)
    for (k0, v0), (k1, v1) in zip(pts, pts[1:]):
        if v0 <= v <= v1:
            if v1 == v0:
                return Position(k0)
            return Position(float(Decimal(repr(k0)) + (v - v0) / (v1 - v0) * Decimal(repr(k1 - k0))))
    return Position(pts[-1][0])


@dataclass(frozen=True)
class SkinfoldResult:
    value_mm: float | None
    position: Position | None = None  # Πίνακας 3 (ή 5 για 5–19 ετών)
    race_position: Position | None = None  # Πίνακας 4
    table_row: str | None = None
    indicative: bool = False
    uncertain: bool = False
    needs_third: bool = False
    needs_confirmation: bool = False
    athletes: dict | None = None  # Πίνακας 6 (μόνο 18+)
    messages: tuple[str, ...] = field(default_factory=tuple)
    measurement_reasons: tuple[str, ...] = ()  # λόγοι «Ενδεικτική» από τη μέτρηση (περνούν στην Ενδομορφία)
    comparison: "MeanComparison | None" = None  # μέσος ± ΤΑ (Στοιχεία 35, 36)
    corrected_calf_cm: float | None = None  # Στοιχείο 36
    corrected_indicative: bool = False
    not_measured: bool = False


def combine(measurements: list[float], d: dict) -> tuple[float | None, bool]:
    """(τιμή, χρειάζεται τρίτη). Δύο μετρήσεις: διαφορά / μικρότερη > 5% → τρίτη. Τιμή = μέσος όρος."""
    dec = [Decimal(repr(x)) for x in measurements]
    if len(dec) == 2:
        lo, hi = min(dec), max(dec)
        if (hi - lo) / lo * 100 > Decimal(repr(d["third_measurement_above_percent"])):
            return None, True
    elif len(dec) != 3:
        raise e01.InvalidInput("Χρειάζονται δύο μετρήσεις (ή τρεις, όταν οι δύο διαφέρουν πάνω από 5%).")
    return float(sum(dec) / len(dec)), False


def prepare(element: str, d: dict, measurements: list[float] | None, user: e01.UserCategories, *,
            caliper: str, confirmed: bool) -> tuple[SkinfoldResult | None, float | None]:
    """Κοινά βήματα εισόδου: επίπεδο, «Δεν μετρήθηκε», δαγκάνα, έλεγχος 2–50 mm, τρίτη μέτρηση.
    Επιστρέφει (πρόωρο αποτέλεσμα, None) ή (None, τιμή)."""
    m = d["messages"]
    if not e46.element_available(element, user.level):
        return SkinfoldResult(None, messages=(e46.normal_message(element),)), None
    if not measurements:
        text = (m["not_measured"],) if "not_measured" in m else ()  # το 36 δεν έχει μήνυμα
        return SkinfoldResult(None, messages=text, not_measured=True), None
    if caliper not in d["calipers"]:
        raise e01.InvalidInput(f"Δαγκάνα: {', '.join(d['calipers'])}.")
    if any(x <= 0 for x in measurements):
        raise e01.InvalidInput("Η δερματοπτυχή πρέπει να είναι θετική (mm).")
    lo, hi = d["plausible_range_mm"]
    if not confirmed:
        for x in measurements:
            if x < lo or x > hi:
                return SkinfoldResult(None, needs_confirmation=True, messages=(m["unusual"].replace("[X]", num(x)),)), None
    value, third = combine(list(measurements), d)
    if third:
        return SkinfoldResult(None, needs_third=True, messages=(m["third"],)), None

    return None, value


def assess(element: str, d: dict, measurements: list[float] | None, user: e01.UserCategories, *,
           isak: bool | None = True, caliper: str = "Harpenden / Holtain", left_side: bool = False,
           confirmed: bool = False, edema: bool = False, postpartum_recent: bool = False) -> SkinfoldResult:
    """isak: True · False · None («δεν ξέρω»). caliper: μία από τις επιλογές του εγγράφου."""
    early, value = prepare(element, d, measurements, user, caliper=caliper, confirmed=confirmed)
    if early is not None:
        return early
    m = d["messages"]
    if user.pregnant:
        return SkinfoldResult(value, indicative=True, messages=(m["pregnancy"],),
                              measurement_reasons=measurement_reasons(d, isak, caliper, left_side, edema))
    age = user.age
    tables = load_tables(d)["tables"][user.sex]
    if age < 20:
        row = str(age)
        pos = position(value, tables["child"][row]["p"])
    else:
        row = decade_row(age)
        pos = position(value, tables["all"][row]["p"])

    msgs = [m["normal"].replace("[X]", num(value)).replace("περίπου στο [P]ο" if pos.percentile is None else "[P]ο",
                                                          pos.label)]
    if e01.is_minor(age):
        msgs.append(m["child"])
    uncertain = pos.uncertain_from >= d["uncertain_from_percentile"]
    if uncertain:
        msgs.append(m["uncertain"])

    reasons = [d["reasons"]["protocol_reference" if isak else "protocol_not_isak"]]
    if caliper not in d["reference_calipers"]:
        reasons.append(d["reasons"][caliper])
    if left_side:
        reasons.append(d["reasons"]["left"])
    msgs.append(m["indicative"].replace("[λόγος]", " · ".join(reasons)))
    mreasons = measurement_reasons(d, isak, caliper, left_side, edema)

    race_pos = None
    group = user.effective_group or "5"
    race_row = d["race_rows"].get(group)
    if age >= 20:
        if race_row:
            race_pos = position(value, tables["race"][race_row][race_band(age)]["p"])
        else:
            msgs.append(m["ancestry"])
    if edema and "edema" in m:
        msgs.append(m["edema"])
    if postpartum_recent and "postpartum" in m:
        msgs.append(m["postpartum"])
    if age >= d["age_60_message_from"]:
        msgs.append(m["age_60"])
    athletes = d["athletes"] if age >= 18 else None
    return SkinfoldResult(value, pos, race_pos, row, True, uncertain, False, False, athletes, tuple(msgs), mreasons)


def measurement_reasons(d: dict, isak: bool | None, caliper: str, left_side: bool, edema: bool,
                        extra: tuple[str, ...] = ()) -> tuple[str, ...]:
    """Λόγοι «Ενδεικτική» από τη μέτρηση (όχι από τον πληθυσμό αναφοράς): περνούν στην Ενδομορφία (Στοιχείο 37)."""
    r = d["reasons"]
    out = []
    if not isak:
        out.append(r["protocol_not_isak"])
    if caliper not in d["reference_calipers"]:
        out.append(r[caliper])
    if left_side:
        out.append(r["left"])
    if edema:
        out.append(r["edema"])
    return tuple(out) + extra


@dataclass(frozen=True)
class MeanComparison:
    group: str
    mean: float
    sd: float
    delta: float  # τιμή − μέσος

    def fill(self, text: str, sex: str, value_decimals: int = 1) -> str:
        word = {"Άνδρας": "άνδρες", "Γυναίκα": "γυναίκες"}[sex]
        return (text.replace("[φύλο]", word).replace("[ηλικία]", self.group)
                .replace("[M]", num(self.mean, value_decimals)).replace("[ΤΑ]", num(self.sd, value_decimals))
                .replace("[Δ]", num(abs(self.delta), value_decimals))
                .replace("[πάνω/κάτω]", "κάτω" if self.delta < 0 else "πάνω"))


CAMPA_GROUPS = (("18–19", 18, 19), ("20–24", 20, 24), ("25–29", 25, 29), ("30–34", 30, 34), ("35–39", 35, 39),
                ("40–44", 40, 44), ("45–49", 45, 49), ("50–54", 50, 54), ("55–59", 55, 59), ("> 60 (έως 65)", 60, 200))


def campa_comparison(value_mm: float, rows: dict, age: int) -> MeanComparison:
    """Ομάδα Campa 2025 για την ηλικία· πάνω από 65 η ομάδα «> 60» (ο καλών προσθέτει «Ενδεικτική»)."""
    label = next(lab for lab, lo, hi in CAMPA_GROUPS if lo <= age <= hi)
    mean, sd = rows[label]["mean_sd"]
    shown = "60–65" if label.startswith(">") else label
    delta = float(Decimal(repr(round_half_up(value_mm, 1))) - Decimal(repr(mean)))
    return MeanComparison(shown, mean, sd, delta)
