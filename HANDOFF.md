# Handoff

_Last updated 2026-10-16._

## State

Milestones 1 and 2 of `docs/spec.md` are done and run locally; nothing is deployed or linked yet (owner's call: link it from quiverdesignworks.net once it's dialled in, and keep it separate from the rocket / trebuchet sessions for now).

- **`fitgen/`** (build123d): round peg / hole, square peg / hole, and the tube shoulder / socket ported from rocket-builder-web `geometry/rocketgen/fit_test.py`. Clearance list (radial), engagement lengths (grid with clearances), sizes, wall, 45° insertion-end chamfer, seat (tube: countersink or flat), square corner radius, vent hole, orientation (flat face down or insertion end down), plate size. Labels recessed 0.6 mm into the bed face with the bundled FreeSans Bold. Layout packs rows centred on the plate inside an 8 mm margin and reports whether it fits. 3MF via `Mesher` (one named object per coupon) and one STL per coupon. CLI: `python -m fitgen`.
- **`server/`** FastAPI + the page: form left, three.js view right (Rocket Builder's set-up, lights and theme tokens), build plate with 10 mm grid / margin / origin marker, coupons coloured by role (sockets grey, pegs blue → orange from tight to loose), hover or click for a coupon's name and clearance, Assembled and Section toggles, coupon table, plate usage, grams, judging guide, 3MF and STL ZIP downloads. Builds are cached in memory by a hash of the params plus `GENERATOR_VERSION`.
- **Tests** (`python -m pytest -q`, ~40 s): one sound solid per coupon (valid + tessellates), seating (no overlap at the seat, overlap 0.05 mm further in; lifted 1 mm, sideways by just under the clearance clears and just over doesn't), every placed coupon on z = 0 and inside the plate with no overlapping footprints, the 3MF has one named object per coupon with every vertex on the plate, the flat print puts the label face on the bed, labels read the right way from below, bad parameters give a plain message, API build / previews / downloads.

## Next steps

See `TODO.md`. In short: print the first plates and check them, then milestone 3 (results form, print sheet, presets, split across plates), then hosting (owner decides).

## Hosting setup (owner steps)

**Status (2026-10-16, end of session):** nothing done yet on either side. The owner is doing the account steps tonight, without giving Claude any Fly or Cloudflare tokens (owner's choice; delete any Fly / Cloudflare tokens or variables added to the Claude environment while trying that). Defaults until the owner says otherwise: address `fit.quiverdesignworks.net`, **unlisted** (noindex, no links), not admin-only.

**Claude's part, not started:** (a) this repo: the page fetches `/static/...` and `/api/...` from the site root; make them relative so it works mounted under `/fit/` and at `fit.*`; add a per-IP build rate limit (copy Rocket Builder's `_rate_limit`); open a PR here so merging it creates `main`. (b) rocket-builder-web: `server/fit_mount.py` modelled on `trebuchet_mount.py` (`FIT_DIR`, mount at `/fit`, `HostRouter` sends `fit.*` hosts there), Dockerfile / deploy.yml checkout of this repo's `main` into `fit/` with `FIT_REPO_TOKEN` (skip with a warning if missing, like Trebuchet), a post-deploy check that `/fit/` answers, and a mount test; open it as a separate PR for the owner to merge. Watch the 1 GB machine: a rocket and a fit build at once may need a shared build lock or 2 GB.

**Kickoff for the next session:** "Read 3D_print_test_fitter HANDOFF.md → Hosting setup and do Claude's part: the relative-URL change and rate limit here (PR), and the Fit Test Builder mount PR in rocket-builder-web. Then check which owner steps are done."

Plan (2026-10-16): run inside the existing Fly app `rocket-fevergeon`, the way Trebuchet Builder does, at **fit.quiverdesignworks.net**. No extra cost. The owner does the account steps below; Claude does the code (relative URLs in this repo, a mount + deploy step + test in rocket-builder-web, opened as a PR there).

1. **GitHub read token** (do any time). github.com/settings/personal-access-tokens/new → fine-grained; name `fit-test-deploy`; Repository access: *Only select repositories* → `3D_print_test_fitter`; Permissions → Repository → **Contents: Read-only**; Generate, copy.
   Then github.com/the-feve/rocket-builder-web → Settings → Secrets and variables → Actions → **New repository secret** → name `FIT_REPO_TOKEN`, paste, Add secret.
   *Check:* the list shows `FIT_REPO_TOKEN` next to `TREBUCHET_REPO_TOKEN`. (Skip this step if this repo is made public.)
2. **`main` branch here.** Merge the PR Claude opens in this repo (or ask Claude to create `main` from the working branch). *Check:* github.com/the-feve/3D_print_test_fitter shows branch `main`.
3. **Merge the rocket-builder-web PR** (titled "Host Fit Test Builder…"). Its deploy runs automatically. *Check:* Actions → *Deploy to Fly.io* is green, and https://rocket-fevergeon.fly.dev/fit/ shows Fit Test Builder.
4. **Cloudflare DNS.** dash.cloudflare.com → quiverdesignworks.net → DNS → Records → **Add record**: Type `CNAME`, Name `fit`, Target `rocket-fevergeon.fly.dev`, Proxy status **DNS only** (grey cloud), Save.
   *Check:* the record list shows `fit` → `rocket-fevergeon.fly.dev`, grey cloud.
5. **Fly certificate.** fly.io/dashboard → `rocket-fevergeon` → **Certificates** → **Add certificate** → `fit.quiverdesignworks.net` (or `fly certs add fit.quiverdesignworks.net -a rocket-fevergeon`).
   *Check:* the certificate's status turns **Issued** / Verified (a few minutes after step 4), then https://fit.quiverdesignworks.net loads.
6. Optional: turn the Cloudflare record's proxy on (orange) later only if wanted; leave it grey until the certificate is issued.

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
- **Hosting plan unchanged from the spec:** mount in the existing Fly app at zero extra cost; not done yet.

## Gotchas

- GLTFLoader strips `.` and `:` from node names (`D18.4` → `D184`); the page uses `userData.name`, which keeps the original.
- The page's form has `novalidate`: the browser's step check (e.g. a 0.01 step with min 0.001) silently blocked submits. The server validates.
- Tests in a Claude cloud container: `pip install -e ".[server,test]"` into a venv (build123d isn't preinstalled). For screenshots use Playwright with `executable_path` set to the preinstalled Chromium under `/opt/pw-browsers/` and `--use-gl=swiftshader`.

## Log

- 2026-10-16: hosting plan and owner steps written (Hosting setup); owner does the account steps, Claude the code (not started).
- 2026-10-15: repo created; milestone 1 (fitgen + CLI + tests) and milestone 2 (FastAPI + page) built and checked in a headless browser.
