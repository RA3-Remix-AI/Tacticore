# Full-match production audit: 20261025-034721

Result: verified. Native read-only final mapping and all five executable entries were checked.

6 accepted orders, 15 pre-build rejections. Real cost/paid total 510 of budget 4000. All accepted orders have queue nodes, debit events, object creation, completion and live samples.

|seq|queue|unit object|cost=paid|debits|live samples|
|---:|---:|---:|---:|---:|---:|
|1|5|779|85|60|2011|
|3|10|797|85|60|7472|
|4|13|804|85|60|7228|
|5|14|806|85|60|7054|
|6|15|808|85|60|6879|
|7|16|812|85|60|1420|

No-build rejection reasons: {'minimum_interval_guard': 2, 'price_budget_reserve_or_liability_guard': 12, 'queue_guard': 1}.

Native stopped at phase2/error0/restore31/active0; all five original code-entry bytes match. No status-persistence or binding stop occurred in this match. The temporary-file sharing repair remained stable during the run.

The host reached a native result candidate. Winner confirmation is delegated to the native result and visual reviewers. Earlier interrupted runs are not counted.
