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
        level="Normal")


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
    if m.waist_cm is None and m.upper_thigh_cm is None and m.scale_visceral_level is None:
        return None
    r = e06.assess(user, weight_kg, waist_cm=m.waist_cm, upper_thigh_cm=m.upper_thigh_cm,
                   scale_level=m.scale_visceral_level)
    lines: list[tuple[str, str]] = []
    if r.source == e06.EQUATION:  # Κανόνας 3
        lo, hi = r.range_cm2
        lines.append((f"Σπλαχνικό λίπος ({r.label})", f"≈ {_n(r.value, 0)} cm² (εύρος {_n(lo, 0)} – {_n(hi, 0)})"))
        lines.append(("Ταξινόμηση", r.category))
    elif r.source == e06.SCALE:  # Κανόνας 2: χωρίς μονάδα, χωρίς ταξινόμηση
        lines.append((f"Σπλαχνικό λίπος ({r.label})", _n(r.value)))
    if r.source != e06.SCALE and r.scale_level is not None:  # Κανόνας 2: καταγράφεται πάντα
        lines.append(("Τιμή ζυγαριάς (χωρίς μονάδα)", _n(r.scale_level)))
    if not lines and not r.messages:
        return None
    return Section("Σπλαχνικό λίπος (Στοιχείο 06)", tuple(lines), _dedupe(r.messages), r.indicative)


def section_muscle(m: Measures, user: e01.UserCategories, weight_kg: float, fat_percent: float) -> Section:
    """Στοιχείο 07 (Πίνακας 3 · Κανόνες 1–7 · Συμπλήρωμα Α)· στόχος μόνο όταν το Στοιχείο 03 δίνει άλιπη-στόχο."""
    from davinci import element_07 as e07
    r = e07.assess(weight_kg, fat_percent, user, scale_percent=m.scale_muscle_percent)
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
    msgs = list(r.messages)
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
    r = e08.assess_water(weight_kg, fat_percent, user, scale_percent=m.scale_water_percent)
    lines = [("Υγρά", f"{_n(r.water_kg)} kg ({r.source})"),
             ("Αναλογία νερού / άλιπη μάζα", _n(r.ratio, 3) + (f" — {r.ratio_label}" if r.ratio_label else "")),
             ("% του βάρους (πληροφορία)", f"{_n(r.pct_of_weight)}%")]
    if r.out_of_reference_label:
        lines.append(("Ηλικία", r.out_of_reference_label))
    msgs = list(r.messages)
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
                             thirst=m.thirst)
    lines = []
    if r.result is not None:
        lines.append((f"Ενυδάτωση ({r.method})", r.result))
        lines.append(("Θετικές ενδείξεις", f"{r.positives} από {len(r.evaluated)} ({', '.join(r.evaluated)})"))
    return Section("Ενυδάτωση (Στοιχείο 08)", tuple(lines), _dedupe(r.messages), r.indicative)


def _bone(m: Measures, user: e01.UserCategories, weight_kg: float, fat_percent: float):
    from davinci import element_09 as e09
    # Κανόνας 8· το μήνυμα αφορά μόνο ενήλικες εκτός εγκυμοσύνης/θηλασμού (Κανόνας 9), όπου υπάρχει εύρος λίπους
    losing = (not (e01.is_minor(user.age) or user.pregnant_or_breastfeeding)
              and e42.direction(fat_percent, user).direction == "loss")
    return e09.assess_bone(weight_kg, fat_percent, user, scale_percent=m.scale_bone_percent, losing_weight=losing)


def section_bone(m: Measures, user: e01.UserCategories, weight_kg: float, fat_percent: float) -> Section:
    """Στοιχείο 09 (Πίνακες 2, 3 · Κανόνες 1–3, 6–9)· η DXA είναι επίπεδο Professional."""
    from davinci import element_09 as e09
    r = _bone(m, user, weight_kg, fat_percent)
    lines = [("Οστικά μέταλλα", f"{'≈ ' if r.typical else ''}{_n(r.bone_kg)} kg" + (f" ({r.label})" if r.label else "")),
             ("% της άλιπης μάζας", f"{_n(r.pct_of_ffm)}%"), ("% του βάρους (πληροφορία)", f"{_n(r.pct_of_weight)}%")]
    h = e09.assess_health(user)
    return Section("Οστά (Στοιχείο 09)", tuple(lines), _dedupe([*r.messages, *h.messages]))


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
    water = None if m.scale_water_percent is None else e03.scale_kg(weight_kg, m.scale_water_percent)
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


def guide_extra(field: str, inp: PlanInput) -> tuple[str, ...]:
    """Επιπλέον κείμενο στο ⓘ ανά χρήστη (Στοιχείο 13, Πίνακας 11: σημείωση για γυναίκες)."""
    from davinci import element_13 as e13
    if field == "στήθος" and inp.sex == "Γυναίκα":
        return (e13.load_data()["messages"]["women_info"],)
    return ()


def measurement_sections(inp: PlanInput, m: Measures) -> tuple[tuple[Section, ...], tuple[str, ...]]:
    """Όλες οι ενότητες της καρτέλας «Μετρήσεις»· επιστρέφει (ενότητες, σφάλματα).
    Ένα μήνυμα που εμφανίστηκε ήδη σε προηγούμενη ενότητα δεν επαναλαμβάνεται."""
    from davinci import element_07 as e07
    try:
        user = _user(inp)
        w, f = inp.weight_kg, inp.fat_percent
        muscle = e07.assess(w, f, user, scale_percent=m.scale_muscle_percent).muscle_kg
        bone = _bone(m, user, w, f)
        out = [section_ffmi(user, w, f), section_waist(m, user, w), section_hip(m, user, w, f),
               section_neck(m, user, f), section_chest(m, user, w, f), section_visceral(m, user, w),
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
        fresh = tuple(x for x in sec.messages if x not in seen)
        seen.update(fresh)
        result.append(Section(sec.title, sec.lines, fresh, sec.indicative, sec.table, sec.warnings))
    return tuple(result), ()
