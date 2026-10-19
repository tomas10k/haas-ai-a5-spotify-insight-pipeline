# Memo review notes

The brief requires that a person inspect the final argument. `memo_model_output.md` is the exact text the memo model returned and code rendered (prompt `memo_v3`, `claude-sonnet-5`). It passed the automatic number and ID check.
A careful read still found the problems below, which the automatic check cannot catch: an ordering contradiction, a fact attributed to the wrong area, and wording without support in the pack. `memo.md` applies only these minimal edits.
The code check was re-run on the edited text: passed.

| # | Model text | Reviewed text | Why |
|---|---|---|---|
| 1 | billing and support is the only area whose complaint share rose sharply between the 2022 and 2023 comparison windows, climbing from 3.8% [F026] to 13.2% [F033] | billing complaints are the only ones whose share of classified reviews rose sharply between the 2022 and 2023 comparison windows, climbing from 3.8% [F026] to 13.2% [F033] | The trend facts F026/F033 are for the billing topic only; the model attributed them to billing and support combined. |
| 2 | - Trend direction diverges across areas: billing and support share rose from 3.8% [F026] to 13.2% [F033]; | - Trend direction diverges across areas: the billing share rose from 3.8% [F026] to 13.2% [F033]; | Same attribution fix (billing topic, not the combined area). |
| 3 | - **Playback**: Highest mean severity among the four areas (3.445708 [T018]), per orderings_computed_by_code topics_by_mean_severity, | - **Playback**: Second highest mean severity among the four areas after access (3.445708 [T053]), per areas_by_mean_severity, | Factual error: areas_by_mean_severity orders access first, playback second; the model's sentence contradicted its own Access bullet. Token T018 (playback topic) replaced by T053 (playback area), same value. |
| 4 | Reviews are self-selected and skew toward complaints, | Reviews are self selected, | Removed 'skew toward complaints' (not supported by a pack fact) and the hyphen (style rule). |
| 5 | severity exact-match is 81% [F016]; golden-set agreement | severity exact match is 81% [F016]; golden set agreement | Hyphens (style rule). |

Earlier drafts are kept for transparency:
- `archive_memo_v2/` holds the first draft (prompt `memo_v2`). It recommended usability, without trend facts or orderings.
- `calls.jsonl` holds every memo call and its cost.
