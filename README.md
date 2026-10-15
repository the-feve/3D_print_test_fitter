# Fit Test Builder

Printable **slip-fit test coupons**: a socket per size and a peg per clearance (× engagement length), laid out on a build plate and exported as a **3MF with one named object per coupon** (for Bambu Studio) plus one STL per coupon. Print the plate, try each peg in its socket, and use the clearance that felt right in the real design.

Grew out of Rocket Builder's joint fit test (`geometry/rocketgen/fit_test.py` in the-feve/rocket-builder-web). The plan is [`docs/spec.md`](docs/spec.md); state and next steps are in [`HANDOFF.md`](HANDOFF.md) and [`TODO.md`](TODO.md).

Quiver Design Works LLC. Not public yet: it will be linked from quiverdesignworks.net once it's dialled in.

## Shapes

| Shape | Socket | Peg | Size means |
|---|---|---|---|
| `round` | blind round bore, floor with a vent hole, label tab | solid round peg with a head (flat stop) | hole diameter |
| `square` | blind square hole with rounded inside corners | square peg = the hole offset inward by the clearance, with a head | hole side |
| `tube` | the top of a tube: bore + 45° countersink (or flat), open both ends | hollow shoulder + rise + band + closed end (the rocket joint) | tube bore (ID) |

**Clearances are radial (per side).** The diameter gap is twice the number. Labels are the clearance in hundredths of a mm: `C15` = 0.15 mm radial. With more than one length or size, the label adds `L10` and `D18` lines. Object names are `D18_L10_C15` and `D18_socket` (`S` for square).

Defaults built in from the rocket fit test (Bambu P1S, PLA): clearances 0.05–0.30 mm (0.15–0.20 was right for a glued slip fit), a 0.5 mm 45° chamfer on the peg's insertion end, and pegs printed **flat face down** (head / closed end on the bed, label recessed 0.6 mm into it, reading from below). `--orientation functional` prints the peg insertion end down instead, as a real part would.

## Use

```
pip install -e ".[server,test]"
python -m pytest -q                       # about a minute

python -m fitgen --shape round --sizes 10 13 --lengths 7 10 --out out
python -m fitgen --shape tube --sizes 18.4 --range 0.10 0.05 5 --seat countersink
python -m fitgen --shape square --clearances 0.1 0.15 0.2 --corner-radius 1.5 --plate 180

uvicorn server.app:app --reload           # http://127.0.0.1:8000
```

The page has the form on the left, a three.js view of the plate (10 mm grid, margin, origin marker at the front-left corner) with **Assembled** (each peg seated in a copy of its socket) and **Section** (every coupon cut through its axis) toggles, the coupon table, plate usage, filament estimate, the judging guide, and the 3MF / STL ZIP downloads.

## Layout

```
fitgen/            geometry (build123d): coupons.py, labels.py, plate.py, geom.py, cli.py, fonts/
server/app.py      FastAPI: /api/options, /api/build, /api/builds/<id>/{plate.glb,assembled.glb,fit_test.3mf,stl.zip}
server/static/     the page; three.js r160 vendored (same as Rocket Builder)
tests/             geometry and API tests
docs/spec.md       the plan (from rocket-builder-web docs/fit_test_app_handoff.md)
```

The bundled font is GNU FreeFont FreeSans Bold (GPLv3 with the font exception); see `fitgen/fonts/README.md`.
