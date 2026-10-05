# Product Priority Memo: Q Focus on Usability

## Recommendation
Prioritize usability for the next quarter of product effort. The usability topic carries 12 [T006] complaints and a severity sum of 30 [T007] (mean severity 2.500000 [T008]), ranking second only to the diffuse "other" bucket among topic totals, and it contains two concrete, addressable issues: excessive ads and problematic interface updates after recent releases. Fixing these has the clearest path to measurable improvement since the complaints point to specific UI and ad-frequency regressions rather than vague dissatisfaction.

## Evidence
- ISS_USABILITY_ADS has 6 [C009] complaints with severity sum 14 [C010] and mean severity 2.333333 [C011], ranked 14 [C012] in priority score. Example reviews: cf6166ae-d71a-4839-9add-088645ad3b78, e5e6c55f-3069-4b7c-9807-f8b5d5bf2726, 035213ba-b1b9-411c-b028-70296e5f0e73.
- ISS_USABILITY_UPDATE_LAYOUT has 5 [C013] complaints with severity sum 13 [C014] and mean severity 2.600000 [C015], priority score 13 [C016]. Example reviews: 5c9c17d3-9d6a-4fa1-a2a4-ae98eefbbd25, 7084ced1-0428-4093-9328-442f74719b4f, 9e5f9745-f8be-48d3-b9de-4d118507d94a.
- Topic-level usability totals: 12 [T006] complaints, severity sum 30 [T007], mean severity 2.500000 [T008], cancellations 2 [T009], share of all complaints 23.5% [T010].
- By contrast, billing's flagship issue ISS_BILLING_SKIP_LIMIT has 5 [C005] complaints, severity sum 15 [C006], mean severity 3.000000 [C007], priority score 15 [C008], smaller in volume than usability's combined issues.
- Playback's top issue ISS_PLAYBACK_CRASH_OPEN has only 2 [C017] complaints (severity sum 8 [C018], mean severity 4.000000 [C019]), and general playback issues add 2 [C025] complaints (severity sum 7 [C026]).
- Access shows the lowest volume: ISS_ACCESS_ACCOUNT has just 1 [C037] complaint (severity sum 4 [C038]), and topic totals confirm access complaints at 2 [T026] with share 3.9% [T030].

## Alternatives considered
- Billing/support: ISS_BILLING_SKIP_LIMIT is severe per-complaint (mean severity 3.000000 [C007]) and topic severity sum is 26 [T012], but overall volume (9 [T011] complaints, share 17.6% [T015]) trails usability.
- Playback: highest mean severity among larger topics (topic mean 3.500000 [T018]), but total volume (6 [T016] complaints) is lower than usability, suggesting a narrower fix population.
- Access: smallest topic by complaint count (2 [T026]) and share (3.9% [T030]), making it the lowest leverage area this quarter despite a high mean severity (4.000000 [T028]).

## Limitations
This pack covers {source_rows} reviews from a single platform window and all were classified with none quarantined or pending, per the summary counts in the pack. Public Google Play reviews are self selected and likely skew toward dissatisfied users, so complaint shares may not reflect the full user base. Severity and topic labels rely on automated classification; label quality has not been independently audited here. Cancellation mentions in examples reflect expressed intent in review text, not confirmed account cancellations.