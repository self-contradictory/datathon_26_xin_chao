# Qwen3-VL-32B experiment findings

18 October 2026. One quick run of `eval/experiment_sweep.py` on the RTX A6000 (Windows 11, Qwen3-VL-32B-Instruct
in 4-bit, torch 2.14.1+cu126, transformers 5.20.1, commit `b5f59d2`). Two videos: Х-3 (clean) and Х-15
(violation: bag left on the desk, CD04). 41 seconds of video in total.

Two videos cannot show that any change improves verdicts. Treat every number below as a smoke-test reading.

## Results

### Verdicts and timelines

| Approach | Correct | False alarms | Timeline F1 | Missed segments | Fake segments |
|---|---:|---:|---:|---:|---:|
| api_default (the API today: full frame + region crops + pose/motion, uncalibrated) | 2/2 | 0 | 71.4% | 2/14 | 3 |
| calibrated (same + Otsu calibration per question) | 1/2 | 1 (Х-3) | 69.5% | 0/14 | 9 |
| Any new technique built on the calibrated base | 1/2 | 1 (Х-3) | 67–72% | 0/14 | 6–10 |
| Any new technique built on the uncalibrated base (re-scored on the Mac) | 2/2 | 0 | 56–71% | 2–4/14 | 2–4 |

- Calibration hurt with 32B: it added the false alarm on Х-3. 32B scores already split well at 0.5.
- On Х-15 the API flagged the right rule (CD04). It also raised two alarms for the wrong reasons:
  CD08 (stamps) and CD14 (personal items).
- The weakest timeline key was counting_cash: F1 0%. The API missed the one counting segment in Х-3 and
  reported one fake segment. cash_from_customer had F1 34%.

### Problems found

1. **Scene grounding failed for the safe, desk and door handle on both videos.** Those crops used the
   hard-coded default boxes. Grounding took 54 s (Х-15) and 129 s (Х-3) for 5 objects. 32B wrote prose before
   the coordinates and ran out of its 48-token limit.
2. **The generic desk stamps question fired on the wrong things.** "Are any small objects left on the
   desktop…?" was yes on 48% of frames of the clean video Х-3 and on 99% of Х-15 (the bag), which caused the
   off-target CD08 alarm. The specific question "Is a rubber stamp, a stamp pad or a seal lying on the desk?"
   stayed at or below 0.05 on both videos.
3. **The personal-items question fired on Х-15** (mean 0.25, max 1.0), causing the off-target CD14 alarm.
   Not fixed: the cause is not clear from these two videos.
4. **Follow-ups never ran in the sweep.** Another session moved them to plain text (`text()` and `entail()`),
   and the sweep's model wrapper only had `structured()`. They failed with warnings.
5. **Two jobs ran at the same time on one GPU** (API screenshot), which makes each job take twice as long.

### How well each view answers each question

AUC on annotated frames, where 0.5 is chance and 1.0 is perfect. counting_cash had only 3 positive samples,
so these differences may be noise.

| Key | Full frame 256 | Region crop | 3-frame hand clip | Pose-guided hand crop | Pose/motion |
|---|---:|---:|---:|---:|---:|
| counting_cash | 0.765 | 0.819 | 0.931 | 0.949 | 0.661 |
| handover | 0.972 | 0.993 | 1.000 | – | 0.906 |
| person_in_doorway | 0.868 | – | – | – | 0.905 |
| at_safe | 1.000 | 0.981 | – | – | 0.822 |

- "Is someone holding banknotes?" scored 0.907 (region crop) and 0.939 (hand crop) against counting_cash,
  higher than the counting question itself.
- full448, active320, full128 and clip_full were within a few AUC points of full256; full128 was worse.

### Cost

GPU seconds per second of video:

| Step | Cost |
|---|---:|
| Region crops (5 crops, desk and hands every second) | 5.33 |
| Scene grounding (fixed per video, shown per second) | 4.47 |
| 3-frame hand clip | 2.90 |
| Full frame, 256 tokens | 2.13 |
| Full frame, 448 tokens | 1.48 |
| Active-area crop | 1.36 |
| 3-frame full clip | 1.27 |
| Full frame, 128 tokens | 1.22 |
| 3-frame door clip | 0.94 |
| Pose-guided hand crop | 0.76 |
| Pose (Keypoint R-CNN) | 0.31 |
| Patch motion (CPU) | 0.24 |

- From the grounding timings, 4-bit 32B generates only about 2–5 tokens per second. Steps that generate text
  (grounding, the caption scan, follow-ups) are therefore the slow ones.
- The old JSON cash-provenance scan was 6/6 valid at 5.8 s per call. The API no longer uses it.

### Tried and rejected

Reusing the previous answer when a crop had not changed (to skip probe calls). Simulated on the 32B caches,
it skipped 16–46% of calls but flipped about one answer across 0.5 per skipped call. 32B answers jitter between
near-identical frames, and the timeline smoothing needs the repeated samples.

## Changes made (commit `7dd77fa`)

| Change | File | Reason |
|---|---|---|
| Grounding starts the answer with `{"bbox_2d": [` and generates 24 tokens; failures are logged with the raw answer | `perception/scene.py` | Fixes problem 1. With 2B on the Mac, all 5 objects were found on Х-3 with correct boxes, ~10 s per video |
| Minimum box size lowered from 0.01 to 0.005 | `perception/scene.py` | A real 16 × 10 door-handle box on Х-22 was rejected |
| Desk stamps question asks for a stamp, stamp pad or seal | `perception/regions.py` | Fixes problem 2 |
| `probe()` asks up to 32 questions per forward pass (was 8) | `reconstruction/vlm.py` | Fewer passes over the 4-bit weights; answers unchanged |
| `TEMPORAL_SCAN` defaults to false | `config.py` | The caption scan generates 96 tokens every 4 s of video; benefit unmeasured |
| Setup notes: `TEMPORAL_SCAN=false`, keep `JOB_WORKERS=1` | `WINDOWS_A6000.md` | Problem 5 |
| Sweep: refinement uses the API's plain-text captions and follow-ups; B and C approaches build on whichever of calibrated or uncalibrated did better; full448, full128 and clip_full skipped unless `--all-views`; output in a fresh `-v2` folder | `eval/experiment_sweep.py` | Fixes problem 4 and saves GPU time |

All 44 backend tests pass. The updated sweep re-scored the returned caches correctly, and its fast scorer
matches the API's reconstruction exactly (difference 0).

## Not verified

- No verdict improvement is shown; there are only two videos.
- The grounding fix was tested with 2B, not 32B.
- The new stamps question has not been run on the stamps video Х-24.
- The caption scan's cost is an estimate from the generation speed, and its accuracy effect is unknown.
- The personal-items false alarm (problem 3) is not fixed.

## Next run

Three new videos, about 25–30 minutes:

```powershell
.\.venv\Scripts\python.exe -u -B eval\experiment_sweep.py --videos X-24 X-1 X-16
```

| Video | Label | What it checks |
|---|---|---|
| Х-24 | violation, stamps (CD08) | The new stamps question still catches real stamps |
| X-1 | violation, counted cash returned (CD17) | Counting and handover timeline; whether the hand clip or hand crop beats the region crop |
| Х-16 | clean | False alarms from the ID card and the green bag (CD14) |

Also check that `grounding fell back to default boxes` shows 0 for every object, and how long the caption scan
takes per video.

# Round 2: fixes from the X-1, Х-16, Х-24 run

18 October 2026. Run 2 (commit `7dd77fa`, X-1, Х-16, Х-24) scored 0/3 with the API settings. I merged its caches
with run 1 (Х-3, Х-15) and re-scored every change on those 5 videos. I also checked each change on the 42-video 2B cache
(`eval/tuning/fused_bench.py`) so a fix for 32B does not break the other model.

## What went wrong, from the frames

| Video | Result | Cause |
|---|---|---|
| Х-16 (clean) | CD25 phone, CD13 | The cashier holds the customer's ID card up to her face. Every view said "phone" and "eating". Customer presence came from pose alone (AUC 0.83 vs 1.00 for the full frame), flickered, and split one visit into two. |
| X-1 (CD17) | missed | Counting got fused away: the full frame (counting AUC 0.54) had weight 1.0 against 0.5 for the hands crop. 32B also can't tell which way cash moves; at 6 s, where the customer hands over cash, it scored "cashier hands cash to customer" 0.65. |
| Х-24 (CD08) | missed | The stamps are two teal round self-inking stamps. 32B called them cups (`food_on_desk` 0.9+) and answered the stamp question with 0.00. The generic "any small objects left on the desk" question was yes on every frame. |
| Х-3, Х-16 | | In customer videos the cashier sits with her back to the camera. The prompt said "the cashier works behind the desk", which describes the customer. |

## Changes

| Change | File |
|---|---|
| Customer presence uses the full-frame answer as well as pose, weight (0.5, 0, 1.0) | `perception/fusion.py` |
| Counting and handover lean on the hands crop: (0.2, 1.0, 0.2) and (0.5, 1.0, 0.2). Cash direction gets crop weight. | `perception/fusion.py` |
| Phone and eating are multiplied by (1 − held ID card or banknotes) | `perception/fusion.py` |
| New desk question "any small objects left besides phone, laptop, counting machine". Whatever isn't cash, a bag or a personal item counts as stamps. | `perception/regions.py`, `fusion.py` |
| desk_hands is a 3-frame clip (t−0.5, t, t+0.5 s) at 160 tokens per frame instead of one crop | `perception/regions.py`, `pipeline.py`, `reconstruction/vlm.py` |
| CD05B "safe left open" needs the cashier away from the desk too | `reconstruction/derived.py` |
| Role wording: the cashier is the one at the laptop and may sit with their back to the camera | `reconstruction/probes.py`, `regions.py` |
| Speed: the full frame no longer asks 8 questions a crop answers better (23 → 15 questions) | `perception/pipeline.py` |
| Speed: one batched grounding call for all 5 objects (same boxes on 2B; X-24 11.4 s → 6.8 s on the Mac) | `perception/scene.py` |
| Speed: desk crop at 0.5 fps; follow-ups off by default (`FOLLOWUP_MAX_CALLS=0`, ~45 s per video on 32B, never shown to change a verdict) | `regions.py`, `config.py` |
| Sweep: same crops and clip as the API, `--api-only`, output folder `-v3` | `eval/experiment_sweep.py` |

## Scores

| | 32B, 5 videos | 2B, 42 videos |
|---|---:|---:|
| Before | 2/5, FP 1, timeline F1 58.8%, visits 4/5 | 28/42, FP 8, FN 6 |
| After | 4/5, FP 0, timeline F1 59.5%, visits 5/5 | 28/42, FP 7, FN 7 |

The 32B "after" row is simulated: the new desk_hands clip and leftovers question were taken from the
`clip_hands` view and the old generic stamps question, which used the same wording. The new role wording
is not in any cache. Five videos prove little; the 42-video run below is the real test. All 53 backend tests pass.
The API runs end to end on the Mac with 2B (Х-24: CD08 found, 75 s).

Still missed: X-1. The cash direction questions are close to chance on 32B. The role wording is the only change aimed at it.

## Next run (10 short videos, API views only)

```powershell
.\.venv\Scripts\python.exe -u -B eval\experiment_sweep.py --api-only --videos X-1 X-16 X-17 X-20 X-23 X-24 X-28 X-33 X-37 X-46
```

175 s of video. Estimate from the per-view costs of run 2: 2.2–3 GPU s per video second, so about 7–9 minutes
plus model loading. Pose, grounding, the full frame and the region crops only: no extra questions, no follow-ups,
no tuning. Writes to `var\experiments\Qwen3-VL-32B-Instruct-4bit-v3-api`. Send back `send_me.zip`.

| Video | Label | Checks |
|---|---|---|
| X-1 | CD17 cash handed back | the only remaining miss; role wording and the hands clip |
| Х-16 | clean, ID check | the phone false alarm stays gone with the real clip |
| Х-17 | CD12 no ID | missing-ID detection |
| Х-20 | CD05 safe open, cashier left | the stricter CD05B still fires |
| Х-23 | clean, room empty at the end | the new "anything left on the desk" question on a clear desk |
| Х-24 | CD08 stamps | the new desk question for real |
| Х-28 | CD07 computer on | laptop crop when unattended |
| Х-33 | CD09 door open | door crop |
| Х-37 | clean, customer visit | no CD12/CD13/CD25 false alarms |
| Х-46 | CD15 eating with cash out | eating still fires when nothing is held |
