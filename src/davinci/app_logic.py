"""Λογική της εφαρμογής (streamlit_app.py): συνδέει τα Στοιχεία 01–45 σε ένα πλάνο.

Χωρίς καμία οθόνη εδώ, ώστε να ελέγχεται με τεστ. Δεν προσθέτει κανέναν αριθμό ορίου: όλα έρχονται από τα στοιχεία.
Η εφαρμογή καλύπτει: επίπεδο Normal, απώλεια λίπους (Φάση 1) και συντήρηση. Η αύξηση μυών (Φάση 2) δεν
περιλαμβάνεται ακόμη· ο κώδικας του Στοιχείου 43 (`forecast_gain`) υπάρχει, αλλά δεν είναι συνδεδεμένος εδώ.
Όπου ο χρήστης πρέπει να διαλέξει (έλλειμμα AHA ή ρυθμός %), το πλάνο ζητά την επιλογή και δεν διαλέγει μόνο του.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from davinci import element_01 as e01
from davinci import element_02 as e02
from davinci import element_03 as e03
from davinci import element_04 as e04
from davinci import element_40 as e40
from davinci import element_41 as e41
from davinci import element_42 as e42
from davinci import element_43 as e43
from davinci import element_44 as e44

NOT_SUPPORTED_GAIN = "Η αύξηση μυών (Φάση 2) δεν περιλαμβάνεται ακόμη στην εφαρμογή."
SAFETY_NOTE = ("⚠ Σημείωση εφαρμογής: το λίπος είναι κάτω από το κατώτατο όριο ασφαλείας (Στοιχείο 02, Κανόνας 4)· "
               "δεν δίνεται στόχος απώλειας.")


@dataclass(frozen=True)
class PlanInput:
    birth_date: date
    sex: str
    height_cm: float
    weight_kg: float
    fat_percent: float
    today: date
    ancestry: str | None = None
    mixed_chosen_group: str | None = None
    profile: str = "Υγεία"
    resistance_training: bool = False
    pregnant: bool = False
    breastfeeding: bool = False
    pal: float = 1.4
    level: str = "Normal"  # Στοιχείο 46
    aha_deficit: int | str | None = None  # 500 · 750 · «30%» (ΔΜΣ ≥ 25, απώλεια)
    rate_percent: float | None = None  # % του βάρους την εβδομάδα (ΔΜΣ < 25, απώλεια)


@dataclass(frozen=True)
class Choice:
    """Ό,τι πρέπει να διαλέξει ο χρήστης πριν βγει το πλάνο."""
    kind: str  # «aha» · «rate»
    options: tuple = ()  # aha: (500, 750, "30%") · rate: (κάτω, πάνω) σε % την εβδομάδα
    source: str = ""


@dataclass(frozen=True)
class Prep:
    user: e01.UserCategories | None = None
    fat: e02.FatResult | None = None
    bmi: e04.BMIResult | None = None
    direction: str | None = None  # «loss» · «maintain» · None (χωρίς στόχο)
    target: e03.TargetPoint | None = None
    choice: Choice | None = None
    errors: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class PlanResult:
    prep: Prep
    presentation: e44.Presentation | None = None
    pending_choice: Choice | None = None
    messages: tuple[str, ...] = ()  # μηνύματα των Στοιχείων 02 και 04
    errors: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()
    energy: e40.EnergyResult | None = None


def today() -> date:
    """Η σημερινή ημερομηνία· ξεχωριστή συνάρτηση για να ελέγχεται η οθόνη με σταθερή ημερομηνία."""
    return date.today()


def pal_options() -> dict[str, str]:
    """PAL που δίνονται σε όλους (όχι 2,2 και 2,4 που είναι μόνο για αθλητές)."""
    d = e40.load_data()
    return {k: v for k, v in d["pal"].items() if k not in d["pal_athlete_only"]}


def allowed_profiles(birth_date: date, today: date) -> tuple[str, ...]:
    return e01.allowed_profiles(e01.age_in_completed_years(birth_date, today))


def _user(inp: PlanInput) -> e01.UserCategories:
    return e01.UserCategories(
        birth_date=inp.birth_date, measurement_date=inp.today, sex=inp.sex, height_cm=inp.height_cm,
        ancestry=inp.ancestry, mixed_chosen_group=inp.mixed_chosen_group, pregnant=inp.pregnant,
        breastfeeding=inp.breastfeeding, resistance_training=inp.resistance_training, profile=inp.profile,
        level=inp.level)


def prepare(inp: PlanInput) -> Prep:
    """Ταξινομεί (02, 04), βρίσκει κατεύθυνση (42) και στόχο (03) και λέει τι πρέπει να διαλέξει ο χρήστης."""
    try:
        user = _user(inp)
        fat = e02.assess(inp.fat_percent, user, inp.weight_kg)
        bmi = e04.classify(inp.weight_kg, user, fat_in_healthy_range=fat.in_healthy_range)
    except (e01.InvalidInput, ValueError, LookupError) as exc:
        return Prep(errors=(str(exc),))
    if e01.is_minor(user.age) or user.pregnant_or_breastfeeding:
        return Prep(user, fat, bmi, direction=None, notes=("Ανήλικοι, εγκυμοσύνη και θηλασμός: μόνο καταγραφή, χωρίς στόχους.",))

    dr = e42.direction(inp.fat_percent, user)
    if dr.no_loss:
        # Το Στοιχείο 02 (Κανόνας 4) ζητά «προειδοποίηση» χωρίς να δίνει κείμενο· αυτή είναι σημείωση της εφαρμογής.
        warn = (SAFETY_NOTE,) if fat.below_safety_floor else ()
        return Prep(user, fat, bmi, direction=None, notes=warn)
    if dr.direction != "loss":
        return Prep(user, fat, bmi, direction="maintain")
    # Κατεύθυνση «απώλεια» = λίπος πάνω από το εύρος του προφίλ, άρα το Στοιχείο 03 δίνει πάντα στόχο.
    wt = e03.weight_target(inp.weight_kg, inp.fat_percent, user)
    aha = e40.load_data()["aha"]
    if bmi.value >= aha["bmi_from"]:  # Στοιχείο 40, Κανόνας 13: το λίπος είναι πάνω από το υγιές εύρος
        choice = Choice("aha", (*aha["deficits_kcal"], f"{aha['deficit_percent']}%"), aha["source"])
    else:
        choice = Choice("rate", tuple(e40.rate_range("loss", None)), "Στοιχείο 40, Πίνακας ρυθμών")
    return Prep(user, fat, bmi, "loss", wt.points[0], choice,
                notes=(() if len(wt.points) == 1 else
                       ("Το προφίλ έχει δύο σημεία-στόχους· χρησιμοποιείται το πρώτο (πάνω όριο λίπους).",)))


def _maintain(inp: PlanInput, prep: Prep) -> PlanResult:
    user, w = prep.user, inp.weight_kg
    energy = e40.assess(user, w, inp.pal, goal="maintain")
    part = e42.partition("maintain", w * inp.fat_percent / 100, user, trained=user.resistance_training, bmi=prep.bmi.value)
    macros = e41.compute(energy.target_intake_kcal, user, w, goal="maintain")
    pres = e44.present(user, weight_kg=w, fat_percent=inp.fat_percent, start=inp.today, goal="maintain",
                       energy=energy, macros=macros, partition=part, trained=user.resistance_training,
                       fat_in_healthy_range=prep.fat.in_healthy_range)
    return PlanResult(prep, pres, messages=_messages(prep), notes=prep.notes, energy=energy)


def _messages(prep: Prep) -> tuple[str, ...]:
    out: list[str] = []
    for m in (*(prep.fat.messages if prep.fat else ()), *(prep.bmi.messages if prep.bmi else ())):
        if m not in out:
            out.append(m)
    return tuple(out)


def plan(inp: PlanInput) -> PlanResult:
    prep = prepare(inp)
    if prep.errors:
        return PlanResult(prep, errors=prep.errors)
    user, w, fat_pct = prep.user, inp.weight_kg, inp.fat_percent

    if prep.direction is None:  # ανήλικοι / εγκυμοσύνη / θηλασμός / λίπος κάτω από το ελάχιστο
        pres = e44.present(user, weight_kg=w, fat_percent=fat_pct, start=inp.today,
                           fat_in_healthy_range=prep.fat.in_healthy_range)
        return PlanResult(prep, pres, messages=_messages(prep), notes=prep.notes)
    if prep.direction == "maintain":
        return _maintain(inp, prep)

    # --- απώλεια (Φάση 1) ---
    ch, tp = prep.choice, prep.target
    fat_kg = w * fat_pct / 100
    trained = user.resistance_training
    healthy = prep.fat.in_healthy_range
    errors: list[str] = []
    deficit = None
    if ch.kind == "aha":
        if inp.aha_deficit is None:
            return PlanResult(prep, pending_choice=ch, messages=_messages(prep), notes=prep.notes)
        if inp.aha_deficit == "30%":
            tdee = e40.assess(user, w, inp.pal, goal="maintain").tdee
            deficit = tdee * e40.load_data()["aha"]["deficit_percent"] / 100
        else:
            deficit = float(inp.aha_deficit)
    else:
        if inp.rate_percent is None:
            return PlanResult(prep, pending_choice=ch, messages=_messages(prep), notes=prep.notes)
        lo, hi = ch.options
        if not (lo <= inp.rate_percent <= hi):
            errors.append(f"Ρυθμός εκτός εύρους {lo}–{hi}% του βάρους την εβδομάδα.")
            return PlanResult(prep, pending_choice=ch, messages=_messages(prep), errors=tuple(errors), notes=prep.notes)

    bmi = prep.bmi.value
    try:
        if deficit is not None:
            part = e42.partition("loss", fat_kg, user, trained=trained, bmi=bmi, deficit_kcal_day=deficit)
        else:
            part = e42.partition("loss", fat_kg, user, trained=trained, bmi=bmi,
                                 weekly_change_kg=-w * inp.rate_percent / 100)
        energy = e40.assess(user, w, inp.pal, goal="loss", aha_deficit=inp.aha_deficit if deficit is not None else None,
                            rate_percent=None if deficit is not None else inp.rate_percent,
                            kcal_per_kg=part.e_kcal_per_kg, fat_in_healthy_range=healthy)
    except e01.InvalidInput as exc:
        return PlanResult(prep, pending_choice=ch, messages=_messages(prep), errors=(str(exc),), notes=prep.notes)

    macros = None
    if energy.target_intake_kcal is not None:
        macros = e41.compute(energy.target_intake_kcal, user, w, goal="loss", health_target_weight_kg=tp.weight_kg)
    if deficit is not None:
        fc = e43.forecast(w, fat_kg, user, trained=trained, target_fat_percent=tp.target_fat_percent,
                          target_weight_kg=tp.weight_kg, deficit_kcal_day=deficit)
        weekly_abs = deficit * 7 / part.e_kcal_per_kg
    else:
        fc = e43.forecast(w, fat_kg, user, trained=trained, target_fat_percent=tp.target_fat_percent,
                          target_weight_kg=tp.weight_kg, rate_percent=inp.rate_percent)
        weekly_abs = w * inp.rate_percent / 100
    rates = e44.rate_range(weekly_abs, energy.tdee, part.e_kcal_per_kg)
    pres = e44.present(user, weight_kg=w, fat_percent=fat_pct, start=inp.today, goal="loss", energy=energy,
                       macros=macros, partition=part, target=tp, forecast=fc, rates=rates, trained=trained,
                       fat_in_healthy_range=healthy)
    return PlanResult(prep, pres, messages=_messages(prep), notes=prep.notes, energy=energy)


# --- Κάρτα μέτρησης (Στοιχείο 45) ----------------------------------------------------------------------------
CARD_KINDS: dict[str, str] = {
    "Περιφέρεια (cm)": "circumference",
    "Εύρος οστού (cm)": "bone_breadth",
    "Δερματοπτυχή (mm)": "skinfold",
    "Λίπος % της ζυγαριάς": "scale_fat_percent",
    "Άλλο % της ζυγαριάς (μύες, νερό, οστά)": "scale_percent",
}


def measurement_card(kind: str, rows: list[tuple[date, float, str, bool]], user: e01.UserCategories, *,
                     waist: bool = False, scale_fat_range: tuple[float, float] | None = None):
    """rows: (ημερομηνία, τιμή, συσκευή/μέθοδος, ISAK). Επιστρέφει την κάρτα του Στοιχείου 45."""
    from davinci import element_45 as e45

    if kind not in CARD_KINDS.values():
        raise e01.InvalidInput(f"Η εφαρμογή δεν υποστηρίζει ακόμη κάρτα για «{kind}».")
    readings = []
    for day, value, method, isak in rows:
        if not method or not str(method).strip():
            raise e01.InvalidInput("Κάθε μέτρηση χρειάζεται συσκευή ή μέθοδο (Στοιχείο 45, Κανόνας 9).")
        if not value or value <= 0:
            raise e01.InvalidInput("Η τιμή πρέπει να είναι θετική.")
        readings.append(e45.Reading(float(value), day, str(method).strip(), bool(isak)))
    if not readings:
        raise e01.InvalidInput("Η κάρτα χρειάζεται τουλάχιστον μία μέτρηση.")
    target = e45.NO_TARGET
    if kind == "circumference" and waist:
        target = e45.waist_target(user.height_cm)
    elif kind == "scale_fat_percent" and scale_fat_range is not None:
        target = e45.Target("range", low=scale_fat_range[0], high=scale_fat_range[1],
                            text="όριο του προφίλ (Στοιχείο 02)")
    return e45.card(kind, readings, user, target=target)


def _blank(x) -> bool:
    if x is None:
        return True
    try:
        return bool(x != x) or (isinstance(x, str) and x.strip() == "")  # NaN, NaT
    except (TypeError, ValueError):  # pd.NA
        return True


def clean_rows(records: list[dict]) -> list[tuple[date, float, str, bool]]:
    """Γραμμές του πίνακα μετρήσεων → (ημερομηνία, τιμή, μέθοδος, ISAK). Παραλείπει τις εντελώς κενές γραμμές·
    μια μισή γραμμή (τιμή χωρίς ημερομηνία ή ανάποδα) είναι σφάλμα, δεν παραλείπεται σιωπηλά."""
    out = []
    for i, r in enumerate(records, start=1):
        day, value, method = r.get("Ημερομηνία"), r.get("Τιμή"), r.get("Συσκευή / μέθοδος")
        if _blank(day) and _blank(value) and _blank(method):
            continue
        if _blank(day) or _blank(value):
            raise e01.InvalidInput(f"Γραμμή {i}: χρειάζεται ημερομηνία και τιμή.")
        if hasattr(day, "to_pydatetime"):
            day = day.to_pydatetime()
        if hasattr(day, "date") and callable(day.date):
            day = day.date()
        out.append((day, float(value), "" if _blank(method) else str(method), bool(r.get("ISAK") or False)))
    return out


# --- Καρτέλα «Μετρήσεις» (Στοιχεία 05–39, σε δόσεις) -------------------------------------------------------
@dataclass(frozen=True)
class Measures:
    """Μετρήσεις της φόρμας· None = δεν μετρήθηκε."""
    waist_cm: float | None = None
    upper_thigh_cm: float | None = None
    scale_visceral_level: float | None = None
    scale_muscle_percent: float | None = None
    scale_water_percent: float | None = None
    scale_bone_percent: float | None = None
    previous_morning_weights: tuple[float, ...] = ()  # από το παλαιότερο στο πιο πρόσφατο
    today_morning_weight: float | None = None
    urine_color: int | None = None
    thirst: float | None = None
    hip_cm: float | None = None
    neck_cm: float | None = None
    chest_cm: float | None = None
    # Ιατρικές εξετάσεις — μόνο Professional (Στοιχείο 46, Κανόνας 6)
    ct_visceral_cm2: float | None = None
    visceral_volume: float | None = None
    medical_muscle_kg: float | None = None
    isotope_water_kg: float | None = None
    serum_osmolality: float | None = None
    osmolality_inputs: tuple[float, float, float, float] | None = None  # Na, K, γλυκόζη, ουρία (mmol/L)
    dxa_bone_kg: float | None = None
    t_score: float | None = None
    z_score: float | None = None
    menopause: bool | None = None
    shoulders_cm: float | None = None
    arm_relaxed_cm: float | None = None
    biceps_flexed_cm: float | None = None
    forearm_relaxed_cm: float | None = None
    forearm_flexed_cm: float | None = None
    wrist_cm: float | None = None
    thigh_cm: float | None = None  # 1 cm κάτω από τη γλουτιαία πτυχή (Στοιχείο 18)· όχι ο «άνω μηρός» του 06
    knee_cm: float | None = None  # πάνω από το γόνατο (Στοιχείο 19)
    knee_swollen: bool = False
    calf_cm: float | None = None
    ankle_cm: float | None = None
    leg_edema: bool = False  # πρήξιμο (οίδημα) στα πόδια ή στον αστράγαλο (Στοιχεία 20, 21)
    ankle_injured: bool = False
    arm_injured: bool = False  # τραυματισμός ή πρήξιμο στο δεξί χέρι ή στον καρπό (Στοιχεία 25, 27)
    leg_injured: bool = False  # τραυματισμός στο δεξί πόδι, μηρός ή γάμπα (Στοιχεία 26, 28)
    lipedema: bool = False  # δηλωμένη διάγνωση λιποιδήματος (Στοιχεία 28, 29)


@dataclass(frozen=True)
class Section:
    title: str
    lines: tuple[tuple[str, str], ...] = ()
    messages: tuple[str, ...] = ()
    indicative: bool = False
    table: tuple[tuple[str, ...], ...] = ()  # πρώτη γραμμή = επικεφαλίδες
    warnings: tuple[str, ...] = ()


def _n(x: float, d: int = 1) -> str:
    from davinci.fmt import num
    return num(x, d)


def _below(x: float) -> str:
    """Τιμή «κάτω από»: στρογγυλεύεται προς τα κάτω, ώστε η εμφανιζόμενη τιμή να είναι πράγματι κάτω από το όριο
    (όπως το «≈ 109,6 kg» του Πίνακα 8 του Στοιχείου 05 για όριο 109,65)."""
    from decimal import ROUND_FLOOR, Decimal
    return _n(float(Decimal(repr(x)).quantize(Decimal("0.1"), rounding=ROUND_FLOOR)))


def _signed(x: float) -> str:
    """Διαφορά με πρόσημο, όπως «(−9,9)» του Πίνακα Β2 του Στοιχείου 03."""
    return ("−" if x < 0 else "+") + _n(abs(x))


def _two_values(*values) -> tuple[str, ...]:
    """Στοιχείο 46, μήνυμα Ν4: δύο τιμές για το ίδιο μέγεθος → χρησιμοποιείται η πιο ακριβής."""
    from davinci import element_46 as e46
    return (e46.load_data()["messages"]["N4"],) if sum(v is not None for v in values) > 1 else ()


def _dedupe(msgs) -> tuple[str, ...]:
    return tuple(dict.fromkeys(m for m in msgs if m))


def section_waist(m: Measures, user: e01.UserCategories, weight_kg: float) -> Section | None:
    """Στοιχείο 05 (Πίνακες 2, 3, 6 · Κανόνες 1–5)."""
    from davinci import element_05 as e05
    if m.waist_cm is None:
        return None
    r = e05.assess(m.waist_cm, weight_kg, user)
    lines = [("Περιφέρεια μέσης", f"{_n(r.waist_cm)} cm"), ("Λόγος μέσης/ύψους", _n(r.ratio, 2))]
    if r.category:
        lines.append(("Ταξινόμηση", r.category + (f" — {r.meaning}" if r.meaning else "")))
    if r.max_weight_for_classification_kg is not None:  # Κανόνας 1 (Πίνακας 8)
        lines.append(("Πότε αρχίζει η ταξινόμηση",
                      f"Όταν ο ΔΜΣ πέσει κάτω από 35 (βάρος κάτω από ≈ {_below(r.max_weight_for_classification_kg)} kg)"))
    if not user.pregnant_or_breastfeeding:  # Στοιχείο 01: εγκυμοσύνη/θηλασμός χωρίς στόχους
        lines.append(("Μέση-στόχος", f"κάτω από {_below(r.target_waist_below_cm)} cm"))
        if r.distance_to_target_cm > 0:
            lines.append(("Απόσταση από τον στόχο", f"{_n(r.distance_to_target_cm)} cm"))
    return Section("Μέση (Στοιχείο 05)", tuple(lines), _dedupe(r.messages))


def section_visceral(m: Measures, user: e01.UserCategories, weight_kg: float) -> Section | None:
    """Στοιχείο 06 (Πίνακες 2, 5 · Κανόνες 1–4)."""
    from davinci import element_06 as e06
    if all(x is None for x in (m.waist_cm, m.upper_thigh_cm, m.scale_visceral_level, m.ct_visceral_cm2,
                               m.visceral_volume)):
        return None
    r = e06.assess(user, weight_kg, waist_cm=m.waist_cm, upper_thigh_cm=m.upper_thigh_cm,
                   scale_level=m.scale_visceral_level, ct_cm2=m.ct_visceral_cm2, volume_value=m.visceral_volume)
    lines: list[tuple[str, str]] = []
    if r.source == e06.CT:  # Κανόνας 1, προτεραιότητα 1
        lines.append((f"Σπλαχνικό λίπος ({r.label}, τομογραφία)", f"{_n(r.value)} cm²"))
        lines.append(("Ταξινόμηση", r.category))
    elif r.source == e06.VOLUME:  # χωρίς όρια (Πίνακας 2)
        lines.append((f"Σπλαχνικό λίπος ({r.label}, DXA ή μαγνητική)", f"{_n(r.value)} (μονάδα της γνωμάτευσης)"))
    elif r.source == e06.EQUATION:  # Κανόνας 3
        lo, hi = r.range_cm2
        lines.append((f"Σπλαχνικό λίπος ({r.label})", f"≈ {_n(r.value, 0)} cm² (εύρος {_n(lo, 0)} – {_n(hi, 0)})"))
        lines.append(("Ταξινόμηση", r.category))
    elif r.source == e06.SCALE:  # Κανόνας 2: χωρίς μονάδα, χωρίς ταξινόμηση
        lines.append((f"Σπλαχνικό λίπος ({r.label})", _n(r.value)))
    if r.source != e06.SCALE and r.scale_level is not None:  # Κανόνας 2: καταγράφεται πάντα
        lines.append(("Τιμή ζυγαριάς (χωρίς μονάδα)", _n(r.scale_level)))
    if not lines and not r.messages:
        return None
    equation = m.waist_cm if m.upper_thigh_cm is not None else None
    n4 = _two_values(m.ct_visceral_cm2 or m.visceral_volume, equation, m.scale_visceral_level)
    return Section("Σπλαχνικό λίπος (Στοιχείο 06)", tuple(lines), _dedupe([*r.messages, *n4]), r.indicative)


def section_muscle(m: Measures, user: e01.UserCategories, weight_kg: float, fat_percent: float) -> Section:
    """Στοιχείο 07 (Πίνακας 3 · Κανόνες 1–7 · Συμπλήρωμα Α)· στόχος μόνο όταν το Στοιχείο 03 δίνει άλιπη-στόχο."""
    from davinci import element_07 as e07
    r = e07.assess(weight_kg, fat_percent, user, scale_percent=m.scale_muscle_percent,
                   medical_kg=m.medical_muscle_kg)
    if r.muscle_kg is None:
        return Section("Σκελετικοί μύες (Στοιχείο 07)", (), _dedupe(r.messages), r.indicative)
    lines = [("Σκελετικοί μύες", f"{_n(r.muscle_kg)} kg ({r.source})"),
             ("% της άλιπης μάζας", f"{_n(r.pct_of_ffm)}%"),
             ("% του βάρους (πληροφορία)", f"{_n(r.pct_of_weight)}%"),
             ("Δείκτης Σκελετικών Μυών (ΔΣΜ)", f"{_n(r.smi)} kg/m²")]
    if r.category:
        lines.append(("Ταξινόμηση", r.category + (f" ({r.out_of_reference_label})" if r.out_of_reference_label else "")))
    if r.dry_muscle_kg is not None:
        lo, hi = r.dry_muscle_range_kg
        lines.append(("Ξηροί μύες (εκτίμηση)", f"≈ {_n(r.dry_muscle_kg)} kg (εύρος {_n(lo)} – {_n(hi)})"))
    msgs = [*r.messages, *_two_values(m.medical_muscle_kg, m.scale_muscle_percent)]
    # Το Στοιχείο 03 δεν δίνει στόχο σε ανηλίκους, εγκυμοσύνη/θηλασμό ή λίπος μέσα στο εύρος (Κανόνας 8).
    wt = e03.weight_target(weight_kg, fat_percent, user)
    if wt.status == "υπολογίστηκε":  # Κανόνας 5 με την άλιπη-στόχο της Φάσης 1
        ffm_now = e03.ffm(weight_kg, fat_percent)
        ts = [e07.target(r.muscle_kg, ffm_now, p.ffm_kg) for p in wt.points]
        h2 = (user.height_cm / 100) ** 2
        lines.append(("Ενδεικτικός στόχος μυών",
                      " → ".join(f"≈ {_n(t.muscle_kg)} kg (ΔΣΜ ≈ {_n(t.muscle_kg / h2)})" for t in ts)))
        lines.append(("Ξηροί μύες-στόχος", " → ".join(f"≈ {_n(t.dry_muscle_kg)} kg" for t in ts)))
        msgs += [x for t in ts for x in t.messages]
        msgs += wt.messages  # η άλιπη-στόχος είναι εκτίμηση του Στοιχείου 03 (π.χ. «ενδεικτική»)
    indicative = r.indicative or wt.indicative
    return Section("Σκελετικοί μύες (Στοιχείο 07)", tuple(lines), _dedupe(msgs), indicative)


def _targets(weight_kg: float, fat_percent: float, user: e01.UserCategories):
    """Σημεία-στόχοι της Φάσης 1 (Στοιχείο 03)· () σε ανηλίκους, εγκυμοσύνη/θηλασμό ή όταν δεν χρειάζεται απώλεια."""
    return e03.weight_target(weight_kg, fat_percent, user).points  # σημεία μόνο όταν «υπολογίστηκε»


def section_ffmi(user: e01.UserCategories, weight_kg: float, fat_percent: float) -> Section:
    """Στοιχείο 03: άλιπη μάζα, ΔΑΜ (Πίνακες 2, 4 · Συμπλήρωματα Ε, Ζ) και άλιπη-στόχος (Φάση 1)."""
    r = e03.assess_ffmi(weight_kg, fat_percent, user)
    lines = [("Άλιπη μάζα", f"{_n(r.ffm_kg)} kg"), ("ΔΑΜ", f"{_n(r.ffmi)} kg/m²")]
    if user.sex == "Άνδρας":  # οι ενδείξεις των ανδρών χρησιμοποιούν τον κανονικοποιημένο ΔΑΜ (Πίνακας 4)
        lines.append(("Κανονικοποιημένος ΔΑΜ", _n(r.normalized_ffmi)))
    if e01.is_minor(user.age):  # ο Πίνακας 2 αφορά ενήλικες· σε ανηλίκους μόνο καταγραφή (σύμβαση εφαρμογής)
        return Section("Άλιπη μάζα και ΔΑΜ (Στοιχείο 03)", tuple(lines))
    if r.indications:
        lines.append(("Ένδειξη", " · ".join(r.indications)))
    if r.reference_range is not None:
        lo, hi = r.reference_range
        lines.append(("Φυσιολογικό εύρος (πληροφορία)", f"{_n(lo)} – {_n(hi)} · {r.reference_label}"))
    pts = _targets(weight_kg, fat_percent, user)
    if pts:
        lines.append(("Άλιπη μάζα-στόχος (Φάση 1)", " → ".join(
            f"≈ {_n(p.ffm_kg)} kg ({_signed(p.ffm_kg - r.ffm_kg)})" for p in pts)))
    return Section("Άλιπη μάζα και ΔΑΜ (Στοιχείο 03)", tuple(lines), _dedupe(r.messages), r.indicative)


def section_water(m: Measures, user: e01.UserCategories, weight_kg: float, fat_percent: float) -> Section:
    """Στοιχείο 08, Μέρος Α (Πίνακες 3, 5 · Κανόνες 1–3, 6–8)."""
    from davinci import element_08 as e08
    r = e08.assess_water(weight_kg, fat_percent, user, scale_percent=m.scale_water_percent,
                         medical_kg=m.isotope_water_kg)
    lines = [("Υγρά", f"{_n(r.water_kg)} kg ({r.source})"),
             ("Αναλογία νερού / άλιπη μάζα", _n(r.ratio, 3) + (f" — {r.ratio_label}" if r.ratio_label else "")),
             ("% του βάρους (πληροφορία)", f"{_n(r.pct_of_weight)}%")]
    if r.out_of_reference_label:
        lines.append(("Ηλικία", r.out_of_reference_label))
    msgs = [*r.messages, *_two_values(m.isotope_water_kg, m.scale_water_percent)]
    pts = _targets(weight_kg, fat_percent, user)
    if pts:  # Κανόνας 7
        ts = [e08.water_target(p.ffm_kg) for p in pts]
        lines.append(("Ενδεικτικός στόχος υγρών", " → ".join(f"≈ {_n(kg)} kg" for kg, _ in ts)))
        msgs.append(ts[0][1])
    return Section("Υγρά (Στοιχείο 08)", tuple(lines), _dedupe(msgs), r.indicative)


def section_hydration(m: Measures, user: e01.UserCategories) -> Section:
    """Στοιχείο 08, Μέρος Β (Πίνακες 6–8 · Κανόνες 4, 5)· η εξέταση αίματος είναι επίπεδο Professional."""
    from davinci import element_08 as e08
    r = e08.assess_hydration(user, previous_morning_weights=m.previous_morning_weights,
                             today_morning_weight=m.today_morning_weight, urine_color=m.urine_color,
                             thirst=m.thirst, serum_osmolality=m.serum_osmolality,
                             calc_osmolality_inputs=m.osmolality_inputs)
    lines = []
    if r.method == "εξέταση αίματος":  # Πίνακας 9
        b = e08.load_data()["blood"]
        if m.serum_osmolality is not None:
            lines.append(("Ωσμωτικότητα ορού (μετρημένη)", f"{_n(m.serum_osmolality)} mOsm/kg · όριο > {b['measured_gt']}"))
        else:
            calc = e08.calculated_osmolality(*m.osmolality_inputs)
            lines.append(("Υπολογισμένη ωσμωτικότητα", f"{_n(calc)} mmol/L · όριο > {b['calculated_gt']}"))
        lines.append(("Ενυδάτωση (εξέταση αίματος)", r.result or "κάτω από το όριο"))
    elif r.result is not None:
        lines.append((f"Ενυδάτωση ({r.method})", r.result))
        lines.append(("Θετικές ενδείξεις", f"{r.positives} από {len(r.evaluated)} ({', '.join(r.evaluated)})"))
    return Section("Ενυδάτωση (Στοιχείο 08)", tuple(lines), _dedupe(r.messages), r.indicative)


def _bone(m: Measures, user: e01.UserCategories, weight_kg: float, fat_percent: float):
    from davinci import element_09 as e09
    # Κανόνας 8· το μήνυμα αφορά μόνο ενήλικες εκτός εγκυμοσύνης/θηλασμού (Κανόνας 9), όπου υπάρχει εύρος λίπους
    losing = (not (e01.is_minor(user.age) or user.pregnant_or_breastfeeding)
              and e42.direction(fat_percent, user).direction == "loss")
    return e09.assess_bone(weight_kg, fat_percent, user, scale_percent=m.scale_bone_percent, dxa_kg=m.dxa_bone_kg,
                           losing_weight=losing)


def section_bone(m: Measures, user: e01.UserCategories, weight_kg: float, fat_percent: float) -> Section:
    """Στοιχείο 09 (Πίνακες 2, 3 · Κανόνες 1–3, 6–9)· η DXA είναι επίπεδο Professional."""
    from davinci import element_09 as e09
    r = _bone(m, user, weight_kg, fat_percent)
    lines = [("Οστικά μέταλλα", f"{'≈ ' if r.typical else ''}{_n(r.bone_kg)} kg" + (f" ({r.label})" if r.label else "")),
             ("% της άλιπης μάζας", f"{_n(r.pct_of_ffm)}%"), ("% του βάρους (πληροφορία)", f"{_n(r.pct_of_weight)}%")]
    h = e09.assess_health(user, t_score=m.t_score, z_score=m.z_score, menopause=m.menopause)
    if h.category:  # Πίνακες 7, 8: μόνο από DXA
        lines.append((f"Υγεία οστών ({h.index}, DXA)", h.category))
    n4 = _two_values(m.dxa_bone_kg, m.scale_bone_percent)
    return Section("Οστά (Στοιχείο 09)", tuple(lines), _dedupe([*r.messages, *n4, *h.messages]))


def section_ratios(m: Measures, user: e01.UserCategories, weight_kg: float, fat_percent: float,
                   muscle_kg: float | None, bone) -> Section:
    """Στοιχείο 10 (Πίνακες 3, 4, 5 · Κανόνες 1–6). Σήμερα 2 δεκαδικά, στόχοι 1 (όπως ο Πίνακας 8)."""
    from davinci import element_10 as e10
    measured_bone = None if bone.typical else bone.bone_kg  # όχι η τυπική τιμή (Στοιχείο 10, assess)
    r = e10.assess(weight_kg, fat_percent, user, muscle_kg=muscle_kg, bone_kg=measured_bone)
    lines = [("Λόγος άλιπης / λίπους", _n(r.ffm_to_fat, 2))]
    if r.compared_ratio is not None and measured_bone is not None:
        lines.append(("Σύγκριση με το όριο (χωρίς οστά)", _n(r.compared_ratio, 2)))
    if r.category:
        lines.append(("Ένδειξη", r.category))
    if r.muscle_to_fat is not None:
        lines.append(("Λόγος μυών / λίπους", _n(r.muscle_to_fat, 2)))
    if r.target_ffm_to_fat:
        lines.append(("Στόχος άλιπης / λίπους (προφίλ)", " – ".join(_n(x) for x in r.target_ffm_to_fat)))
    if r.target_muscle_to_fat:
        lines.append(("Στόχος μυών / λίπους (προφίλ)", " – ".join(_n(x) for x in r.target_muscle_to_fat)))
    return Section("Λόγοι άλιπης / λίπους και μυών / λίπους (Στοιχείο 10)", tuple(lines), _dedupe(r.messages),
                   r.indicative)


def section_analysis(m: Measures, user: e01.UserCategories, weight_kg: float, fat_percent: float,
                     muscle_kg: float | None, bone) -> Section:
    """Στοιχείο 03, Συμπληρώματα Β και Γ: ανάλυση της άλιπης μάζας σε δύο τρόπους (Α υλικό, Β ιστοί).
    Νερό μόνο από τη ζυγαριά (το «0,73 × άλιπη» θα έδινε κυκλικό αποτέλεσμα, Πίνακας Γ4)."""
    water = m.isotope_water_kg if m.isotope_water_kg is not None else (
        None if m.scale_water_percent is None else e03.scale_kg(weight_kg, m.scale_water_percent))
    # Το μήνυμα του 09 για την τυπική τιμή οστών (Πίνακας Γ4) εμφανίζεται ήδη στην ενότητα «Οστά».
    a = e03.analysis(weight_kg, fat_percent, user, water_kg=water, bone_kg=bone.bone_kg, muscle_kg=muscle_kg,
                     bone_typical=bone.typical)

    def row(name, kg, typical=False):
        estimate = typical or name == "Ξηροί μύες"  # «≈ … (εκτίμηση)», Πίνακας Γ2
        label = " (τυπική τιμή)" if typical else " (εκτίμηση)" if estimate else ""
        return (name + label, ("≈ " if estimate else "") + _n(kg),
                f"{_n(a.pct_of_ffm(kg))}%", f"{_n(kg / weight_kg * 100)}%")
    rows = [("Γραμμή", "kg", "% άλιπης", "% βάρους"), row("Άλιπη μάζα", a.ffm_kg), ("Α. Από τι υλικό", "", "", "")]
    rows += [row(x.name, x.kg, x.typical) for x in a.material]
    if a.tissues:
        rows += [("Β. Από ποιους ιστούς", "", "", "")] + [row(x.name, x.kg, x.typical) for x in a.tissues]
    return Section("Ανάλυση άλιπης μάζας (Στοιχείο 03)", (), _dedupe(a.messages), table=tuple(rows),
                   warnings=_dedupe(a.warnings))


def _cm(x: float | None) -> list[tuple[str, str]]:
    return [] if x is None else [("Μέτρηση", f"{_n(x)} cm")]


def section_hip(m: Measures, user: e01.UserCategories, weight_kg: float, fat_percent: float) -> Section | None:
    """Στοιχείο 11 (Πίνακες 3–6): καμία ταξινόμηση· εκτίμηση στο βάρος-στόχο (Φάση 1, Στοιχείο 03).
    Η ενότητα εμφανίζεται όταν υπάρχει μέτρηση ή εκτίμηση (σύμβαση εφαρμογής)."""
    from davinci import element_11 as e11
    pts = _targets(weight_kg, fat_percent, user)
    r = e11.assess(user, m.hip_cm, [(p.weight_kg, p.target_fat_percent) for p in pts])
    if m.hip_cm is None and not r.estimates:
        return None
    lines = _cm(m.hip_cm) + [
        (f"Αναμενόμενο ισχίο στα {_n(e.target_weight_kg)} kg (λίπος {_n(e.target_fat_percent)}%)",
         f"≈ {_n(e.hip_cm)} cm ({_n(e.range_cm[0])} – {_n(e.range_cm[1])})") for e in r.estimates]
    if r.out_of_reference_label:
        lines.append(("Ηλικία", r.out_of_reference_label))
    return Section("Ισχίο (Στοιχείο 11)", tuple(lines), _dedupe(r.messages), r.indicative)


def section_neck(m: Measures, user: e01.UserCategories, fat_percent: float) -> Section | None:
    """Στοιχείο 12 (Πίνακες 3–5): καμία ταξινόμηση ή στόχος· μόνο ο έλεγχος STOP-Bang."""
    from davinci import element_12 as e12
    if m.neck_cm is None:
        return None
    rng = None if (e01.is_minor(user.age) or user.pregnant_or_breastfeeding) else e02.profile_range(user)
    status = None if rng is None else "εντός" if rng[0] <= fat_percent <= rng[1] else "εκτός"
    r = e12.assess(m.neck_cm, user, fat_status=status)
    lines = _cm(m.neck_cm)
    if r.stop_bang_flag is not None:
        limit = e12.load_data()["stop_bang"][user.sex]
        lines.append(("Όριο STOP-Bang", f"στο όριο ή πάνω (≥ {limit} cm)" if r.stop_bang_flag
                      else f"κάτω από το όριο ({limit} cm)"))
    if r.out_of_reference_label:
        lines.append(("Ηλικία", r.out_of_reference_label))
    return Section("Λαιμός (Στοιχείο 12)", tuple(lines), _dedupe(r.messages), r.indicative)


def section_chest(m: Measures, user: e01.UserCategories, weight_kg: float, fat_percent: float) -> Section | None:
    """Στοιχείο 13 (Πίνακες 3–8): καμία ταξινόμηση· εκτίμηση ANSUR II στο βάρος-στόχο."""
    from davinci import element_13 as e13
    pts = _targets(weight_kg, fat_percent, user)
    r = e13.assess(user, m.chest_cm, [p.weight_kg for p in pts])
    if m.chest_cm is None and not r.estimates:
        return None
    lines = _cm(m.chest_cm) + [
        (f"Αναμενόμενο στήθος στα {_n(e.weight_kg)} kg", f"≈ {_n(e.value_cm)} cm ({_n(e.range_cm[0])} – {_n(e.range_cm[1])})")
        for e in r.estimates]
    return Section("Στήθος (Στοιχείο 13)", tuple(lines), _dedupe(r.messages), r.indicative)


def _estimate_lines(name: str, ests, minimum: bool = False) -> list[tuple[str, str]]:
    """Εκτιμήσεις ANSUR II στο βάρος-στόχο· «≥» όταν η εκτίμηση είναι κατώτατο όριο (15, 16: Αθλητικό / Bodybuilding)."""
    return [(f"{name} στα {_n(e.weight_kg)} kg",
             f"≥ {_n(e.value_cm)} cm (εύρος {_n(e.range_cm[0])} – {_n(e.range_cm[1])})" if minimum
             else f"≈ {_n(e.value_cm)} cm ({_n(e.range_cm[0])} – {_n(e.range_cm[1])})") for e in ests]


def section_shoulders(m: Measures, user: e01.UserCategories, weight_kg: float, fat_percent: float) -> Section | None:
    """Στοιχείο 14 (Πίνακες 3–8): καμία ταξινόμηση· εκτίμηση ANSUR II στο βάρος-στόχο."""
    from davinci import element_14 as e14
    pts = _targets(weight_kg, fat_percent, user)
    r = e14.assess(user, m.shoulders_cm, [p.weight_kg for p in pts])
    if m.shoulders_cm is None and not r.estimates:
        return None
    lines = _cm(m.shoulders_cm) + _estimate_lines("Αναμενόμενοι ώμοι", r.estimates)
    return Section("Ώμοι (Στοιχείο 14)", tuple(lines), _dedupe(r.messages), r.indicative)


def _flexed_lines(label: str, f, name: str) -> list[tuple[str, str]]:
    lines = [] if f.measured_cm is None else [(label, f"{_n(f.measured_cm)} cm")]
    if f.today is not None:  # έλεγχος σήμερα (μήνυμα Γ)
        lo, hi = f.today.range_cm
        lines.append((f"Αναμενόμενο στο σημερινό βάρος", f"{_n(f.today.value_cm)} cm ({_n(lo)} – {_n(hi)})"))
    return lines + _estimate_lines(name, f.estimates, f.is_minimum)


def section_arm(m: Measures, user: e01.UserCategories, weight_kg: float, fat_percent: float) -> Section | None:
    """Στοιχείο 15: μπράτσο χαλαρό (όριο με διόρθωση ΔΜΣ, Πίνακες 3–4) και δικέφαλος σφιγμένος (ANSUR II)."""
    from davinci import element_15 as e15
    pts = _targets(weight_kg, fat_percent, user)
    rel = e15.assess_relaxed(m.arm_relaxed_cm, weight_kg, user)
    flx = e15.assess_flexed(m.biceps_flexed_cm, weight_kg, user, [p.weight_kg for p in pts])
    if m.arm_relaxed_cm is None and m.biceps_flexed_cm is None and not flx.estimates:
        return None
    lines: list[tuple[str, str]] = []
    if m.arm_relaxed_cm is not None:
        lines.append(("Μπράτσο χαλαρό", f"{_n(m.arm_relaxed_cm)} cm"))
    if rel.corrected_cm is not None:
        lines.append(("Διορθωμένο για τον ΔΜΣ", f"{_n(rel.corrected_cm)} cm"))
        lines.append(("Ταξινόμηση", rel.category))
    adult = not (user.age < e15.load_data()["relaxed_arm"]["min_age"] or user.pregnant_or_breastfeeding)
    if adult:  # Πίνακας 11: ελάχιστο για «Φυσιολογικό» στο σημερινό βάρος
        lines.append(("Ελάχιστο για «Φυσιολογικό» σήμερα", f"≥ {_n(e15.minimum_for_normal(weight_kg, user))} cm"))
    lines += _flexed_lines("Δικέφαλος σφιγμένος", flx, "Αναμενόμενος δικέφαλος")
    return Section("Μπράτσο και δικέφαλος (Στοιχείο 15)", tuple(lines), _dedupe([*rel.messages, *flx.messages]),
                   rel.indicative or flx.indicative)


def section_forearm(m: Measures, user: e01.UserCategories, weight_kg: float, fat_percent: float) -> Section | None:
    """Στοιχείο 16: πήχης χαλαρός (όριο Canda 2015, Πίνακας 3) και πήχης σφιγμένος (ANSUR II)."""
    from davinci import element_16 as e16
    pts = _targets(weight_kg, fat_percent, user)
    rel = e16.assess_relaxed(m.forearm_relaxed_cm, weight_kg, user)
    flx = e16.assess_flexed(m.forearm_flexed_cm, weight_kg, user, [p.weight_kg for p in pts])
    if m.forearm_relaxed_cm is None and m.forearm_flexed_cm is None and not flx.estimates:
        return None
    lines: list[tuple[str, str]] = []
    if m.forearm_relaxed_cm is not None:
        lines.append(("Πήχης χαλαρός", f"{_n(m.forearm_relaxed_cm)} cm"))
    if rel.category:
        limit = e16.load_data()["relaxed_forearm"][user.sex]["normal_ge"]
        lines.append(("Ταξινόμηση", f"{rel.category} (όριο {_n(limit)} cm)"))
    lines += _flexed_lines("Πήχης σφιγμένος", flx, "Αναμενόμενος πήχης")
    return Section("Πήχης (Στοιχείο 16)", tuple(lines), _dedupe([*rel.messages, *flx.messages]),
                   rel.indicative or flx.indicative)


def section_wrist(m: Measures, user: e01.UserCategories, weight_kg: float) -> Section | None:
    """Στοιχείο 17: μόνο καταγραφή για τις αναλογίες· ο σκελετός ορίζεται μόνο από το εύρος αγκώνα (Στοιχείο 30)."""
    from davinci import element_17 as e17
    if m.wrist_cm is None:
        return None
    r = e17.assess(m.wrist_cm, weight_kg, user, elbow_breadth_measured=False)  # το 30 είναι Professional (Δόση 9)
    lines = _cm(m.wrist_cm)
    if not (e01.is_minor(user.age) or user.pregnant_or_breastfeeding):
        lines.append(("Σκελετός", r.frame))
    return Section("Καρπός (Στοιχείο 17)", tuple(lines), _dedupe(r.messages))


def section_thigh(m: Measures, user: e01.UserCategories, weight_kg: float, fat_percent: float) -> Section | None:
    """Στοιχείο 18: όριο υγείας 60 cm (προς επιβεβαίωση) και εκτίμηση ANSUR II· Αθλητικό / Bodybuilding: ≥ max(εκτίμηση, 60)."""
    from davinci import element_18 as e18
    pts = _targets(weight_kg, fat_percent, user)
    r = e18.assess(m.thigh_cm, weight_kg, user, [p.weight_kg for p in pts])
    if m.thigh_cm is None and not r.estimates:
        return None
    t = e18.load_data()["health_threshold"]
    lines = _cm(m.thigh_cm)
    if r.category:
        lines.append(("Ταξινόμηση", f"{r.category} ({t['cm']} cm · από μία μελέτη, προς επιβεβαίωση)"))
    if r.below_expected_today is not None:
        today = e18.estimate(weight_kg, user)
        lines.append(("Αναμενόμενο στο σημερινό βάρος",
                      f"{_n(today.value_cm)} cm ({_n(today.range_cm[0])} – {_n(today.range_cm[1])})"))
    for i, e in enumerate(r.estimates):
        rng = f"{_n(e.range_cm[0])} – {_n(e.range_cm[1])}"
        value = (f"≥ {_n(r.minimums_cm[i])} cm (εκτίμηση {_n(e.value_cm)}, εύρος {rng})" if r.minimums_cm
                 else f"≈ {_n(e.value_cm)} cm ({rng})")
        lines.append((f"Αναμενόμενος μηρός στα {_n(e.weight_kg)} kg", value))
    return Section("Μηρός (Στοιχείο 18)", tuple(lines), _dedupe(r.messages), r.indicative)


def section_knee(m: Measures, user: e01.UserCategories, weight_kg: float, fat_percent: float) -> Section | None:
    """Στοιχείο 19: χωρίς όριο και στόχο· εκτίμηση ANSUR II και βάση για την αναλογία Μηρού-Γόνατος."""
    from davinci import element_19 as e19
    pts = _targets(weight_kg, fat_percent, user)
    r = e19.assess(m.knee_cm, user, [p.weight_kg for p in pts], swollen_or_injured=m.knee_swollen)
    if m.knee_cm is None and not r.estimates:
        return None
    lines = _cm(m.knee_cm) + _estimate_lines("Αναμενόμενο πάνω από το γόνατο", r.estimates)
    return Section("Πάνω από το γόνατο (Στοιχείο 19)", tuple(lines), _dedupe(r.messages), r.indicative)


def section_calf(m: Measures, user: e01.UserCategories, weight_kg: float, fat_percent: float) -> Section | None:
    """Στοιχείο 20: όριο με διόρθωση ΔΜΣ ανά καταγωγή (Πίνακες 3–4) και εκτίμηση ANSUR II·
    Αθλητικό / Bodybuilding: ≥ max(εκτίμηση, τιμή για «φυσιολογική» στο βάρος-στόχο)."""
    from davinci import element_20 as e20
    pts = _targets(weight_kg, fat_percent, user)
    r = e20.assess(m.calf_cm, weight_kg, user, [p.weight_kg for p in pts], edema=m.leg_edema)
    if m.calf_cm is None and not r.estimates:
        return None
    lines = _cm(m.calf_cm)
    if r.corrected_cm is not None:
        lines.append(("Διορθωμένη για τον ΔΜΣ", f"{_n(r.corrected_cm)} cm"))
        lines.append(("Ταξινόμηση", r.category))
        lines.append(("Τιμή για «φυσιολογική» σήμερα", f"≥ {_n(e20.normal_value_at(weight_kg, user))} cm"))
    if r.below_expected_today is not None:
        today = e20.estimate(weight_kg, user)
        lines.append(("Αναμενόμενο στο σημερινό βάρος",
                      f"{_n(today.value_cm)} cm ({_n(today.range_cm[0])} – {_n(today.range_cm[1])})"))
    for i, e in enumerate(r.estimates):
        rng = f"{_n(e.range_cm[0])} – {_n(e.range_cm[1])}"
        normal = f"για «φυσιολογική» ≥ {_n(r.normal_values_at_targets[i])} cm"
        value = (f"≥ {_n(r.minimums_cm[i])} cm (εκτίμηση {_n(e.value_cm)}, εύρος {rng} · {normal})" if r.minimums_cm
                 else f"≈ {_n(e.value_cm)} cm ({rng} · {normal})")
        lines.append((f"Αναμενόμενη γάμπα στα {_n(e.weight_kg)} kg", value))
    return Section("Γάμπα (Στοιχείο 20)", tuple(lines), _dedupe(r.messages), r.indicative)


def ankle_field_note() -> str:
    """Στοιχείο 21, μήνυμα Τ: «Πάντα, δίπλα στο πεδίο καταχώρησης»."""
    from davinci import element_21 as e21
    return e21.load_data()["messages"]["T"]


def section_ankle(m: Measures, user: e01.UserCategories, weight_kg: float, fat_percent: float) -> Section | None:
    """Στοιχείο 21: χωρίς όριο και στόχο· εκτίμηση ANSUR II σήμερα και στο βάρος-στόχο.
    Το μήνυμα Τ εμφανίζεται δίπλα στο πεδίο, όχι εδώ."""
    from davinci import element_21 as e21
    pts = _targets(weight_kg, fat_percent, user)
    r = e21.assess(m.ankle_cm, weight_kg, user, [p.weight_kg for p in pts], edema=m.leg_edema,
                   injured=m.ankle_injured)
    if m.ankle_cm is None and not r.estimates:
        return None
    lines = _cm(m.ankle_cm)
    if r.today is not None:
        lines.append(("Αναμενόμενο στο σημερινό βάρος",
                      f"{_n(r.today.value_cm)} cm ({_n(r.today.range_cm[0])} – {_n(r.today.range_cm[1])})"))
    lines += _estimate_lines("Αναμενόμενος αστράγαλος", r.estimates)
    msgs = [x for x in r.messages if x != ankle_field_note()]
    return Section("Αστράγαλος (Στοιχείο 21)", tuple(lines), _dedupe(msgs), r.indicative)


def section_whr(m: Measures, user: e01.UserCategories, weight_kg: float, fat_percent: float) -> Section | None:
    """Στοιχείο 22: ταξινόμηση με το όριο του ΠΟΥ (Πίνακας 2)· πληροφορία μέσης ανά βάρος-στόχο (Πίνακας 5)."""
    from davinci import element_22 as e22
    pts = _targets(weight_kg, fat_percent, user)
    r = e22.assess(m.waist_cm, m.hip_cm, user, [(p.weight_kg, p.target_fat_percent) for p in pts])
    if m.waist_cm is None and m.hip_cm is None and not r.rows:
        return None
    lines = []
    if r.ratio is not None:
        lines.append(("Λόγος μέσης / ισχίου", _n(r.ratio, 2)))
    if r.category:
        lines.append(("Ταξινόμηση", r.category))
    for w in r.rows:
        lines.append((f"Μέση στα {_n(w.target_weight_kg)} kg (λίπος {_n(w.target_fat_percent)}%)",
                      f"κάτω από {_n(w.waist_for_both_cm)} cm (ΛΜΙ: κάτω από {_n(w.waist_for_whr_cm)} · "
                      f"μέση/ύψος: κάτω από {_n(w.waist_for_whtr_cm)} · ισχίο ≈ {_n(w.expected_hip_cm)})"))
    if r.out_of_reference_label:
        lines.append(("Ηλικία", r.out_of_reference_label))
    return Section("Λόγος μέσης / ισχίου (Στοιχείο 22)", tuple(lines), _dedupe(r.messages), r.indicative)


def _percentile_section(title, label, r, d, user, row_line, field_note=None) -> Section:
    """Στοιχεία 23–25: τιμή, ζώνη εκατοστημορίου ANSUR II και γραμμές ανά βάρος-στόχο, μόνο όταν ο πίνακας
    «Τι εμφανίζεται» του εγγράφου έχει το μήνυμα Ε για το φύλο και το προφίλ."""
    lines = []
    if r.ratio is not None:
        lines.append((label, _n(r.ratio, 2)))
    if r.band:
        lines.append(("Εκατοστημόριο ANSUR II", r.band))
    group = "athletic" if user.profile in d["show"]["athletic_profiles"] else "health"
    if "E" in d["show"][user.sex][group]:
        lines += [row_line(x) for x in r.rows]
    msgs = [x for x in r.messages if x != field_note]
    return Section(title, tuple(lines), _dedupe(msgs), r.indicative)


def section_chest_waist(m: Measures, user: e01.UserCategories, weight_kg: float, fat_percent: float) -> Section | None:
    """Στοιχείο 23: χωρίς όριο και στόχο· εκατοστημόριο και ελάχιστος λόγος στο βάρος-στόχο (Πίνακες 5, 7, 8)."""
    from davinci import element_23 as e23
    pts = _targets(weight_kg, fat_percent, user)
    r = e23.assess(m.chest_cm, m.waist_cm, user, [p.weight_kg for p in pts])
    if m.chest_cm is None and m.waist_cm is None and not r.rows:
        return None
    return _percentile_section(
        "Λόγος στήθους / μέσης (Στοιχείο 23)", "Λόγος στήθους / μέσης", r, e23.load_data(), user,
        lambda x: (f"Ελάχιστος λόγος στα {_n(x.weight_kg)} kg",
                   f"≥ {_n(x.ratio, 2)} (στήθος ≈ {_n(x.numerator_cm)} cm · μέση κάτω από {_n(x.denominator_cm)} cm)"))


def section_shoulders_waist(m: Measures, user: e01.UserCategories, weight_kg: float,
                            fat_percent: float) -> Section | None:
    """Στοιχείο 24: χωρίς όριο και στόχο· εκατοστημόριο και ελάχιστος λόγος στο βάρος-στόχο (Πίνακες 6, 8, 9)."""
    from davinci import element_24 as e24
    pts = _targets(weight_kg, fat_percent, user)
    r = e24.assess(m.shoulders_cm, m.waist_cm, user, [p.weight_kg for p in pts])
    if m.shoulders_cm is None and m.waist_cm is None and not r.rows:
        return None
    return _percentile_section(
        "Λόγος ώμων / μέσης (Στοιχείο 24)", "Λόγος ώμων / μέσης", r, e24.load_data(), user,
        lambda x: (f"Ελάχιστος λόγος στα {_n(x.weight_kg)} kg",
                   f"≥ {_n(x.ratio, 2)} (ώμοι ≈ {_n(x.numerator_cm)} cm · μέση κάτω από {_n(x.denominator_cm)} cm)"))


def arm_field_note() -> str:
    """Στοιχείο 25, μήνυμα Τ: «Πάντα, δίπλα στα πεδία καταχώρησης»."""
    from davinci import element_25 as e25
    return e25.load_data()["messages"]["T"]


def section_forearm_biceps(m: Measures, user: e01.UserCategories, weight_kg: float,
                           fat_percent: float) -> Section | None:
    """Στοιχείο 25: μόνο σφιγμένες τιμές· εκατοστημόριο και αναμενόμενος λόγος στο βάρος-στόχο (Πίνακες 3, 6, 7).
    Το μήνυμα Τ εμφανίζεται δίπλα στα πεδία, όχι εδώ."""
    from davinci import element_25 as e25
    pts = _targets(weight_kg, fat_percent, user)
    r = e25.assess(m.forearm_flexed_cm, m.biceps_flexed_cm, user, [p.weight_kg for p in pts],
                   injured_or_swollen=m.arm_injured)
    if m.forearm_flexed_cm is None and m.biceps_flexed_cm is None and not r.rows:
        return None
    return _percentile_section(
        "Λόγος πήχη / δικεφάλου (Στοιχείο 25)", "Λόγος πήχη / δικεφάλου (σφιγμένοι)", r, e25.load_data(), user,
        _expected_ratio_rows("πήχης", "δικέφαλος"), field_note=arm_field_note())


def field_note(element: int) -> str:
    """Μήνυμα Τ των Στοιχείων 25–29: «Πάντα, δίπλα στα πεδία καταχώρησης»."""
    import importlib
    return importlib.import_module(f"davinci.element_{element}").load_data()["messages"]["T"]


def _expected_ratio_rows(name_num: str, name_den: str):
    return lambda x: (f"Αναμενόμενος λόγος στα {_n(x.weight_kg)} kg",
                      f"≈ {_n(x.ratio, 2)} ({name_num} {_n(x.numerator_cm)} cm · {name_den} {_n(x.denominator_cm)} cm)")


def section_thigh_calf(m: Measures, user: e01.UserCategories, weight_kg: float, fat_percent: float) -> Section | None:
    """Στοιχείο 26 (Πίνακες 3, 5, 6, 8). Τραυματισμός: δηλωμένος στο πόδι ή στον αστράγαλο (σύμβαση εφαρμογής)."""
    from davinci import element_26 as e26
    pts = _targets(weight_kg, fat_percent, user)
    r = e26.assess(m.thigh_cm, m.calf_cm, user, [p.weight_kg for p in pts], edema=m.leg_edema,
                   injured=m.leg_injured or m.ankle_injured)
    if m.thigh_cm is None and m.calf_cm is None and not r.rows:
        return None
    return _percentile_section("Λόγος μηρού / γάμπας (Στοιχείο 26)", "Λόγος μηρού / γάμπας", r, e26.load_data(),
                               user, _expected_ratio_rows("μηρός", "γάμπα"), field_note(26))


def section_wrist_biceps(m: Measures, user: e01.UserCategories, weight_kg: float,
                         fat_percent: float) -> Section | None:
    """Στοιχείο 27 (Πίνακες 4, 7, 8, 10): καρπός / σφιγμένος δικέφαλος."""
    from davinci import element_27 as e27
    pts = _targets(weight_kg, fat_percent, user)
    r = e27.assess(m.wrist_cm, m.biceps_flexed_cm, user, [p.weight_kg for p in pts],
                   injured_or_swollen=m.arm_injured)
    if m.wrist_cm is None and m.biceps_flexed_cm is None and not r.rows:
        return None
    return _percentile_section("Λόγος καρπού / δικεφάλου (Στοιχείο 27)", "Λόγος καρπού / δικεφάλου (σφιγμένος)", r,
                               e27.load_data(), user, _expected_ratio_rows("καρπός", "δικέφαλος"), field_note(27))


def section_ankle_calf(m: Measures, user: e01.UserCategories, weight_kg: float, fat_percent: float) -> Section | None:
    """Στοιχείο 28 (Πίνακες 4, 7, 8, 10): οίδημα ή τραυματισμός στο πόδι → δεν υπολογίζεται· λιποίδημα → καταγραφή."""
    from davinci import element_28 as e28
    pts = _targets(weight_kg, fat_percent, user)
    r = e28.assess(m.ankle_cm, m.calf_cm, user, [p.weight_kg for p in pts], lipedema=m.lipedema,
                   edema_or_injury=m.leg_edema or m.ankle_injured or m.leg_injured)
    if m.ankle_cm is None and m.calf_cm is None and not r.rows:
        return None
    return _percentile_section("Λόγος αστραγάλου / γάμπας (Στοιχείο 28)", "Λόγος αστραγάλου / γάμπας", r,
                               e28.load_data(), user, _expected_ratio_rows("αστράγαλος", "γάμπα"), field_note(28))


def section_thigh_knee(m: Measures, user: e01.UserCategories, weight_kg: float, fat_percent: float) -> Section | None:
    """Στοιχείο 29 (Πίνακες 4, 7, 8, 10): γόνατο πρησμένο ή τραυματισμένο → δεν υπολογίζεται· λιποίδημα → καταγραφή."""
    from davinci import element_29 as e29
    pts = _targets(weight_kg, fat_percent, user)
    r = e29.assess(m.thigh_cm, m.knee_cm, user, [p.weight_kg for p in pts], lipedema=m.lipedema,
                   knee_swollen_or_injured=m.knee_swollen)
    if m.thigh_cm is None and m.knee_cm is None and not r.rows:
        return None
    return _percentile_section("Λόγος μηρού / γονάτου (Στοιχείο 29)", "Λόγος μηρού / γονάτου", r, e29.load_data(),
                               user, _expected_ratio_rows("μηρός", "πάνω από το γόνατο"), field_note(29))


def guide_extra(field: str, sex: str) -> tuple[str, ...]:
    """Επιπλέον κείμενο στο ⓘ ανά φύλο (Στοιχείο 13, Πίνακας 11: σημείωση για γυναίκες)."""
    from davinci import element_13 as e13
    if field == "στήθος" and sex == "Γυναίκα":
        return (e13.load_data()["messages"]["women_info"],)
    return ()


def measurement_sections(inp: PlanInput, m: Measures) -> tuple[tuple[Section, ...], tuple[str, ...]]:
    """Όλες οι ενότητες της καρτέλας «Μετρήσεις»· επιστρέφει (ενότητες, σφάλματα).
    Ένα μήνυμα που εμφανίστηκε ήδη σε προηγούμενη ενότητα δεν επαναλαμβάνεται, εκτός αν η ενότητα θα έμενε
    χωρίς κανένα μήνυμα: τότε κρατά το πρώτο της (π.χ. το ίδιο μήνυμα οιδήματος στα Στοιχεία 26 και 28),
    ώστε να φαίνεται γιατί ο λόγος δεν υπολογίστηκε (σύμβαση εφαρμογής)."""
    from davinci import element_07 as e07
    try:
        user = _user(inp)
        w, f = inp.weight_kg, inp.fat_percent
        muscle = e07.assess(w, f, user, scale_percent=m.scale_muscle_percent, medical_kg=m.medical_muscle_kg).muscle_kg
        bone = _bone(m, user, w, f)
        out = [section_ffmi(user, w, f), section_waist(m, user, w), section_hip(m, user, w, f),
               section_neck(m, user, f), section_chest(m, user, w, f), section_shoulders(m, user, w, f),
               section_arm(m, user, w, f), section_forearm(m, user, w, f), section_wrist(m, user, w),
               section_thigh(m, user, w, f), section_knee(m, user, w, f), section_calf(m, user, w, f),
               section_ankle(m, user, w, f), section_whr(m, user, w, f), section_chest_waist(m, user, w, f),
               section_shoulders_waist(m, user, w, f), section_forearm_biceps(m, user, w, f),
               section_thigh_calf(m, user, w, f), section_wrist_biceps(m, user, w, f),
               section_ankle_calf(m, user, w, f), section_thigh_knee(m, user, w, f),
               section_visceral(m, user, w),
               section_muscle(m, user, w, f), section_water(m, user, w, f), section_hydration(m, user),
               section_bone(m, user, w, f), section_ratios(m, user, w, f, muscle, bone),
               section_analysis(m, user, w, f, muscle, bone)]
    except (e01.InvalidInput, ValueError, LookupError) as exc:
        return (), (str(exc),)
    seen: set[str] = set()
    result = []
    for sec in out:
        if sec is None:
            continue
        fresh = tuple(x for x in sec.messages if x not in seen) or sec.messages[:1]
        seen.update(fresh)
        result.append(Section(sec.title, sec.lines, fresh, sec.indicative, sec.table, sec.warnings))
    return tuple(result), ()


def level_info(level: str) -> tuple[str, ...]:
    """Στοιχείο 46: όργανα του επιπέδου (Πίνακας 1) και, στο Professional, το μήνυμα Ν3."""
    from davinci import element_46 as e46
    d = e46.load_data()
    out = ["Όργανα: " + ", ".join(d["tools"][level]) + "."]
    if level == "Professional":
        out.append(d["messages"]["N3"])
    return tuple(out)


def medical_message() -> str:
    from davinci import element_46 as e46
    return e46.medical_entry_message()


def calipers() -> tuple[str, ...]:
    from davinci import element_33 as e33
    return tuple(e33.load_data()["calipers"])
