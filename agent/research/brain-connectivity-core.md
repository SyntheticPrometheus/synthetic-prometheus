# Brain connectivity as a cognitive core — the shipped mapping

Source package: `Documents/inbox/brain_regions_connectivity_package.zip` (7 CSVs, 124 rows,
`brain_connection_atlas.md`, `signal_pathway_reference.md`). Full seven-section run:
`research/rr/brain-region-connectivity-as-a-cognitive-core-architecture.md`.

The package labels systems by function (relay, gating and selection, prediction and error
correction, state control, modulation), not by single-purpose modules. The shipped artifact pairs
14 of those functions with the harness component already doing the job — `core/brain-map.json`,
resolved on every run by `bin/pi-core-map`. A mapped component that is deleted makes the command
exit 1 and name the row; `tests/pi-core-map.sh` pins that failure mode (7/7 ok, identical twice).

What it is not: an argument for spending, a new cadence, or an anatomical claim. The only metric
is resolved == rows (14/14 today); the falsifier is any run that cannot resolve a mapped path.
