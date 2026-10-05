# Label guide (shared definitions plus worked examples)

The eight topics, five intents and five severity levels are copied from `GRADING_CONTRACT.md` and are not changed. This page shows how we apply them. **All examples come from the development file `checkpoint_500.csv`; none come from the golden 50.** Row numbers are positions in that file (first data row = 0).

## Rules we apply

1. Classify the text only. Stars, likes, version and date never set a label.
2. Topic = the most severe supported problem; on a tie, the first one mentioned. Positive review: first specific praised feature; general praise is `other`.
3. Premium only controls (skip limits, forced shuffle, choosing songs, lyrics locked) are `billing`. Mentioning premium alone is not.
4. Offline listening is `downloads`. App will not open or crashes is `playback`; `access` is only login, signup, password, account.
5. Intent precedence: cancellation > complaint > request > praise > unclear. Boycott slogans with no product complaint and no personal departure are `unclear`.
6. Severity 5 needs explicit financial, privacy or data harm. Cancellation intent does not raise severity.
7. Missing context, unsupported language or a guess sets `needs_review = true`.

## Worked examples

| Row | Review (shortened) | topic | intent | sev | Why |
|---|---|---|---|---|---|
| 4 | "now you can't even pick a certain song without Spotify premium, and now you can only skip 6 songs" | billing | complaint | 3 | Premium only controls; music still plays |
| 32 | "The latest update has caused my app to crash I cant open the app" | playback | complaint | 4 | Core task blocked; crash is playback, not access |
| 76 | "Will not except my password" | access | complaint | 4 | Cannot log in |
| 37 | "Soo trash wayy to many ads I don't want premium but too much ads" | usability | complaint | 2 | Ad frequency is usability; annoyance |
| 67 | "It needs the feature to download lyrics for offline." | downloads | request | 1 | Pure feature request; offline is downloads |
| 28 | "recent update is very disappointing bye Spotify" | other | cancellation | 2 | "bye Spotify" is a personal departure; no specific defect |
| 85 | "Useless aap boycott sweden" | other | complaint | 2 | "Useless" is a product complaint, so not a bare slogan |
| 110 | "I paid my subscription and im still getting a pause subscription screen and can't access my music" | billing | complaint | 4 | Paid plan not activating blocks listening; no wrong charge stated, so not 5 |
| 58 | "Love the mixes they make, always fire suggestions!" | catalog | praise | 1 | First praised feature is recommendations |
| 86 | "sometime the lyrics don't show" | catalog | complaint | 3 | Lyrics availability degraded |
| 151 | "offline mode USELESS, and moving storage failed and deleted everything" | downloads | complaint | 5 | Explicit data loss |
| 98 | "Nbjmmjnmjvkjnzudbdnidbdnad Brkdn..." | other | unclear | 1 | Meaningless text |

Examples are guidance for people. They are not sent to Jev as labeled examples, so the golden set stays blind and Jev sees only the definitions in `prompts/enrich_v1.json`.
