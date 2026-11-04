"""Στοιχείο 33 — Δερματοπτυχή τρικεφάλου (μόνο Professional).

Μέτρηση εισόδου σε mm, όχι στόχος. Εκατοστημόριο NHANES 2007–2010 (περιγραφή) και τιμές αθλητών για σύγκριση.
Η τιμή περνά στην Ενδομορφία, στο Στοιχείο 15 (διορθωμένη περιφέρεια μπράτσου) και στο Στοιχείο 02.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from davinci import element_01 as e01
from davinci import skinfolds

DATA_FILE = Path(__file__).resolve().parents[2] / "data" / "element_33.json"


@lru_cache(maxsize=1)
def load_data() -> dict:
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


def assess(measurements: list[float] | None, user: e01.UserCategories, **kw) -> skinfolds.SkinfoldResult:
    """Βλ. skinfolds.assess (isak, caliper, left_side, confirmed, edema, postpartum_recent)."""
    return skinfolds.assess("33", load_data(), measurements, user, **kw)


def info() -> dict:
    """Κουμπί ⓘ: πρωτόκολλο ISAK· τίτλος, βήματα, ✕ (χωρίς βίντεο, απόφαση του χρήστη)."""
    return load_data()["measurement"]
