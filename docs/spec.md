# Fit Test Builder: kickoff handoff

_Written 2026-10-16 in a Rocket Builder session, to start a new Claude Code session. Paste the "Kickoff prompt" at the bottom into the new session, with this file attached or its path given._

## What it is

A separate web app for generating **slip-fit test coupons**: small printable peg-and-socket pairs at a range of clearances, laid out on a build plate, exported as a 3MF (one object per coupon) for Bambu Studio. Print, try each peg in its socket, record which clearance felt right, and use that number in the real design.

It grows out of `rocket-builder-web`'s `geometry/rocketgen/fit_test.py` (branch `claude/epic-einstein-4im4l4`), which made rocket-joint coupons and set Rocket Builder's printed fits. The new app generalises that to any shape, so it isn't tied to rockets.

Owner: Matthew Fevergeon (Quiver Design Works LLC). Printers: Bambu Lab **X1C** and **P1S** (256 × 256 mm plate), PLA by default.

## What the rocket fit test taught us (build these in)

- **CAD clearances print far too tight.** 0.02 mm radial couldn't be assembled. On a P1S in PLA, round shoulders 7–20 mm long in 13–30 mm bores were best at **0.15–0.20 mm radial for a glued slip fit**, and **about 0.15 mm for a friction fit that must still pull out** (a rocket nose cone). 0.05–0.10 were too tight on every size. These are good default ranges.
- **Engagement length changes the feel.** At the same clearance, a shorter peg (7 mm vs 10 mm) felt looser: it wobbles more and grips less. So length must be a test variable, not a constant.
- **Print orientation matters.** The first coupons stood on a thin shoulder edge (risky first layer). The owner switched to the **flat closed end on the bed, cup open upward**, which prints reliably. Default to the flat face down; offer the "as the real part prints" orientation as an option, because the real part's orientation changes the result (elephant foot only affects the bed edge).
- **Elephant foot:** the first layers flare out. A **0.5 mm 45° chamfer** on the bed edge of a peg removes it and gives a lead-in. Make it an option, on by default.
- **Labels:** recessed 0.6 mm into the bed face, readable from below (raised text on top needed a bridged cap). Labels are the clearance in hundredths of a mm (J15 = 0.15 mm radial). Bold sans font (FreeSans Bold is available in the Linux container; ship the font file with the app so it doesn't depend on the system).
- **Radial vs diametral:** always say "radial (per side)" in the UI. Diameter gap = 2 × radial.
- **Judging guide** (put it in the app next to the results form): *too tight* = needs force or twisting; *right* = slides to the seat with light pressure, no wobble; *too loose* = rocks or falls out. For pull-out fits: holds its own weight upside down, drops with a light shake.

## Features

### Shape types (start with the first three)
1. **Round peg / round hole** (cylinder in a bore). Inputs: nominal diameter, engagement length, wall.
2. **Tube shoulder / socket** (the rocket joint): hollow shoulder into a tube bore, optional 45° countersink seat on the socket and matching rise on the peg. Port this one directly from `fit_test.py`.
3. **Square / rectangular peg** (corner radius option: sharp inside corners print tight).
4. Later: hex (nut traps), D-shaft, dovetail slide, press-fit pin, snap-fit hook, thread (pitch × clearance).

### Variables
- **Clearance range:** start, step and count (e.g. 0.05 → 0.30 in 0.05), or a typed list. Radial, mm.
- **Engagement length:** one value, or a short list so that length × clearance becomes a grid.
- **Nominal size(s):** one or several (e.g. 13, 18, 24, 29 mm), each with its own socket.
- **Wall thickness**, socket outer diameter / margin.

### Features (checkboxes)
- Bed-edge chamfer on the peg (elephant foot) and its size.
- Lead-in chamfer at the socket mouth.
- Seat: countersink or flat shoulder stop.
- Closed end with a recessed label (default) or open tube.
- Grip tab or knurl, for pulling a peg out.
- Vent hole (a sealed peg in a blind socket acts as a piston).
- Orientation: flat face down (default) or functional end down.
- One socket per size, or one socket per peg.

### Output
- **3MF**, one named object per coupon (e.g. `D18_L10_C15`), laid out on the plate, plus an STL ZIP.
- A small **print sheet** (HTML or PDF) listing every coupon, its clearance, a results table to fill in, and the judging guide.
- **Results:** a form to mark each coupon too tight / right / too loose, plus printer, filament and notes. It saves to the browser and exports JSON / CSV, and it suggests the clearance midway between the last "too tight" and the first "too loose".

### Printer presets
X1C / P1S (256 × 256), A1 mini (180 × 180), custom. The layout auto-packs coupons into rows centred on the plate and warns when a set doesn't fit. Optionally it splits the set across plates (one 3MF per plate).

## Preview window (match Rocket Builder's)

Rocket Builder's viewer is in `rocket-builder-web/server/static/index.html`: three.js vendored under `server/static/vendor/three/` (import map, `OrbitControls`, `GLTFLoader`), with the server returning a **GLB** preview. Reuse that approach and its look: dark/light theme tokens, orbit controls, form column on the left and view on the right, a status line while building.

The new view shows:
- The **build plate**: a 256 mm square with a 10 mm grid and an origin marker, in the plate colour.
- Every coupon in its plate position, coloured by role (sockets one colour, pegs graded by clearance), with labels shown on hover or click.
- Toggles: **section view** (cut through the middle to show the clearance and seat) and **assembled view** (each peg seated in its socket, so the overlap can be checked by eye).
- Plate usage (mm used, fits or doesn't), coupon count and estimated filament grams.

## Architecture (recommended)

**Python + build123d on the server, three.js in the browser, in the existing Fly app.**

- Geometry: port `fit_test.py` and the helpers it uses from `rocketgen/geom.py` (`revolve`, `one_solid`, `meshes`, `solids_of`) into a small package (`fitgen/`). build123d is already proven for this: text, booleans and the 3MF writer (`Mesher`) all worked first time.
- Server: FastAPI, same pattern as Rocket Builder. `POST /api/build` (params → coupons, GLB preview, plate report), `GET /api/files/<id>.3mf` and `.zip`. Cache builds by a hash of the params plus a generator version (as `server/app.py` does with `GENERATOR_VERSION`).
- Hosting at **zero extra cost**: mount it into the existing Fly app `rocket-fevergeon` the way Trebuchet Builder is mounted (`rocket-builder-web/server/trebuchet_mount.py` + `HostRouter`, HANDOFF.md "Trebuchet Builder shares this Fly app"). Use its own repo (e.g. `the-feve/fit-test-builder`), and a host such as `fit.quiverdesignworks.net` (DNS-only A/AAAA to the Fly IPs, plus a Fly cert). Add it to the header's builder switcher (`nav.apps`).
- Admin only at first: Rocket Builder already has accounts and an admin email list (`ROCKETGEN_ADMIN_EMAILS`). Either gate the mount behind that or keep the app unlisted until it's ready for the public.

**Alternative, if it should be static and free anywhere:** in the browser only, with `manifold-3d` (WASM CSG) for the solids, three.js for the view, `fflate` to zip the 3MF, and a bundled font turned into outlines for the labels. Hosted on Cloudflare Pages. This needs no server, but the geometry is a rewrite rather than a port, and the labels are fiddlier. Pick it only if the owner wants it outside the rocket app.

## Tests (keep them, they caught real problems)

- Every coupon is **one valid solid that tessellates** (`is_valid` alone isn't enough; see `rocket-builder-web/geometry/report.md`).
- **Seating test** per shape: a peg placed at its seat doesn't overlap its socket, and 0.05 mm further in it does overlap (`test_fit_test_coupons_seat_without_overlap` in `geometry/tests/test_rocket.py`).
- Every part rests on z = 0 and stays inside the plate. The 3MF reads back with the right object count (`Mesher().read`).
- The labels are cut into the right face and read the right way from below.

## Milestones

1. `fitgen` package and CLI: round peg, tube shoulder and socket (ported), square peg; 3MF + STL output; tests.
2. FastAPI server + page: form, three.js plate preview, downloads. Runs locally (`uvicorn`).
3. Results form, print sheet, presets (saved in the browser), printer presets.
4. Mount in the Fly app behind admin; DNS. **Owner decides** the host name and whether it's public.
5. Later shapes: hex, D-shaft, dovetail, snap fit, thread. Rocket Builder can import a result ("use 0.18 mm for joints").

## Owner's working rules (carry these over)

- Keep `HANDOFF.md` (state, next steps, decisions) and `TODO.md` up to date; write a handoff and progress log before usage runs out.
- Budget is tight: zero running cost (free tiers, or the existing Fly app), and batch changes.
- Develop on a branch; push; open a PR only when asked. Run the tests before every push.
- Plain user-facing text, units in mm, and radial clearance always labelled as such.

## Kickoff prompt

> Build a new web app, "Fit Test Builder", following `docs/fit_test_app_handoff.md` (from the-feve/rocket-builder-web, branch `claude/epic-einstein-4im4l4`; copy it into the new repo as `docs/spec.md`). Start with milestone 1: a `fitgen` Python package (build123d) that ports `geometry/rocketgen/fit_test.py` and adds a round peg/hole and a square peg, with configurable clearance range, engagement length, sizes, wall, bed-edge chamfer, recessed labels on the bed face, and printing flat face down; output a 3MF with one object per coupon laid out on a 256 mm plate, plus STLs; and tests for one valid solid per coupon, seating without overlap, z = 0 and within the plate. Then milestone 2: a FastAPI server and a page whose 3D view matches Rocket Builder's (three.js, orbit controls, theme), showing the build plate grid and the coupon layout, with section and assembled toggles and the downloads. Write HANDOFF.md and TODO.md as you go, and run the tests before every push.
