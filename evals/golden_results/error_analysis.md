# Golden 50: error analysis

Source: [`golden_v1/per_case.csv`](golden_v1/per_case.csv) (field by field results) and [`golden_v1/disagreements.md`](golden_v1/disagreements.md).
The answer key is in [`../golden_50_labeled.csv`](../golden_50_labeled.csv), and [`../golden_50_provenance.md`](../golden_50_provenance.md) records how it was made.
Each disagreement below was read against the review text and the shared definitions in `docs/GRADING_CONTRACT.md`.
The cause categories were drafted with an AI assistant from the saved results, then checked by the project owner.
No label, prompt or threshold was changed because of these results, so the golden 50 is still a held-out check of the configuration that ran.

| Field | Agreement | What the misses have in common |
|---|---|---|
| topic | 44/50 (0.88), macro F1 0.74 | Boundary cases between `other` and a specific topic, plus one review edited over time (details below) |
| intent | 45/50 (0.90) | Very short or non-English text, and one boycott slogan |
| severity | 39/50 exact (0.78), MAE 0.28 | 10 of 11 misses are one level off; 9 of 11 are over-estimates. The one larger miss (off by 3) is the edited review `723f07de` |
| sentiment | 17/50 within ±0.25 (declared before the run), MAE 0.37 | A systematic scale difference, not individual errors |
| evidence_quote | 50/50 exact substrings | Checked in code |
| needs_review | precision 0.43, recall 0.50 | A weak signal, so it is used to route cases for review, never as a guarantee |

## 1. Severity: one level too high when a function is restricted (7 of 11 severity misses)

Over-estimates from restriction or annoyance: `991b6b3a`, `16d640e9`, `46c0b49f`, `8c0546b0`, `d2f3874f`, `ac4e860a`, `dceb14e7`.

The other four severity misses:

- two over-estimates explained in sections 2 and 3: `723f07de` (edited review, off by 3) and `5de7f95b` (boycott slogan, 1 vs 2)
- two under-estimates: `947821dc` and `3ddb3f4e`

- When features sit behind Premium or ads interrupt listening, Jev picks 3 ("degraded or restricted function"). The key uses 2 ("annoyance, no supported functional loss") unless the text describes a real loss of use.
- The two under-estimates are playback that "only plays a little bit then stops" (key 4, blocked) and a cancellation with several removed controls (key 4).
- Effect on the business answer: billing and usability complaints get slightly higher mean severity than the key would give. Ranking is count × mean severity, so this can lift billing and usability issues a little.
- This is one reason the memo cites counts and severity sums separately.

## 2. Topic boundaries (6 topic misses)

| Review | Key | Pipeline | Why it is hard |
|---|---|---|---|
| `1fc8b08f` "Duo Premium .... No ads at all!" | other | usability | Praise that names ads. The key treats it as general praise of the plan; ads fall under usability. Defensible either way. |
| `b58dd6f0` organize saved albums into collections | other | usability | The contract lists "queue/playlist management" under usability, so **the pipeline's label is arguably the better one**. A possible key error, kept unchanged and disclosed here. |
| `283b5843` "give me a free dollar to go with 3 months" | other | billing | Meaningless text that mentions money. The rule "a paid plan mention alone is not billing" applies. |
| `292ce26a` banning religious or political songs | catalog | other | A content removal complaint written as a political statement. |
| `dceb14e7` "can't even play the songs that I like and can't rewind" | billing | playback | On the free tier these are premium-only controls (billing). The text never says Premium, so the model read it as a playback failure. |
| `723f07de` "Update: support fixed it. Old post: crashes" | support / praise / 1 | playback / complaint / 4 | Review edited over time. The key follows the latest state; the model labeled the original crash. All three fields miss. |

## 3. Intent on short, non-English or slogan text (5 intent misses)

- `fc344263` "Great..." and `ac6cd66d` (Tagalog): the model said `unclear`, the key says `praise`. With very short or non-English text the model is cautious.
- `372d4e67` (Hinglish "please reduce ads"): the model said `request`, the key says `complaint`. Marked ambiguous in the key.
- `5de7f95b` boycott slogan: the model said `complaint`, the key says `unclear`. **This breaks a stated contract rule** (bare boycott slogans are `unclear`).
  - It matters at scale. In the 10,000 review development run, 106 reviews mention a boycott, Sweden, the Quran or Islam; 80 of them are from July 2023.
  - 71 of those were correctly labeled `unclear`, but 27 became complaints or cancellations under topic `other`.
  - Those 27 fall into the generic `ISS_OTHER_GENERAL` issue, which inflates it. The memo and README list this as a limitation.

## 4. Sentiment: a scale difference, not individual errors

33 of the 50 reviews fall outside the declared ±0.25 tolerance. Almost all are praise ("Good", "Excellent", "best app ever"):

- Jev's 5-level score maps strong praise to +1.0.
- The key scored short generic praise at about +0.5 to +0.7.
- On complaints, the two agree much more closely.

Sentiment is not used in ranking or in the memo, so this does not change the recommendation. We report the miss rather than relax the tolerance after seeing the results.

## 5. A known consistency gap found at scale

In the 10,000 review run, Jev gave severity 1 ("no reported problem") to some records labeled `complaint` (182 of them in `ISS_OTHER_GENERAL` alone).

- The contract defines severity 2 as "dislike or generic criticism", so a complaint should be at least 2.
- We did not patch labels after the fact, because changing classification fields without changing `label_config` would break provenance.
- The final run report counts these records, and the next configuration should add a code rule: complaint or cancellation implies severity ≥ 2, under a new label_config.

## What we would change next (not applied, to keep this evaluation held out)

1. Add worked examples for premium restrictions (severity 2 vs 3) and for boycott slogans to the Jev instructions. Use development reviews for these, never golden ones.
2. Add the code rule from section 5.
3. Re-run the golden 50 together with fresh held-out cases. Any golden-driven change must be disclosed, as the brief requires.
