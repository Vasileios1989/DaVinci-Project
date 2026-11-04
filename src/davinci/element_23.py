"""Στοιχείο 23 — Λόγος Στήθους-Μέσης (ΛΣΜ).

Χωρίς όριο υγείας και χωρίς στόχο. Θέση στα εκατοστημόρια ANSUR II και ελάχιστος λόγος στο βάρος-στόχο:
Λ = αναμενόμενο στήθος (Στοιχείο 13) / μέση-στόχος 0,50 × ύψος (Στοιχείο 05). Ο τύπος ελέγχου του εγγράφου
χρησιμοποιείται μόνο στα τεστ.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Iterable

from davinci import element_01 as e01
from davinci import element_05 as e05
from davinci import element_13 as e13
from davinci.fmt import num
from davinci.ratios import PercentileResult, TargetRow, assess_percentile, fmt_ratio

DATA_FILE = Path(__file__).resolve().parents[2] / "data" / "element_23.json"


@lru_cache(maxsize=1)
def load_data() -> dict:
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


def target_rows(user: e01.UserCategories, target_weights: Iterable[float]) -> tuple[TargetRow, ...]:
    k = e05.load_data()["target_ratio"] * user.height_cm
    return tuple(TargetRow(w, c, k, c / k) for w in target_weights for c in [e13.estimate(w, user).value_cm])


def fill_e(text: str, r: TargetRow) -> str:
    return (text.replace("(Υ cm)", f"({num(r.numerator_cm)} cm)")
            .replace("(Κ cm)", f"({num(r.denominator_cm)} cm)")
            .replace("τουλάχιστον Λ.", f"τουλάχιστον {fmt_ratio(r.ratio)}."))


def assess(chest_cm: float | None, waist_cm: float | None, user: e01.UserCategories,
           target_weights: Iterable[float] = ()) -> PercentileResult:
    """target_weights: βάρη-στόχοι της Φάσης 1 (Στοιχείο 03)· το πρώτο είναι του προφίλ του χρήστη."""
    return assess_percentile(load_data(), chest_cm, waist_cm, user, target_rows(user, target_weights), fill_e)
