# Perception tuning

Offline tooling for the perception pipeline (`backend/perception/`): cache the expensive
observations once, then tune the timeline and verdict parameters against the 42 labelled videos
without rerunning the model. All scripts run from `backend/` with `PYTHONPATH=eval/tuning`.

## Pipeline

Qwen3-VL-2B still answers yes/no questions by reading the Yes/No logits; nothing generates JSON.
The structured follow-up calls and the cash provenance scan are off by default
(`FOLLOWUP_MAX_CALLS=0`, `TEMPORAL_SCAN=false`): with the 2B model most of them ran out of tokens
on invalid JSON at ~150 s per call.

| Stage | What it adds | Code |
|---|---|---|
| Scene grounding | Desk, safe, laptop, counting machine and door handle boxes from one short grounding generation per object on the median frame | `perception/scene.py` |
| Full-frame probes | The original 23 questions at 1 fps | `reconstruction/probes.py` |
| Zoomed region probes | Desk, hands-over-desk, safe, laptop and door crops, each with its own questions | `perception/regions.py` |
| Body keypoints | Keypoint R-CNN people and skeletons at 4 fps (torchvision, no new dependency) | `perception/pose.py` |
| Local patch motion | Frame difference, DIS optical flow and background difference on an 8 px grid at 10 fps | `perception/motion.py` |
| Signals | In-room people (desk-line test, duplicate boxes merged, people sitting behind the glass dropped), customer present, at station, doorway, at safe, hands over desk, hand to mouth, door change against the start | `perception/features.py` |
| Fusion | Per-question label-free calibration (Otsu threshold on every frame's logit), then a weighted logit average per key; pose evidence is one-sided where a missed wrist proves little; the door needs the crop and the patch change to agree; object states are unknown in the dark | `perception/fusion.py` |
| Timeline | The existing binary HMM, `build_timeline` and rule engine; customer actions are split at visit boundaries | `reconstruction/` |

`PerceptionReconstructor` (`perception/pipeline.py`) is a drop-in replacement for `Reconstructor`;
the API uses it when `PERCEPTION=true` (default) and loads `perception/calibration.json` for the
observer model.

## Reproduce

```sh
PYTHONPATH=eval/tuning .venv/bin/python -B eval/tuning/probe_cache.py --name base-full --fps 1 --tokens 256
PYTHONPATH=eval/tuning .venv/bin/python -B eval/tuning/scene_cache.py
PYTHONPATH=eval/tuning .venv/bin/python -B eval/tuning/motion_cache.py --fps 10
PYTHONPATH=eval/tuning .venv/bin/python -B eval/tuning/pose_cache.py
PYTHONPATH=eval/tuning .venv/bin/python -B eval/tuning/region_cache.py
PYTHONPATH=eval/tuning .venv/bin/python -B eval/tuning/region_cache.py --name regions2 --keys stamps_on_desk --rate 0.5

PYTHONPATH=eval/tuning .venv/bin/python -B eval/tuning/bench.py base-full --original-rules   # baseline
PYTHONPATH=eval/tuning .venv/bin/python -B eval/tuning/run_tuning.py --regions regions+regions2 --label regions2
PYTHONPATH=eval/tuning .venv/bin/python -B eval/tuning/report.py base-full-original-rules E5-tuned-regions2
```

Caches and results go to `var/tuning/`. `timeline_eval.py` scores decoded tracks against
`eval/reconstruction_annotations.json` (15 annotated videos, 0.25 s samples, ignore spans skipped).

## Caveats

Every number here is measured on the same 42 videos the rules and features were developed on.
Rule refinements were made after watching these videos, so the verdict accuracy is optimistic.
The tuner reports a stratified 7-fold held-out accuracy for its parameters, but the design choices
above it were not held out.
