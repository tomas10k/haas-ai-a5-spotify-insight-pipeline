# Golden 50: how the answer key was made

* Source: `data/golden_50_to_label.csv` exactly as supplied (SHA256 1a125c3e..., matches manifest.json). The six source fields of `golden_50_labeled.csv` are unchanged (row hashes verified in code).
* Labeled by Tomas Diez Canedo from review text only; star rating, likes, app version and date were hidden while labeling.
* topic, intent, sentiment, severity, needs_review: Tomas's own labels.
* entities and evidence_quote (rows 3 to 50): drafted by an AI assistant to match Tomas's labels, then reviewed by Tomas. Every quote is checked in code as an exact substring.
* After a check against GRADING_CONTRACT.md rules, Tomas accepted 27 field changes on 17 reviews before any model saw these reviews (no model output influenced the key). Main reasons: offline listening is downloads; premium only controls are billing; first specific praised feature sets the topic; tie goes to the first mentioned problem; severity 5 is only financial, privacy or data harm.
* Ambiguous cases (another careful labeler could reasonably differ): 8 reviews, rows 17, 18, 19, 21, 24, 27, 33, 34. needs_review = true: 6 reviews.
* Only explicit cancellation in the set: row 29 ("Deleting this App", "i am deleting this app after years of using").
* These labels are never sent to any model, used as prompt examples, or used to set thresholds.
