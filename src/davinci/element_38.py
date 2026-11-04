"""Στοιχείο 38 — Μεσομορφία (Heath-Carter, Carter 2002), μόνο Professional.

Μ = 0,858·αγκώνας + 0,601·γόνατο + 0,188·(σφιγμένος δικέφαλος − τρικέφαλος/10) + 0,161·(γάμπα − πτυχή γάμπας/10)
    − 0,131·ύψος + 4,5 (cm) · ένα δεκαδικό · ≤ 0 → 0,1
Υπολογισμός, όχι στόχος· δεν είναι δείκτης μυϊκής μάζας. Τα εύρη μπαίνουν μόνο στον τύπο (όχι η κατηγορία σκελετού).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from davinci import element_01 as e01
from davinci import element_46 as e46
from davinci import skinfolds
from davinci import somatotype as st
from davinci.fmt import num

DATA_FILE = Path(__file__).resolve().parents[2] / "data" / "element_38.json"


@lru_cache(maxsize=1)
def load_data() -> dict:
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


@dataclass(frozen=True)
class MesomorphyResult:
    value: float | None
    exact: float | None = None
    corrected_arm_cm: float | None = None
    corrected_calf_cm: float | None = None
    scale: str | None = None
    comparison: st.Comparison | None = None
    indicative: bool = False
    reasons: tuple[str, ...] = ()
    messages: tuple[str, ...] = ()


def exact_value(elbow_cm, knee_cm, corrected_arm_cm, corrected_calf_cm, height_cm) -> float:
    f = load_data()["formula"]
    return (f["elbow"] * elbow_cm + f["knee"] * knee_cm + f["arm"] * corrected_arm_cm + f["calf"] * corrected_calf_cm
            + f["height"] * height_cm + f["constant"])


def _sf(v):
    if isinstance(v, skinfolds.SkinfoldResult):
        return v.value_mm, v.measurement_reasons
    return v, ()


def compute(elbow_cm, knee_breadth_cm, biceps_flexed_cm, calf_cm, triceps, calf_skinfold,
            user: e01.UserCategories, *, endomorphy: float | None = None, no_caliper: bool = False,
            extra_reasons: tuple[str, ...] = ()) -> MesomorphyResult:
    """triceps / calf_skinfold: mm ή αποτελέσματα των Στοιχείων 33 / 36. endomorphy: για το μήνυμα λίπους (≥ 5,5).
    extra_reasons: λόγοι «Ενδεικτική» από τις μετρήσεις περιφερειών ή ευρών (π.χ. αριστερό χέρι)."""
    d = load_data()
    m = d["messages"]
    if not e46.element_available("38", user.level):
        return MesomorphyResult(None, messages=(e46.normal_message("38"),))
    if no_caliper:
        return MesomorphyResult(None, messages=(m["no_caliper"],))
    (tri, rt), (csf, rc) = _sf(triceps), _sf(calf_skinfold)
    names = d["missing_names"]
    vals = {"elbow": elbow_cm, "knee": knee_breadth_cm, "biceps": biceps_flexed_cm, "calf": calf_cm,
            "triceps": tri, "calf_skinfold": csf, "height": user.height_cm}
    missing = [names[k] for k, v in vals.items() if v is None]
    if missing:
        return MesomorphyResult(None, messages=(m["missing"].replace("[μέτρηση]", ", ".join(missing)),))

    arm = biceps_flexed_cm - tri / 10
    calf = calf_cm - csf / 10
    exact = exact_value(elbow_cm, knee_breadth_cm, arm, calf, user.height_cm)
    value = st.rounded(exact, d["min_value"])
    reasons = tuple(dict.fromkeys(rt + rc + tuple(extra_reasons)))
    v_txt = num(value)
    msgs = [m["value"].replace("[M]", v_txt)]
    if user.pregnant:
        return MesomorphyResult(value, exact, arm, calf, None, None, True, reasons, tuple(msgs + [m["pregnancy"]]))
    sc = st.scale(value)
    msgs.append(m["scale"].replace("[χαμηλή/μέτρια/υψηλή/πολύ υψηλή]", sc))
    if value < d["check_below"]:
        msgs.append(m["below_1"].replace("[M]", v_txt))
    if reasons:
        msgs.append(m["indicative"].replace("[λόγος από τη μέτρηση]", " · ".join(reasons)))
    if endomorphy is not None and endomorphy >= d["high_endomorphy_from"]:
        msgs.append(m["high_endomorphy"])
    if e01.is_minor(user.age):
        return MesomorphyResult(value, exact, arm, calf, sc, None, True, reasons, tuple(msgs + [m["child"]]))
    cmp = st.find_comparison(d["comparisons"], user.sex, user.age)
    if cmp is None:
        msgs.append(m["no_comparison"])
    else:
        msgs.append(cmp.fill(m["comparison"], value, user.sex))
        if (user.effective_group or "5") not in d["reference_ancestries"]:
            msgs.append(m["ancestry"])
    msgs += st.athlete_messages(m["athletes"], d["athletes"], user.sex)
    return MesomorphyResult(value, exact, arm, calf, sc, cmp, bool(reasons) or cmp is not None, reasons, tuple(msgs))
