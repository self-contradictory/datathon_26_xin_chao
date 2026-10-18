# Dataset rule coverage

The frozen scoring labels were extracted from the user-provided `open_labels.xlsx` and
`Нарушения_кассовых_операций_НПА_РК_2026_расширено.xlsm`.
See `dataset_labels.json` for source hashes, worksheet rows, exact descriptions, and normative caveats.

All 42 dataset videos are covered: 22 labelled violation and 20 labelled no_violation.
The 22 positive observations map to 20 reusable candidate rules. A rule is not unique to a filename.
The observer receives frames and timestamps, never these expected labels or dataset examples.

| Video | Expected | Labelled aspects and alternative rules |
|---|---|---|
| X-1.mov | violation | counted_cash_returned: CD17 |
| X-2.mov | violation | identification: CD12 |
| Х-3.mov | no_violation | negative control |
| Х-4.mov | violation | cash_storage: CD02, CD03 |
| Х-5.mov | no_violation | negative control |
| Х-8.mov | no_violation | negative control |
| Х-10.mov | no_violation | negative control |
| Х-11.mov | violation | unattended_computer: CD07 |
| Х-12.mov | no_violation | negative control |
| Х-13.mov | violation | cash_count: CD13; accounting_record: CD20 (external records required) |
| Х-14.mov | no_violation | negative control |
| Х-15.mov | violation | bag_storage: CD04 |
| Х-16.mov | no_violation | negative control |
| Х-17.mov | violation | identification: CD12 |
| Х-18.mov | violation | identification: CD12; cash_storage: CD02 |
| Х-19.mov | no_violation | negative control |
| Х-20.mov | violation | unattended_safe: CD05 |
| Х-21.mov | no_violation | negative control |
| Х-22.mov | violation | safe_key: CD06 |
| Х-23.mov | no_violation | negative control |
| Х-24.mov | violation | stamps_storage: CD08 |
| Х-25.mov | no_violation | negative control |
| Х-26.mov | violation | cash_storage: CD02, CD03 |
| Х-27.mov | no_violation | negative control |
| Х-28.mov | violation | unattended_computer: CD07 |
| Х-29.mov | no_violation | negative control |
| Х-30.mov | violation | equipment_ready: CD11 |
| Х-31.mov | no_violation | negative control |
| Х-32.mov | violation | open_door: CD09, CD10 |
| Х-33.mov | violation | open_door: CD09, CD10 |
| Х-34.mov | violation | customer_present_during_count: CD01 |
| Х-35.mov | no_violation | negative control |
| Х-37.mov | no_violation | negative control |
| Х-38.mov | violation | cash_storage: CD02, CD03; customer_present_during_count: CD01 |
| Х-39.mov | no_violation | negative control |
| Х-40.mov | violation | personal_items: CD14 |
| Х-43.mov | no_violation | negative control |
| Х-44.mov | violation | rejected_banknotes: CD18 |
| Х-45.mov | no_violation | negative control |
| Х-46.mov | violation | cash_exposed_during_food_break: CD15 |
| Х-47.mov | violation | cash_storage: CD02; different_customer_cash_mixed: CD19 |
| Х-48.mov | no_violation | negative control |

## Added coverage

- CD15 already covers Х-46. Food alone is not a violation trigger; exposed banknotes must also be observed.
- CD18 covers visibly rejected notes recombined without a visible check. It does not identify counterfeit currency.
- CD19 covers mixing cash whose origins from different customers or operations are visible.
- CD20 records the accounting requirement from Х-13. It requires external accounting evidence and is not inferred from camera footage.

The API now scans overlapping 12-second windows for the two provenance-dependent actions.
Each window contains up to six current frames and up to two earlier cash-receipt frames.
Uncertain origins produce hypothesis events; unknown frame references are rejected.
`TEMPORAL_SCAN=false` disables this extra pass. Temporal call counts and parsing errors are saved with the follow-up report.
These are sampled-frame checks, so events between samples can be missed. GPU accuracy has not been established by adding rules.

## Accuracy

With the API running, `python eval/batch_api.py` submits the labelled videos sequentially,
persists job IDs, resumes saved jobs, and scores after every terminal result.
`python eval/score_api.py var/dataset-verdicts` can also score existing API JSON files named `<video>.mov.json`,
including files created by the earlier PowerShell batch loop.
Both tools save `verdicts.csv` and `summary.json`.
Accuracy, precision, recall, F1, false positives and false negatives use completed jobs.
`correct_over_all`, failure counts and remaining counts keep unprocessed or failed cases visible.
Labelled-aspect recall checks whether a relevant rule was reported, excluding external-only accounting.
It does not establish timestamp accuracy or the absence of additional violations.

All rules remain candidates. The API reports some unconfirmed possible violations as `violation`.
The workbook itself makes several legal assessments conditional. Its 65 background NPA summaries
are retained as source context, not converted into camera-detectable rules about licensing, audits, or banking records.
Official Adilet pages did not expose their full text to the reader used for this change;
the new references are workbook-derived and remain `verified: false`.
