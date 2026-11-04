"""Στοιχείο 39 — Εκτομορφία (Heath-Carter, Carter 2002).

HWR = ύψος (cm) / ∛βάρος (kg) · HWR ≥ 40,75: 0,732·HWR − 28,58 · 38,25 < HWR < 40,75: 0,463·HWR − 17,63 ·
HWR ≤ 38,25 (ή τιμή < 0,1): 0,1. Μόνο ύψος και βάρος: δεν χρειάζεται δαγκάνα, άρα και στο Normal.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from davinci import element_01 as e01
from davinci import somatotype as st
from davinci.fmt import num

DATA_FILE = Path(__file__).resolve().parents[2] / "data" / "element_39.json"


@lru_cache(maxsize=1)
def load_data() -> dict:
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


def hwr(height_cm: float, weight_kg: float) -> float:
    return height_cm / weight_kg ** (1 / 3)


def exact_value(h: float) -> float | None:
    """None όταν HWR ≤ 38,25 (κατώτατο όριο)."""
    f = load_data()["formula"]
    if h <= f["floor_hwr_le"]:
        return None
    eq = f["upper"] if h >= f["upper"]["from"] else f["middle"]
    return eq["a"] * h + eq["b"]


@dataclass(frozen=True)
class EctomorphyResult:
    value: float | None
    hwr: float | None = None
    exact: float | None = None
    floor: bool = False
    scale: str | None = None
    comparison: st.Comparison | None = None
    indicative: bool = False
    messages: tuple[str, ...] = ()


def compute(weight_kg: float | None, user: e01.UserCategories, *, edema: bool = False,
            amputation: bool = False) -> EctomorphyResult:
    d = load_data()
    m = d["messages"]
    missing = [d["missing_names"][k] for k, v in (("height", user.height_cm), ("weight", weight_kg)) if v is None]
    if missing:
        return EctomorphyResult(None, messages=(m["missing"].replace("[τιμή]", ", ".join(missing)),))
    if weight_kg <= 0:
        raise e01.InvalidInput("Το βάρος πρέπει να είναι θετικό.")
    h = hwr(user.height_cm, weight_kg)
    exact = exact_value(h)
    value = st.rounded(exact, d["formula"]["floor_value"]) if exact is not None else d["formula"]["floor_value"]
    floor = exact is None or exact < d["formula"]["floor_value"]
    msgs = [m["value"].replace("[E]", num(value))]
    if user.pregnant:
        return EctomorphyResult(value, h, exact, floor, None, None, True, tuple(msgs + [m["pregnancy"]]))
    sc = st.scale(value)
    msgs += [m["scale"].replace("[χαμηλή/μέτρια/υψηλή/πολύ υψηλή]", sc), m["height"]]
    if value == d["formula"]["floor_value"]:
        msgs.append(m["floor"])
    conditions = [w for k, w in d["condition_words"].items() if {"edema": edema, "amputation": amputation}[k]]
    for w in conditions:
        msgs.append(m["condition"].replace("[το οίδημα/ο ακρωτηριασμός]", w))
    indicative = bool(conditions)
    if e01.is_minor(user.age):
        return EctomorphyResult(value, h, exact, floor, sc, None, True, tuple(msgs + [m["child"]]))
    cmp = st.find_comparison(d["comparisons"], user.sex, user.age)
    if cmp is None:
        msgs.append(m["no_comparison"])
    else:
        indicative = True
        msgs.append(cmp.fill(m["comparison"], value, user.sex))
        src = next(c for c in d["comparisons"] if c["source"] == cmp.source)
        if src.get("height_not_reported"):
            msgs.append(m["comparison_bulgaria"])
        if (user.effective_group or "5") not in d["reference_ancestries"]:
            msgs.append(m["ancestry"])
    msgs += st.athlete_messages(m["athletes"], d["athletes"], user.sex)
    return EctomorphyResult(value, h, exact, floor, sc, cmp, indicative, tuple(msgs))
