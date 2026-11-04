"""Οδηγίες μέτρησης για κάθε πεδίο της φόρμας (κουμπί ⓘ: τίτλος, βήματα, ✕).

Χωρίς βίντεο (απόφαση του χρήστη, 4/11/2026). Τα βήματα έρχονται αυτολεξεί από το στοιχείο κάθε μέτρησης·
για ύψος, ζυγαριά και άνω μηρό από το `data/measurement_guides.json`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

DATA = Path(__file__).resolve().parents[2] / "data"

# πεδίο της φόρμας (Στοιχείο 46) → (αρχείο, διαδρομή μέσα στο αρχείο)
FIELD_SOURCES: dict[str, tuple[str, tuple[str, ...]]] = {
    "ύψος": ("measurement_guides.json", ("guides", "height")),
    "βάρος": ("measurement_guides.json", ("guides", "scale")),
    "λίπος % (ζυγαριά)": ("measurement_guides.json", ("guides", "scale")),
    "μύες % (ζυγαριά)": ("measurement_guides.json", ("guides", "scale")),
    "υγρά % (ζυγαριά)": ("measurement_guides.json", ("guides", "scale")),
    "οστά % (ζυγαριά)": ("measurement_guides.json", ("guides", "scale")),
    "επίπεδο σπλαχνικού λίπους (ζυγαριά)": ("measurement_guides.json", ("guides", "scale")),
    "μέση": ("element_05.json", ("measurement",)),
    "άνω μηρός": ("measurement_guides.json", ("guides", "upper_thigh")),
    "ισχίο": ("element_11.json", ("measurement",)),
    "λαιμός": ("element_12.json", ("measurement",)),
    "στήθος": ("element_13.json", ("measurement",)),
    "ώμοι": ("element_14.json", ("measurement",)),
    "δικέφαλος χαλαρός": ("element_15.json", ("measurement", "relaxed")),
    "δικέφαλος σφιγμένος": ("element_15.json", ("measurement", "flexed")),
    "πήχης": ("element_16.json", ("measurement", "relaxed")),
    "πήχης σφιγμένος": ("element_16.json", ("measurement", "flexed")),
    "καρπός": ("element_17.json", ("measurement",)),
    "μηρός": ("element_18.json", ("measurement",)),
    "γόνατο": ("element_19.json", ("measurement",)),
    "γάμπα": ("element_20.json", ("measurement",)),
    "αστράγαλος": ("element_21.json", ("measurement",)),
    "εύρος αγκώνα": ("element_30.json", ("measurement",)),
    "εύρος γονάτου": ("element_31.json", ("measurement",)),
    "δερματοπτυχή τρικεφάλου": ("element_33.json", ("measurement",)),
    "δερματοπτυχή υποπλάτιου": ("element_34.json", ("measurement",)),
    "δερματοπτυχή υπερακάνθιου": ("element_35.json", ("measurement",)),
    "δερματοπτυχή γάμπας": ("element_36.json", ("measurement",)),
}


@lru_cache(maxsize=None)
def _load(name: str) -> dict:
    return json.loads((DATA / name).read_text(encoding="utf-8"))


@dataclass(frozen=True)
class Guide:
    field: str
    title: str
    steps: tuple[str, ...]
    protocol: str | None = None


def guide(field: str) -> Guide | None:
    """Οδηγία για ένα πεδίο· None για τα πεδία-δηλώσεις (τύπος δαγκάνας, εξεταστής ISAK)."""
    if field in _load("measurement_guides.json")["not_measured_fields"]:
        return None
    if field not in FIELD_SOURCES:
        from davinci.element_01 import InvalidInput

        raise InvalidInput(f"Άγνωστο πεδίο μέτρησης: {field}")
    name, path = FIELD_SOURCES[field]
    node = _load(name)
    for key in path:
        node = node[key]
    g = _load("measurement_guides.json")
    extra = g["extra_steps"].get(field, {"before": [], "after": []})
    common = [c["steps"] for c in g["common_steps"].values() if field in c["fields"]]
    body = list(node["steps"])
    for idx in sorted((int(i) for i in extra.get("insert", {})), reverse=True):  # μετά το βήμα idx του εγγράφου
        body[idx:idx] = extra["insert"][str(idx)]
    steps = [*extra["before"], *body, *extra["after"]] + [s for c in common for s in c]
    return Guide(field, node["info_title"], tuple(steps), node.get("protocol"))


def fields() -> tuple[str, ...]:
    return tuple(FIELD_SOURCES)
