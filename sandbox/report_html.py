#!/usr/bin/env python3
"""Report renderer (T0, research/PUBLIC_DEBUT_DESIGN_SCOPE.md) — checker JSON -> one
self-contained HTML file a practitioner can read, print, and attach to a dossier draft.

Deliberate properties:
  * PURE STDLIB (json/html/argparse only) — no engine import, no ifcopenshell, so the
    renderer runs anywhere the JSON travels.
  * SELF-CONTAINED output — inline CSS, system fonts, zero external requests (the same
    local-first posture as the engine; also print-clean).
  * IT-FIRST labels with EN hints (the practitioner audience is Italian; the terminology
    follows the statute's own words: altezza utile, rapporto aeroilluminante).
  * TERNARY IS FIRST-CLASS — CONFORME / VIOLAZIONE / NON DETERMINABILE each get a dignified
    visual state; "non determinabile" is explained, never rendered as an error.
  * EVERY dynamic string is HTML-escaped (IFC space names and notes are untrusted input).
  * DETERMINISTIC — no timestamps, no randomness: same JSON, byte-identical HTML.
  * NOT the P3 provenance report: this renders the verdict JSON verbatim and says so.
    No provenance claims, no certification language (claims discipline, ADR-010).

Usage:
    python report_html.py report.json                # writes report.html next to it
    python report_html.py report.json -o out.html --title "Pratica 123/2026"
Accepts either the checker report JSON or the API envelope (POST /evaluate response).
"""
from __future__ import annotations

import argparse
import html
import json
from typing import Optional

_E = html.escape


def _verdict(report: dict):
    """(css_class, IT label, EN hint) — mirrors api._verdict_word, H-1 included."""
    if report.get("spaces_evaluated", 0) == 0:
        return ("undet", "NON CERTIFICABILE", "not certifiable — no measurable space")
    if report.get("violations"):
        return ("fail", "VIOLAZIONE", "violations found")
    if report.get("spaces_undetermined"):
        return ("undet", "NON DETERMINABILE", "undetermined — could not be measured")
    return ("pass", "CONFORME", "compliant")


def _badge(val, na: bool = False) -> str:
    if na:
        return '<span class="badge na">n/a</span>'
    if val is True:
        return '<span class="badge pass">conforme</span>'
    if val is False:
        return '<span class="badge fail">violazione</span>'
    return '<span class="badge undet">non det.</span>'


def _fmt(v, unit: str = "") -> str:
    if v is None:
        return '<span class="dim">—</span>'
    return f"{_E(str(v))}{_E(unit)}"


_CSS = """
:root { --ink:#1c1c1c; --dim:#6b7280; --line:#e5e7eb; --pass:#1a7f37; --fail:#b91c1c;
        --undet:#b45309; --bg-pass:#ecfdf5; --bg-fail:#fef2f2; --bg-undet:#fffbeb; }
* { box-sizing:border-box; }
body { margin:2rem auto; max-width:60rem; padding:0 1rem; color:var(--ink);
       font:15px/1.55 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
       font-variant-numeric:tabular-nums; }
h1 { font-size:1.35rem; margin:0 0 .25rem; }
h2 { font-size:1.05rem; margin:2rem 0 .5rem; }
.sub, .dim { color:var(--dim); }
.sub { font-size:.9rem; }
.verdict { display:inline-block; margin:.75rem 0; padding:.45rem .9rem; border-radius:.4rem;
           font-weight:700; letter-spacing:.03em; }
.verdict.pass { background:var(--bg-pass); color:var(--pass); border:1px solid var(--pass); }
.verdict.fail { background:var(--bg-fail); color:var(--fail); border:1px solid var(--fail); }
.verdict.undet { background:var(--bg-undet); color:var(--undet); border:1px solid var(--undet); }
.tiles { display:flex; gap:1rem; flex-wrap:wrap; margin:.75rem 0 0; }
.tile { border:1px solid var(--line); border-radius:.4rem; padding:.55rem .9rem; min-width:9rem; }
.tile b { display:block; font-size:1.25rem; }
table { border-collapse:collapse; width:100%; margin-top:.5rem; font-size:.92rem; }
th, td { text-align:left; padding:.45rem .6rem; border-bottom:1px solid var(--line);
         vertical-align:top; }
th { font-size:.78rem; text-transform:uppercase; letter-spacing:.05em; color:var(--dim); }
td.num { text-align:right; white-space:nowrap; }
.badge { display:inline-block; padding:.1rem .5rem; border-radius:.65rem; font-size:.78rem;
         font-weight:600; white-space:nowrap; }
.badge.pass { background:var(--bg-pass); color:var(--pass); }
.badge.fail { background:var(--bg-fail); color:var(--fail); }
.badge.undet { background:var(--bg-undet); color:var(--undet); }
.badge.na { background:#f3f4f6; color:var(--dim); }
ul.notes { margin:.15rem 0 0; padding-left:1.1rem; color:var(--dim); font-size:.85rem; }
.legend { font-size:.85rem; color:var(--dim); margin-top:.5rem; }
footer { margin-top:2.5rem; padding-top:1rem; border-top:1px solid var(--line);
         font-size:.82rem; color:var(--dim); }
@media print { body { margin:0 auto; } .tile { break-inside:avoid; } }
"""


def render_report(data: dict, title: Optional[str] = None) -> str:
    """Render a checker report dict (or the API envelope wrapping one) to standalone HTML."""
    pack = None
    if "report" in data and "verdict" in data:          # API envelope
        pack = data.get("pack")
        report = data["report"]
        model_name = (data.get("model") or {}).get("filename")
    else:
        report = data
        model_name = report.get("model")
    vcls, vit, ven = _verdict(report)
    thr = report.get("thresholds", {})
    bars = (f"altezza abitabile ≥ {_fmt(thr.get('min_height_habitable_m'), ' m')} · "
            f"accessori ≥ {_fmt(thr.get('min_height_accessory_m'), ' m')} · "
            f"Salva Casa ≥ {_fmt(thr.get('min_height_salva_casa_m'), ' m')} · "
            f"aeroilluminante ≥ {_fmt(thr.get('aero_illuminating_ratio'))}")
    head_title = _E(title or "Rapporto di verifica — abitabilità")
    pack_line = ""
    if pack:
        pack_line = (f'<div class="sub">Pacchetto normativo (rule pack): '
                     f'<b>{_E(str(pack.get("id")))}</b> — {_E(str(pack.get("description")))}'
                     f'</div>')
    rows = []
    for f in report.get("findings", []):
        occ = str(f.get("occupancy"))
        aero_na = occ == "accessory"
        notes = "".join(f"<li>{_E(str(n))}</li>" for n in f.get("notes", []))
        notes_html = f'<ul class="notes">{notes}</ul>' if notes else ""
        comp = f.get("compliant")
        rows.append(
            "<tr>"
            f"<td><b>{_E(str(f.get('name')))}</b>"
            f'<div class="dim" style="font-size:.75rem">{_E(str(f.get("global_id")))}</div>'
            f"{notes_html}</td>"
            f"<td>{_E(occ)}</td>"
            f'<td class="num">{_fmt(f.get("height_m"), " m")}</td>'
            f'<td class="num">{_fmt(f.get("height_required_m"), " m")}</td>'
            f'<td class="num">{_fmt(f.get("floor_area_m2"), " m²")}</td>'
            f'<td class="num">{_fmt(f.get("window_area_m2"), " m²")}</td>'
            f'<td class="num">{_fmt(f.get("aero_ratio"))}</td>'
            f"<td>{_badge(f.get('height_ok'))}</td>"
            f"<td>{_badge(f.get('aero_ok'), na=aero_na)}</td>"
            f"<td>{_badge(comp)}</td>"
            "</tr>")
    mono = report.get("monostanza") or {}
    mono_line = ""
    if mono:
        mono_line = (f'<h2>Alloggio monostanza (canale separato)</h2><div class="sub">'
                     f'stato: <b>{_E(str(mono.get("status")))}</b> — '
                     f'{_E(str(mono.get("reason", "")))}</div>')
    salva = "sì" if report.get("salva_casa") else "no"
    return f"""<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{head_title}</title>
<style>{_CSS}</style>
</head>
<body>
<h1>{head_title}</h1>
<div class="sub">Modello: <b>{_E(str(model_name))}</b> · schema {_E(str(report.get('schema')))}
 · regime Salva Casa: {salva}</div>
{pack_line}
<div class="sub">Soglie applicate (applied legal bars): {bars}</div>
<div class="verdict {vcls}">{vit}</div> <span class="sub">({_E(ven)})</span>
<div class="tiles">
 <div class="tile"><b>{report.get('spaces_evaluated', 0)}</b>locali valutati<br>
  <span class="dim">spaces evaluated</span></div>
 <div class="tile"><b>{report.get('violations', 0)}</b>violazioni<br>
  <span class="dim">violations</span></div>
 <div class="tile"><b>{report.get('spaces_undetermined', 0)}</b>non determinabili<br>
  <span class="dim">undetermined</span></div>
</div>
<h2>Esito per locale (per-space findings)</h2>
<table>
<thead><tr>
 <th>Locale / note</th><th>Classe</th><th>Altezza</th><th>Min.</th><th>Pavimento</th>
 <th>Finestre</th><th>Aeroillum.</th><th>Altezza</th><th>Aero</th><th>Esito</th>
</tr></thead>
<tbody>
{''.join(rows)}
</tbody>
</table>
<div class="legend"><b>Legenda.</b> <span class="badge pass">conforme</span> requisito
soddisfatto · <span class="badge fail">violazione</span> requisito non soddisfatto ·
<span class="badge undet">non det.</span> il dato non è misurabile dal modello: il motore
<b>rifiuta di indovinare</b> — un locale non misurabile non è mai dichiarato conforme ·
<span class="badge na">n/a</span> requisito non applicabile alla classe del locale.</div>
{mono_line}
<footer>
Questo documento è la resa leggibile del verdetto JSON del motore ACC (deterministico,
fail-closed) e <b>non</b> è un rapporto di provenienza certificata né un atto asseverato:
non sostituisce il giudizio professionale. Copertura attuale: DM 5/7/1975 art. 1 (altezze) e
art. 5 (rapporto aeroilluminante 1/8), DPR 380/2001 art. 24 c. 5-bis (Salva Casa) — ogni altro
requisito edilizio è fuori ambito. / This is a human-readable rendering of the engine's JSON
verdict, not a certified provenance report; professional judgment is not replaced. Current
coverage: the two DM-1975 habitability rules + the Salva Casa derogation only.
</footer>
</body>
</html>
"""


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Render an ACC checker report JSON to HTML")
    ap.add_argument("json_path", help="checker report JSON (or API /evaluate envelope)")
    ap.add_argument("-o", "--out", help="output .html (default: alongside the input)")
    ap.add_argument("--title", help="document title (e.g. the pratica reference)")
    args = ap.parse_args(argv)
    with open(args.json_path, encoding="utf-8") as fh:
        data = json.load(fh)
    out = args.out or (args.json_path.rsplit(".", 1)[0] + ".html")
    html_text = render_report(data, title=args.title)
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(html_text)
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
