# 3D_print_test_fitter (Fit Test Builder) — working rules

- Read `HANDOFF.md` first, then `TODO.md`. Keep both up to date when something changes. The plan is `docs/spec.md`.
- **Origin:** `geometry/rocketgen/fit_test.py` in the-feve/rocket-builder-web (branch `claude/epic-einstein-4im4l4`). The tube shape is a port of it; port behaviour and the "why" comments.
- **Units are mm. Clearances are radial (per side)** and the UI always says so; the diameter gap is twice the number.
- **Don't trust OpenCascade's `is_valid` alone.** Every coupon goes through `geom.sound` (one solid, valid, tessellates). Keep the seating, layout and 3MF tests green.
- Linked only from Rocket Builder's Advanced download area (owner's request, 2026-10-17). Not from quiverdesignworks.net or the trebuchet builder yet: don't add other links until the owner says.
- Run `python -m pytest -q` before every push (about 2 minutes).
- Budget is tight: zero running cost, batch changes, develop on a branch, open a PR only when asked.
