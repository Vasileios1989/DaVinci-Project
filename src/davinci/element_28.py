"""Στοιχείο 28 — Λόγος Αστραγάλου-Γάμπας (ΛΑΓ).

Αστράγαλος (Στοιχείο 21, όρθια) / γάμπα (Στοιχείο 20, όρθια). Χωρίς όριο και χωρίς στόχο· θέση στα εκατοστημόρια
ANSUR II, μήνυμα Υ πάνω από τη μέγιστη τιμή του ANSUR. Αναμενόμενος λόγος: εκτίμηση 21 / εκτίμηση 20.

Κανόνας Κ6: το μήνυμα Β του Στοιχείου 20 αντικαθίσταται από το μήνυμα Δ (βλ. element_20).
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Iterable

from davinci import element_01 as e01
from davinci import element_20 as e20
from davinci import element_21 as e21
from davinci.fmt import num
from davinci.ratios import PercentileResult, TargetRow, assess_percentile, fmt_ratio

DATA_FILE = Path(__file__).resolve().parents[2] / "data" / "element_28.json"


@lru_cache(maxsize=1)
def load_data() -> dict:
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


def target_rows(user: e01.UserCategories, target_weights: Iterable[float]) -> tuple[TargetRow, ...]:
    out = []
    for w in target_weights:
        a, c = e21.estimate(w, user).value_cm, e20.estimate(w, user).value_cm
        out.append(TargetRow(w, a, c, a / c))
    return tuple(out)


def fill_e(text: str, r: TargetRow) -> str:
    return (text.replace("γάμπα Υ cm", f"γάμπα {num(r.denominator_cm)} cm")
            .replace("αστράγαλος Κ cm", f"αστράγαλος {num(r.numerator_cm)} cm")
            .replace("περίπου Λ.", f"περίπου {fmt_ratio(r.ratio)}."))


def assess(ankle_cm: float | None, calf_cm: float | None, user: e01.UserCategories,
           target_weights: Iterable[float] = (), *, lipedema: bool = False, edema_or_injury: bool = False) -> PercentileResult:
    """ankle_cm: μόνο όρθια μέτρηση (καθιστή → None).

    lipedema: δηλωμένη διάγνωση → μόνο καταγραφή. edema_or_injury: οίδημα ή τραυματισμός στο δεξί πόδι → δεν υπολογίζεται.
    Σύμβαση συστήματος: όταν ισχύουν και τα δύο, προηγείται το οίδημα/τραυματισμός (ο λόγος δεν υπολογίζεται).
    """
    d = load_data()
    m = d["messages"]
    exclusion = ("skip", m["edema"]) if edema_or_injury else ("record", m["lipedema"]) if lipedema else None
    return assess_percentile(d, ankle_cm, calf_cm, user, target_rows(user, target_weights), fill_e, exclusion)
