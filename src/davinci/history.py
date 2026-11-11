"""Ιστορικό μετρήσεων (απόφαση του χρήστη 11/11/2026, σύμβαση συστήματος).

Δεν υπολογίζει τίποτα. Κρατά, για κάθε μέτρηση, την ημερομηνία, ό,τι συμπλήρωσε ο χρήστης και το αποτέλεσμα
της καρτέλας «Αποτελέσματα» όπως βγήκε εκείνη την ημέρα (`results_view.results`). Αν αλλάξει αργότερα κάποιος
υπολογισμός, το ιστορικό δείχνει ό,τι έδειχνε τότε.

Αποθήκευση: λίστα από λεξικά (JSON). Η οθόνη τα κρατά στη συνεδρία και ο χρήστης κατεβάζει / φορτώνει αντίγραφο
(αρχείο .json). Μία μέτρηση ανά ημερομηνία: νέα αποθήκευση της ίδιας ημερομηνίας αντικαθιστά την παλιά.
Εξαγωγή μίας μέτρησης σε .docx: όλα τα στοιχεία κάθετα, με τη σειρά της οθόνης.
"""

from __future__ import annotations

import io
import json
from dataclasses import fields
from datetime import date

from davinci import app_logic as al
from davinci import results_view as rv
from davinci.fmt import num

FORMAT = "davinci-history"
VERSION = 1


# --- αποθήκευση μίας μέτρησης ------------------------------------------------------------------------------------
def _plain(x):
    """Τιμές πεδίων σε μορφή JSON (ημερομηνίες ως «ΕΕΕΕ-ΜΜ-ΗΗ», πλειάδες ως λίστες)."""
    if isinstance(x, date):
        return x.isoformat()
    if isinstance(x, (list, tuple)):
        return [_plain(v) for v in x]
    if isinstance(x, dict):
        return {k: _plain(v) for k, v in x.items()}
    if hasattr(x, "__dataclass_fields__"):
        return {f.name: _plain(getattr(x, f.name)) for f in fields(x)}
    return x


def _row(r: rv.Row) -> dict:
    return {"name": r.name, "value": r.value, "missing": r.missing, "note": r.note,
            "change": [list(p) for p in r.change.parts] if r.change else None,
            "target_word": r.target_word, "target": r.target, "subs": [list(s) for s in r.subs], "level": r.level}


def _card(c: rv.Card) -> dict:
    return {"title": c.title, "rows": [_row(r) for r in c.rows], "needs": list(c.needs),
            "info": [[t, [list(ln) for ln in lines]] for t, lines in c.info],
            "table": [list(r) for r in c.table] if c.table and c.show_table else []}


def snapshot(inp: al.PlanInput, m: al.Measures, groups: tuple[rv.Group, ...]) -> dict:
    """Μία εγγραφή του ιστορικού: ημερομηνία, ό,τι δήλωσε ο χρήστης και το αποτέλεσμα όπως εμφανίζεται."""
    return {
        "date": inp.today.isoformat(),
        "input": _plain(inp),
        "measures": {k: v for k, v in _plain(m).items() if v not in (None, False, [], ())},
        "summary": {"weight_kg": inp.weight_kg, "fat_percent": inp.fat_percent,
                    "muscle_percent": m.scale_muscle_percent, "water_percent": m.scale_water_percent},
        "results": [{"title": g.title, "parts": [
            {"heading": p.heading, "fold": p.fold, "lines": [list(ln) for ln in p.lines], "todo": p.todo,
             "cards": [_card(c) for c in p.cards]} for p in g.parts]} for g in groups],
    }


# --- ιστορικό: προσθήκη, διαγραφή, σειρά --------------------------------------------------------------------------
def ordered(history: list[dict]) -> list[dict]:
    """Με σειρά ημερομηνίας: η πρώτη μέτρηση είναι η 1."""
    return sorted(history, key=lambda e: e["date"])


def add(history: list[dict], entry: dict) -> tuple[list[dict], bool]:
    """Νέα λίστα με την εγγραφή· True αν αντικατέστησε μέτρηση της ίδιας ημερομηνίας."""
    rest = [e for e in history if e["date"] != entry["date"]]
    return ordered([*rest, entry]), len(rest) != len(history)


def remove(history: list[dict], day: str) -> list[dict]:
    return [e for e in history if e["date"] != day]


def merge(history: list[dict], loaded: list[dict]) -> list[dict]:
    """Φόρτωση αντιγράφου: οι εγγραφές του αρχείου προστίθενται· για την ίδια ημερομηνία κρατιέται η του αρχείου."""
    out = list(history)
    for e in loaded:
        out, _ = add(out, e)
    return out


# --- κείμενα -----------------------------------------------------------------------------------------------------
def day_text(day: str) -> str:
    return date.fromisoformat(day).strftime("%d/%m/%Y")


def label(index: int, entry: dict) -> str:
    """«1. 11/11/2026 · 140,0 kg · Λίπος 42,5% · Μύες 30,0% · Υγρά 40,0%» (όσα συμπληρώθηκαν)."""
    s = entry["summary"]
    parts = [f"{index}. {day_text(entry['date'])}", f"{num(s['weight_kg'], 1)} kg", f"Λίπος {num(s['fat_percent'], 1)}%"]
    if s.get("muscle_percent") is not None:
        parts.append(f"Μύες {num(s['muscle_percent'], 1)}%")
    if s.get("water_percent") is not None:
        parts.append(f"Υγρά {num(s['water_percent'], 1)}%")
    return " · ".join(parts)


def row_from(d: dict) -> rv.Row:
    ch = rv.Change(tuple(tuple(p) for p in d["change"])) if d.get("change") else None
    return rv.Row(d["name"], d["value"], d["missing"], d["note"], ch, d["target_word"], d["target"],
                  tuple(tuple(s) for s in d["subs"]), d["level"])


def card_from(d: dict) -> rv.Card:
    return rv.Card(d["title"], rows=tuple(row_from(r) for r in d["rows"]), needs=tuple(d["needs"]),
                   info=tuple((t, tuple(tuple(ln) for ln in lines)) for t, lines in d["info"]))


# --- αντίγραφο (αρχείο .json) ------------------------------------------------------------------------------------
def to_json(history: list[dict]) -> str:
    return json.dumps({"format": FORMAT, "version": VERSION, "measurements": ordered(history)},
                      ensure_ascii=False, indent=1)


class BadBackup(ValueError):
    pass


def from_json(text: str | bytes) -> list[dict]:
    try:
        data = json.loads(text)
    except (ValueError, UnicodeDecodeError) as exc:
        raise BadBackup("Το αρχείο δεν είναι αντίγραφο του DaVinci Fitness.") from exc
    if not isinstance(data, dict) or data.get("format") != FORMAT or not isinstance(data.get("measurements"), list):
        raise BadBackup("Το αρχείο δεν είναι αντίγραφο του DaVinci Fitness.")
    if data.get("version", 0) > VERSION:
        raise BadBackup("Το αντίγραφο είναι από νεότερη έκδοση της εφαρμογής.")
    for e in data["measurements"]:
        if not isinstance(e, dict) or not {"date", "summary", "results"} <= set(e):
            raise BadBackup("Το αντίγραφο είναι ελλιπές.")
        date.fromisoformat(e["date"])
    return ordered(data["measurements"])


# --- εξαγωγή σε .docx ------------------------------------------------------------------------------------------------
_RED, _GREEN, _GREY = (0xD9, 0x3B, 0x3B), (0x1E, 0x9E, 0x55), (0x80, 0x80, 0x80)


def to_docx(entry: dict, index: int | None = None) -> bytes:
    """Μία μέτρηση σε Word: όλες οι ενότητες, κάθε στοιχείο κάθετα με τη σειρά της οθόνης.
    Μέτρηση · αλλαγή προς τον στόχο (κόκκινο ▼ / πράσινο ▲) · (Στόχος: …) με γκρι · τα κείμενα του «ⓘ info»."""
    from docx import Document
    from docx.shared import Cm, Pt, RGBColor

    doc = Document()
    doc.styles["Normal"].font.size = Pt(10.5)
    doc.styles["Normal"].font.name = "Calibri"

    def para(level: int = 0, space: float = 2):
        p = doc.add_paragraph()
        p.paragraph_format.left_indent = Cm(0.7 * level)
        p.paragraph_format.space_after = Pt(space)
        return p

    def run(p, text, bold=False, color=None, size=None, italic=False):
        r = p.add_run(text)
        r.bold, r.italic = bold, italic
        if color:
            r.font.color.rgb = RGBColor(*color)
        if size:
            r.font.size = Pt(size)
        return r

    title = "DaVinci Fitness — Μέτρηση " + day_text(entry["date"])
    doc.add_heading(title if index is None else f"{title} (μέτρηση {index})", level=0)
    for g in entry["results"]:
        doc.add_heading(g["title"], level=1)
        for p in g["parts"]:
            if len(g["parts"]) > 1 or p["heading"] != g["title"]:
                doc.add_heading(p["heading"], level=2)
            for a, b in p["lines"]:
                q = para()
                run(q, f"{a}: ", bold=True)
                run(q, b)
            if p.get("todo"):
                run(para(), p["todo"], italic=True, color=_GREY)
            for c in p["cards"]:
                for r in c["rows"]:
                    q = para(r["level"], 0)
                    run(q, r["name"], bold=True)
                    value = r["value"] if r["value"] is not None else r["missing"]
                    if value:
                        run(q, f": {value}")
                    if r.get("note") and r["value"] is not None:
                        run(q, f" · {r['note']}", color=_GREY)
                    for direction, text in r.get("change") or ():
                        run(q, f"  {text}", bold=True, color=_RED if direction == rv.DOWN else _GREEN)
                    for a, b in r["subs"]:
                        q = para(r["level"] + 1, 0)
                        run(q, f"{a}: ", bold=True)
                        run(q, b)
                    if r.get("target_word"):
                        run(para(r["level"], 6), f"({r['target_word']}: {r['target']})", color=_GREY, size=9)
                    else:
                        para(r["level"], 4)
                for n in c.get("needs") or ():
                    run(para(), n, italic=True, color=_GREY)
                if c.get("table"):
                    head, *body = c["table"]
                    t = doc.add_table(rows=1, cols=len(head))
                    t.style = "Table Grid"
                    for cell, h in zip(t.rows[0].cells, head):
                        cell.text = h
                    for row in body:
                        for cell, v in zip(t.add_row().cells, row):
                            cell.text = v
                if c.get("info"):
                    q = para(1, 0)
                    run(q, f"ⓘ info — {c['title']}", bold=True, color=_GREY, size=9)
                    for section, lines in c["info"]:
                        run(para(1, 0), section, bold=True, color=_GREY, size=9)
                        for a, b in lines:
                            q = para(1, 0)
                            if a:
                                run(q, f"{a}: ", bold=True, color=_GREY, size=9)
                            run(q, b, color=_GREY, size=9)
                    para(0, 4)
    out = io.BytesIO()
    doc.save(out)
    return out.getvalue()


def docx_name(entry: dict) -> str:
    return f"DaVinci_Metrisi_{entry['date']}.docx"
