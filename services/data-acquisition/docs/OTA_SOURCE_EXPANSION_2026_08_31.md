# OTA Source Expansion — 2026-08-31

Status: bounded Explore only. No booking, authentication, production approval, storage, or scheduling is authorized.

## Existing pattern

The repository already contains a deterministic Booking.com public-search technique. Its approval contract requires exact destination/property, check-in, check-out, occupancy, currency, source URL, and observation time. A card without that context cannot become a comparable rate observation. Member or personalized prices are not universal public truth.

Tonight selected two registered, not-yet-validated transfer candidates with strong Thailand relevance: Agoda and Traveloka. Booking.com was not redundantly re-run.

## Agoda

One public HTTP request used this explicit context:

- destination: Bangkok (`city=9395`);
- check-in: 2026-09-15;
- check-out: 2026-09-16;
- rooms: 1;
- adults: 2;
- children: 0;
- requested currency: THB;
- first response only.

The official search URL returned HTTP 200 HTML (391,041 bytes), but the response contained a challenge marker. It exposed no accepted property URL, stable property identity, or explicit contextual THB rate to the bounded parser. The result is an access-boundary stop with zero retained records.

The Booking.com rendered-card/search-state technique remains conceptually transferable, but Agoda access was not validated. No browser, Edge, alternate date, alternate property, retry, login, member rate, or reservation flow followed.

## Traveloka

One public HTTP request targeted the registered official Thailand hotel destination surface. It returned HTTP 403 HTML (773 bytes) with a challenge marker and zero accepted property or rate records. Because this was an access-control response, no browser or Edge escalation followed.

No dates, occupancy, currency, or rate were observed, so the result is discovery-access failure only. It must not be represented as rate or availability evidence.

## Transfer assessment

| Source | Property identity | Contextual rate | Promotion | Access | Transfer status |
|---|---|---|---|---|---|
| Booking.com fixture | demonstrated deterministically | demonstrated with required context | context-dependent | fixture only tonight | existing pattern |
| Agoda | not retained | not retained | not retained | challenge marker on first request | promising pattern, access unvalidated |
| Traveloka | not retained | not retained | not retained | HTTP 403 challenge | not validated |

Both sources are paused pending a separately reviewed compliant public access technique. A blocked source is a valid Explore result and does not justify CAPTCHA handling, cookie/session reuse, proxy rotation, browser fingerprinting, or account use.

`production_approved=false`, production storage is disabled, and `scheduler_action=null`.
