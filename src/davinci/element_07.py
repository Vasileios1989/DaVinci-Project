"""Στοιχείο 07 — Σκελετικοί μύες (με Συμπληρώματα Α: ξηροί μύες, Β: στόχος Φάσης 2).

Η τιμή της ζυγαριάς δεν ταξινομείται ποτέ (Κανόνας 2). Ταξινόμηση μόνο 60+ και μόνο
με εξίσωση Lee ή ιατρική μέτρηση (Κανόνας 3). Ποτέ «σαρκοπενία» (Κανόνας 6).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from davinci import element_01 as e01
from davinci import element_03 as e03
from davinci import element_04 as e04
from davinci import element_46 as e46

DATA_FILE = Path(__file__).resolve().parents[2] / "data" / "element_07.json"
SCALE, LEE, MEDICAL = "ζυγαριά", "εξίσωση Lee", "ιατρική μέτρηση"


@lru_cache(maxsize=1)
def load_data() -> dict:
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


def lee_muscle(weight_kg: float, user: e01.UserCategories) -> float | None:
    """Lee 2000, μοντέλο 2. None αν ΔΜΣ ≥ 30 (η εξίσωση δεν ισχύει)."""
    c = load_data()["lee_2000_model_2"]
    if e04.bmi(weight_kg, user.height_cm) >= c["max_bmi_exclusive"]:
        return None
    group = user.effective_group or "5"
    return (c["weight"] * weight_kg + c["height_m"] * user.height_cm / 100
            + c["sex_male"] * (1 if user.sex == "Άνδρας" else 0)
            + c["age"] * user.age + c["ancestry"][group] + c["intercept"])


def smi_category(smi: float, sex: str) -> str:
    t = load_data()["smi_classification"]
    normal, low, very_low = t["labels"]
    if smi > t[sex]["normal_gt"]:
        return normal
    if smi > t[sex]["low_gt"]:
        return low
    return very_low


@dataclass(frozen=True)
class MuscleResult:
    source: str | None
    muscle_kg: float | None
    pct_of_ffm: float | None = None
    pct_of_weight: float | None = None  # μόνο πληροφορία (Κανόνας 1)
    smi: float | None = None
    category: str | None = None
    out_of_reference_label: str | None = None
    dry_muscle_kg: float | None = None
    dry_muscle_range_kg: tuple[float, float] | None = None
    indicative: bool = False
    messages: tuple[str, ...] = ()


def assess(weight_kg: float, fat_percent: float, user: e01.UserCategories, *,
           scale_percent: float | None = None, medical_kg: float | None = None) -> MuscleResult:
    """Πηγή κατά σειρά: ιατρική μέτρηση > ζυγαριά > εξίσωση Lee (μόνο χωρίς τιμή ζυγαριάς)."""
    d = load_data()
    m, dm = d["messages"], d["dry_muscle"]["messages"]
    age = user.age
    msgs: list[str] = []
    indicative = False

    if medical_kg is not None:
        e46.require_professional(user, "Ιατρική μέτρηση μυών")
        source, kg = MEDICAL, medical_kg
    elif scale_percent is not None:
        source, kg = SCALE, e03.scale_kg(weight_kg, scale_percent)  # Κανόνας Β-7
        msgs.append(m["scale"])
    else:
        source, kg = LEE, lee_muscle(weight_kg, user)
        if kg is None:
            return MuscleResult(LEE, None, messages=(m["lee_bmi_30"], dm["no_muscle"]))
        if (user.effective_group or "5") in d["lee_2000_model_2"]["ancestry_without_coefficient"]:
            msgs.append(m["ancestry_lee"])
            indicative = True

    ffm = e03.ffm(weight_kg, fat_percent)
    h = user.height_cm / 100
    smi = kg / (h * h)
    category = out_label = None
    minor = e01.is_minor(age)

    if minor:
        msgs.append(m["minor"])
    elif not user.pregnant_or_breastfeeding:
        cls = d["smi_classification"]
        if age < cls["min_age"]:
            msgs.append(m["age_18_59"])
        elif source in cls["sources_allowed"]:
            category = smi_category(smi, user.sex)
            if user.effective_group != "1":
                msgs.append(m["ancestry_classification"])
                indicative = True
            label = e01.zone_for_age(age).label
            if label:
                out_label = label
                msgs.append(m["age_80"])
                indicative = True

    dry = dry_range = None
    if user.pregnant_or_breastfeeding and not minor:
        pass  # Συμπλήρωμα Α «Ανήλικοι / εγκυμοσύνη: καμία τιμή / μόνο καταγραφή»· 03 Γ-7· θηλασμός όπως 01. Χωρίς κείμενο στο έγγραφο.
    elif not minor:  # Συμπλήρωμα Α
        f = d["dry_muscle"]
        dry = f["factor"] * kg
        dry_range = (f["range"][0] * kg, f["range"][1] * kg)
        msgs.append(dm["info"])
        if user.effective_group != "1":
            msgs.append(dm["ancestry"])
        if e01.zone_for_age(age).label:
            msgs.append(dm["age_80"])
    else:
        msgs.append(dm["minor"])

    return MuscleResult(source, kg, kg / ffm * 100, kg / weight_kg * 100, smi, category, out_label,
                        dry, dry_range, indicative, tuple(dict.fromkeys(msgs)))


@dataclass(frozen=True)
class MuscleTarget:
    muscle_kg: float
    dry_muscle_kg: float
    messages: tuple[str, ...]


def target(muscle_kg: float, ffm_today_kg: float, ffm_target_kg: float, *, phase2: bool = False) -> MuscleTarget:
    """Κανόνας 5: (μύες / άλιπη σήμερα) × άλιπη-στόχος· πάντα «Ενδεικτικός»."""
    d = load_data()
    t = muscle_kg / ffm_today_kg * ffm_target_kg
    msgs = [d["messages"]["target"]]
    if phase2:
        msgs.append(d["messages"]["target_phase2"])
    msgs.append(d["dry_muscle"]["messages"]["target_note"])
    return MuscleTarget(t, d["dry_muscle"]["factor"] * t, tuple(msgs))
