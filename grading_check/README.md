# Zero-API self-check of `grading/`

[`self-check.json`](self-check.json) is the output of the supplied deterministic checker. It was run against the declared scope file, `data/scope_100k.csv`:

```sh
python3 check_submission.py profile   --full data/spotify_reviews_18months.csv --out grading/ingestion.json
python3 check_submission.py reference --full data/spotify_reviews_18months.csv --analysis data/scope_100k.csv --out local-reference.json
python3 check_submission.py check     --reference local-reference.json --submission grading --out grading_check/self-check.json
```

`grading/` is written by `python3 -m pipeline export --run-id final_100k`, with no model call. The checker step takes about 5 seconds with no API key.

## Result

| Check | Result |
|---|---|
| Rows | 100,013 expected, 100,013 received, 0 missing, 0 duplicate |
| Classified | 100,000 (all 100,000 labelable rows) |
| Quarantined | 13, the empty texts (`empty_review_text`) |
| Exact text cache reuse | 21,901 valid (`cache_source_id` points to a direct original) |
| Full file profile | matches (`ingestion.json` is the whole 660,622 row file) |
| Ranking and claims | recomputed from `records.jsonl.gz` and `membership.csv`; no `claim_mismatch` |
| Resume evidence | valid: checkpoint before (45,606 IDs) ⊂ checkpoint after (100,000 IDs) |
| Reprocessed IDs | none (`reprocessed_checkpoint` = 0) |
| Model roles | all four present: enrich, verify, group, memo |
| `working_coverage_point_candidate` | 1.0, relative to the **declared 100,000 review scope**. Against all 660,609 nonempty reviews, the classified fraction would be 100,000 / 660,609 = 15.1%. |
| Status | `review_required` because of one item, explained below |

### The only flag: `invalid_usage` (26 = 13 failed attempts × 2 token fields)

- **What failed:** 13 of the 78,985 logged attempts failed before the provider returned any response: timeouts, connection resets, and a DNS failure during a network outage.
- **Why the fields are empty:** these calls have no provider usage, so `input_tokens` and `output_tokens` are `null` and the exported row says `"usage_available": false`.
- **No invented zeros:** writing 0 would claim the attempt was not billed, which we cannot know.
- **All 13 were recovered:** each was retried with backoff or resumed later, and no record was lost.
- **Details:** the errors are listed per call in `runs/final_100k/calls.jsonl` (field `error`).
