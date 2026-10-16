# TODO

Milestones are from `docs/spec.md`. Done items move to HANDOFF.md's log.

## Next: check the first prints
- [ ] Print a round and a square plate on the P1S (PLA, 0.20 Standard) and confirm: labels legible, pegs reach the seat, vent works, the 0.5 mm tip chamfer is enough lead-in.
- [ ] Compare the tube coupons with Rocket Builder's round-1 results (M18: J15–J20 right) to check the port.

## Milestone 3: results, print sheet, presets
- [ ] Results form next to the coupon table: too tight / right / too loose per peg, printer, filament, notes. Save to the browser; export JSON / CSV; suggest the clearance midway between the last too-tight and the first too-loose.
- [ ] Print sheet (HTML, printable): every coupon, its clearance, a results table to fill in, the judging guide.
- [ ] Save / load parameter presets in the browser.
- [ ] Split a set that doesn't fit across plates (one 3MF per plate) instead of only warning.

## Shape options not built yet
- [ ] Lead-in chamfer at the socket mouth.
- [ ] Countersink seat on round pegs (now flat stop only); flat-stop variants are there for tube.
- [ ] Grip tab or knurl on the peg head.
- [ ] Open tube option for round pegs (now always a closed head).
- [ ] One socket per peg (now one per size).
- [ ] Rectangular (non-square) pegs.

## Milestone 4: hosting
- [x] Mount code in rocket-builder-web (`server/fit_mount.py`, admin-only gate, shared build lock) and per-address build limit here. Branch `claude/inspiring-mayer-m1ipwo` in both repos, not merged.
- [ ] Owner: `main` here, a token that can read this repo, merge rocket-builder-web (HANDOFF.md Next steps 1–3).
- [ ] `fit.quiverdesignworks.net`: A/AAAA to the Fly IPs (DNS only), `fly certs add` (step 4).
- [ ] Open to everyone (`ROCKETGEN_FIT=open`) and links from quiverdesignworks.net and the builders' switcher (`nav.apps`) — only once the owner says it's ready.

## Milestone 5: later shapes
- [ ] Hex (nut traps), D-shaft, dovetail slide, press-fit pin, snap-fit hook, thread (pitch × clearance).
- [ ] Let Rocket Builder import a result ("use 0.18 mm for joints").
