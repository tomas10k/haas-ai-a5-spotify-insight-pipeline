# Product Priority Memo: Q Next Focus Area

## Recommendation

Next quarter's product effort should prioritize **usability**. It is the second highest ranked issue area by severity sum, with ISS_USABILITY_ADS alone contributing {C006} severity points across {C005} complaints, and the usability topic overall carries {T007} severity sum and {T006} complaints, the second largest share of all complaints at {T010}. Within usability, disruptive ad breaks, layout/navigation regressions after updates, and playlist/liked-song deletions are recurring, high severity complaint clusters that directly degrade the core listening experience for both free and paying users.

## Evidence

- ISS_USABILITY_ADS ranks second overall with {C005} complaints, severity sum {C006}, and mean severity {C007}; example reviews report repeated ad breaks and lost liked songs (e.g. ee11e1df-cb73-4c3a-b5e8-7268c7872b01, 1e4d3214-63de-4ba0-9870-a4ee8aa32942).
- ISS_USABILITY_UPDATE_LAYOUT (rank 5) shows {C017} complaints and severity sum {C018}, driven by layout changes causing lost playlists (abbaae58-fa49-48c6-a973-f71a978be85d, 16f4505c-8b84-41e3-8cb8-2cef60b269f1).
- ISS_USABILITY_QUEUE_PLAYLIST (rank 10) adds {C037} complaints, severity sum {C038}, centered on unexpected deletion of liked songs (f2c11a77-9616-4d3c-9ea9-85895f42ea7c, 9581a175-9da8-4523-89ac-6ae066c95532).
- ISS_USABILITY_GENERAL contributes {C033} complaints and severity sum {C034}, with recurring complaints about hidden or deleted content (27aa8b25-fec9-4408-9a7e-e582f98e24bb).
- At the topic level, usability shows {T009} instances of cancellation intent language, the second highest after billing, suggesting usability friction is strongly tied to expressed intent to leave.

## Alternatives considered

- **Playback**: Topic mean severity is highest ({T018}), and ISS_PLAYBACK_GENERAL and ISS_PLAYBACK_CRASH_OPEN are severe, but total topic complaint volume ({T016}) and severity sum ({T017}) are lower than usability, placing it third priority.
- **Billing/support**: Billing has the highest cancellation-intent count ({T014}) and meaningful severity ({T012}), and ISS_BILLING_PREMIUM_PUSH ranks third overall ({C010} severity sum). It remains a strong secondary candidate but trails usability on complaint volume ({T011} vs {T006}). Support is negligible in volume ({T036}, {T040} share).
- **Access**: Smallest topic by complaint share ({T030}) despite high mean severity ({T028}); ISS_ACCESS_LOGIN is notable but lower overall priority score than top usability issues.

## Limitations

- Coverage: {F002} classifications completed from {F001} source rows, with {F003} quarantined and {F004} pending unclassified; conclusions reflect only classified reviews.
- Intent distribution shows {F005} cancellation, {F006} complaint, {F007} praise, {F008} request, and {F009} unclear labels; cancellation language is self-reported intent, not observed churn.
- Reviews are self-selected Google Play submissions, not a random sample of all users, so volume and severity may not generalize to the full user base.
- Label quality: verifier agreement on topic is {F011} and intent is {F012} over a sample of {F010}; severity exact match is {F013}. Golden set agreement ({F014} reviews) shows topic agreement {F015}, intent agreement {F016}, and severity exact match {F017}, indicating some residual labeling noise should temper precise ranking confidence.