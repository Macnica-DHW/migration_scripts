# Figure rules: Page Acceptance Guidelines (Macnica Americas → global2)

The figure modules in `figs/` are the source of truth. This file keeps only the shared rules every figure follows;
the numbers each figure shows must match the guideline text in `part2.html` / `part3.html`.

The document is a client-facing acceptance guideline. Figures must make each criterion unambiguous:
a reviewer looks at a page, compares it with the figure, and decides pass/fail. Figures are schematic
wireframes drawn with `svgkit.py` (read it first; its docstring describes the visual language).

## Shared rules (all figures)
- Use only `svgkit.Panel` + `svgkit.figure`. Do not write raw SVG outside the Panel helpers except small
  additions via `Panel.add()` when a helper is missing (keep the same colours from svgkit constants).
- Panel size: 300 × 170 by default (you may use 300 × 150–220 when needed). Panels in one figure share one size.
- Every panel starts with `p.page()` (desktop) or `p.phone(...)` (phone), unless the figure is a pure outline.
- Verdict chips: `'ok'` → "Accepted", `'bad'` → "Not accepted", `'opt'` with label "Option A" / "Option B" / "Option C".
- Measurements: orange `dim_v` / `dim_h` with short labels like "≤ 45px", "120px", "50px". Keep all text INSIDE the
  panel's viewBox (right edge ≤ w-4). Labels ≥ 6.5 units. No text overlapping shapes.
- Show the problem, not decoration: highlight empty space that is the defect with `hatch()`.
- Captions: one short sentence per panel, factual, with the number that decides pass/fail. English (US).
  Never name people or companies; never say "agency". Component names as in AEM: Text with Image, Title,
  Flex Container, Container, Button, Table, Embed, Tabs, Sticky Tabs, Card List, Experience Fragment.
- Figure caption (the `caption=` argument): "Figure N. <what it shows>"; `build.py` renumbers N.
- Scale hint: a panel represents a 1400px-wide browser window; the page frame is ~288 units wide, so 1 unit ≈ 4.9px.
  Keep proportions plausible (e.g. side padding 25px ≈ 5 units, 50px ≈ 10 units; a 120px gap ≈ 25 units).

## Output
- Write `figs/fig_<group>.py` defining `FIGS = {'<id>': function, ...}`; each function returns `figure([...], caption=..., fid='<id>')`.
- Render: `python3 render_figs.py figs/fig_<group>.py` → `dados/mapas/page-acceptance-guidelines/png/<id>.png`. Check each PNG
  (clipping, overlap, legibility, the defect is obvious), fix, re-render.
- The figure number in `caption=` is replaced by `build.py` with the order of appearance in the document.
