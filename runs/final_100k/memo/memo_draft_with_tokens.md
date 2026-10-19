# Product Priority Memo: Q1 Next Quarter Focus

## Recommendation
Prioritize **billing and support** for next quarter's product effort. While usability carries the largest overall volume and severity, billing and support is the only area whose complaint share rose sharply between the 2022 and 2023 comparison windows, climbing from {F026} to {F033}, signaling a worsening trend layered on already substantial volume ({T056} complaints, {T057} severity sum) and the highest cancellation association among the four areas ({T059} cancellations).

## Evidence
- Area ordering by complaint count and severity sum both place billing and support second behind usability: {T046} vs {T056} complaints, {T047} vs {T057} severity sum.
- Billing and support shows the highest cancellation count of the four areas at {T059}, well above usability's {T049}, playback's {T054}, and access's {T044}.
- Trend direction diverges across areas: billing and support share rose from {F026} to {F033}; usability fell slightly from {F024} to {F031}; playback fell from {F025} to {F032}; access rose modestly from {F023} to {F030} but from a much smaller base.
- Top ranked issue ISS_BILLING_PREMIUM_PUSH shows concrete billing pain: {C009} complaints, {C010} severity sum, with example reviews a835c23b-3e27-493c-a9df-1a9b5ee04f09 ("I paid for the ad free but there's ad's") and 1be24878-5115-490a-bb7f-dad95d0630ab describing an unexpected deduction.
- Usability remains the largest single area by volume and severity ({T046}, {T047}), driven heavily by ISS_USABILITY_ADS ({C005} complaints, {C006} severity sum), but its trend share is falling, not rising.
- The generic "other" bucket is the single largest topic overall ({T001} complaints, {T002} severity sum, {T005} share) but is not one of the four product areas and reflects undifferentiated dissatisfaction, not an actionable area.

## Alternatives considered
- **Usability**: Highest raw volume and severity sum among the four areas ({T046}, {T047}), and still worth incremental fixes (ad load, playlist integrity), but its trend share declined ({F024} to {F031}), suggesting pressure is easing relative to classified volume.
- **Playback**: Highest mean severity among the four areas ({T018}), per orderings_computed_by_code topics_by_mean_severity, but both volume ({T051}) and trend share ({F025} to {F032}) are declining, making it a lower relative priority now.
- **Access**: Lowest volume and severity of the four ({T041}, {T042}), despite having the highest mean severity in the area set per areas_by_mean_severity ordering. Its trend share rose ({F023} to {F030}) but remains the smallest in absolute share, so it is a watch item, not a top priority.

## Limitations
This analysis covers a seeded sample of classified reviews; the full file contains {F005} rows with {F006} nonempty reviews, of which {F007} nonempty reviews were not classified and lie outside this scope. Reviews are self-selected and skew toward complaints, so rising shares are signals, not confirmed population shifts. Label quality is imperfect: verifier topic agreement is {F014} and severity exact-match is {F016}; golden-set agreement is {F018} topic and {F020} severity, meaning some issue and severity assignments may be noisy. The large "other" topic bucket is generic and not diagnostic of a specific product area, limiting how much of overall dissatisfaction can be attributed to the four areas above.