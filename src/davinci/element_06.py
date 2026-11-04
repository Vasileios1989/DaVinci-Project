"""Στοιχείο 06 — Σπλαχνικό λίπος.

Ιεραρχία: τομογραφία (cm²) > εξίσωση Samouda (μεζούρα) > ζυγαριά (μόνο καταγραφή).
Η τιμή «επιπέδου» της ζυγαριάς δεν ταξινομείται και δεν μετατρέπεται ποτέ σε cm² ή λίτρα.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from davinci import element_01 as e01
from davinci import element_04 as e04
from davinci import element_46 as e46

DATA_FILE = Path(__file__).resolve().parents[2] / "data" / "element_06.json"
CT, EQUATION, SCALE, VOLUME = "τομογραφία", "εξίσωση Samouda", "ζυγαριά", "DXA ή μαγνητική (όγκος / μάζα)"


@lru_cache(maxsize=1)
def load_data() -> dict:
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


def samouda(waist_cm: float, upper_thigh_cm: float, age: int, sex: str, bmi: float) -> float:
    """Επιφάνεια σπλαχνικού λίπους (cm², Ο4–Ο5) — Samouda 2013, Πίνακας 3."""
    c = load_data()["samouda_2013"][sex]
    return (c["waist"] * waist_cm + c["upper_thigh"] * upper_thigh_cm + c["age"] * age
            + c["bmi"] * bmi + c["intercept"])


def waist_for_estimate(estimate_cm2: float, upper_thigh_cm: float, age: int) -> float:
    """Αντίστροφη εξίσωση ανδρών: μέση που δίνει την εκτίμηση (Πίνακας 9)."""
    c = load_data()["samouda_2013"]["Άνδρας"]
    return (estimate_cm2 - c["upper_thigh"] * upper_thigh_cm - c["age"] * age - c["intercept"]) / c["waist"]


def within_validity(waist_cm: float, upper_thigh_cm: float, age: int, sex: str, bmi: float) -> bool:
    v = load_data()["samouda_2013"]["validity"]
    checks = [(age, v["age"]), (bmi, v["bmi"]), (waist_cm, v["waist"][sex]), (upper_thigh_cm, v["upper_thigh"][sex])]
    return all(lo <= x <= hi for x, (lo, hi) in checks)


@dataclass(frozen=True)
class VisceralResult:
    source: str | None
    value: float | None  # cm² (τομογραφία / εξίσωση), όγκος/μάζα, ή επίπεδο ζυγαριάς
    label: str | None  # «Μέτρηση», «Εκτίμηση», «Τιμή ζυγαριάς»
    range_cm2: tuple[float, float] | None = None  # εκτίμηση ± SEE
    category: str | None = None
    scale_level: float | None = None  # καταγράφεται πάντα, χωρίς μονάδα (Κανόνας 2)
    indicative: bool = False
    messages: tuple[str, ...] = ()


def assess(user: e01.UserCategories, weight_kg: float, *, waist_cm: float | None = None,
           upper_thigh_cm: float | None = None, scale_level: float | None = None,
           ct_cm2: float | None = None, volume_value: float | None = None) -> VisceralResult:
    d = load_data()
    m, cats, thr = d["messages"], d["categories"], d["threshold_cm2"]
    if e01.is_minor(user.age):  # Κανόνας 7
        return VisceralResult(None, None, None, messages=(m["minor"],))
    if user.pregnant_or_breastfeeding:
        return VisceralResult(None, None, None)

    group = user.effective_group or "5"
    msgs: list[str] = []

    if ct_cm2 is not None:  # Κανόνας 1, προτεραιότητα 1
        e46.require_professional(user, "Αξονική ή μαγνητική τομογραφία")
        cat = cats["measured"][0] if ct_cm2 < thr else cats["measured"][1]
        indicative = group != "3b"
        if indicative:
            msgs.append(m["threshold"])
        return VisceralResult(CT, ct_cm2, d["source_labels"][CT], None, cat, scale_level, indicative, tuple(msgs))

    if waist_cm is not None and upper_thigh_cm is not None:  # προτεραιότητα 2
        bmi = e04.bmi(weight_kg, user.height_cm)
        est = samouda(waist_cm, upper_thigh_cm, user.age, user.sex, bmi)
        see = d["samouda_2013"][user.sex]["see"]
        lo, hi = est - see, est + see
        cat = cats["estimated"][0] if hi < thr else cats["estimated"][1] if lo >= thr else cats["estimated"][2]
        if not within_validity(waist_cm, upper_thigh_cm, user.age, user.sex, bmi):  # Κανόνας 4
            msgs.append(m["out_of_range"])
        if group != "1":
            msgs.append(m["ancestry_equation"])
        if group != "3b":
            msgs.append(m["threshold"])
        return VisceralResult(EQUATION, est, d["source_labels"][EQUATION], (lo, hi), cat, scale_level,
                              True, tuple(msgs))

    if waist_cm is not None and upper_thigh_cm is None:
        msgs.append(m["no_thigh"])

    if volume_value is not None:
        e46.require_professional(user, "DXA ή μαγνητική (όγκος / μάζα)")
        msgs.append(m["volume"])
        return VisceralResult(VOLUME, volume_value, d["source_labels"][VOLUME], scale_level=scale_level,
                              messages=tuple(msgs))

    if scale_level is not None:  # προτεραιότητα 3
        msgs.append(m["scale"])
        return VisceralResult(SCALE, scale_level, d["source_labels"][SCALE], scale_level=scale_level,
                              messages=tuple(msgs))

    return VisceralResult(None, None, None, messages=tuple(msgs))
