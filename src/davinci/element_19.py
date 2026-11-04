"""Στοιχείο 19 — Περιφέρεια πάνω από το γόνατο (άνω χείλος επιγονατίδας).

Χωρίς όριο υγείας και χωρίς στόχο· εκτίμηση ANSUR II στο βάρος-στόχο και βάση για την αναλογία Μηρού-Γόνατος.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Iterable

from davinci import ansur
from davinci import element_01 as e01

DATA_FILE = Path(__file__).resolve().parents[2] / "data" / "element_19.json"


@lru_cache(maxsize=1)
def load_data() -> dict:
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


def estimate(weight_kg: float, user: e01.UserCategories) -> ansur.AnsurEstimate:
    return ansur.estimate(load_data()["ansur_ii_model"], weight_kg, user)


@dataclass(frozen=True)
class KneeResult:
    knee_cm: float | None
    estimates: tuple[ansur.AnsurEstimate, ...] = ()
    usable_for_ratio: bool = False  # Στοιχείο 29
    indicative: bool = False
    messages: tuple[str, ...] = ()


def assess(knee_cm: float | None, user: e01.UserCategories, target_weights: Iterable[float] = (), *,
           swollen_or_injured: bool = False) -> KneeResult:
    d = load_data()
    m = d["messages"]
    if knee_cm is not None and knee_cm <= 0:
        raise e01.InvalidInput("Η περιφέρεια πρέπει να είναι θετική.")
    msgs: list[str] = [] if knee_cm is not None else [m["no_value"]]
    if e01.is_minor(user.age) or user.pregnant_or_breastfeeding:
        return KneeResult(knee_cm, messages=tuple(msgs + [m["record_only"]]))
    if swollen_or_injured:
        return KneeResult(knee_cm, messages=tuple(msgs + [m["swollen"]]))
    ests = tuple(estimate(w, user) for w in target_weights)
    msgs.insert(0, m["A"])
    k0 = ansur.k0_messages(d["ansur_ii_model"], user, ests, m)
    return KneeResult(knee_cm, ests, knee_cm is not None, bool(k0), tuple(msgs + k0))
