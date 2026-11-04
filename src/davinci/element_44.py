"""Στοιχείο 44 — Παρουσίαση ενέργειας, μακροθρεπτικών και χρονοδιαγράμματος.

Δεν υπολογίζει τίποτα δικό του: παίρνει τις εξόδους των Στοιχείων 01–43 και τις δείχνει σε 4 μέρη (Πίνακας 3).
Κάθε πρόταση είναι μήνυμα «αυτολεξεί» των Στοιχείων 01–43 ή του Πίνακα 8 (Κανόνας 2). Κάθε πρόβλεψη με εύρος
(Κανόνας 5). Ορόσημα −5% / −10% μόνο σε απώλεια με ΔΜΣ στο υπέρβαρο ή πάνω (Κανόνας 6).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from functools import lru_cache
from pathlib import Path

from davinci import element_01 as e01
from davinci import element_04 as e04
from davinci import element_43 as e43
from davinci.fmt import num

DATA_FILE = Path(__file__).resolve().parents[2] / "data" / "element_44.json"


@lru_cache(maxsize=1)
def load_data() -> dict:
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


# --- Μορφή αριθμών (Πίνακας 5) --------------------------------------------------------------------
def measured(x: float) -> str:
    """Μετρημένη τιμή όπως δόθηκε: 72 → «72», 72.4 → «72,4»."""
    dec = max(0, -Decimal(repr(float(x))).normalize().as_tuple().exponent)
    return num(x, dec)


def kg(x: float) -> str:
    return num(x, load_data()["format"]["forecast_kg_decimals"])


def pct(x: float) -> str:
    return num(x, load_data()["format"]["forecast_percent_decimals"])


def signed_kg(x: float) -> str:
    s = num(abs(x), 2)
    return s if s == num(0, 2) else ("\u2212" if x < 0 else "+") + s


def approx(text: str) -> str:
    return f"{load_data()['format']['approx']} {text}"


def kcal10(x: float) -> str:
    step = load_data()["format"]["energy_round_kcal"]
    q = (Decimal(repr(x)) / step).quantize(Decimal(1), rounding=ROUND_HALF_UP) * step
    return num(float(q), 0)


def day_text(d: date) -> str:
    return f"{d.day} {load_data()['format']['months'][d.month - 1]} {d.year}"


def round_weeks(x: float) -> int:
    return int(Decimal(repr(x)).quantize(Decimal(1), rounding=ROUND_HALF_UP))


# --- Εύρος ρυθμού, εβδομάδων και ημερομηνιών (Κανόνας 5 · Στοιχείο 43, Κανόνας 11) ---------------------
def rate_range(rate_kg_week: float, tdee_kcal: float, e_kcal_per_kg: float) -> tuple[float, float | None]:
    """Πριν από την πρώτη διόρθωση: ρυθμός ± (10% της δαπάνης) × 7 / E, σε kg/εβδομάδα (μέγεθος, χωρίς πρόσημο).
    Κάτω όριο ≤ 0 → 0 (το πάνω όριο εβδομάδων μένει ανοιχτό)."""
    spread = load_data()["tdee_uncertainty"] * tdee_kcal * 7 / e_kcal_per_kg
    r = abs(rate_kg_week)
    return max(r - spread, 0.0), r + spread


def rate_range_after_correction(a_kg_week: float, se_kg_week: float) -> tuple[float, float]:
    """Μετά από διόρθωση: πραγματικός ρυθμός ± 2 × SE (σύμβαση συστήματος)."""
    k = e43.load_data()["significance_se"]
    r = abs(a_kg_week)
    return max(r - k * se_kg_week, 0.0), r + k * se_kg_week


def weeks_range(change_kg: float, rates: tuple[float, float]) -> tuple[int, int | None]:
    """(εβδομάδες με τον γρήγορο ρυθμό, εβδομάδες με τον αργό)· None όταν ο αργός ρυθμός είναι 0."""
    slow, fast = rates
    c = abs(change_kg)
    return round_weeks(c / fast), (round_weeks(c / slow) if slow > 0 else None)


def date_range(start: date, weeks: tuple[int, int | None]) -> tuple[date, date | None]:
    lo, hi = weeks
    return start + timedelta(weeks=lo), (start + timedelta(weeks=hi) if hi is not None else None)


def _fill_range(msg: str, dates: tuple[date, date | None], weeks: tuple[int, int | None] | None = None) -> str:
    hi = day_text(dates[1]) if dates[1] is not None else "…"
    msg = msg.replace("[ημερομηνία από]", day_text(dates[0])).replace("[ημερομηνία έως]", hi)
    if weeks is not None:
        msg = msg.replace("[εβδομάδες από]", str(weeks[0])).replace(
            "[εβδομάδες έως]", str(weeks[1]) if weeks[1] is not None else "…")
    return msg


# --- Ορόσημα (Πίνακας 4 · Κανόνας 6) -------------------------------------------------------------------
@dataclass(frozen=True)
class Milestone:
    percent: int
    weight_kg: float
    message_key: str


def overweight_or_above(category: str | None) -> bool:
    return category in e04.load_data()["rules"]["rule_2_overweight_categories"]


def milestones(weight_kg: float, target_weight_kg: float, bmi_category: str | None, goal: str) -> tuple[Milestone, ...]:
    """−5% και −10% του αρχικού βάρους, όσα είναι πριν από τον βάρος-στόχο."""
    if goal != "loss" or not overweight_or_above(bmi_category):
        return ()
    out = []
    for m in load_data()["milestones"]:
        w = weight_kg * (1 - m["percent"] / 100)
        if w > target_weight_kg:
            out.append(Milestone(m["percent"], w, m["message"]))
    return tuple(out)


# --- Μηνύματα του Πίνακα 8 -------------------------------------------------------------------------
def _m() -> dict:
    return load_data()["messages"]


def start_message(weight_kg: float, fat_percent: float, bmi: float, category: str) -> str:
    fat = weight_kg * fat_percent / 100
    return (_m()["start"].replace("[βάρος]", measured(weight_kg)).replace("[Λ%]", measured(fat_percent))
            .replace("[Λ]", kg(fat)).replace("[Α]", kg(weight_kg - fat)).replace("[ΔΜΣ]", num(bmi, 1))
            .replace("[κατηγορία]", category))


def milestone_message(m: Milestone, dates: tuple[date, date | None]) -> str:
    return _fill_range(_m()[m.message_key].replace("[βάρος]", kg(m.weight_kg)), dates)


def target_message(profile: str, weight_kg: float, fat_percent: float, weeks: tuple[int, int | None],
                   dates: tuple[date, date | None]) -> str:
    msg = _m()["target"].replace("[προφίλ]", profile).replace("[βάρος]", kg(weight_kg)).replace("[Λ%]", pct(fat_percent))
    return _fill_range(msg, dates, weeks)


def composition_message(change_kg: float, ffm_change_kg: float, trained: bool) -> str:
    """[Χ] = αλλαγή βάρους, [Ζ] = αλλαγή άλιπης, [Υ] = [Χ] − [Ζ] (Στοιχεία 03, 42)."""
    msg = (_m()["composition"].replace("[Χ]", kg(abs(change_kg))).replace("[Υ]", kg(abs(change_kg) - abs(ffm_change_kg)))
           .replace("[Ζ]", kg(abs(ffm_change_kg))))
    return f"{msg} {_m()['composition_trained']}" if trained else msg


def target_category_message(bmi: float, category: str, extra: tuple[str, ...] = ()) -> str:
    msg = _m()["target_category"].replace("[ΔΜΣ]", num(bmi, 1)).replace("[κατηγορία]", category)
    return " ".join((msg, *extra))


def progress_message(planned_kg: float, predicted_kg: float, actual_trend_kg: float) -> str:
    """Κανόνας 10: προγραμματισμένη τιμή, πρόβλεψη και πραγματική (τάση), με αυτή τη σειρά."""
    parts = iter((kg(planned_kg), kg(predicted_kg), kg(actual_trend_kg)))
    out, msg = "", _m()["progress"]
    while "[βάρος]" in msg:
        head, msg = msg.split("[βάρος]", 1)
        out += head + next(parts)
    return out + msg


def conclusion(profile: str) -> str:
    return _m()[f"conclusion_{profile}"]


def _result_first(messages: tuple[str, ...], template: str) -> tuple[str, ...]:
    """Κανόνας 3: κάθε μέρος ξεκινά με τη γραμμή «αποτέλεσμα» του στοιχείου."""
    prefix = template.split("[", 1)[0]
    head = [m for m in messages if m.startswith(prefix)]
    return tuple(head + [m for m in messages if m not in head])


# --- Χρονοδιάγραμμα (μέρος 4) --------------------------------------------------------------------------
@dataclass(frozen=True)
class Row:
    week: int
    day: date
    cells: dict[str, str]


def timeline(forecast: e43.Forecast, start: date, weight_kg: float, fat_percent: float, height_cm: float,
             muscle_kg: float | None = None, bone_kg: float | None = None) -> tuple[Row, ...]:
    """Εβδομάδα 0 με τις μετρημένες τιμές, μετά οι εβδομάδες της πρόβλεψης με «≈» (Πίνακας 5)."""
    fat0 = weight_kg * fat_percent / 100
    ffm0 = weight_kg - fat0
    water_k = e43.load_data()["water_per_ffm"]
    rows = [Row(0, start, {
        "βάρος": f"{measured(weight_kg)} kg", "λίπος": f"{kg(fat0)} kg ({measured(fat_percent)}%)",
        "άλιπη": f"{kg(ffm0)} kg", "μύες": f"{kg(muscle_kg)} kg" if muscle_kg is not None else "—",
        "νερό": approx(f"{kg(water_k * ffm0)} kg"), "οστά": f"{kg(bone_kg)} kg" if bone_kg is not None else "—",
        "ΔΜΣ": num(e04.bmi(weight_kg, height_cm), 1)})]
    for w in forecast.weeks:
        rows.append(Row(w.week, start + timedelta(weeks=w.week), {
            "βάρος": approx(f"{kg(w.weight_kg)} kg"), "λίπος": approx(f"{kg(w.fat_kg)} kg ({pct(w.fat_percent)}%)"),
            "άλιπη": approx(f"{kg(w.ffm_kg)} kg"),
            "μύες": approx(f"{kg(w.muscle_kg)} kg") if w.muscle_kg is not None else "—",
            "νερό": approx(f"{kg(w.water_kg)} kg"), "οστά": f"{kg(w.bone_kg)} kg" if w.bone_kg is not None else "—",
            "ΔΜΣ": approx(num(w.bmi, 1))}))
    return tuple(rows)


@dataclass(frozen=True)
class ChartPoint:
    week: int
    predicted_kg: float
    band_low_kg: float
    band_high_kg: float


def chart(forecast: e43.Forecast, weight_kg: float, target_weight_kg: float,
          rates: tuple[float, float]) -> tuple[ChartPoint, ...]:
    """Κανόνας 9: γραμμή πρόβλεψης και σκιασμένο εύρος (απώλεια· το εύρος σταματά στον βάρος-στόχο)."""
    slow, fast = rates
    pts = [ChartPoint(0, weight_kg, weight_kg, weight_kg)]
    for w in forecast.weeks:
        pts.append(ChartPoint(w.week, w.weight_kg, max(target_weight_kg, weight_kg - fast * w.week),
                              max(target_weight_kg, weight_kg - slow * w.week)))
    return tuple(pts)


# --- Παρουσίαση ---------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Part:
    name: str
    messages: tuple[str, ...] = ()
    lines: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class Presentation:
    parts: tuple[Part, ...]
    before: tuple[str, ...] = ()  # πριν από το πλάνο (π.χ. ιστορικό διατροφικής διαταραχής)
    milestones: tuple[Milestone, ...] = ()
    weeks_to_target: tuple[int, int | None] | None = None
    rows: tuple[Row, ...] = ()
    chart: tuple[ChartPoint, ...] = ()
    hide_daily_weighings: bool = False
    indicative: bool = False
    info: str = ""
    notes: tuple[str, ...] = field(default=())


def energy_lines(energy, partition=None) -> tuple[tuple[str, str], ...]:
    """Μέρος 1 (Πίνακας 3) από το EnergyResult του Στοιχείου 40 και το Partition του 42· ενέργεια στις 10 kcal."""
    out = []
    if energy.tdee is not None:
        lo, hi = energy.tdee_range
        out.append(("Αρχική δαπάνη (TDEE)", f"{approx(kcal10(energy.tdee))} kcal ({kcal10(lo)}–{kcal10(hi)})"))
    if energy.bmr is not None:
        out.append(("Βασικός μεταβολισμός", f"{approx(kcal10(energy.bmr.kcal))} kcal ({energy.bmr.equation})"))
    if energy.pal is not None:
        out.append(("Επίπεδο δραστηριότητας (PAL)", num(energy.pal, 1)))
    if energy.daily_delta_kcal is not None:
        name = "Ημερήσιο έλλειμμα" if energy.daily_delta_kcal < 0 else "Ημερήσιο πλεόνασμα"
        out.append((name, f"{kcal10(abs(energy.daily_delta_kcal))} kcal"))
    if energy.target_intake_kcal is not None:
        out.append(("Πρόσληψη-στόχος", f"{approx(kcal10(energy.target_intake_kcal))} kcal"))
    weekly = energy.weekly_change_kg
    if weekly is None and partition is not None:
        weekly = partition.weekly_change_kg
    if weekly is not None:
        out.append(("Εβδομαδιαία αλλαγή βάρους", approx(f"{signed_kg(weekly)} kg")))
    return tuple(out)


def macro_lines(macros) -> tuple[tuple[str, str], ...]:
    """Μέρος 2 (Πίνακας 3) από το Macros του Στοιχείου 41."""
    from davinci import element_41 as e41

    k = e41.load_data()["kcal_per_g"]
    out = [("Πρωτεΐνη", f"{num(macros.protein_g, 0)} g · {kcal10(macros.protein_g * k['protein'])} kcal · "
                        f"{num(macros.percent('protein'), 0)}% · {num(macros.protein_g_per_kg, 1)} g/kg "
                        f"(βάρος αναφοράς {num(macros.reference_weight_kg, 0)} kg)"),
           ("Λίπος", f"{num(macros.fat_g, 0)} g · {kcal10(macros.fat_g * k['fat'])} kcal · {num(macros.percent('fat'), 0)}%"),
           ("Υδατάνθρακες", f"{num(macros.carbs_g, 0)} g · {kcal10(macros.carbs_g * k['carbs'])} kcal · "
                            f"{num(macros.percent('carbs'), 0)}%"),
           ("Φυτικές ίνες", f"τουλάχιστον {num(macros.fiber_min_g, 0)} g")]
    return tuple(out)


def present(user: e01.UserCategories, *, weight_kg: float, fat_percent: float, start: date, goal: str = "loss",
            energy=None, macros=None, partition=None, target=None, forecast: e43.Forecast | None = None,
            rates: tuple[float, float] | None = None, trained: bool = False,
            fat_in_healthy_range: bool | None = None, target_fat_in_healthy_range: bool | None = None,
            muscle_kg: float | None = None, bone_kg: float | None = None, eating_disorder_history: bool = False,
            hide_daily_weighings: bool = False, lactation_timeline_allowed: bool = True,
            indicative_condition: bool = False) -> Presentation:
    """energy: e40.EnergyResult · macros: e41.Macros · partition: e42.Partition · target: e03.TargetPoint
    (βάρος-στόχος της Φάσης 1) · rates: εύρος ρυθμού (αργός, γρήγορος) σε kg/εβδομάδα."""
    from davinci import element_40 as e40
    from davinci import element_41 as e41
    from davinci import element_42 as e42

    d = load_data()
    m = d["messages"]
    names = d["parts"]
    indicative = indicative_condition or user.age >= 80
    before = (m["eating_disorder"],) if eating_disorder_history and goal == "loss" else ()

    p1_msgs = () if energy is None else _result_first(energy.messages, e40.load_data()["messages"]["result"])
    if partition is not None:
        p1_msgs += _result_first(partition.messages, e42.load_data()["messages"]["result"])
        indicative = indicative or partition.indicative
    if energy is not None:
        indicative = indicative or energy.indicative
    parts = []
    if energy is not None or partition is not None:
        parts.append(Part(names[0], p1_msgs,
                          energy_lines(energy, partition) if energy is not None and energy.tdee is not None else ()))
    if macros is not None:
        parts.append(Part(names[1], _result_first(macros.messages, e41.load_data()["messages"]["result"]),
                          macro_lines(macros)))
        indicative = indicative or macros.indicative

    bmi_now = e04.classify(weight_kg, user, fat_in_healthy_range=fat_in_healthy_range)
    start_msgs = [start_message(weight_kg, fat_percent, bmi_now.value, bmi_now.category)] if bmi_now.category else []
    if bmi_now.category:
        start_msgs += [x for x in bmi_now.messages if x == e04.load_data()["messages"]["rule_2"]]
    if bmi_now.elderly_note:
        start_msgs.append(bmi_now.elderly_note)  # 65+: μηνύματα του Στοιχείου 04 (Κανόνας 12)

    # Κανόνας 12: ανήλικοι και εγκυμοσύνη χωρίς στόχους και χωρίς χρονοδιάγραμμα
    if e01.is_minor(user.age) or user.pregnant:
        extra = (m["pregnancy"],) if user.pregnant else ()
        parts.append(Part(names[2], tuple(start_msgs) + extra))
        return Presentation(tuple(parts), before, indicative=indicative, info=m["info"])

    summary = list(start_msgs)
    ms: tuple[Milestone, ...] = ()
    weeks = None
    if target is not None and goal == "loss" and rates is not None:
        ms = milestones(weight_kg, target.weight_kg, bmi_now.category, goal)
        for mi in ms:
            w = weeks_range(weight_kg - mi.weight_kg, rates)
            summary.append(milestone_message(mi, date_range(start, w)))
        weeks = weeks_range(weight_kg - target.weight_kg, rates)
        summary.append(target_message(user.profile, target.weight_kg, target.target_fat_percent, weeks,
                                      date_range(start, weeks)))
        summary.append(composition_message(weight_kg - target.weight_kg,
                                           weight_kg * (1 - fat_percent / 100) - target.ffm_kg, trained))
        bmi_t = e04.classify(target.weight_kg, user, fat_in_healthy_range=target_fat_in_healthy_range)
        extra = tuple(x for x in bmi_t.messages if x == e04.load_data()["messages"]["rule_2"])
        if bmi_t.category:  # χωρίς κατηγορία ΔΜΣ στον θηλασμό (Στοιχείο 04, Κανόνας 5)
            summary.append(target_category_message(bmi_t.value, bmi_t.category, extra))
        summary.append(m["forecast"])
    summary.append(conclusion(user.profile))
    parts.append(Part(names[2], tuple(summary)))

    rows: tuple[Row, ...] = ()
    pts: tuple[ChartPoint, ...] = ()
    show_timeline = forecast is not None and (not user.breastfeeding or lactation_timeline_allowed)
    if show_timeline:
        rows = timeline(forecast, start, weight_kg, fat_percent, user.height_cm, muscle_kg, bone_kg)
        if target is not None and rates is not None:
            pts = chart(forecast, weight_kg, target.weight_kg, rates)
        parts.append(Part(names[3], forecast.messages + (m["hide_weighings"],)))
    return Presentation(tuple(parts), before, ms, weeks, rows, pts, hide_daily_weighings, indicative, m["info"])
