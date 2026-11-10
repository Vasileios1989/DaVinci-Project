"""Στοιχείο 40 — Ενεργειακό ισοζύγιο.

TDEE = BMR × PAL (EFSA 2013), χωρίς ξεχωριστό TEF· δείχνεται με εύρος ±10% ως «αρχική εκτίμηση» και διορθώνεται
από την πορεία του βάρους (Στοιχείο «Καθημερινή Επαναπροσαρμογή»). Ενήλικες 18+.

Η ενέργεια ανά κιλό αλλαγής βάρους ορίζεται σε άλλο στοιχείο («3.2»)· εδώ δίνεται ως όρισμα (kcal_per_kg).
Χωρίς αυτήν, στον δρόμο του ρυθμού (%) δεν υπολογίζεται πρόσληψη-στόχος.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from davinci import element_01 as e01
from davinci import element_04 as e04
from davinci.fmt import num

DATA_FILE = Path(__file__).resolve().parents[2] / "data" / "element_40.json"


@lru_cache(maxsize=1)
def load_data() -> dict:
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


def kcal(x: float) -> str:
    return num(x, 0)


def is_athlete(hours_per_week: float, sessions_per_week: int) -> bool:
    a = load_data()["athlete"]
    return hours_per_week >= a["min_hours_week"] and sessions_per_week >= a["min_sessions_week"]


def training_level(years: float) -> str:
    """< 1 έτος: αρχάριος · 1–3 έτη: μεσαίος · > 3 έτη: προχωρημένος (σύμβαση συστήματος)."""
    if years < 1:
        return "αρχάριος"
    return "μεσαίος" if years <= 3 else "προχωρημένος"


@dataclass(frozen=True)
class Bmr:
    kcal: float
    equation: str
    out_of_sample: bool = False  # ten Haaf εκτός 18–35 ή ΔΜΣ > 27


def bmr(user: e01.UserCategories, weight_kg: float, *, athlete: bool = False,
        fat_free_mass_kg: float | None = None) -> Bmr:
    d = load_data()
    eq = d["bmr_equations"]
    h_cm, age = user.height_cm, user.age
    bmi = e04.bmi(weight_kg, h_cm)
    if bmi >= d["severe_obesity_bmi"]:
        a, b, c, k = eq["harris_benedict"][user.sex]
        return Bmr(a * weight_kg + b * h_cm / 100 + c * age + k, eq["harris_benedict"]["name"])
    if athlete and fat_free_mass_kg is not None:
        cu = eq["cunningham"]
        return Bmr(cu["a"] + cu["b"] * fat_free_mass_kg, cu["name"])
    if athlete:
        th = eq["ten_haaf"]
        a, b, c, s, k = th["kj"]
        kj = a * weight_kg + b * h_cm / 100 + c * age + s * (1 if user.sex == "Άνδρας" else 0) + k
        smp = th["sample"]
        out = not (smp["age"][0] <= age <= smp["age"][1]) or bmi > smp["bmi_max"]
        return Bmr(kj / th["kj_per_kcal"], th["name"], out)
    a, b, c, k = eq["mifflin"][user.sex]
    return Bmr(a * weight_kg + b * h_cm + c * age + k, eq["mifflin"]["name"])


@dataclass(frozen=True)
class EnergyResult:
    bmr: Bmr | None = None
    pal: float | None = None
    tdee: float | None = None
    tdee_range: tuple[float, float] | None = None
    bmr_share: float | None = None  # 1 / PAL
    goal: str | None = None
    rate_percent: float | None = None
    rate_range: tuple[float, float] | None = None
    weekly_change_kg: float | None = None
    daily_delta_kcal: float | None = None  # αρνητικό = έλλειμμα
    target_intake_kcal: float | None = None
    needs_confirmation: bool = False
    indicative: bool = False
    messages: tuple[str, ...] = ()


def rate_range(goal: str, level: str | None) -> tuple[float, float] | None:
    r = load_data()["rates"]
    if goal == "loss":
        return tuple(r["loss"])
    if goal == "gain":
        return tuple(r["gain"][level or "αρχάριος"])
    return None


def assess(user: e01.UserCategories, weight_kg: float, pal: float, *, goal: str = "maintain",
           athlete: bool = False, fat_free_mass_kg: float | None = None, ffm_indicative: bool = False,
           rate_percent: float | None = None, training_years: float | None = None,
           aha_deficit: int | str | None = None, kcal_per_kg: float | None = None,
           confirmed_fast_rate: bool = False, lea_signs: bool = False, lea_cleared: bool = False,
           trimester: int | None = None, pre_pregnancy_weight_kg: float | None = None, twins: bool = False,
           lactation_exclusive_months: float | None = None, condition: str | None = None,
           watch_kcal: float | None = None, fat_in_healthy_range: bool | None = None) -> EnergyResult:
    """goal: «loss» · «maintain» · «gain». aha_deficit (ΔΜΣ ≥ 25, απώλεια): 500 · 750 · «30%».
    condition: η φράση που μπαίνει στη θέση του «Η [κατάσταση/το φάρμακο]» (π.χ. «Η θεραπεία του θυρεοειδούς»).
    fat_in_healthy_range: από το Στοιχείο 02. Με ΔΜΣ ≥ 25 και λίπος στο υγιές εύρος ο ΔΜΣ είναι αυξημένος από
    μυϊκή μάζα (Στοιχείο 04, Κανόνας 2): ισχύει ο ρυθμός %, όχι το έλλειμμα AHA (Παράδειγμα 2· σύμβαση συστήματος)."""
    d = load_data()
    m = d["messages"]
    if user.age < d["min_age"]:
        return EnergyResult(messages=(m["under_18"],))
    if goal not in ("loss", "maintain", "gain"):
        raise e01.InvalidInput("Στόχος: loss · maintain · gain.")
    key = f"{pal:.1f}"
    if key not in d["pal"]:
        raise e01.InvalidInput(f"PAL: {', '.join(d['pal'])}.")
    if key in d["pal_athlete_only"] and not athlete:
        raise e01.InvalidInput("Τα PAL 2,2 και 2,4 δίνονται μόνο σε αθλητή.")

    msgs: list[str] = []
    indicative = ffm_indicative or key in d["pal_athlete_only"]
    pregnant = trimester is not None
    w_bmr = pre_pregnancy_weight_kg if (pregnant and pre_pregnancy_weight_kg) else weight_kg
    if (pregnant and not pre_pregnancy_weight_kg) or (user.pregnant and not pregnant):
        indicative = True  # χωρίς βάρος πριν ή χωρίς τρίμηνο (δεν μπαίνει η προσθήκη του Πίνακα 6)
    b = bmr(user, w_bmr, athlete=athlete, fat_free_mass_kg=fat_free_mass_kg)
    tdee = b.kcal * pal
    extra = 0
    if pregnant:
        extra = d["pregnancy_extra_kcal"][str(trimester)]
    elif lactation_exclusive_months is not None and lactation_exclusive_months <= d["lactation_months"]:
        extra = d["lactation_extra_kcal"]
    tdee += extra
    p = d["range_percent"] / 100
    rng = (tdee * (1 - p), tdee * (1 + p))
    msgs.append(m["result"].replace("[TDEE]", kcal(tdee)).replace("[κάτω]", kcal(rng[0])).replace(
        "[πάνω]", kcal(rng[1])).replace("[BMR]", kcal(b.kcal)).replace("[PAL]", num(pal)))
    msgs.append(m["initial"])
    if b.out_of_sample:
        msgs.append(m["athlete_out"])
        indicative = True
    if pregnant:
        msgs.append(m["pregnancy"].replace("[τρίμηνο]", f"{trimester}ο").replace("[Χ]", kcal(extra)))
        if twins:
            msgs.append(m["twins"])
            indicative = True
    elif lactation_exclusive_months is not None:
        msgs.append(m["lactation"] if lactation_exclusive_months <= d["lactation_months"] else m["lactation_after_6"])
    if condition:
        msgs.append(m["condition"].replace("Η [κατάσταση/το φάρμακο]", condition))
        indicative = True
    if (user.effective_group or "5") not in d["reference_ancestries"]:
        msgs.append(m["ancestry"])
        indicative = True
    if watch_kcal is not None:
        msgs.append(m["watch"])

    base = dict(bmr=b, pal=pal, tdee=tdee, tdee_range=rng, bmr_share=1 / pal, goal=goal)
    if (pregnant or user.pregnant) and goal == "loss":
        goal = "maintain"  # καμία πρόταση ελλείμματος στην εγκυμοσύνη (σύμβαση συστήματος)
        base["goal"] = goal
    if goal == "maintain":
        return EnergyResult(**base, target_intake_kcal=tdee, indicative=indicative, messages=tuple(msgs))
    if goal == "loss" and lea_signs and not lea_cleared:
        msgs.append(m["lea_yes"])
        return EnergyResult(**base, target_intake_kcal=tdee, indicative=indicative, messages=tuple(msgs))

    bmi = e04.bmi(weight_kg, user.height_cm)
    delta = weekly = rr = None
    muscular = bool(fat_in_healthy_range) and bmi >= d["aha"]["bmi_from"]
    if goal == "loss" and bmi >= d["aha"]["bmi_from"] and not muscular:
        # Κανόνας 13: ΔΜΣ ≥ 25 με λίπος πάνω από το υγιές εύρος (ή χωρίς μέτρηση λίπους) → έλλειμμα AHA
        if rate_percent is not None and aha_deficit is None:
            raise e01.InvalidInput("ΔΜΣ ≥ 25: έλλειμμα 500 ή 750 kcal ή «30%» (AHA/ACC/TOS 2013). Ο ρυθμός % "
                                   "ισχύει μόνο όταν το λίπος είναι στο υγιές εύρος (Στοιχείο 04, Κανόνας 2).")
        if aha_deficit is None:
            raise e01.InvalidInput("ΔΜΣ ≥ 25: έλλειμμα 500 ή 750 kcal ή «30%» (AHA/ACC/TOS 2013).")
        if aha_deficit == "30%":
            delta = -tdee * d["aha"]["deficit_percent"] / 100
        elif aha_deficit in d["aha"]["deficits_kcal"]:
            delta = -float(aha_deficit)
        else:
            raise e01.InvalidInput("Έλλειμμα: 500 · 750 · «30%».")
    else:
        if goal == "loss" and muscular and aha_deficit is not None:
            raise e01.InvalidInput("Λίπος στο υγιές εύρος: ο ΔΜΣ είναι αυξημένος από μυϊκή μάζα· "
                                   "χρησιμοποιείται ρυθμός %, όχι έλλειμμα AHA.")
        level = training_level(training_years) if training_years is not None else None
        rr = rate_range(goal, level)
        if rate_percent is None:
            raise e01.InvalidInput("Χρειάζεται ρυθμός (% του βάρους την εβδομάδα).")
        weekly = weight_kg * rate_percent / 100
        if rate_percent > rr[1] and not confirmed_fast_rate:
            txt = f"{num(rr[0], 2).rstrip('0').rstrip(',')}–{num(rr[1], 2).rstrip('0').rstrip(',')}%"
            msgs.append(m["above_range"].replace("[εύρος]", txt))
            return EnergyResult(**base, rate_percent=rate_percent, rate_range=rr, weekly_change_kg=weekly,
                                needs_confirmation=True, indicative=indicative, messages=tuple(msgs))
        if kcal_per_kg is not None:
            delta = weekly * kcal_per_kg / 7 * (-1 if goal == "loss" else 1)
    if delta is None:  # χωρίς ενέργεια ανά κιλό: δεν υπολογίζεται πρόσληψη
        return EnergyResult(**base, rate_percent=rate_percent, rate_range=rr, weekly_change_kg=weekly,
                            indicative=indicative, messages=tuple(msgs))
    intake = tdee + delta
    out = dict(**base, rate_percent=rate_percent, rate_range=rr, weekly_change_kg=weekly, daily_delta_kcal=delta,
               indicative=indicative)
    if intake < d["floor_kcal"]:
        msgs.append(m["below_800"])
        return EnergyResult(**out, messages=tuple(msgs))
    msgs.append(m["intake"].replace("[πρόσληψη]", kcal(intake)).replace(
        "[έλλειμμα/πλεόνασμα]", "έλλειμμα" if delta < 0 else "πλεόνασμα").replace("[Χ]", kcal(abs(delta))))
    if goal == "loss" and intake < d["low_intake_kcal"][user.sex]:
        msgs.append(m["low_intake"])
    return EnergyResult(**out, target_intake_kcal=intake, messages=tuple(msgs))


def lea_question() -> str:
    """Ερώτηση χαμηλής διαθεσιμότητας ενέργειας (σε απώλεια βάρους)."""
    return load_data()["messages"]["lea_question"]
