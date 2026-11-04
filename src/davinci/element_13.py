"""Στοιχείο 13 — Περιφέρεια στήθους.

Χωρίς ταξινόμηση. Εκτίμηση στο βάρος-στόχο με τον τύπο ANSUR II του εγγράφου: πληροφορία, όχι στόχος.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Iterable

from davinci import ansur
from davinci import element_01 as e01

DATA_FILE = Path(__file__).resolve().parents[2] / "data" / "element_13.json"
ChestEstimate = ansur.AnsurEstimate


@lru_cache(maxsize=1)
def load_data() -> dict:
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


def estimate(weight_kg: float, user: e01.UserCategories) -> ansur.AnsurEstimate:
    return ansur.estimate(load_data()["ansur_ii_model"], weight_kg, user)


@dataclass(frozen=True)
class ChestResult:
    chest_cm: float | None
    estimates: tuple[ansur.AnsurEstimate, ...] = ()
    indicative: bool = False
    messages: tuple[str, ...] = ()


def assess(user: e01.UserCategories, chest_cm: float | None,
           target_weights: Iterable[float] = ()) -> ChestResult:
    """target_weights: βάρη-στόχοι της Φάσης 1 (Στοιχείο 03)."""
    d = load_data()
    m = d["messages"]
    if chest_cm is not None and chest_cm <= 0:
        raise e01.InvalidInput("Η περιφέρεια στήθους πρέπει να είναι θετική.")
    msgs: list[str] = []
    if chest_cm is None:
        msgs.append(m["no_chest"])
    if e01.is_minor(user.age) or user.pregnant_or_breastfeeding:
        return ChestResult(chest_cm, messages=tuple(msgs + [m["record_only"]]))

    ests = tuple(estimate(w, user) for w in target_weights)
    msgs.insert(0, m["A"])
    if user.profile in ("Αθλητικό", "Bodybuilding"):
        msgs.append(m["B"])
    k0 = ansur.k0_messages(d["ansur_ii_model"], user, ests, m)
    return ChestResult(chest_cm, ests, bool(k0), tuple(msgs + k0))


def info_messages(user: e01.UserCategories) -> tuple[str, ...]:
    """Κουμπί ⓘ: βήματα μέτρησης και, για γυναίκες, το μήνυμα του Πίνακα 11."""
    d = load_data()
    extra = (d["messages"]["women_info"],) if user.sex == "Γυναίκα" else ()
    return tuple(d["measurement"]["steps"]) + extra
