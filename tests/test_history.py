"""Ιστορικό μετρήσεων (history): αποθήκευση του αποτελέσματος όπως εμφανίζεται, αντίγραφο, εξαγωγή σε docx."""

import io
import json
import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from davinci import app_logic as al  # noqa: E402
from davinci import history as hist  # noqa: E402
from davinci import results_view as rv  # noqa: E402

from test_results_view import CASES  # noqa: E402


def entry(name="άνδρας 139 kg, όλα τα πεδία", day=None):
    inp, m = CASES[name]
    if day:
        inp = al.PlanInput(**{**inp.__dict__, "today": day})
    groups, errors = rv.results(inp, m)
    assert not errors
    return hist.snapshot(inp, m, groups), groups


@pytest.mark.parametrize("name", CASES)
def test_snapshot_keeps_every_row_and_info_as_shown(name):
    e, groups = entry(name)
    json.dumps(e)  # σε μορφή JSON
    back = [hist.card_from(c) for g in e["results"] for p in g["parts"] for c in p["cards"]]
    shown = [c for g in groups for c in g.cards]
    assert [c.rows for c in back] == [c.rows for c in shown]
    assert [c.info for c in back] == [c.info for c in shown]
    assert [g["title"] for g in e["results"]] == [g.title for g in groups]


def test_label_and_order():
    a, _ = entry(day=date(2026, 10, 4))
    b, _ = entry(day=date(2026, 9, 1))
    h, replaced = hist.add([a], b)
    assert not replaced and [x["date"] for x in h] == ["2026-09-01", "2026-10-04"]
    assert hist.label(1, h[0]) == "1. 01/09/2026 · 138,9 kg · Λίπος 43,2% · Μύες 29,9% · Υγρά 39,0%"
    h2, replaced = hist.add(h, a)  # ίδια ημερομηνία: αντικατάσταση
    assert replaced and len(h2) == 2
    assert [x["date"] for x in hist.remove(h2, "2026-09-01")] == ["2026-10-04"]


def test_backup_round_trip_and_bad_files():
    a, _ = entry()
    text = hist.to_json([a])
    assert hist.from_json(text) == [a] and hist.from_json(text.encode()) == [a]
    assert hist.merge([], hist.from_json(text)) == [a]
    for bad in ("όχι json", "{}", json.dumps({"format": "x", "measurements": []}),
                json.dumps({"format": hist.FORMAT, "version": 99, "measurements": []}),
                json.dumps({"format": hist.FORMAT, "measurements": [{"date": "2026-01-01"}]})):
        with pytest.raises(hist.BadBackup):
            hist.from_json(bad)


def test_docx_has_every_section_and_row_vertically():
    from docx import Document
    e, groups = entry()
    doc = Document(io.BytesIO(hist.to_docx(e, 1)))
    text = [p.text for p in doc.paragraphs]
    assert text[0] == "DaVinci Fitness — Μέτρηση 04/10/2026 (μέτρηση 1)"
    for g in groups:
        assert g.title in text
    joined = "\n".join(text)
    for c in (c for g in groups for c in g.cards):
        for r in c.rows:
            assert r.name in joined
            if r.target_word:
                assert f"({r.target_word}: {r.target})" in joined
    w = next(p for p in doc.paragraphs if p.text.startswith("Βάρος: 138,9 kg"))
    assert "▼ −59,7 kg έως −71,1 kg" in w.text
    red = [r for r in w.runs if r.text.strip().startswith("▼")][0]
    assert str(red.font.color.rgb) == "D93B3B"
    assert hist.docx_name(e) == "DaVinci_Metrisi_2026-10-04.docx"
