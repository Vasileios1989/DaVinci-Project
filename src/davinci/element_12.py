"""Στοιχείο 12 — Περιφέρεια λαιμού.

Χωρίς ταξινόμηση και στόχο. Ένας έλεγχος: όριο STOP-Bang (πληροφορία, όχι διάγνωση).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from davinci import element_01 as e01

DATA_FILE = Path(__file__).resolve().parents[2] / "data" / "element_12.json"


@lru_cache(maxsize=1)
def load_data() -> dict:
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


@dataclass(frozen=True)
class NeckResult:
    neck_cm: float
    stop_bang_flag: bool | None  # None = χωρίς έλεγχο (ανήλικοι / εγκυμοσύνη)
    out_of_reference_label: str | None = None
    indicative: bool = False
    messages: tuple[str, ...] = ()


def assess(neck_cm: float, user: e01.UserCategories, *, fat_status: str | None = None) -> NeckResult:
    """fat_status: κατάσταση λίπους ως προς το όριο προφίλ (Στοιχείο 02: «εντός», «πάνω», «κάτω»)."""
    if neck_cm <= 0:
        raise e01.InvalidInput("Η περιφέρεια λαιμού πρέπει να είναι θετική.")
    d = load_data()
    m = d["messages"]
    msgs = [m["A"]]
    if e01.is_minor(user.age) or user.pregnant_or_breastfeeding:
        return NeckResult(neck_cm, None, messages=tuple(msgs + [m["record_only"]]))

    flag = neck_cm >= d["stop_bang"][user.sex]
    indicative = False
    if flag:
        msgs.append(m["B"])
        if (user.effective_group or "5") in d["indicative_ancestries"]:
            msgs.append(m["ancestry_3b"])
            indicative = True
    if user.profile == "Bodybuilding" or (user.profile == "Αθλητικό" and fat_status == "εντός"):
        msgs.append(m["C"])
    return NeckResult(neck_cm, flag, e01.zone_for_age(user.age).label, indicative, tuple(msgs))
