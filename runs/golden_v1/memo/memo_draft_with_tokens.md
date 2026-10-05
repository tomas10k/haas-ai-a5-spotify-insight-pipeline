# Product Priority Memo: Playback Reliability for Next Quarter

## Recommendation
Prioritize **playback** this quarter. It carries the highest mean severity among sizable topics ({T003} mean severity, {T001} complaints, {T005} share of all complaints), and its top issue ISS_PLAYBACK_GENERAL has the highest priority score among playback issues ({C012} priority score). Fixing core play/pause/rewind reliability addresses the most acute pain even though it is not the highest-volume topic.

## Evidence
- ISS_PLAYBACK_GENERAL: {C009} complaints, mean severity {C011}, priority score {C012}. Example: review dceb14e7-2df0-422f-bb2b-73d7c373159a describes being unable to play or rewind songs after an update.
- ISS_PLAYBACK_AUDIO: {C017} complaints, mean severity {C019}, priority score {C020}. Example: review 47f1406d-4918-4d60-9647-5ca8e610caca reports playback quality degraded by recent updates.
- ISS_PLAYBACK_CRASH_OPEN: {C021} complaints, mean severity {C023}, priority score {C024}. Example: review 723f07de-9881-4049-8680-1a9e25652914 reports app crashing on launch.
- Topic-level, playback shows the highest mean severity of all topics ({T003}) with {T001} total complaints and {T005} share of complaints, and zero cancellations recorded ({T004}).
- Related ISS_DOWNLOADS_DOWNLOADS (offline playback failing) reinforces the same functional failure pattern, with priority score {C016}.

## Alternatives considered
- **Access**: No access-labeled topic or issues appear in the ranked list or topic totals; there is no evidence base here to support prioritizing access this quarter.
- **Usability**: ISS_USABILITY_ADS has notable volume ({C005} complaints, priority score {C008}) and the usability topic holds {T015} share of complaints, but its mean severity ({T013}) is lower than playback's, and the underlying issue (ad intrusiveness) is more about annoyance than functional breakage.
- **Billing/support**: Billing issues (ISS_BILLING_PREMIUM_PUSH, ISS_BILLING_PRICE, ISS_BILLING_SHUFFLE_FORCED) each have lower priority scores ({C028}, {C032}, {C036}) and the topic holds a smaller complaint share ({T020}). Notably this is the only topic with a recorded cancellation ({T019}), which deserves monitoring but does not outweigh the severity concentration in playback. The ISS_OTHER_GENERAL bucket ranks highest by volume ({C001} complaints, priority score {C004}) but its content spans unrelated app grievances and low mean severity ({C003}), so it is not actionable as a single area without further subclassification.

## Limitations
Coverage is partial: {F002} classifications completed against {F001} source rows, with {F003} quarantined and {F004} pending unclassified, so some topics may be undercounted. Reviews are self-selected public Google Play posts and skew toward complaints ({F006}) versus praise ({F007}) or requests ({F008}), with some unclear intent ({F009}). Cancellation mentions reflect expressed intent only, not observed churn. Label quality checks show verifier topic agreement {F011} and intent agreement {F012} on a sample of {F010}, and golden set agreement of {F015} topic and {F016} intent on {F014} hand labeled reviews, so issue groupings should be treated as directionally reliable but not exact.