"""Στοιχείο 43 — Πρόβλεψη και διόρθωση από τη ζυγαριά (κλειστός βρόχος, Hall & Chow 2011).

Τάση: γραμμική παλινδρόμηση του βάρους σε παράθυρο 28 ημερών (56 σε αργούς ρυθμούς ή συντήρηση). Πρώτη διόρθωση
την ημέρα 42 (ή 70), μετά κάθε 28 ημέρες. Διόρθωση μόνο αν |a − aστόχος| > 2 × SE (και ο a εκτός εύρους, όπου
υπάρχει εύρος). Νέα πρόσληψη = πρόσληψη + (aστόχος − a) × E / 7, στις 10 kcal.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from functools import lru_cache
from pathlib import Path

from davinci import element_01 as e01
from davinci import element_04 as e04
from davinci import element_40 as e40
from davinci import element_42 as e42
from davinci.fmt import num

DATA_FILE = Path(__file__).resolve().parents[2] / "data" / "element_43.json"


@lru_cache(maxsize=1)
def load_data() -> dict:
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


# --- Τάση ------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Trend:
    a_kg_week: float
    se_kg_week: float
    n: int


def trend(points: list[tuple[float, float]]) -> Trend:
    """points: (ημέρα, kg). Ελάχιστα τετράγωνα· SE από τις αποκλίσεις του ίδιου του χρήστη."""
    n = len(points)
    if n < 3:
        raise e01.InvalidInput("Για την τάση χρειάζονται τουλάχιστον 3 ζυγίσεις.")
    tx = sum(t for t, _ in points) / n
    wy = sum(w for _, w in points) / n
    sxx = sum((t - tx) ** 2 for t, _ in points)
    slope = sum((t - tx) * (w - wy) for t, w in points) / sxx
    resid = [w - (wy + slope * (t - tx)) for t, w in points]
    s = math.sqrt(sum(r * r for r in resid) / (n - 2)) if n > 2 else 0.0
    return Trend(slope * 7, s / math.sqrt(sxx) * 7, n)


def slope_se_percent(days: list[float], sd_percent: float, window_days: float) -> float:
    """Τυπικό σφάλμα της αλλαγής στο παράθυρο (% βάρους) για ανεξάρτητες ζυγίσεις (Πίνακας 3)."""
    tx = sum(days) / len(days)
    sxx = sum((t - tx) ** 2 for t in days)
    return sd_percent / math.sqrt(sxx) * window_days


def window_days(rate_percent: float | None, goal: str) -> int:
    d = load_data()
    slow = goal == "maintain" or (rate_percent is not None and abs(rate_percent) < d["slow_rate_percent_below"])
    return d["slow_window_days"] if slow else d["window_days"]


def correction_days(window: int, last_day: int) -> list[int]:
    """Πίνακας 5: πρώτη διόρθωση την ημέρα 42 (ή 70), μετά κάθε 28 ημέρες."""
    d = load_data()
    first = d["first_correction_day"][str(window)]
    return list(range(first, last_day + 1, d["correction_every_days"]))


def included(points: list[tuple[int, float]], day: int, window: int, *, change_days: list[int] = (),
             excluded_days: set[int] = frozenset()) -> list[tuple[int, float]]:
    """Ζυγίσεις του παραθύρου που λήγει την ημέρα day· χωρίς τις 14 πρώτες ημέρες, 14 ημέρες μετά από αλλαγή
    και τις ημέρες που σημείωσε ο χρήστης. Οι κενές ημέρες δεν συμπληρώνονται."""
    d = load_data()
    start = day - window + 1
    out = []
    for t, w in points:
        if not (start <= t <= day) or t <= d["excluded_start_days"] or t in excluded_days:
            continue
        if any(c < t <= c + d["excluded_after_change_days"] for c in change_days):
            continue
        out.append((t, w))
    return out


def enough_weighings(points: list[tuple[int, float]], day: int, window: int) -> bool:
    """Ελάχιστο 3 ζυγίσεις σε κάθε εβδομάδα του παραθύρου (σύμβαση συστήματος)."""
    d = load_data()
    first = max(day - window + 1, d["excluded_start_days"] + 1)
    weeks = range(first, day + 1, 7)
    return all(sum(1 for t, _ in points if s <= t < s + 7) >= d["min_weighings_per_week"] for s in weeks)


# --- Διόρθωση ----------------------------------------------------------------------------------
@dataclass(frozen=True)
class Correction:
    a_kg_week: float | None
    target_kg_week: float
    se_kg_week: float | None
    changed: bool
    new_intake_kcal: float
    delta_kcal: float = 0.0
    needs_confirmation: bool = False
    floor_applied: bool = False
    plateau: bool = False
    indicative: bool = False
    messages: tuple[str, ...] = ()


def _kg(x: float) -> str:
    return num(x, 2)


def correct(intake_kcal: float, target_kg_week: float, e_kcal_per_kg: float, window_points: list[tuple[int, float]],
            user: e01.UserCategories, *, goal: str, rate_range_kg_week: tuple[float, float] | None = None,
            enough: bool = True, confirmed_big: bool = False, remaining_kg: float | None = None,
            today: date | None = None) -> Correction:
    """Κανόνες 7–9, 14. Ρυθμοί με πρόσημο (αρνητικός σε απώλεια). rate_range_kg_week: εύρος του Στοιχείου 40
    σε kg/εβδομάδα με πρόσημο (π.χ. (−0,72, −0,36))· None για έλλειμμα AHA (ΔΜΣ ≥ 25)."""
    d = load_data()
    m = d["messages"]
    if not enough:
        return Correction(None, target_kg_week, None, False, intake_kcal, indicative=True,
                          messages=(m["few_weighings"],))
    tr = trend(window_points)
    a, se = tr.a_kg_week, tr.se_kg_week
    msgs: list[str] = []
    plateau = goal == "loss" and abs(a) <= d["significance_se"] * se
    if plateau:
        msgs.append(m["plateau"])
    significant = abs(a - target_kg_week) > d["significance_se"] * se
    outside = True
    if rate_range_kg_week is not None:
        lo, hi = sorted(rate_range_kg_week)
        outside = not (lo <= a <= hi)
    if not (significant and outside):
        msgs.insert(0, m["no_change"].replace("[a]", _kg(a)).replace("[aστόχος]", _kg(target_kg_week))
                    .replace("[πρόσληψη]", num(intake_kcal, 0)))
        return Correction(a, target_kg_week, se, False, intake_kcal, plateau=plateau, messages=tuple(msgs))

    delta = (target_kg_week - a) * e_kcal_per_kg / 7
    if delta < 0 and (user.pregnant or e01.is_minor(user.age)):
        # Κανόνας 16: καμία διόρθωση προς έλλειμμα (μείωση πρόσληψης)· το έγγραφο δεν δίνει κείμενο
        return Correction(a, target_kg_week, se, False, intake_kcal, plateau=plateau, messages=tuple(msgs))
    step = Decimal(d["round_kcal"])
    new = float((Decimal(repr(intake_kcal + delta)) / step).quantize(Decimal(1), rounding=ROUND_HALF_UP) * step)
    if abs(delta) > d["confirm_above_kcal"] and not confirmed_big:
        msgs.append(m["big_correction"].replace("[Χ]", num(abs(delta), 0)))
        return Correction(a, target_kg_week, se, False, intake_kcal, delta, needs_confirmation=True,
                          plateau=plateau, messages=tuple(msgs))
    e40d = e40.load_data()
    floor = e40d["floor_kcal"]
    floor_applied = False
    if new < floor:
        new, floor_applied = float(floor), True
        txt = m["floor"].replace("[όριο]", num(floor, 0))
        if remaining_kg is not None and today is not None:
            achievable = target_kg_week + (new - (intake_kcal + delta)) * 7 / e_kcal_per_kg
            weeks = abs(remaining_kg / achievable) if achievable else float("inf")
            when = today + timedelta(weeks=weeks)
            txt = txt.replace("[ημερομηνία]", when.strftime("%d/%m/%Y"))
        msgs.append(txt)
    verb = "χάνεις" if a < 0 else "παίρνεις"
    msgs.insert(0, m["correction"].replace("[χάνεις / παίρνεις]", verb).replace("[a]", _kg(abs(a)))
                .replace("[aστόχος]", _kg(abs(target_kg_week))).replace("[νέα πρόσληψη]", num(new, 0)))
    if goal == "loss" and not floor_applied and new < e40d["low_intake_kcal"][user.sex]:
        msgs.append(e40d["messages"]["low_intake"])
    return Correction(a, target_kg_week, se, True, new, delta, False, floor_applied, plateau, False, tuple(msgs))


# --- Πρόβλεψη ------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Week:
    week: int
    weight_kg: float
    fat_kg: float
    ffm_kg: float
    fat_percent: float
    muscle_kg: float | None
    water_kg: float
    bone_kg: float | None
    bmi: float
    f: float
    e_kcal_per_kg: float


@dataclass(frozen=True)
class Forecast:
    weeks: tuple[Week, ...]
    reached: bool
    too_long: bool
    indicative: bool = True  # νερό «Ενδεικτική»· πριν από διόρθωση εύρος ±10%
    messages: tuple[str, ...] = ()


def forecast(weight_kg: float, fat_kg: float, user: e01.UserCategories, *, trained: bool, target_fat_percent: float,
             target_weight_kg: float, rate_percent: float | None = None, deficit_kcal_day: float | None = None,
             muscle_kg: float | None = None, bone_kg: float | None = None) -> Forecast:
    """Απώλεια (Φάση 1): εβδομαδιαίο χρονοδιάγραμμα (Πίνακας 6) έως λίπος ≤ στόχος και βάρος ≤ βάρος-στόχος
    (Κανόνας 12) ή 104 εβδομάδες. Ρυθμός % του βάρους της εβδομάδας ή σταθερό έλλειμμα (ΔΜΣ ≥ 25)."""
    d = load_data()
    if (rate_percent is None) == (deficit_kcal_day is None):
        raise e01.InvalidInput("Δώσε ρυθμό % ή έλλειμμα kcal (όχι και τα δύο).")
    ffm0 = weight_kg - fat_kg
    muscle_ratio = muscle_kg / ffm0 if muscle_kg is not None else None
    w, fat = weight_kg, fat_kg
    rows = []
    reached = False
    for week in range(1, d["max_weeks"] + 1):
        f = e42.ffm_fraction_loss(fat, trained)
        e = e42.energy_per_kg(f)
        change = w * rate_percent / 100 if rate_percent is not None else e42.weekly_change_from_deficit(deficit_kcal_day, e)
        w -= change
        fat -= change * (1 - f)
        ffm = w - fat
        rows.append(Week(week, w, fat, ffm, fat / w * 100, None if muscle_ratio is None else muscle_ratio * ffm,
                         d["water_per_ffm"] * ffm, bone_kg, e04.bmi(w, user.height_cm), f, e))
        if fat / w * 100 <= target_fat_percent and w <= target_weight_kg:
            reached = True
            break
    msgs = () if reached else (d["messages"]["long"],)
    return Forecast(tuple(rows), reached, not reached, True, msgs)


def forecast_gain(weight_kg: float, fat_kg: float, user: e01.UserCategories, *, trained: bool,
                  rate_percent: float, ffm_target_kg: float, muscle_kg: float | None = None,
                  bone_kg: float | None = None) -> Forecast:
    """Φάση 2 (αύξηση): εβδομαδιαίο χρονοδιάγραμμα με τους Κανόνες 10 και 12 εφαρμοσμένους στην αύξηση.

    Κάθε εβδομάδα: αύξηση = βάρος της εβδομάδας × ρυθμός % (Στοιχείο 40)· μερίδιο άλιπης f της εβδομάδας από το
    Στοιχείο 42 (με προπόνηση: έως 1,4 kg άλιπης ανά 12 εβδομάδες· χωρίς: Forbes με k = 1, «Ενδεικτική»).
    Τέλος όταν η άλιπη μάζα φτάσει τον στόχο της Φάσης 2 (Στοιχείο 03, Συμπλήρωμα Δ) ή στις 104 εβδομάδες
    (σύμβαση συστήματος· ο ρυθμός μένει σταθερός σε % του βάρους της εβδομάδας)."""
    d = load_data()
    if rate_percent <= 0:
        raise e01.InvalidInput("Αύξηση: ο ρυθμός πρέπει να είναι θετικός (% του βάρους την εβδομάδα).")
    if e01.is_minor(user.age) or user.pregnant_or_breastfeeding:
        raise e01.InvalidInput("Φάση 2: δεν εφαρμόζεται σε ανηλίκους, εγκυμοσύνη και θηλασμό (Στοιχείο 03).")
    ffm0 = weight_kg - fat_kg
    if ffm_target_kg <= ffm0:
        return Forecast((), True, False, False, ())
    muscle_ratio = muscle_kg / ffm0 if muscle_kg is not None else None
    w, fat = weight_kg, fat_kg
    rows = []
    reached = False
    for week in range(1, d["max_weeks"] + 1):
        change = w * rate_percent / 100
        f = e42.ffm_fraction_gain(fat, trained, change)
        e = e42.energy_per_kg(f)
        w += change
        fat += change * (1 - f)
        ffm = w - fat
        rows.append(Week(week, w, fat, ffm, fat / w * 100, None if muscle_ratio is None else muscle_ratio * ffm,
                         d["water_per_ffm"] * ffm, bone_kg, e04.bmi(w, user.height_cm), f, e))
        if ffm >= ffm_target_kg:
            reached = True
            break
    msgs = () if reached else (d["messages"]["long"],)
    return Forecast(tuple(rows), reached, not reached, True, msgs)
