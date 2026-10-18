# Plain-text semantic benchmark

Run from `backend/` on the machine that will perform inference:

```sh
.venv/bin/python -u -B eval/benchmark_semantics.py --model Qwen/Qwen3-VL-32B-Instruct --device cuda --quantization 4bit
```

Replace the model with another Qwen3-VL checkpoint or use `--model-path /path/to/checkpoint`.
Omit `--device` to choose CUDA, Apple MPS or CPU automatically. On Windows use
`.venv\Scripts\python.exe` instead. Install the project dependencies first using `uv sync --locked`.
The selected model downloads from Hugging Face if needed; `--offline` disables downloads.
For 4-bit CUDA loading, install bitsandbytes and pass `--quantization 4bit`.

The default runs fresh perception on every video in `data/open/videos`, so it does not need
the author's local inference caches or tuned 2B configuration. Video files must be present
on the target machine. `--videos-dir /path/to/videos` selects their location. The default
label file is `eval/expected_api_verdicts.json`. All 42 labelled files are evaluated.
JSON labels and artifacts use UTF-8 explicitly on Windows. Latin `X` and Cyrillic `Х`
filename prefixes are matched while retaining the canonical label names for scoring.
Missing or ambiguous files are reported before model loading. Snapshot creation does not
require symlinks or Windows administrator privileges.

Five methods share the same initial observations and captions per video:

| Method | What runs |
|---|---|
| baseline | Fresh VLM probes, regions, pose, motion, timeline and rules |
| plain_followups | Baseline plus prose evidence checks and semantic classification |
| captions_only | Sliding-window prose, semantic facts, timeline and rules |
| baseline_captions | Baseline with explicit caption evidence added; omissions preserve the baseline |
| captions_followups | Caption timeline plus plain-text follow-ups |

Descriptions use 8-second windows, a 4-second stride, up to six ordered frames and 96 output
tokens. Semantic matching reads supported/contradicted/unclear token scores; it does not
parse generated JSON. IDs and graph facts are assembled by application code. Unmentioned
facts remain unknown. Follow-ups recheck uncertain findings and positive alerts. Derived
states are recomputed after evidence changes. Event checks inspect frames even when the rule
omits participant mappings. Actors are resolved only from existing, unambiguous graph roles,
episode roles or anchors. An unresolved actor keeps its raw description without inventing
an event. Speculative descriptions are not upgraded to observed actions.
A missing action between samples never proves
that a required procedure was omitted.

The default follow-up budget is two visual questions per video and method, with at most two
sampled frames per question. A separate, bounded semantic alignment pass does not consume
this budget. Visual checks may require multiple model calls. Generation has a cooperative
20-second stopping limit, not a hard GPU deadline. Adjust with `--followup-max-calls`,
`--followup-frames` and `--call-seconds`. Generated JSON is disabled in the plain-text model.
Internal graphs and saved JSON reports are still validated application data.

The terminal prints accuracy, precision, recall, F1, timeline F1 and follow-up error counts.
`var/semantic_benchmark_2b/REPORT.md`, `comparison.csv` and `summary.json` contain full results.
Per-video folders retain captions, graphs, rule reports, follow-up answers and errors.
The default output directory name can be overridden with `--out var/semantic_32b`.

Repeating the exact command resumes completed methods and cached model calls. Failed methods
are retried. A changed model, source, labels, videos or settings requires a new output directory.
Use `--score-only --out <previous-output>` to print saved scores without loading model weights.

For a smaller run add `--videos Х-15 Х-16`; use `--methods` to select comparisons. The author's
old 2B caches are optional through `--baseline cached`, and are only accepted with the matching
model and complete cache files. They are not needed for the normal fresh run.

Scores measure these development videos, not an untouched test set. Failures count as wrong
for accuracy, and timeline abstentions count as errors. Unknowns are not rewarded as correct
negatives. Unique-video and common-completed-video comparisons are included in `summary.json`.
Cached work and inference calls are reported separately; shared setup/caption work is performed
once and is not a fair end-to-end latency comparison between methods. One-video smoke results
establish that paths execute, not that their accuracy improves. The active API caption and follow-up paths use prose and semantic matching; the old structured
follow-up benchmark option has been removed. To disable the API caption scan, set
`TEMPORAL_SCAN=false`; `FOLLOWUP_MAX_CALLS=0` disables visual follow-ups.
