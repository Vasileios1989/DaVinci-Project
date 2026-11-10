"""Στοιχείο 42 — Κατεύθυνση, κατανομή λίπους/άλιπης και ενέργεια ανά κιλό.

Μερίδιο άλιπης στην απώλεια: f = k × 10,4 / (λίπος kg + k × 10,4) (k = 1 · 0,543 με βάρη/μικτή, όπως στο Στοιχείο 03).
Ενέργεια ανά κιλό: E = (1 − f) × 9.441 + f × 1.816 kcal/kg. Ξαναϋπολογίζονται κάθε εβδομάδα με το λίπος της εβδομάδας.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from davinci import element_01 as e01
from davinci import element_02 as e02
from davinci.fmt import num

DATA_FILE = Path(__file__).resolve().parents[2] / "data" / "element_42.json"


@lru_cache(maxsize=1)
def load_data() -> dict:
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


def ffm_fraction_loss(fat_kg: float, trained: bool) -> float:
    d = load_data()
    k = d["k_trained"] if trained else d["k_untrained"]
    a = k * d["forbes_constant"]
    return a / (fat_kg + a)


def ffm_fraction_gain(fat_kg: float, trained: bool, weekly_gain_kg: float | None = None) -> float:
    """Με προπόνηση: f = min(1, (1,4 / 12) / εβδομαδιαία αύξηση) · χωρίς: Forbes με k = 1 («Ενδεικτική»)."""
    d = load_data()
    if trained:
        if not weekly_gain_kg or weekly_gain_kg <= 0:
            raise e01.InvalidInput("Αύξηση με προπόνηση: χρειάζεται εβδομαδιαία αύξηση (kg).")
        return min(1.0, d["gain_trained_ffm_kg_per_12_weeks"] / 12 / weekly_gain_kg)
    return ffm_fraction_loss(fat_kg, trained=False)


def energy_per_kg(f: float) -> float:
    e = load_data()["energy_kcal_per_kg"]
    return (1 - f) * e["fat"] + f * e["ffm_change"]


def weekly_change_from_deficit(deficit_kcal_day: float, e_kcal_kg: float) -> float:
    """Κανόνας 4: όταν το Στοιχείο 40 δίνει απευθείας έλλειμμα (ΔΜΣ ≥ 25)."""
    return deficit_kcal_day * 7 / e_kcal_kg


def daily_delta_from_rate(weekly_kg: float, e_kcal_kg: float) -> float:
    return weekly_kg * e_kcal_kg / 7


@dataclass(frozen=True)
class Direction:
    direction: str | None  # «loss» · «gain» · «maintain» · None (καμία απώλεια χωρίς πρόταση)
    suggested: str | None
    no_loss: bool = False
    below_minimum: bool = False
    messages: tuple[str, ...] = ()


def direction(fat_percent: float, user: e01.UserCategories, *, ffmi_below_phase2_target: bool | None = None,
              user_choice: str | None = None, low_energy_availability: bool = False) -> Direction:
    """Πίνακας 5. ffmi_below_phase2_target: από το Στοιχείο 03 (Συμπλήρωμα Δ)."""
    d = load_data()
    m, words = d["messages"], d["direction_words"]
    if e01.is_minor(user.age) or user.pregnant or low_energy_availability:
        return Direction(None, None, no_loss=True)
    if fat_percent < d["absolute_min_fat_percent"][user.sex]:
        return Direction(None, None, no_loss=True, below_minimum=True)  # προειδοποίηση του Στοιχείου 02
    lo, hi = e02.profile_range(user)
    msgs: list[str] = []
    if fat_percent > hi:
        sug, where = "loss", "πάνω από"
    else:
        sug = "gain" if ffmi_below_phase2_target else "maintain"
        where = "μέσα στο" if fat_percent >= lo else None  # κάτω από το εύρος: χωρίς μήνυμα (σύμβαση)
    if where:
        msgs.append(m["direction"].replace("[πάνω από / μέσα στο]", where)
                    .replace("[απώλεια / αύξηση / συντήρηση]", words[sug]))
    chosen = sug
    if user_choice and user_choice != sug:
        chosen = user_choice
        msgs.append(m["user_direction"].replace("[κατεύθυνση]", words[user_choice], 1)
                    .replace("[κατεύθυνση]", words[sug], 1))
    return Direction(chosen, sug, messages=tuple(msgs))


@dataclass(frozen=True)
class Partition:
    direction: str
    f: float | None  # μερίδιο άλιπης
    e_kcal_per_kg: float | None
    weekly_change_kg: float | None = None
    weekly_fat_kg: float | None = None
    weekly_ffm_kg: float | None = None
    daily_delta_kcal: float | None = None
    allowed: bool = True
    indicative: bool = False
    messages: tuple[str, ...] = ()


def partition(direction_: str, fat_kg: float, user: e01.UserCategories, *, trained: bool, bmi: float,
              weekly_change_kg: float | None = None, deficit_kcal_day: float | None = None,
              glp1: bool = False, bariatric: bool = False, regain: bool = False,
              lactation_weeks_postpartum: float | None = None, lactation_exclusive: bool = True) -> Partition:
    """weekly_change_kg: αρνητικό σε απώλεια, θετικό σε αύξηση. deficit_kcal_day: θετικό έλλειμμα (ΔΜΣ ≥ 25)."""
    d = load_data()
    m = d["messages"]
    msgs: list[str] = []
    indicative = False
    if direction_ == "maintain" and not regain:
        if trained:
            msgs.append(m["maintain_trained"])
        return Partition("maintain", None, None, 0.0, 0.0, 0.0, 0.0, messages=tuple(msgs))

    if direction_ == "loss" and user.breastfeeding and lactation_weeks_postpartum is None:
        # Κανόνας 12: απώλεια «μόνο αν έχουν περάσει τουλάχιστον 4 εβδομάδες»· χωρίς τη δήλωση δεν επιτρέπεται
        return Partition("loss", None, None, allowed=False, messages=(m["lactation_no"],))
    if direction_ == "loss" and lactation_weeks_postpartum is not None:
        lc = d["lactation"]
        if lactation_weeks_postpartum < lc["min_weeks_postpartum"] or bmi < lc["min_bmi"]:
            return Partition("loss", None, None, allowed=False, messages=(m["lactation_no"],))
        msgs.append(m["lactation_ok"])
        indicative = (not lactation_exclusive) or bmi > lc["indicative_bmi_above"]

    if regain or (direction_ == "gain" and not trained):
        f = ffm_fraction_loss(fat_kg, trained=False)
        indicative = True
        if regain:
            msgs.append(m["regain"])
    elif direction_ == "gain":
        if weekly_change_kg is None:
            raise e01.InvalidInput("Αύξηση: χρειάζεται εβδομαδιαία αύξηση (kg).")
        f = ffm_fraction_gain(fat_kg, True, weekly_change_kg)
        per_month = d["gain_trained_ffm_kg_per_12_weeks"] / 3
        msgs.append(m["gain_trained"].replace("[Χ]", num(per_month, 2).rstrip("0").rstrip(",")))
    elif glp1 or bariatric:
        f = d["special_f"]["glp1" if glp1 else "bariatric"]
        indicative = True
        msgs.append(m["glp1"])
    else:
        f = ffm_fraction_loss(fat_kg, trained)
        msgs.append(m["trained"] if trained else m["untrained"])
    e = energy_per_kg(f)
    if direction_ == "gain":
        msgs.append(m["gain_energy"])
        indicative = True

    weekly = weekly_change_kg
    if weekly is None and deficit_kcal_day is not None:
        weekly = -weekly_change_from_deficit(deficit_kcal_day, e)
    if direction_ == "loss" and lactation_weeks_postpartum is not None and weekly is not None:
        weekly = max(weekly, -d["lactation"]["max_kg_week"])
    delta = daily_delta_from_rate(weekly, e) if weekly is not None else None
    head = (m["result"].replace("[100 − f]", num((1 - f) * 100, 0)).replace("[f]", num(f * 100, 0))
            .replace("[E]", num(e, 0)))
    msgs.insert(0, head)
    if user.age >= d["age_message_from"]:
        msgs.append(m["age_60"])
    if user.age >= d["age_no_data_from"]:
        msgs.append(m["age_80"])
        indicative = True
    if (user.effective_group or "5") not in d["reference_ancestries"]:
        msgs.append(m["ancestry"])
        indicative = True
    return Partition(direction_, f, e, weekly,
                     None if weekly is None else weekly * (1 - f), None if weekly is None else weekly * f,
                     delta, True, indicative, tuple(msgs))


def info() -> str:
    return load_data()["messages"]["info"]
