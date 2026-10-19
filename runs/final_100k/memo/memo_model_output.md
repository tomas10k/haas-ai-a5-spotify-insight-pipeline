# Product Priority Memo: Q1 Next Quarter Focus

## Recommendation
Prioritize **billing and support** for next quarter's product effort. While usability carries the largest overall volume and severity, billing and support is the only area whose complaint share rose sharply between the 2022 and 2023 comparison windows, climbing from 3.8% [F026] to 13.2% [F033], signaling a worsening trend layered on already substantial volume (8712 [T056] complaints, 25091 [T057] severity sum) and the highest cancellation association among the four areas (1342 [T059] cancellations).

## Evidence
- Area ordering by complaint count and severity sum both place billing and support second behind usability: 10748 [T046] vs 8712 [T056] complaints, 27860 [T047] vs 25091 [T057] severity sum.
- Billing and support shows the highest cancellation count of the four areas at 1342 [T059], well above usability's 919 [T049], playback's 578 [T054], and access's 75 [T044].
- Trend direction diverges across areas: billing and support share rose from 3.8% [F026] to 13.2% [F033]; usability fell slightly from 10.8% [F024] to 9.4% [F031]; playback fell from 8.0% [F025] to 4.4% [F032]; access rose modestly from 1.0% [F023] to 1.8% [F030] but from a much smaller base.
- Top ranked issue ISS_BILLING_PREMIUM_PUSH shows concrete billing pain: 3457 [C009] complaints, 9673 [C010] severity sum, with example reviews a835c23b-3e27-493c-a9df-1a9b5ee04f09 ("I paid for the ad free but there's ad's") and 1be24878-5115-490a-bb7f-dad95d0630ab describing an unexpected deduction.
- Usability remains the largest single area by volume and severity (10748 [T046], 27860 [T047]), driven heavily by ISS_USABILITY_ADS (5825 [C005] complaints, 13662 [C006] severity sum), but its trend share is falling, not rising.
- The generic "other" bucket is the single largest topic overall (14108 [T001] complaints, 27937 [T002] severity sum, 31.8% [T005] share) but is not one of the four product areas and reflects undifferentiated dissatisfaction, not an actionable area.

## Alternatives considered
- **Usability**: Highest raw volume and severity sum among the four areas (10748 [T046], 27860 [T047]), and still worth incremental fixes (ad load, playlist integrity), but its trend share declined (10.8% [F024] to 9.4% [F031]), suggesting pressure is easing relative to classified volume.
- **Playback**: Highest mean severity among the four areas (3.445708 [T018]), per orderings_computed_by_code topics_by_mean_severity, but both volume (6069 [T051]) and trend share (8.0% [F025] to 4.4% [F032]) are declining, making it a lower relative priority now.
- **Access**: Lowest volume and severity of the four (1473 [T041], 5806 [T042]), despite having the highest mean severity in the area set per areas_by_mean_severity ordering. Its trend share rose (1.0% [F023] to 1.8% [F030]) but remains the smallest in absolute share, so it is a watch item, not a top priority.

## Limitations
This analysis covers a seeded sample of classified reviews; the full file contains 660622 [F005] rows with 660609 [F006] nonempty reviews, of which 560609 [F007] nonempty reviews were not classified and lie outside this scope. Reviews are self-selected and skew toward complaints, so rising shares are signals, not confirmed population shifts. Label quality is imperfect: verifier topic agreement is 83% [F014] and severity exact-match is 81% [F016]; golden-set agreement is 88% [F018] topic and 78% [F020] severity, meaning some issue and severity assignments may be noisy. The large "other" topic bucket is generic and not diagnostic of a specific product area, limiting how much of overall dissatisfaction can be attributed to the four areas above.