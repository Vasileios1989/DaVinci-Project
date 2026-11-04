"""Στοιχείο 36 — Δερματοπτυχή γάμπας, έσω πλευρά (μόνο Professional).

Κύρια χρήση: διορθωμένη περιφέρεια γάμπας = περιφέρεια (cm, Στοιχείο 20) − δερματοπτυχή (mm) / 10, για τη Μεσομορφία.
Δεν μπαίνει στην Ενδομορφία. Ενδείξεις: εκατοστημόριο CHMS (μόνο ΔΜΣ < 30) και μέσος ± ΤΑ Campa (18–79).
"""

from __future__ import annotations

import json
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

from davinci import element_01 as e01
from davinci import element_04 as e04
from davinci import skinfolds
from davinci.fmt import num

DATA_FILE = Path(__file__).resolve().parents[2] / "data" / "element_36.json"


@lru_cache(maxsize=1)
def load_data() -> dict:
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


def before_message() -> str:
    return load_data()["messages"]["before"]


def chms_row(age: int) -> str | None:
    for label, (lo, hi) in load_data()["chms_rows"].items():
        if lo <= age <= hi:
            return label
    return None  # 5 ετών


def corrected_calf(calf_cm: float, skinfold_mm: float) -> float:
    return float(Decimal(repr(calf_cm)) - Decimal(repr(skinfold_mm)) / 10)


def assess(measurements: list[float] | None, user: e01.UserCategories, weight_kg: float, *,
           calf_cm: float | None = None, at_max_girth: bool = True, isak: bool | None = True,
           caliper: str = "Harpenden / Holtain", left_varicose: bool = False, left_side: bool = False,
           edema_or_cellulite: bool = False, confirmed: bool = False) -> skinfolds.SkinfoldResult:
    """calf_cm: περιφέρεια γάμπας (Στοιχείο 20)· at_max_girth: η πτυχή μετρήθηκε στο ύψος της μέγιστης περιφέρειας.
    left_varicose: κιρσοί δεξιά → μέτρηση αριστερά (μήνυμα κιρσών)· left_side: αριστερά για άλλο λόγο."""
    d = load_data()
    m, rs = d["messages"], d["reasons"]
    early, value = skinfolds.prepare("36", d, measurements, user, caliper=caliper, confirmed=confirmed)
    if early is not None:
        return early
    left = left_side or left_varicose
    mreasons = skinfolds.measurement_reasons(d, isak, caliper, left, edema_or_cellulite)

    corrected = corrected_calf(calf_cm, value) if calf_cm is not None else None
    corr_ind = corrected is not None and not at_max_girth
    corr_msgs = ([m["corrected"].replace("[C]", num(calf_cm)).replace("[X]", num(value))
                  .replace("[CCG]", num(corrected, 2))] if corrected is not None else [])
    if user.pregnant:
        return skinfolds.SkinfoldResult(value, indicative=True, messages=tuple([m["pregnancy"]] + corr_msgs),
                                        measurement_reasons=mreasons, corrected_calf_cm=corrected,
                                        corrected_indicative=corr_ind)
    age = user.age
    row = chms_row(age)
    tables = skinfolds.load_tables(d)["tables"]
    msgs: list[str] = []
    pos = None
    reasons = [rs["chms_protocol"]]
    bmi_ok = e04.bmi(weight_kg, user.height_cm) < d["chms_bmi_below"]
    if row is not None and bmi_ok:
        pos = skinfolds.position(value, tables["chms"][user.sex][row]["p"])
        msgs.append(m["normal"].replace("[X]", num(value)).replace(
            "περίπου στο [P]ο" if pos.percentile is None else "[P]ο", pos.label))
        if e01.is_minor(age):
            reasons.append(rs["broad_age"])
        elif age < 20:
            reasons.append(rs["age_18_19"])
    elif row is not None and not bmi_ok:
        msgs.append(m["bmi_30"])

    cmp = None
    lo, hi = d["campa_age_range"]
    if lo <= age <= hi:
        cmp = skinfolds.campa_comparison(value, tables["campa"][user.sex], age)
        msgs.append(cmp.fill(m["second"], user.sex))
        if age >= d["campa_indicative_from"]:
            reasons.append(rs["campa_over_65"])
    if msgs:
        msgs.append(m["indicative"].replace("[λόγος]", " · ".join(reasons + list(mreasons))))
    if e01.is_minor(age) and pos is not None:
        msgs.append(m["child"])
    if age >= 80 and pos is not None:
        msgs.append(m["over_80"])
    if edema_or_cellulite:
        msgs.append(m["edema"])
    if left_varicose:
        msgs.append(m["varicose"])
    if msgs and (user.effective_group or "5") not in d["reference_ancestries"]:
        msgs.append(m["ancestry"])
    msgs += corr_msgs
    athletes = d["athletes"] if age >= 18 else None
    return skinfolds.SkinfoldResult(value, pos, None, row, bool(msgs) or bool(mreasons), False, False, False, athletes,
                                    tuple(msgs), mreasons, cmp, corrected, corr_ind)


def info() -> dict:
    return load_data()["measurement"]
