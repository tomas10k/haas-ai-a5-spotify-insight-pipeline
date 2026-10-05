# Spotify Insight Pipeline

MBA 290T final assignment (Tomas Diez Canedo). A staged program that turns 660,622 Spotify Google Play reviews into a ranked, cited product recommendation.

**Live overview:** see the Vercel site linked in the repository description (built from `site/`, read only, no API keys).

**Status (October 5, 2026):** work in progress. Done: full file ingestion and profile, golden 50 hand labels, measured 100 review cost pilot (cold and warm) with offline replay, golden 50 evaluation, 500 review development run. Next: system tests, 10,000 review budget check, full run with interruption and resume, grading export, full README.

| What | Where |
|---|---|
| Pipeline code (six stages, orchestrator) | [`pipeline/`](pipeline/) |
| Every instruction sent to a model | [`prompts/`](prompts/) |
| Label definitions with worked examples | [`docs/label_guide.md`](docs/label_guide.md) |
| Golden 50 answer key and how it was made | [`evals/`](evals/) |
| Cost calculator, measured pilot, report | [`cost/`](cost/) (`python3 cost/calculator.py` replays offline) |
| Saved runs (handoff files, call logs) | [`runs/`](runs/) |
| Website source | [`site/`](site/) |

The raw dataset is not committed (97.4 MB). Place `spotify_reviews_18months.csv` and the other supplied files in `data/`; SHA256 of the full CSV: `1fc85de68a304dd8978b537cfa58793d5f41cbaf417fa32cb53899f83a2fcef6`.
