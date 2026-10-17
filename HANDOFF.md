# Handoff

_Last updated 2026-10-17._

## State

Milestones 1 and 2 of `docs/spec.md` are done and run locally; nothing is deployed or linked yet (owner's call: link it from quiverdesignworks.net once it's dialled in, and keep it separate from the rocket / trebuchet sessions for now).

- **`fitgen/`** (build123d): round peg / hole, square peg / hole, and the tube shoulder / socket ported from rocket-builder-web `geometry/rocketgen/fit_test.py`. Clearance list (radial), engagement lengths (grid with clearances), sizes, wall, 45° insertion-end chamfer, seat (tube: countersink or flat), square corner radius, vent hole, orientation (flat face down or insertion end down), plate size. Labels recessed 0.6 mm into the bed face with the bundled FreeSans Bold. Layout packs rows centred on the plate inside an 8 mm margin and reports whether it fits. 3MF via `Mesher` (one named object per coupon) and one STL per coupon. CLI: `python -m fitgen`.
- **`server/`** FastAPI + the page: form left, three.js view right (Rocket Builder's set-up, lights and theme tokens), build plate with 10 mm grid / margin / origin marker, coupons coloured by role (sockets grey, pegs blue → orange from tight to loose), hover or click for a coupon's name and clearance, Assembled and Section toggles, coupon table, plate usage, grams, judging guide, 3MF and STL ZIP downloads. Builds are cached in memory by a hash of the params plus `GENERATOR_VERSION`.
- **Tests** (`python -m pytest -q`, ~40 s): one sound solid per coupon (valid + tessellates), seating (no overlap at the seat, overlap 0.05 mm further in; lifted 1 mm, sideways by just under the clearance clears and just over doesn't), every placed coupon on z = 0 and inside the plate with no overlapping footprints, the 3MF has one named object per coupon with every vertex on the plate, the flat print puts the label face on the bed, labels read the right way from below, bad parameters give a plain message, API build / previews / downloads.

## Next steps

See `TODO.md`. In short: print the first plates and check them, then milestone 3 (results form, print sheet, presets, split across plates).

## Hosting setup (owner steps)

Runs inside the existing Fly app `rocket-fevergeon`, the way Trebuchet Builder does, at **fit.quiverdesignworks.net**, no extra cost. Owner's choices (2026-10-16): Claude gets **no Fly or Cloudflare tokens** (the owner does the account steps; delete any Fly / Cloudflare tokens or variables added to the Claude environment while trying that); **unlisted** (noindex, no links), not admin-only.

**Status (2026-10-17):** Claude's code is done: relative URLs and the per-address build limit here, now on `main` (created 2026-10-17 from `claude/inspiring-mayer-m1ipwo` + the plan notes); the mount, deploy checkout and tests in rocket-builder-web, open as a PR there ("Host Fit Test Builder…"). Owner steps not started.

1. **GitHub read token: do this first; it is the one thing blocking the deploy.** github.com/settings/personal-access-tokens/new → fine-grained; name `fit-test-deploy`; Resource owner `the-feve`; Repository access: *Only select repositories* → `3D_print_test_fitter`; Permissions → Repository → **Contents: Read-only**; Generate, copy.
   Then github.com/the-feve/rocket-builder-web → Settings → Secrets and variables → Actions → **New repository secret** → name `FIT_REPO_TOKEN`, paste, Add secret. Don't paste it in chat.
   *Check:* the list shows `FIT_REPO_TOKEN` next to `TREBUCHET_REPO_TOKEN`. (Instead of a new token you can edit the trebuchet one to add this repo; the deploy falls back to it. Skip this step if this repo is made public.)
2. ~~**`main` branch here.**~~ Done 2026-10-17. Optional: Settings → General → Default branch → `main`.
3. **Merge the rocket-builder-web PR** (titled "Host Fit Test Builder…"). Its deploy runs automatically. *Check:* Actions → *Deploy to Fly.io* is green, with no "Fit Test Builder not checked out" warning, and https://rocket-fevergeon.fly.dev/fit/ shows Fit Test Builder.
4. **Cloudflare DNS.** dash.cloudflare.com → quiverdesignworks.net → DNS → Records → **Add record**: Type `CNAME`, Name `fit`, Target `rocket-fevergeon.fly.dev`, Proxy status **DNS only** (grey cloud), Save. (Trebuchet ended up with A `66.241.125.123` / AAAA `2a09:8280:1::1ae:4f69:0` instead; either works.)
   *Check:* the record list shows `fit` → `rocket-fevergeon.fly.dev`, grey cloud.
5. **Fly certificate.** fly.io/dashboard → `rocket-fevergeon` → **Certificates** → **Add certificate** → `fit.quiverdesignworks.net` (or `fly certs add fit.quiverdesignworks.net -a rocket-fevergeon`).
   *Check:* the certificate's status turns **Issued** / Verified (a few minutes after step 4), then https://fit.quiverdesignworks.net loads.
6. Optional: turn the Cloudflare record's proxy on (orange) later only if wanted; leave it grey until the certificate is issued. To make it admin-only instead of unlisted: `fly secrets set ROCKETGEN_FIT=admin -a rocket-fevergeon`.

Don't link it from quiverdesignworks.net or the builders until the owner says so.

## Decisions

- **Every peg is built seated in its socket's coordinates**, and the print orientation is derived from that. The seating tests and the Assembled view use the same solids that get printed.
- **Flat print = turned over about Y**, not X, so the label (made reading from above in the seated position) reads from below with its top towards +Y, the same way as the socket tabs' labels. Pick a coupon up and turn it over left-to-right, and its label reads upright.
- **Round and square pegs have a head** (flat stop) that rests on the socket top: it carries the label and sets the engagement length exactly. Sockets are blind (a floor) with a 2 mm vent hole, since a sealed peg in a blind hole acts as a piston, and carry their label on a tab on the bed.
- **The chamfer is on the peg's insertion end.** Printed flat, the insertion end is on top and the chamfer is a lead-in; printed insertion end down, it also removes the elephant foot (the rocket finding).
- **Square pegs are the socket hole offset inward by the clearance** (corner radius r − c, sharp if c ≥ r), so the clearance is the same all round.
- **Tube port:** same profile as the rocket (`shoulder_foot`, 45° rise, 5 mm band, 1.6 mm closed end, 45° inner step), but generic: size = bore, wall = tube wall, shoulder length = engagement length. The socket's label is now recessed into the bottom of a 2 mm tab (was raised on the rocket's flag).
- **3MF read-back test parses the XML** (`Mesher().read` took ~50 s for 6 objects).
- **Clearance codes** are hundredths of a mm with one decimal when needed (0.175 → C17.5); two clearances with the same code are rejected.
- **Hosting (2026-10-16): mounted in Rocket Builder's Fly app `rocket-fevergeon`**, like Trebuchet Builder, at zero extra cost. rocket-builder-web `server/fit_mount.py` loads `server/app.py` from a `fittest/` checkout and mounts it at `/fit/`; `HostRouter` sends `fit.*` hosts there. It is unlisted: Rocket Builder adds `X-Robots-Tag: noindex` to every response (and the page has a robots meta tag); `ROCKETGEN_FIT=admin` restricts it to admin accounts (`ROCKETGEN_ADMIN_EMAILS`). Rocket Builder also swaps in its build lock so a rocket and a coupon set never build at once on the 1 GB machine (this app's `_turn()` reads `_lock` at call time for that). So the page's URLs are relative (`api/…`, `static/…`). New builds are rate-limited per address (`FITGEN_BUILDS_PER_10_MIN`, 30) and wait at most `FITGEN_BUILD_WAIT_S` (60 s) for the lock. Owner steps: Hosting setup above.

## Gotchas

- GLTFLoader strips `.` and `:` from node names (`D18.4` → `D184`); the page uses `userData.name`, which keeps the original.
- The page's form has `novalidate`: the browser's step check (e.g. a 0.01 step with min 0.001) silently blocked submits. The server validates.
- Tests in a Claude cloud container: `pip install -e ".[server,test]"` into a venv (build123d isn't preinstalled). For screenshots use Playwright with `executable_path` set to the preinstalled Chromium under `/opt/pw-browsers/` and `--use-gl=swiftshader`.

## Log

- 2026-10-17: `main` created; hosting made unlisted (noindex) instead of admin-only, per the owner's 2026-10-16 choice.
- 2026-10-16: hosting code: relative page URLs, per-address build limit, bounded lock wait, lock shared with the host; the mount and admin gate in rocket-builder-web. Fly / Cloudflare tokens not available in the session.
- 2026-10-16: hosting plan and owner steps written (Hosting setup); owner does the account steps, Claude the code (not started).
- 2026-10-15: repo created; milestone 1 (fitgen + CLI + tests) and milestone 2 (FastAPI + page) built and checked in a headless browser.
