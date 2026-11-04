"""Στοιχείο 35 — Δερματοπτυχή υπερακάνθιου (μόνο Professional).

Μέτρηση εισόδου σε mm, όχι στόχος. Χωρίς εκατοστημόριο (λοξή κατανομή): σύγκριση με μέσο όρο ± ΤΑ ανά φύλο
και πενταετία (Campa 2025, Ιταλία, 18–65), πάντα «Ενδεικτική». Η τιμή περνά στην Ενδομορφία και στο Στοιχείο 02.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from davinci import element_01 as e01
from davinci import skinfolds
from davinci.fmt import num

DATA_FILE = Path(__file__).resolve().parents[2] / "data" / "element_35.json"


@lru_cache(maxsize=1)
def load_data() -> dict:
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


def before_message() -> str:
    """Μήνυμα πριν τη μέτρηση (σημείο)."""
    return load_data()["messages"]["before"]


def assess(measurements: list[float] | None, user: e01.UserCategories, *, site_confirmed: bool | None = True,
           isak: bool | None = True, caliper: str = "Harpenden / Holtain", left_side: bool = False,
           confirmed: bool = False, edema: bool = False) -> skinfolds.SkinfoldResult:
    """site_confirmed: ο χρήστης επιβεβαίωσε ότι μέτρησε την υπερακάνθια (True) ή «δεν ξέρω» (None).
    Η λαγόνια ακρολοφία δεν δίνεται εδώ· στην Ενδομορφία απορρίπτεται (Στοιχείο 37)."""
    d = load_data()
    m = d["messages"]
    early, value = skinfolds.prepare("35", d, measurements, user, caliper=caliper, confirmed=confirmed)
    if early is not None:
        return early
    extra = () if site_confirmed else (d["reasons"]["site_unknown"],)
    mreasons = skinfolds.measurement_reasons(d, isak, caliper, left_side, edema, extra)
    if user.pregnant:
        return skinfolds.SkinfoldResult(value, indicative=True, messages=(m["pregnancy"],), measurement_reasons=mreasons)
    if e01.is_minor(user.age):
        return skinfolds.SkinfoldResult(value, indicative=True, messages=(m["child"],), measurement_reasons=mreasons)

    rows = skinfolds.load_tables(d)["tables"]["campa"][user.sex]
    cmp = skinfolds.campa_comparison(value, rows, user.age)
    msgs = [cmp.fill(m["normal"].replace("[X]", num(value)), user.sex)]
    msgs.append(m["indicative"].replace("[λόγος]", " · ".join((d["reasons"]["sample"],) + mreasons)))
    if user.age > d["max_reference_age"]:
        msgs.append(m["over_65"])
    if (user.effective_group or "5") not in d["reference_ancestries"]:
        msgs.append(m["ancestry"])
    if user.age >= d["age_60_message_from"]:
        msgs.append(m["age_60"])
    return skinfolds.SkinfoldResult(value, table_row=cmp.group, indicative=True, athletes=d["athletes"],
                                    messages=tuple(msgs), measurement_reasons=mreasons, comparison=cmp)


def info() -> dict:
    return load_data()["measurement"]
