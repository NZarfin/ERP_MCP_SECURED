# services/renderer

Deterministic document/report rendering: Jinja2 + WeasyPrint (PDF), python-pptx,
openpyxl, python-docx, Vega-Lite (charts). Pinned fonts and renderer versions so a
locked template version renders byte-identically forever (golden tests enforce this).
See `docs/ARCHITECTURE.md` §5, §7. Phase 3 of `docs/ROADMAP.md`.
