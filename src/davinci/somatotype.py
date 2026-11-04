"""Κοινά για τις τρεις συνιστώσες Heath-Carter (Στοιχεία 37–39): στρογγυλοποίηση, κλίμακα Carter, σύγκριση
πληθυσμού (μέσος ± ΤΑ, πάντα «Ενδεικτική») και τιμές αθλητών. Δεν υπάρχει «Κατηγορία Σωματότυπου».
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from davinci.fmt import num, round_half_up

SCALE = ((0.5, 2.5, "χαμηλή"), (3.0, 5.0, "μέτρια"), (5.5, 7.0, "υψηλή"), (7.5, None, "πολύ υψηλή"))  # Carter 2002


def rounded(exact: float, minimum: float = 0.1) -> float:
    """Ένα δεκαδικό· τιμή ≤ 0 (ή κάτω από το ελάχιστο) → 0,1 (Carter 2002)."""
    v = round_half_up(exact, 1)
    return v if v >= minimum else minimum


def scale(value_1dp: float, bands=SCALE) -> str:
    """Κλίμακα Carter στη μισή μονάδα (x,2 → x,0 · x,3 → x,5 · x,8 → x+1)· κάτω από ½ → «χαμηλή»."""
    half = float(Decimal(repr(round_half_up(value_1dp * 2, 0))) / 2)
    for _lo, hi, label in bands:
        if hi is None or half <= hi:
            return label
    raise AssertionError("unreachable")


@dataclass(frozen=True)
class Comparison:
    source: str
    group: str
    country: str
    mean: float
    sd: float
    decimals: int

    def delta(self, value: float) -> float:
        return float(Decimal(repr(value)) - Decimal(repr(self.mean)))

    def fill(self, text: str, value: float, sex: str) -> str:
        d = self.delta(value)
        word = {"Άνδρας": "άνδρες", "Γυναίκα": "γυναίκες"}[sex]
        return (text.replace("[άνδρες/γυναίκες]", word).replace("[ομάδα]", self.group)
                .replace("[Ιταλία/Βουλγαρία/Ρωσία]", self.country).replace("[Ιταλία/Βουλγαρία]", self.country)
                .replace("[M]", num(self.mean, self.decimals)).replace("[ΤΑ]", num(self.sd, self.decimals))
                .replace("[Δ]", num(abs(d), self.decimals)).replace("[πάνω/κάτω]", "κάτω" if d < 0 else "πάνω"))


def find_comparison(sources: list[dict], sex: str, age: int) -> Comparison | None:
    """sources: [{"source", "country", "decimals", "rows": {φύλο: [[ομάδα, από, έως, n, μέσος, ΤΑ], ...]}}]·
    η πρώτη πηγή με γραμμή για το φύλο και την ηλικία."""
    for s in sources:
        for row in s["rows"].get(sex, []):
            label, lo, hi, _n, mean, sd = row
            if lo <= age <= hi:
                return Comparison(s["source"], label, s["country"], mean, sd, s["decimals"])
    return None


def athlete_messages(template: str, athletes: list[dict], sex: str) -> list[str]:
    out = []
    for a in athletes:
        if sex in a:
            mean, sd = a[sex]
            out.append(template.replace("[ομάδα]", a["label"][sex]).replace("[M]", num(mean)).replace("[ΤΑ]", num(sd)))
    return out
