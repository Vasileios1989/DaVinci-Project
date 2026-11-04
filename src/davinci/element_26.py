"""Στοιχείο 26 — Λόγος Μηρού-Γάμπας (ΛΜΓ).

Μηρός (Στοιχείο 18, 1 cm κάτω από τη γλουτιαία πτυχή) / γάμπα (Στοιχείο 20, όρθια). Χωρίς όριο και χωρίς στόχο·
θέση στα εκατοστημόρια ANSUR II. Αναμενόμενος λόγος: εκτίμηση 18 / εκτίμηση 20 (όχι τα κατώτατα όρια).
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Iterable

from davinci import element_01 as e01
from davinci import element_18 as e18
from davinci import element_20 as e20
from davinci.fmt import num
from davinci.ratios import PercentileResult, TargetRow, assess_percentile, fmt_ratio

DATA_FILE = Path(__file__).resolve().parents[2] / "data" / "element_26.json"


@lru_cache(maxsize=1)
def load_data() -> dict:
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


def target_rows(user: e01.UserCategories, target_weights: Iterable[float]) -> tuple[TargetRow, ...]:
    out = []
    for w in target_weights:
        t, c = e18.estimate(w, user).value_cm, e20.estimate(w, user).value_cm
        out.append(TargetRow(w, t, c, t / c))
    return tuple(out)


def fill_e(text: str, r: TargetRow) -> str:
    return (text.replace("μηρός Υ cm", f"μηρός {num(r.numerator_cm)} cm")
            .replace("γάμπα Ζ cm", f"γάμπα {num(r.denominator_cm)} cm")
            .replace("περίπου Λ.", f"περίπου {fmt_ratio(r.ratio)}."))


def assess(thigh_cm: float | None, calf_cm: float | None, user: e01.UserCategories,
           target_weights: Iterable[float] = (), *, edema: bool = False, injured: bool = False) -> PercentileResult:
    """thigh_cm: μόνο μηρός στο σημείο του Στοιχείου 18 (μέτρηση σε άλλο σημείο → None).

    edema: οίδημα στη γάμπα ή στον αστράγαλο → δεν υπολογίζεται. injured: τραυματισμός στο δεξί πόδι → μόνο καταγραφή.
    """
    d = load_data()
    m = d["messages"]
    exclusion = ("skip", m["edema"]) if edema else ("record", m["injury"]) if injured else None
    return assess_percentile(d, thigh_cm, calf_cm, user, target_rows(user, target_weights), fill_e, exclusion)
