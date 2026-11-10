"""Ξαναϋπολογίζει από τα δημόσια αρχεία ANSUR II τους συντελεστές των μοντέλων περιφέρειας των Στοιχείων
13, 14, 15, 16, 18, 19, 20, 21 και τους συγκρίνει με τα data/element_XX.json.

Μοντέλο: ln(περιφέρεια, cm) = a + b × ln(βάρος kg / ύψος cm) + Δ(καταγωγή) [+ c × ηλικία]
Δείγμα: DODRace 1–4 (λευκοί, μαύροι, ισπανόφωνοι, Ασιάτες)· 4.016 άνδρες, 1.941 γυναίκες.
Μονάδες των αρχείων: mm, και weightkg σε kg × 10 (ANSURII-MFR).

Για κάθε μοντέλο ελέγχει ότι οι a, b, c, Δ2, Δ(Ασιάτες), τυπικό σφάλμα και R² του αρχείου δεδομένων
είναι αυτά του μοντέλου με τον ίδιο όρο ηλικίας που εφαρμόζει ο κώδικας (απόκλιση ≤ 0,0005 και R² ≤ 0,01).
Αποτυγχάνει με κωδικό εξόδου 1 αν όχι. Τυπώνει και τη μέση απόκλιση ανά ζώνη ΔΜΣ και ηλικίας
(Πίνακας 5 του Στοιχείου 14).

Χωρίς εξωτερικές βιβλιοθήκες. Τα αρχεία ANSUR II δεν ανήκουν στο repository.
Χρήση: python3 tools/check_ansur_models.py "ANSUR II MALE Public.csv" "ANSUR II FEMALE Public.csv"
"""

import csv
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COLUMNS = {13: "chestcircumference", 14: "shouldercircumference", 15: "bicepscircumferenceflexed",
           16: "forearmcircumferenceflexed", 18: "thighcircumference", 19: "lowerthighcircumference",
           20: "calfcircumference", 21: "anklecircumference"}
TOL, TOL_R2 = 0.0005, 0.01


def read(path: str) -> list[dict]:
    for enc in ("utf-8", "latin-1"):
        try:
            with open(path, newline="", encoding=enc) as f:
                return [r for r in csv.DictReader(f) if r["DODRace"] in ("1", "2", "3", "4")]
        except UnicodeDecodeError:
            continue
    raise SystemExit(f"Δεν διαβάζεται: {path}")


def solve(a: list[list[float]], b: list[float]) -> list[float]:
    n = len(b)
    m = [row[:] + [b[i]] for i, row in enumerate(a)]
    for i in range(n):
        p = max(range(i, n), key=lambda r: abs(m[r][i]))
        m[i], m[p] = m[p], m[i]
        for r in range(n):
            if r != i:
                f = m[r][i] / m[i][i]
                m[r] = [x - f * y for x, y in zip(m[r], m[i])]
    return [m[i][n] / m[i][i] for i in range(n)]


def ols(rows: list[list[float]], y: list[float]):
    k = len(rows[0])
    xtx = [[sum(r[i] * r[j] for r in rows) for j in range(k)] for i in range(k)]
    xty = [sum(r[i] * v for r, v in zip(rows, y)) for i in range(k)]
    beta = solve(xtx, xty)
    res = [v - sum(b * x for b, x in zip(beta, r)) for r, v in zip(rows, y)]
    mean = sum(y) / len(y)
    se = math.sqrt(sum(e * e for e in res) / (len(y) - k))
    r2 = 1 - sum(e * e for e in res) / sum((v - mean) ** 2 for v in y)
    return beta, se, r2, res


def pct(values: list[float]) -> str:
    return f"{100 * (math.exp(sum(values) / len(values)) - 1):+.1f}%" if values else "—"


def main(male: str, female: str) -> int:
    data = {"Άνδρας": read(male), "Γυναίκα": read(female)}
    print("Δείγμα:", {k: len(v) for k, v in data.items()})
    failed = False
    for el, col in COLUMNS.items():
        model = json.loads((ROOT / "data" / f"element_{el}.json").read_text(encoding="utf-8"))["ansur_ii_model"]
        for sex, rows in data.items():
            c = model[sex]
            with_age = c.get("c") is not None
            x, y, age, bmi = [], [], [], []
            for r in rows:
                w, h = float(r["weightkg"]) / 10, float(r["stature"]) / 10
                race = r["DODRace"]
                row = [1.0, math.log(w / h)] + [1.0 if race == k else 0.0 for k in ("2", "3", "4")]
                if with_age:
                    row.append(float(r["Age"]))
                x.append(row)
                y.append(math.log(float(r[col]) / 10))
                age.append(int(r["Age"]))
                bmi.append(w / (h / 100) ** 2)
            beta, se, r2, res = ols(x, y)
            got = {"a": beta[0], "b": beta[1], "Δ2": beta[2], "Δ Ασιάτες": beta[4], "log_se": se}
            want = {"a": c["a"], "b": c["b"], "Δ2": model["delta"]["2"][sex], "Δ Ασιάτες": model["delta"]["3a"][sex],
                    "log_se": c["log_se"]}
            if with_age:
                got["c"], want["c"] = beta[5], c["c"]
            bad = [k for k in got if abs(got[k] - want[k]) > TOL]
            if abs(round(r2, 2) - c["r2"]) > TOL_R2 + 1e-9:
                bad.append("r2")
            failed |= bool(bad)
            print(f"{el} {sex}: {'με' if with_age else 'χωρίς'} ηλικία · "
                  + " · ".join(f"{k} {got[k]:.4f}" for k in got) + f" · R² {r2:.2f} → "
                  + ("ΣΦΑΛΜΑ: " + ", ".join(bad) if bad else "ίδιο με τα δεδομένα"))
            if el == 14:
                bands = [(0, 20), (20, 25), (25, 30), (30, 35), (35, 99)]
                ages = [(17, 25), (25, 35), (35, 45), (45, 59)]
                print("   απόκλιση ανά ΔΜΣ:", " · ".join(pct([e for e, b in zip(res, bmi) if lo <= b < hi])
                                                     for lo, hi in bands),
                      "| ανά ηλικία:", " · ".join(pct([e for e, a in zip(res, age) if lo <= a < hi]) for lo, hi in ages))
    return 1 if failed else 0


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    raise SystemExit(main(sys.argv[1], sys.argv[2]))
