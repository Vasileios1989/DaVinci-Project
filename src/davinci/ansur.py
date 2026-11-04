"""Κοινό μοντέλο εκτίμησης περιφέρειας από τα δεδομένα ANSUR II (Στοιχεία 13, 14, 15).

ln(περιφέρεια, cm) = a + b × ln(βάρος / ύψος) + c × ηλικία + Δ(καταγωγή)
Εύρος: εκτίμηση × e^(±log_se). Οι συντελεστές είναι αυτοί των εγγράφων (υπολογισμός του
συστήματος από τα αρχεία ANSUR II· δεν ξαναϋπολογίζονται εδώ).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from davinci import element_01 as e01
from davinci import element_04 as e04


@dataclass(frozen=True)
class AnsurEstimate:
    weight_kg: float
    value_cm: float
    range_cm: tuple[float, float]
    bmi_in_range: bool


def estimate(model: dict, weight_kg: float, user: e01.UserCategories) -> AnsurEstimate:
    c = model[user.sex]
    delta = model["delta"][user.effective_group or "5"][user.sex]
    ln = c["a"] + c["b"] * math.log(weight_kg / user.height_cm) + c.get("c", 0.0) * user.age + delta
    value = math.exp(ln)
    se = c["log_se"]
    lo_b, hi_b = c["bmi_range"]
    bmi = e04.bmi(weight_kg, user.height_cm)
    return AnsurEstimate(weight_kg, value, (value * math.exp(-se), value * math.exp(se)), lo_b <= bmi <= hi_b)


def k0_messages(model: dict, user: e01.UserCategories, estimates, messages: dict) -> list[str]:
    """Μηνύματα Κ0 κοινά στα 13–15: ηλικία 59+, καταγωγή 4/5 (και μη δηλωμένη), ΔΜΣ στόχου εκτός εύρους."""
    out: list[str] = []
    if not estimates:
        return out
    if user.age > model["age_range"][1]:
        out.append(messages["age_59"])
    if (user.effective_group or "5") in model["no_data_ancestries"]:
        out.append(messages["ancestry_4_5"])
    if not all(e.bmi_in_range for e in estimates):
        out.append(messages["bmi_out_of_range"])
    return out
