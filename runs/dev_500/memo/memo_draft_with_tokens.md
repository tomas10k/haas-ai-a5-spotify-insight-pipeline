# Product Priority Memo: Q Next Focus Area

## Recommendation
Prioritize playback reliability (topic: playback) for the next quarter of product effort. While usability issues have more raw complaint volume, playback carries the highest mean severity among major topics at {T013}, and includes several high severity issues such as ISS_PLAYBACK_GENERAL, ISS_PLAYBACK_CONNECTION, ISS_PLAYBACK_CRASH_OPEN, and ISS_PLAYBACK_STOPS_PAUSES. These are core functionality breakdowns (songs not playing, crashes, unexpected stops) that directly block the app's primary use case.

## Evidence
- Topic playback has {T011} complaints with severity sum {T012} and mean severity {T013}, the highest mean severity of any major topic, with {T014} cancellation mentions.
- ISS_PLAYBACK_GENERAL (rank 4): {C013} complaints, mean severity {C015}, priority score {C016}. Example: review a0cbc9d6-51bb-46f0-9ba9-ad4f4593c266 describes liked songs failing to play.
- ISS_PLAYBACK_CRASH_OPEN (rank 8): {C029} complaints, mean severity {C031}. Example: review 065c418e-7f18-42a3-b241-fe693b7a2b0c describes repeated black screen crashes requiring reinstalls.
- ISS_PLAYBACK_CONNECTION (rank 7): {C025} complaints, mean severity {C027}. Example: review f1abd13b-2391-4b04-8109-efa7f3cfed0b reports continuous random pausing.
- ISS_PLAYBACK_STOPS_PAUSES (rank 10): {C037} complaints, mean severity {C039}, including reports of the app becoming unusable on certain devices.

## Alternatives considered
- Usability ranks higher in share of complaints at {T010} and complaint count {T006}, driven largely by ISS_USABILITY_ADS ({C005} complaints, priority score {C008}) and layout backlash (ISS_USABILITY_UPDATE_LAYOUT). However mean severity {T008} is lower than playback, suggesting more annoyance than functional failure.
- Billing shows meaningful severity ({T003}) and the highest cancellation count among named topics at {T004}, with ISS_BILLING_PREMIUM_PUSH and ISS_BILLING_SKIP_LIMIT as notable issues. Worth a follow on investment but secondary this quarter.
- Access has the highest topic mean severity at {T028} but very low volume ({T026} complaints), limiting overall impact versus playback.

## Limitations
Coverage is partial: of {F001} source rows, {F002} classifications are completed, {F003} quarantined, and {F004} pending unclassified, so rankings may shift as more reviews are processed. Reviews are self selected public posts and may overrepresent frustrated users. Label quality checks show verifier topic agreement {F011} and intent agreement {F012} on a sample of {F010}, and golden set agreement of {F015} topic and {F016} intent on {F014} hand labeled reviews, indicating reasonably but not perfectly reliable labels. Severity exact match rates ({F013} verifier, {F017} golden) suggest some noise in severity scoring specifically, which should temper confidence in precise mean severity rankings.