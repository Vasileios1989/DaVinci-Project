"""Στοιχείο 41 — Μακροθρεπτικά.

Πρωτεΐνη σε g ανά κιλό βάρους αναφοράς (μικρότερο από σημερινό βάρος και βάρος-στόχος Υγείας, Στοιχείο 03) →
λίπος ως % της ενέργειας (20–35%, προεπιλογή 30%) → υδατάνθρακες ό,τι μένει· φυτικές ίνες ≥ 25 g. Χωρίς σωματότυπο.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from davinci import element_01 as e01
from davinci.fmt import num

DATA_FILE = Path(__file__).resolve().parents[2] / "data" / "element_41.json"


@lru_cache(maxsize=1)
def load_data() -> dict:
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


def reference_weight(weight_kg: float, health_target_weight_kg: float | None) -> float:
    """Κανόνας 2: το μικρότερο από σημερινό βάρος και βάρος-στόχος Υγείας."""
    return weight_kg if health_target_weight_kg is None else min(weight_kg, health_target_weight_kg)


def protein_group(goal: str, training: str | None, age: int) -> tuple[str, dict]:
    """training: «weights» (βάρη ή μικτή) · «other» (άλλοι αθλητές) · None. Η υψηλότερη προεπιλογή κερδίζει."""
    g = load_data()["protein_groups"]
    loss = goal == "loss"
    names = ["general_loss" if loss else "general_maintain"]
    if training == "weights":
        names.append("weights_loss" if loss else "weights_maintain")
    elif training == "other":
        names.append("other_athlete")
    if age >= g["age_65"]["from_age"]:
        names.append("age_65")
    # ισοπαλία (π.χ. 65+ με 1,2): η πιο ειδική ομάδα, δηλαδή η τελευταία (σύμβαση συστήματος)
    best = max(reversed(names), key=lambda n: g[n]["default"])
    return best, g[best]


@dataclass(frozen=True)
class Macros:
    intake_kcal: float
    reference_weight_kg: float
    protein_g: float
    fat_g: float
    carbs_g: float
    fiber_min_g: float
    protein_g_per_kg: float  # ανά βάρος αναφοράς
    carbs_g_per_kg: float  # ανά σημερινό βάρος (Πίνακας 4)
    fat_percent: float
    protein_group: str
    adjusted: tuple[str, ...] = ()  # «λίπος», «πρωτεΐνη»
    slower_rate_needed: bool = False
    indicative: bool = False
    messages: tuple[str, ...] = ()

    def percent(self, which: str) -> float:
        k = load_data()["kcal_per_g"]
        return {"protein": self.protein_g * k["protein"], "fat": self.fat_g * k["fat"],
                "carbs": self.carbs_g * k["carbs"]}[which] / self.intake_kcal * 100


def compute(intake_kcal: float, user: e01.UserCategories, weight_kg: float, *, goal: str = "maintain",
            health_target_weight_kg: float | None = None, training: str | None = None,
            fat_in_athletic_range: bool = False, protein_g_per_kg: float | None = None,
            fat_percent: float | None = None, carb_load: str | None = None, trimester: int | None = None,
            pre_pregnancy_weight_kg: float | None = None, lactation_months: float | None = None,
            kidney_disease: bool = False, condition: str | None = None, vegetarian: bool = False) -> Macros:
    """carb_load (αθλητές): «ελαφρύ» · «μέτριο» · «υψηλό» · «πολύ υψηλό» (Πίνακας 4)."""
    d = load_data()
    m, kc = d["messages"], d["kcal_per_g"]
    if user.age < d["min_age"]:
        raise e01.InvalidInput("Στοιχείο 41: μόνο για ενήλικες 18+ (όπως το Στοιχείο 40).")
    msgs: list[str] = []
    indicative = False
    pregnant_or_lact = trimester is not None or lactation_months is not None
    if pregnant_or_lact:
        ref = pre_pregnancy_weight_kg or weight_kg
        indicative = pre_pregnancy_weight_kg is None
    else:
        ref = reference_weight(weight_kg, health_target_weight_kg)

    gname, grp = protein_group(goal, training, user.age)
    lo, hi = grp["range"]
    if gname == "weights_loss" and fat_in_athletic_range:
        hi = grp["max_lean"]
    p_kg = grp["default"] if protein_g_per_kg is None else protein_g_per_kg
    if not (lo - 1e-9 <= p_kg <= hi + 1e-9):
        raise e01.InvalidInput(f"Πρωτεΐνη για την ομάδα: {num(lo, 2)}–{num(hi, 1)} g/kg.")
    if kidney_disease:
        p_kg = min(p_kg, d["kidney_max"])
        lo = min(lo, p_kg)
    protein = p_kg * ref
    extra = 0
    if trimester is not None:
        extra = d["pregnancy_extra_g"][str(trimester)]
    elif lactation_months is not None:
        extra = d["lactation_extra_g"]["0-6" if lactation_months <= 6 else "after_6"]
    protein += extra

    f = d["fat"]
    fat_pct = f["default"] if fat_percent is None else fat_percent
    if fat_pct < f["minimum"]:
        msgs.append(m["fat_below_20"])
        fat_pct = f["minimum"]
    if fat_pct > f["range"][1]:
        raise e01.InvalidInput("Λίπος: 20–35% της ενέργειας.")
    fat_kcal = intake_kcal * fat_pct / 100
    carbs = (intake_kcal - protein * kc["protein"] - fat_kcal) / kc["carbs"]

    # Κανόνας 9: αθλητής κάτω από το κάτω όριο του Πίνακα 4 · Κανόνας 10: αρνητικοί υδατάνθρακες σε όλους
    athlete = training in ("weights", "other") and carb_load is not None
    need = d["carbs_athlete_g_per_kg"][carb_load][0] * weight_kg if athlete else 0.0
    adjusted: list[str] = []
    slower = False
    if carbs < need - 1e-9:
        fat_min = intake_kcal * f["minimum"] / 100
        fat_kcal_needed = intake_kcal - protein * kc["protein"] - need * kc["carbs"]
        new_fat = max(fat_min, fat_kcal_needed)
        if new_fat < fat_kcal:
            fat_kcal, adjusted = new_fat, ["λίπος"]
        carbs = (intake_kcal - protein * kc["protein"] - fat_kcal) / kc["carbs"]
        if carbs < need - 1e-9:
            p_min = lo * ref + extra
            p_needed = (intake_kcal - fat_kcal - need * kc["carbs"]) / kc["protein"]
            new_p = max(p_min, p_needed)
            if new_p < protein:
                protein = new_p
                adjusted.append("πρωτεΐνη")
            carbs = (intake_kcal - protein * kc["protein"] - fat_kcal) / kc["carbs"]
            slower = carbs < need - 1e-9
        words = {"λίπος": "το λίπος", "πρωτεΐνη": "την πρωτεΐνη"}
        txt = m["carbs_low"].replace("[το λίπος/την πρωτεΐνη]", " και ".join(words[a] for a in adjusted) or "το λίπος")
        txt = txt.replace(" [Αν δεν φτάνει: Διάλεξε πιο αργό ρυθμό απώλειας.]",
                          " Διάλεξε πιο αργό ρυθμό απώλειας." if slower else "")
        msgs.append(txt)
    carbs = max(carbs, 0.0)
    fat_g = fat_kcal / kc["fat"]

    def pct(x):
        return num(x / intake_kcal * 100, 0) + "%"
    head = (m["result"].replace("[πρόσληψη]", num(intake_kcal, 0))
            .replace("[Π] g ([%])", f"{num(protein, 0)} g ({pct(protein * kc['protein'])})")
            .replace("[Λ] g ([%])", f"{num(fat_g, 0)} g ({pct(fat_kcal)})")
            .replace("[Υ] g ([%])", f"{num(carbs, 0)} g ({pct(carbs * kc['carbs'])})"))
    msgs.insert(0, head)
    if not pregnant_or_lact and ref < weight_kg:
        msgs.append(m["reference_weight"].replace("[Β]", num(ref, 0)))
    if protein / ref > d["protein_message_above"] and not kidney_disease:
        msgs.append(m["protein_high"])
    if kidney_disease:
        msgs.append(m["kidney"])
    if trimester is not None:
        msgs.append(m["pregnancy"].replace("[τρίμηνο]", f"{trimester}ο").replace("[Χ]", num(extra, 0)))
    lo_meal, hi_meal = (x * ref for x in d["per_meal_g_per_kg"])
    msgs += [m["saturated"], m["distribution"].replace("[0,25–0,3 × Β]", f"{num(lo_meal, 0)}–{num(hi_meal, 0)}"),
             m["plant"]]
    if vegetarian:
        msgs.append(m["vegetarian"])
    if condition:
        msgs.append(m["condition"].replace("[κατάσταση]", condition))
        indicative = True
    return Macros(intake_kcal, ref, protein, fat_g, carbs, d["fiber_min_g"], protein / ref, carbs / weight_kg,
                  fat_kcal / intake_kcal * 100, gname, tuple(adjusted), slower, indicative, tuple(msgs))
