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

## Hosting: builds are too heavy for the shared-CPU machine (owner decides)
- [ ] Owner: check `rocket-fevergeon` → Metrics → CPU (throttling) on the Fly dashboard after a couple of builds.
- [x] Lighter builds: caps without grip ribs, one-line Rocket labels (default M18 set 29 s → 15 s locally), one size per request (2026-10-18).
- [ ] If hosted builds still crawl: keep each built set on the `/data` volume and prebuild the default sets per motor. build123d solids don't pickle (`BRepTools_History`); store BREP text per coupon (`export_brep` / `import_brep`) or the preview meshes and make 3MF / STL from them.
- [ ] Or run Fit Test Builder on its own small Fly machine (costs a few dollars a month) so it can't slow Rocket Builder.

## Rocket Builder tab
- [ ] Rocket Builder Advanced *Fits and joints* inputs (joint clearance, joint lengths, thread clearance / pitch / turns): built 2026-10-17 in rocket-builder-web (PR, not merged). Once merged, this tab could offer the same overrides so a coupon matches a customised rocket.
- [ ] Optional: motor-in-bay coupons (rings at a few clearances to try a real motor in; Rocket Builder uses 0.2 mm, `mtr_clear`).
- [ ] Optional: print the thread boss tail-down like the real aft (now flange down).

## Shape options not built yet
- [ ] Lead-in chamfer at the socket mouth.
- [ ] Countersink seat on round pegs (now flat stop only); flat-stop variants are there for tube.
- [ ] Grip tab or knurl on the peg head.
- [ ] Open tube option for round pegs (now always a closed head).
- [ ] One socket per peg (now one per size).
- [ ] Rectangular (non-square) pegs.

## Milestone 4: hosting (owner steps in HANDOFF.md → Hosting setup)
- [x] Claude: relative URLs, per-address build limit here; mount (unlisted, noindex, shared build lock), deploy checkout and tests in rocket-builder-web (PR).
- [x] `main` branch here (2026-10-17).
- [x] Owner: `FIT_REPO_TOKEN`, rocket-builder-web PR #37, DNS, Fly cert. Live 2026-10-17 at fit.quiverdesignworks.net (unlisted).
- [ ] Optional: redeploy rocket-builder-web automatically when this repo's `main` changes (`fit-updated` dispatch, like trebuchet_builder).
- [ ] Links from quiverdesignworks.net and the builders' switcher (`nav.apps`) — only once the owner says it's ready.

## Milestone 5: later shapes
- [ ] D-shaft, dovetail slide, press-fit pin, snap-fit hook, generic thread (pitch × clearance). (Hex, pentagon, octagon done 2026-10-17.)
- [ ] Let Rocket Builder import a result ("use 0.18 mm for joints").
