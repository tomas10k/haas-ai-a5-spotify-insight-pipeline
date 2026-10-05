# Product Priority Memo: Q Focus on Usability

## Recommendation
Prioritize usability for the next quarter of product effort. The usability topic carries {T006} complaints and a severity sum of {T007} (mean severity {T008}), ranking second only to the diffuse "other" bucket among topic totals, and it contains two concrete, addressable issues: excessive ads and problematic interface updates after recent releases. Fixing these has the clearest path to measurable improvement since the complaints point to specific UI and ad-frequency regressions rather than vague dissatisfaction.

## Evidence
- ISS_USABILITY_ADS has {C009} complaints with severity sum {C010} and mean severity {C011}, ranked {C012} in priority score. Example reviews: cf6166ae-d71a-4839-9add-088645ad3b78, e5e6c55f-3069-4b7c-9807-f8b5d5bf2726, 035213ba-b1b9-411c-b028-70296e5f0e73.
- ISS_USABILITY_UPDATE_LAYOUT has {C013} complaints with severity sum {C014} and mean severity {C015}, priority score {C016}. Example reviews: 5c9c17d3-9d6a-4fa1-a2a4-ae98eefbbd25, 7084ced1-0428-4093-9328-442f74719b4f, 9e5f9745-f8be-48d3-b9de-4d118507d94a.
- Topic-level usability totals: {T006} complaints, severity sum {T007}, mean severity {T008}, cancellations {T009}, share of all complaints {T010}.
- By contrast, billing's flagship issue ISS_BILLING_SKIP_LIMIT has {C005} complaints, severity sum {C006}, mean severity {C007}, priority score {C008}, smaller in volume than usability's combined issues.
- Playback's top issue ISS_PLAYBACK_CRASH_OPEN has only {C017} complaints (severity sum {C018}, mean severity {C019}), and general playback issues add {C025} complaints (severity sum {C026}).
- Access shows the lowest volume: ISS_ACCESS_ACCOUNT has just {C037} complaint (severity sum {C038}), and topic totals confirm access complaints at {T026} with share {T030}.

## Alternatives considered
- Billing/support: ISS_BILLING_SKIP_LIMIT is severe per-complaint (mean severity {C007}) and topic severity sum is {T012}, but overall volume ({T011} complaints, share {T015}) trails usability.
- Playback: highest mean severity among larger topics (topic mean {T018}), but total volume ({T016} complaints) is lower than usability, suggesting a narrower fix population.
- Access: smallest topic by complaint count ({T026}) and share ({T030}), making it the lowest leverage area this quarter despite a high mean severity ({T028}).

## Limitations
This pack covers {source_rows} reviews from a single platform window and all were classified with none quarantined or pending, per the summary counts in the pack. Public Google Play reviews are self selected and likely skew toward dissatisfied users, so complaint shares may not reflect the full user base. Severity and topic labels rely on automated classification; label quality has not been independently audited here. Cancellation mentions in examples reflect expressed intent in review text, not confirmed account cancellations.