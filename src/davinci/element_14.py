"""Στοιχείο 14 — Περιφέρεια ώμων.

Χωρίς ταξινόμηση. Εκτίμηση στο βάρος-στόχο με τον τύπο ANSUR II του εγγράφου.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Iterable

from davinci import ansur
from davinci import element_01 as e01

DATA_FILE = Path(__file__).resolve().parents[2] / "data" / "element_14.json"


@lru_cache(maxsize=1)
def load_data() -> dict:
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


def estimate(weight_kg: float, user: e01.UserCategories) -> ansur.AnsurEstimate:
    return ansur.estimate(load_data()["ansur_ii_model"], weight_kg, user)


@dataclass(frozen=True)
class ShouldersResult:
    shoulders_cm: float | None
    estimates: tuple[ansur.AnsurEstimate, ...] = ()
    indicative: bool = False
    messages: tuple[str, ...] = ()


def assess(user: e01.UserCategories, shoulders_cm: float | None,
           target_weights: Iterable[float] = ()) -> ShouldersResult:
    d = load_data()
    m = d["messages"]
    if shoulders_cm is not None and shoulders_cm <= 0:
        raise e01.InvalidInput("Η περιφέρεια ώμων πρέπει να είναι θετική.")
    msgs: list[str] = [] if shoulders_cm is not None else [m["no_value"]]
    if e01.is_minor(user.age) or user.pregnant_or_breastfeeding:
        return ShouldersResult(shoulders_cm, messages=tuple(msgs + [m["record_only"]]))
    ests = tuple(estimate(w, user) for w in target_weights)
    msgs.insert(0, m["A"])
    if user.profile in ("Αθλητικό", "Bodybuilding"):
        msgs.append(m["B"])
    k0 = ansur.k0_messages(d["ansur_ii_model"], user, ests, m)
    return ShouldersResult(shoulders_cm, ests, bool(k0), tuple(msgs + k0))
