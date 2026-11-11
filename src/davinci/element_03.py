"""Στοιχείο 03 — Άλιπη μάζα, ΔΑΜ και βάρος-στόχος (με τα Συμπληρώματα Σ, Β, Γ, Δ, Ε, Ζ).

Τιμές και μηνύματα στο data/element_03.json. Ο βάρος-στόχος δεν είναι σταθερός:
υπολογίζεται ξανά σε κάθε μέτρηση (Κανόνας 3).
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from davinci import element_01 as e01
from davinci import element_02 as e02
from davinci import element_04 as e04
from davinci.fmt import num

DATA_FILE = Path(__file__).resolve().parents[2] / "data" / "element_03.json"


@lru_cache(maxsize=1)
def load_data() -> dict:
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


def _c() -> dict:
    return load_data()["constants"]


# --- Τύποι (Πίνακας 5) ------------------------------------------------------------

def ffm(weight_kg: float, fat_percent: float) -> float:
    return weight_kg * (1 - fat_percent / 100)


def ffmi(ffm_kg: float, height_cm: float) -> float:
    h = height_cm / 100
    return ffm_kg / (h * h)


def normalized_ffmi(ffmi_value: float, height_cm: float) -> float:
    c = _c()
    return ffmi_value + c["normalization_slope"] * (c["normalization_height_m"] - height_cm / 100)


def k_factor(resistance_training: bool, losing_fat: bool) -> float:
    """Κανόνες 4 και 4α: 0,543 μόνο με προπόνηση ΚΑΙ απώλεια λίπους."""
    c = _c()
    return c["k_training_loss"] if (resistance_training and losing_fat) else c["k_default"]


def expected_ffm(ffm0: float, fat0_kg: float, target_fat_percent: float, k: float) -> float:
    """Forbes: Άλιπη = Άλιπη₀ + k × 10,4 × ln(Λίπος_στόχος / Λίπος₀), λύση επαναληπτικά."""
    f = target_fat_percent / 100
    a = _c()["forbes_constant"]
    x = ffm0
    for _ in range(500):
        fat_t = x * f / (1 - f)
        new = ffm0 + k * a * math.log(fat_t / fat0_kg)
        if abs(new - x) < 1e-10:
            return new
        x = new
    raise ArithmeticError("Η επαναληπτική λύση Forbes δεν συνέκλινε.")


# --- Βάρος-στόχος, Φάση 1 (Κανόνες 1–5, 8) ------------------------------------------

@dataclass(frozen=True)
class TargetPoint:
    target_fat_percent: float
    weight_kg: float
    ffm_kg: float
    k: float
    ffmi: float
    normalized_ffmi: float
    bmi: float
    low_ffmi: bool  # Κανόνας 5


@dataclass(frozen=True)
class Phase1Result:
    status: str  # "υπολογίστηκε", "επιτεύχθηκε", "δεν εφαρμόζεται"
    points: tuple[TargetPoint, ...] = ()  # Υγεία: 1 · Αθλητικό/Bodybuilding: [ανώτατο λίπος, κατώτατο λίπος]
    messages: tuple[str, ...] = ()
    indicative: bool = False


def _point(weight: float, fat_percent: float, target_fat: float, user: e01.UserCategories) -> TargetPoint:
    ffm0 = ffm(weight, fat_percent)
    fat0 = weight - ffm0
    k = k_factor(user.resistance_training, losing_fat=target_fat < fat_percent)
    ffm_t = expected_ffm(ffm0, fat0, target_fat, k)
    w_t = ffm_t / (1 - target_fat / 100)
    fi = ffmi(ffm_t, user.height_cm)
    return TargetPoint(target_fat, w_t, ffm_t, k, fi, normalized_ffmi(fi, user.height_cm),
                       e04.bmi(w_t, user.height_cm),
                       fi < load_data()["ffmi_low"][user.sex])


def weight_target(weight_kg: float, fat_percent: float, user: e01.UserCategories) -> Phase1Result:
    if e01.is_minor(user.age) or user.pregnant_or_breastfeeding:  # Κανόνας 8
        return Phase1Result("δεν εφαρμόζεται")
    rng = e02.profile_range(user)
    m = load_data()["messages_k0"]

    if user.profile == "Υγεία":
        if fat_percent > rng[1]:
            # Εύρος και στην Υγεία, όπως στα άλλα προφίλ: ανώτατο και κατώτατο υγιές λίπος
            # (σύμβαση συστήματος, απόφαση του χρήστη 11/11/2026· πριν: μόνο το ανώτατο, Κανόνας 1)
            targets = [rng[1], rng[0]]
        elif fat_percent < rng[0]:
            targets = [rng[0]]  # σύμβαση: πλησιέστερο σημείο εισόδου (βλ. data, conventions)
        else:
            return Phase1Result("επιτεύχθηκε")
    else:
        targets = [rng[1], rng[0]]  # Κανόνας 2

    points = tuple(_point(weight_kg, fat_percent, t, user) for t in targets)
    msgs: list[str] = []
    if any(p.k != 1.0 for p in points):
        bmi_cat = e04.adult_category(e04.bmi(weight_kg, user.height_cm),
                                     e04.adult_table_name(user.effective_group))
        if bmi_cat not in e04.load_data()["rules"]["rule_2_overweight_categories"]:
            msgs.append(m["lean_training"])
    if user.resistance_training and any(p.target_fat_percent > fat_percent for p in points):
        msgs.append(m["fat_gain"])  # Κανόνας 4α
    return Phase1Result("υπολογίστηκε", points, tuple(msgs), indicative=bool(msgs))


# --- Ταξινόμηση ΔΑΜ (Πίνακες 2, 4 · Σ3 · Ε · Ζ) --------------------------------------

@dataclass(frozen=True)
class FFMIResult:
    ffm_kg: float
    ffmi: float
    normalized_ffmi: float
    low: bool
    indications: tuple[str, ...] = ()
    reference_range: tuple[float, float] | None = None  # μόνο προφίλ Υγεία
    reference_label: str | None = None
    indicative: bool = False
    messages: tuple[str, ...] = ()


def health_reference_range(user: e01.UserCategories) -> tuple[tuple[float, float], str | None]:
    """Φυσιολογικό εύρος ΔΑΜ ανά καταγωγή (Πίνακας Ζ2). Μη δηλωμένη → όπως ομάδα 5 (Κ5)."""
    group = user.effective_group or "5"
    entry = load_data()["health_reference_range"]["ranges"][group]
    return tuple(entry[user.sex]), entry["message"]


def assess_ffmi(weight_kg: float, fat_percent: float, user: e01.UserCategories,
                fat_result: e02.FatResult | None = None) -> FFMIResult:
    d = load_data()
    mass = ffm(weight_kg, fat_percent)
    fi = ffmi(mass, user.height_cm)
    nf = normalized_ffmi(fi, user.height_cm)
    low = fi < d["ffmi_low"][user.sex]
    ind: list[str] = [d["ffmi_low"]["label"]] if low else []
    if user.sex == "Άνδρας":
        for row in d["indications_men"]:
            if nf > row["normalized_gt"]:
                ind.append(row["label"])

    msgs: list[str] = []
    group = user.effective_group
    if group in d["messages_ancestry"]:
        msgs.append(d["messages_ancestry"][group])
    if user.sex == "Γυναίκα":
        msgs.append(d["messages_k0"]["women_no_upper"])

    hr = d["health_reference_range"]
    rng, zmsg = health_reference_range(user)
    above_range = fi > rng[1]
    fr = fat_result or e02.assess(fat_percent, user, weight_kg)
    if above_range and fr.health_category in ("Υπέρβαρο", "Παχυσαρκία"):
        ind.append(d["indication_high_with_excess_fat"])

    ref_range = ref_label = None
    indicative = False
    if user.profile == "Υγεία":
        ref_range = rng
        ref_label = hr["labels"]["above" if above_range else "below" if fi < rng[0] else "within"]
        if zmsg:
            msgs.append(hr["messages"][zmsg])
            indicative = True
        if user.age >= hr["age_message_from"]:
            msgs.append(hr["messages"]["age_40"])
        msgs.append(hr["messages"]["activity"])
        if above_range and e04.bmi(weight_kg, user.height_cm) >= hr["high_message_bmi_from"]:
            msgs.append(hr["messages"]["high_with_bmi_25"])

    return FFMIResult(mass, fi, nf, low, tuple(ind), ref_range, ref_label, indicative, tuple(msgs))


# --- Φάση 2: αύξηση μυών (Συμπλήρωμα Δ) ------------------------------------------------

@dataclass(frozen=True)
class Phase2Result:
    status: str  # "αύξηση", "διατήρηση", "δεν εφαρμόζεται"
    target_index: float | None = None
    ffm_target_kg: float | None = None
    gain_kg: float = 0.0
    weight_kg: float | None = None
    min_weeks: float | None = None
    messages: tuple[str, ...] = ()
    indicative: bool = False


def phase2(ffm_end_kg: float, profile_fat_percent: float, user: e01.UserCategories,
           measured_by_scale: bool = True) -> Phase2Result:
    p = load_data()["phase2"]
    msgs = p["messages"]
    if e01.is_minor(user.age) or user.pregnant_or_breastfeeding:
        return Phase2Result("δεν εφαρμόζεται", messages=(msgs["not_applicable"],))

    h = user.height_cm / 100
    is_man = user.sex == "Άνδρας"
    current = ffmi(ffm_end_kg, user.height_cm)
    current_cmp = normalized_ffmi(current, user.height_cm) if is_man else current
    target = p["targets"][user.profile][user.sex]

    out: list[str] = []
    if user.profile in ("Αθλητικό", "Bodybuilding") and user.age >= 40:
        out.append(msgs["age_40"])
    if user.ancestry != "1":
        out.append(msgs["ancestry_2_5"])
    if user.profile == "Bodybuilding" and not is_man:
        out.append(msgs["women_bodybuilding"])
    if measured_by_scale:
        out.append(msgs["scale"])

    if current_cmp >= target:
        w = ffm_end_kg / (1 - profile_fat_percent / 100)
        return Phase2Result("διατήρηση", target, ffm_end_kg, 0.0, w, None, tuple(out), bool(out))

    raw_target = target - _c()["normalization_slope"] * (_c()["normalization_height_m"] - h) if is_man else target
    ffm_t = raw_target * h * h
    gain = ffm_t - ffm_end_kg
    weeks = gain / p["gain_kg_per_block"] * p["block_weeks"]
    return Phase2Result("αύξηση", target, ffm_t, gain, ffm_t / (1 - profile_fat_percent / 100),
                        weeks, tuple(out), bool(out))


# --- Ανάλυση άλιπης μάζας (Συμπληρώματα Β και Γ) ---------------------------------------

def scale_kg(weight_kg: float, percent_of_weight: float) -> float:
    """Κανόνας Β-7: τα ποσοστά της ζυγαριάς είναι επί του συνολικού βάρους."""
    return weight_kg * percent_of_weight / 100


@dataclass(frozen=True)
class Line:
    name: str
    kg: float
    typical: bool = False  # γκρι «Τυπική τιμή» (Γ-1)


@dataclass(frozen=True)
class Analysis:
    ffm_kg: float
    material: tuple[Line, ...]  # τρόπος Α
    tissues: tuple[Line, ...]  # τρόπος Β (κενό αν λείπουν οι μύες)
    difference_kg: float | None
    messages: tuple[str, ...] = field(default=())
    warnings: tuple[str, ...] = field(default=())

    def pct_of_ffm(self, kg: float) -> float:
        return kg / self.ffm_kg * 100


def analysis(weight_kg: float, fat_percent: float, user: e01.UserCategories,
             water_kg: float | None = None, bone_kg: float | None = None,
             muscle_kg: float | None = None, bone_typical: bool = False,
             bone_note: str | None = None) -> Analysis:
    """bone_typical: η τιμή οστών είναι η «τυπική τιμή» του Στοιχείου 09 → τα «Λοιπά» και η
    «Διαφορά» δεν υπολογίζονται (09, Πίνακας 4 · 03, Πίνακας Γ4)· bone_note: το μήνυμα του 09."""
    d = load_data()
    a, g = d["analysis"], d["dry_mass"]
    mass = ffm(weight_kg, fat_percent)
    minor_or_preg = e01.is_minor(user.age) or user.pregnant_or_breastfeeding
    msgs = [a["note_two_ways"]]
    warns: list[str] = []
    material: list[Line] = []
    tissues: list[Line] = []
    diff = None

    if water_kg is not None:
        material.append(Line("Νερό (υγρά)", water_kg))
        material.append(Line("Ξηρή άλιπη μάζα", mass - water_kg))
    if bone_kg is not None:
        material.append(Line("Οστικά μέταλλα", bone_kg, typical=bone_typical))
        if bone_note:
            msgs.append(bone_note)
    missing = [n for n, v in (("νερό", water_kg), ("οστικά μέταλλα", bone_kg)) if v is None]
    if missing:
        msgs.append(a["msg_incomplete_material"].replace("[νερό / οστικά μέταλλα]", " / ".join(missing)))
    if water_kg is None:
        msgs.append(g["msg_no_water"])

    rest = None
    if not missing and not bone_typical:
        rest = mass - water_kg - bone_kg
        if rest < 0:
            warns.append(a["msg_inconsistent"])
            rest = None
        else:
            material.append(Line("Λοιπά", rest))

    if minor_or_preg:
        if e01.is_minor(user.age):
            msgs.append(g["msg_minor"])
    else:
        protein = g["protein_per_ffm"] * mass
        if muscle_kg is not None:
            glycogen = g["glycogen_per_muscle"] * muscle_kg + g["glycogen_liver_kg"]
        else:
            glycogen = g["glycogen_default_kg"]
            msgs.append(g["msg_no_muscle_glycogen"])
        minerals = g["other_minerals_per_ffm"] * mass
        material += [Line("Πρωτεΐνη", protein, True), Line("Γλυκογόνο", glycogen, True),
                     Line("Άλλα μέταλλα", minerals, True)]
        msgs.append(g["msg_typical"].replace("[Y]", num(mass)))
        if rest is not None:
            diff = rest - protein - glycogen - minerals
            material.append(Line("Διαφορά", diff))
            t = g["difference_threshold_kg"]
            if diff > t:
                warns.append(g["msg_diff_high"].replace("[Δ]", num(diff))
                             .replace("[r]", num(water_kg / mass, 3))
                             .replace("[0,73 × άλιπη]", num(g["typical_water_ratio"] * mass)))
            elif diff < -t:
                warns.append(g["msg_diff_low"].replace("[Δ]", num(diff)))
            else:
                msgs.append(g["msg_diff_ok"].replace("[Δ]", num(diff)))

    if muscle_kg is None:
        msgs.append(a["msg_no_muscle"])
    elif mass - muscle_kg < 0:
        warns.append(a["msg_inconsistent"])
    else:
        tissues.append(Line("Σκελετικοί μύες", muscle_kg))
        if not minor_or_preg:
            tissues.append(Line("Ξηροί μύες", g["dry_muscle_per_muscle"] * muscle_kg))
            msgs.append(g["msg_dry_muscle_info"])
        tissues.append(Line("Λοιποί ιστοί", mass - muscle_kg))

    return Analysis(mass, tuple(material), tuple(tissues), diff, tuple(msgs), tuple(dict.fromkeys(warns)))
