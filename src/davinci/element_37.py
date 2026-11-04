"""Στοιχείο 37 — Ενδομορφία (Heath-Carter, Carter 2002), μόνο Professional.

X = (τρικέφαλος + υποπλάτια + υπερακάνθια, mm) × 170,18 / ύψος (cm)
Ε = −0,7182 + 0,1451·X − 0,00068·X² + 0,0000014·X³ · ένα δεκαδικό · ≤ 0 → 0,1
Υπολογισμός, όχι στόχος. Μόνο με δαγκάνα. Κλίμακα Carter και σύγκριση πληθυσμού (πάντα «Ενδεικτική»).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

from davinci import element_01 as e01
from davinci import element_46 as e46
from davinci import skinfolds
from davinci.fmt import num, round_half_up

DATA_FILE = Path(__file__).resolve().parents[2] / "data" / "element_37.json"


@lru_cache(maxsize=1)
def load_data() -> dict:
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


def x_value(triceps_mm: float, subscapular_mm: float, supraspinale_mm: float, height_cm: float) -> float:
    return (triceps_mm + subscapular_mm + supraspinale_mm) * load_data()["formula"]["height_ref_cm"] / height_cm


def endomorphy_exact(x: float) -> float:
    a, b, c, dd = load_data()["formula"]["coef"]
    return a + b * x + c * x ** 2 + dd * x ** 3


def rounded(exact: float) -> float:
    d = load_data()
    v = round_half_up(exact, d["decimals"])
    return v if v > 0 else d["min_value"]


def scale(value_1dp: float) -> str:
    """Κλίμακα Carter (κοινή με τα 38, 39: somatotype.scale)."""
    from davinci import somatotype
    return somatotype.scale(value_1dp, tuple(tuple(b) for b in load_data()["scale"]["bands"]))


@dataclass(frozen=True)
class EndomorphyResult:
    value: float | None  # ένα δεκαδικό
    exact: float | None = None
    x: float | None = None
    scale: str | None = None
    at_least: bool = False
    comparison: dict | None = None
    indicative: bool = False
    reasons: tuple[str, ...] = ()
    messages: tuple[str, ...] = ()


def _value(v):
    """Δέχεται αριθμό (mm) ή SkinfoldResult (Στοιχεία 33–35)."""
    if isinstance(v, skinfolds.SkinfoldResult):
        return v.value_mm, v.measurement_reasons
    return v, ()


def _delta_text(text: str, mean: float, sd: float, value: float, decimals: int) -> str:
    delta = float(Decimal(repr(value)) - Decimal(repr(mean)))
    return (text.replace("[M]", num(mean, decimals)).replace("[ΤΑ]", num(sd, decimals))
            .replace("[Δ]", num(abs(delta), decimals)).replace("[πάνω/κάτω]", "κάτω" if delta < 0 else "πάνω"))


def compute(triceps, subscapular, supraspinale, user: e01.UserCategories, *, supraspinale_is_iliac: bool = False,
            no_caliper: bool = False, caliper_max: bool = False) -> EndomorphyResult:
    """triceps / subscapular / supraspinale: mm ή αποτέλεσμα των Στοιχείων 33 / 34 / 35."""
    d = load_data()
    m = d["messages"]
    if not e46.element_available("37", user.level):
        return EndomorphyResult(None, messages=(e46.normal_message("37"),))
    if no_caliper:
        return EndomorphyResult(None, messages=(m["no_caliper"],))
    if supraspinale_is_iliac:
        return EndomorphyResult(None, messages=(m["iliac"],))
    (t, rt), (s, rs), (p, rp) = _value(triceps), _value(subscapular), _value(supraspinale)
    names = d["missing_names"]
    missing = [names[k] for k, v in (("triceps", t), ("subscapular", s), ("supraspinale", p),
                                     ("height", user.height_cm)) if v is None]
    if missing:
        return EndomorphyResult(None, messages=(m["missing"].replace("[τιμή]", ", ".join(missing)),))

    x = x_value(t, s, p, user.height_cm)
    exact = endomorphy_exact(x)
    value = rounded(exact)
    reasons = tuple(dict.fromkeys(rt + rs + rp))  # χωρίς διπλότυπα, με τη σειρά
    e_txt = num(value)
    msgs = [m["value"].replace("[E]", e_txt)]
    if user.pregnant:  # χωρίς κλίμακα και σύγκριση (σύμβαση συστήματος)
        return EndomorphyResult(value, exact, x, None, caliper_max, None, True, reasons,
                                tuple(msgs + [m["pregnancy"]]))
    sc = scale(value)
    msgs.append(m["scale"].replace("[χαμηλή/μέτρια/υψηλή/πολύ υψηλή]", sc))
    indicative = bool(reasons) or caliper_max
    if value < d["check_below"]:
        msgs.append(m["below_1"].replace("[E]", e_txt))
    if caliper_max:
        msgs.append(m["caliper_max"].replace("[E]", e_txt))
    if reasons:
        msgs.append(m["indicative"].replace("[λόγος από τη δερματοπτυχή]", " · ".join(reasons)))

    age = user.age
    cmp = None
    if e01.is_minor(age):
        return EndomorphyResult(value, exact, x, sc, caliper_max, None, True, reasons, tuple(msgs + [m["child"]]))
    c = d["comparison"]
    pet = c["petri"][user.sex]
    if pet["ages"][0] <= age <= pet["ages"][1]:
        word = {"Άνδρας": "άνδρες", "Γυναίκα": "γυναίκες"}[user.sex]
        cmp = {"source": "Petri 2024", "mean": pet["mean_sd"][0], "sd": pet["mean_sd"][1]}
        msgs.append(_delta_text(m["cmp_petri"].replace("[άνδρες/γυναίκες]", word), *pet["mean_sd"], value, 1))
    elif user.sex == c["andreenko"]["sex"]:
        row = next((r for r in c["andreenko"]["rows"] if r[1] <= age <= r[2]), None)
        if row:
            cmp = {"source": "Andreenko 2015", "group": row[0], "mean": row[4], "sd": row[5]}
            msgs.append(_delta_text(m["cmp_andreenko"].replace("[ομάδα]", row[0]), row[4], row[5], value, 2))
    if cmp is None:
        msgs.append(m["no_comparison"])
    else:
        indicative = True
        if (user.effective_group or "5") not in d["reference_ancestries"]:
            msgs.append(m["ancestry"])
    for a in d["athletes"]:
        if user.sex in a:
            mean, sd = a[user.sex]
            msgs.append(m["athletes"].replace("[ομάδα]", a["label"][user.sex])
                        .replace("[M]", num(mean)).replace("[ΤΑ]", num(sd)))
    return EndomorphyResult(value, exact, x, sc, caliper_max, cmp, indicative, reasons, tuple(msgs))
