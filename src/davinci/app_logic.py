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
