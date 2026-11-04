"""Στοιχείο 21 — Περιφέρεια αστραγάλου.

Χωρίς όριο υγείας και στόχο· δεν κατατάσσει τον σκελετό. Εκτίμηση ANSUR II και βάση για την αναλογία Αστραγάλου-Γάμπας.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Iterable

from davinci import ansur
from davinci import element_01 as e01

DATA_FILE = Path(__file__).resolve().parents[2] / "data" / "element_21.json"


@lru_cache(maxsize=1)
def load_data() -> dict:
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


def estimate(weight_kg: float, user: e01.UserCategories) -> ansur.AnsurEstimate:
    return ansur.estimate(load_data()["ansur_ii_model"], weight_kg, user)


@dataclass(frozen=True)
class AnkleResult:
    ankle_cm: float | None
    today: ansur.AnsurEstimate | None = None
    estimates: tuple[ansur.AnsurEstimate, ...] = ()
    usable_for_ratio: bool = False  # Στοιχείο 28
    indicative: bool = False
    messages: tuple[str, ...] = ()


def assess(ankle_cm: float | None, weight_kg: float, user: e01.UserCategories,
           target_weights: Iterable[float] = (), *, edema: bool = False, injured: bool = False) -> AnkleResult:
    d = load_data()
    m, mdl = d["messages"], d["ansur_ii_model"]
    if ankle_cm is not None and ankle_cm <= 0:
        raise e01.InvalidInput("Η περιφέρεια αστραγάλου πρέπει να είναι θετική.")
    head = [m["no_value"]] if ankle_cm is None else []
    if e01.is_minor(user.age) or user.pregnant_or_breastfeeding:
        return AnkleResult(ankle_cm, messages=tuple(head + [m["record_only"]]))
    if edema or injured:
        extra = ([m["edema"]] if edema else []) + ([m["injury"]] if injured else [])
        return AnkleResult(ankle_cm, messages=tuple(head + [m["T"]] + extra))

    today = estimate(weight_kg, user)
    ests = tuple(estimate(w, user) for w in target_weights)
    msgs = [m["A"], m["T"]] + head
    k0 = ansur.k0_messages(mdl, user, (today,) + ests, m)  # ΔΜΣ σημερινός ή στόχου (Πίνακας 9)
    return AnkleResult(ankle_cm, today, ests, ankle_cm is not None, bool(k0), tuple(msgs + k0))
