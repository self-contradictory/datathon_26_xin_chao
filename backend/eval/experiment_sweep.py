r"""Try many video-analysis techniques on every labelled video and report how well each one works.

Built for an RTX A6000 running Qwen3-VL-32B in 4-bit; any local Qwen3-VL checkpoint works.

Stages. Every expensive result is cached per video, so Ctrl+C or a crash loses at most one video.
  1. GPU observations ("views"): yes/no probe scores from the full frame at 128/256/448 image tokens, a crop
     of the active area, the API's zoomed region crops plus extra and negated questions, pose-guided hand
     crops and multi-frame clips (hands, door, full frame); body keypoints (Keypoint R-CNN); local patch
     motion (frame difference, DIS optical flow, background difference); scene grounding.
  2. Probe quality: AUC of every question of every view against the annotated timeline frames.
  3. About 25 approaches (combinations of views, calibration, fusion and timeline settings) rebuild the
     timeline and run the rules on every video: verdict accuracy, violation type and time, timeline frame
     F1, missed and fake segments, customer visits.
  4. The structured JSON follow-ups and cash provenance scan on the best approach (GPU, time-limited),
     then cross-validated tuning of its offsets and timeline settings.
  5. Text reports, per-video timeline strips, and send_me.zip with the reports and the small caches.

Run from backend/ (PowerShell). The model settings come from the same environment variables as the API
(MODEL_PATH, MODEL_DEVICE, MODEL_QUANTIZATION); --model-path, --device and --quantization override them.
    $env:PYTHONUTF8 = "1"
    $env:MODEL_PATH = "$env:USERPROFILE\models\Qwen3-VL-32B-Instruct"
    $env:MODEL_DEVICE = "cuda"
    $env:MODEL_QUANTIZATION = "4bit"
    .\.venv\Scripts\python.exe -u -B eval\experiment_sweep.py --quick
    .\.venv\Scripts\python.exe -u -B eval\experiment_sweep.py

--quick runs two short videos end to end as a smoke test. Repeating a command resumes from the caches.
--report-only re-scores the cached observations without loading a model.
Labels are read only by the scorers; the observers never receive them.
"""
import argparse
import contextlib
import copy
import hashlib
import json
import logging
import math
import os
import platform
import re
import shutil
import subprocess
import sys
import time
import traceback
import zipfile
from dataclasses import dataclass, field, replace
from pathlib import Path
from time import perf_counter

import cv2
import numpy as np

BACKEND = Path(__file__).resolve().parents[1]
EVAL = BACKEND / "eval"
if str(BACKEND / "src") not in sys.path:
    sys.path.insert(0, str(BACKEND / "src"))

import torch  # noqa: E402

from backend.followup.pipeline import refine  # noqa: E402
from backend.perception import fusion as fusion_module  # noqa: E402
from backend.perception.features import FeatureConfig, Signals, compute_signals  # noqa: E402
from backend.perception.fusion import CV_ABSENCE, DEFAULT_WEIGHTS, FusionConfig, fuse, logit, sigmoid  # noqa: E402
from backend.perception.hands import HAND_PROBES, HAND_TOKENS, hand_box  # noqa: E402
from backend.perception.motion import PatchMotion, patch_motion  # noqa: E402
from backend.perception.pipeline import Observations, PerceptionConfig, reconstruct  # noqa: E402
from backend.perception.pose import PoseEstimator, PoseSequence, detect_people  # noqa: E402
from backend.perception.regions import CONTEXT as REGION_CONTEXT, RATES, REGION_PROBES, TOKENS, crop  # noqa: E402
from backend.perception.scene import Scene, locate, median_background  # noqa: E402
from backend.reconstruction import derived as derived_module, graph as graph_module  # noqa: E402
from backend.reconstruction.decode import Observation  # noqa: E402
from backend.reconstruction.graph import ACTION_EVENTS, build_timeline  # noqa: E402
from backend.reconstruction.pipeline import AttributeTrack, Reconstruction, decode_tracks  # noqa: E402
from backend.reconstruction.probes import PERCEPTION_PROBES, PROBES, SCENE_CONTEXT  # noqa: E402
from backend.reconstruction.temporal import observe_cash_provenance  # noqa: E402
from backend.reconstruction.video import DecodedVideo, decode  # noqa: E402
from backend.reconstruction.vlm import MODEL_IDS, QuestionVLM, fit_tokens  # noqa: E402
from backend.rules.engine import evaluate  # noqa: E402
from backend.rules.registry import load_registry  # noqa: E402
from backend.rules.verdict import ReportingPolicy, reportable  # noqa: E402

logger = logging.getLogger("experiment_sweep")

GRID_FPS = 2.0      # analysis grid, as PerceptionConfig.grid_fps in the API
POSE_FPS = 4.0
MOTION_FPS = 10.0
STEP = 0.25         # timeline scoring resolution, seconds
CHAR = 0.5          # seconds per character in the timeline strips
PAD = 0.25          # an action event covers its first and last sample +- half the grid spacing
QUICK = ("Х-15", "Х-3")
FUSED_KEYS = [probe.key for probe in PERCEPTION_PROBES]
REGISTRY = load_registry()
SHADOW = ReportingPolicy(production_only=False)
STRICT = ReportingPolicy(production_only=False, surface_unknown=frozenset())

# Hand-made timelines for 16 clips (data/annotations/ideal_timeline_v1 in the main repo), reduced to the
# timeline keys: "a" positive intervals per key, "i" ambiguous spans excluded from scoring, "v" customer
# visits; -1 is the end of the clip. eval/reconstruction_annotations.json wins where both label a key.
IDEAL_TIMELINE = r"""{
 "X-1": {"a":{"cashier_seated":[[0,-1]],"customer_present":[[5.8,-1]],"room_occupied":[[0,-1]],"safe_open":[],"counting_cash":[[7,9.5],[11,13.8],[20.5,22.8]],"cash_from_customer":[[6,7],[19.5,20.5]],"cash_to_customer":[[22.8,24]],"handover":[[6,7],[19.5,20.5],[22.8,24]],"person_in_doorway":[[1.5,3.5]],"at_safe":[],"using_computer":[],"id_document":[]},"i":{"counting_cash":[[13.8,15.5]]},"v":[[5.8,-1]]},
 "X-2": {"a":{"cashier_seated":[[0,-1]],"customer_present":[[8.3,-1]],"room_occupied":[[0,-1]],"safe_open":[],"counting_cash":[],"cash_from_customer":[],"cash_to_customer":[],"handover":[],"person_in_doorway":[[3.2,5.5]],"at_safe":[],"using_computer":[],"id_document":[]},"i":{"counting_cash":[[10,13.5],[13.5,15.8]],"cash_from_customer":[[9,10]],"handover":[[9,10]],"id_document":[[9,10]]},"v":[[8.3,-1]]},
 "Х-3": {"a":{"cashier_seated":[[0,-1]],"customer_present":[[6.3,-1]],"room_occupied":[[0,-1]],"safe_open":[],"counting_cash":[[13.3,16.8]],"cash_from_customer":[[7.3,8.5],[11.8,13.3]],"cash_to_customer":[],"handover":[[7.3,8.5],[11.8,13.3]],"person_in_doorway":[[1.5,4.5]],"at_safe":[],"using_computer":[],"id_document":[]},"i":{"counting_cash":[[8.5,11.8],[16.8,18.7]]},"v":[[6.3,-1]]},
 "Х-4": {"a":{"cashier_seated":[[0,-1]],"customer_present":[[9.5,50.5],[59.5,-1]],"room_occupied":[[0,-1]],"safe_open":[],"counting_cash":[[13,18],[32,39]],"cash_from_customer":[[11.5,13],[65.5,68]],"cash_to_customer":[],"handover":[[11.5,13],[65.5,68]],"person_in_doorway":[[4.5,8],[49.5,54],[55.5,59]],"at_safe":[],"using_computer":[[42,47],[70,-1]],"id_document":[]},"i":{"counting_cash":[[24.5,27.5],[68,70]],"cash_from_customer":[[61.5,63]],"handover":[[61.5,63]],"id_document":[[61.5,63]]},"v":[[9.5,50.5],[59.5,-1]]},
 "Х-5": {"a":{"cashier_seated":[[0,-1]],"customer_present":[[5.5,57],[68,-1]],"room_occupied":[[0,-1]],"safe_open":[[48,52.5]],"counting_cash":[[8.5,13.5],[33,41.5]],"cash_from_customer":[[6.5,8.5]],"cash_to_customer":[],"handover":[[6.5,8.5]],"person_in_doorway":[[0,3],[56.5,61],[63,66]],"at_safe":[[46.5,48.5],[48.5,51.5],[51.5,54]],"using_computer":[[41.5,46.5]],"id_document":[]},"i":{"counting_cash":[[27,29]],"cash_from_customer":[[69,-1]],"handover":[[69,-1]],"id_document":[[69,-1]]},"v":[[5.5,57],[68,-1]]},
 "Х-8": {"a":{"cashier_seated":[[0,-1]],"customer_present":[],"room_occupied":[[0,-1]],"safe_open":[[20,25]],"counting_cash":[[0,3.5],[12,19]],"cash_from_customer":[],"cash_to_customer":[],"handover":[],"person_in_doorway":[],"at_safe":[[19,21],[21,24],[24,27.5]],"using_computer":[],"id_document":[]},"i":{"counting_cash":[[3.5,6],[8.5,12]]},"v":[]},
 "Х-10": {"a":{"cashier_seated":[[0,-1]],"customer_present":[],"room_occupied":[[0,-1]],"safe_open":[],"counting_cash":[[11.5,-1]],"cash_from_customer":[],"cash_to_customer":[],"handover":[],"person_in_doorway":[],"at_safe":[],"using_computer":[],"id_document":[]},"i":{"counting_cash":[[0,1.5],[1.5,4.5],[4.5,7],[7,9],[9,11.5]]},"v":[]},
 "Х-11": {"a":{"cashier_seated":[[0,11.2]],"customer_present":[],"room_occupied":[[0,21.5]],"using_computer":[[0,8.5]],"screen_on":[[0,-1]],"safe_open":[],"counting_cash":[],"cash_from_customer":[],"cash_to_customer":[],"handover":[],"person_in_doorway":[[20,22.5]],"at_safe":[],"id_document":[]},"i":{"person_in_doorway":[[11.5,15.5],[17.5,20],[22.5,25]]},"v":[]},
 "Х-12": {"a":{"cashier_seated":[[0,19],[20,21]],"customer_present":[],"room_occupied":[[0,38.5]],"using_computer":[[0,9.5]],"screen_on":[[0,11]],"safe_open":[],"counting_cash":[],"cash_from_customer":[],"cash_to_customer":[],"handover":[],"person_in_doorway":[[38,41.5]],"at_safe":[[26,31.5]],"id_document":[]},"i":{"counting_cash":[[12,18.5]],"person_in_doorway":[[33.5,38]],"at_safe":[[22.5,26]]},"v":[]},
 "Х-13": {"a":{"cashier_seated":[],"customer_present":[],"room_occupied":[[0,61.5]],"safe_open":[[48,52]],"screen_on":[],"counting_cash":[],"cash_from_customer":[],"cash_to_customer":[],"handover":[],"person_in_doorway":[[60.5,63.5]],"at_safe":[[46,49],[49,51],[51,57.5]],"using_computer":[],"id_document":[]},"i":{"counting_cash":[[42,46]],"person_in_doorway":[[57.5,60.5]]},"v":[]},
 "Х-14": {"a":{"cashier_seated":[[45.5,-1]],"customer_present":[],"room_occupied":[[0,-1]],"safe_open":[[117,124]],"screen_on":[[129,-1]],"counting_cash":[[54.5,63],[66.5,75],[77.5,90],[105,112]],"cash_from_customer":[],"cash_to_customer":[],"handover":[],"person_in_doorway":[],"at_safe":[[116,118],[118,123],[123,128]],"using_computer":[[128,140]],"id_document":[]},"i":{"counting_cash":[[49,52],[52,54.5],[63,66.5],[75,77.5],[90,105],[112,116]]},"v":[]},
 "Х-15": {"a":{"cashier_seated":[[0,7]],"customer_present":[],"room_occupied":[[0,17.8]],"safe_open":[],"bag_on_desk":[[0,-1]],"counting_cash":[],"cash_from_customer":[],"cash_to_customer":[],"handover":[],"person_in_doorway":[[16,18.5]],"at_safe":[[10.5,14]],"using_computer":[],"id_document":[]},"i":{"person_in_doorway":[[14,16]],"at_safe":[[8.5,10.5]]},"v":[]},
 "Х-16": {"a":{"cashier_seated":[[0,-1]],"customer_present":[[6.5,-1]],"room_occupied":[[0,-1]],"safe_open":[],"screen_on":[],"bag_on_desk":[[16.5,-1]],"counting_cash":[],"cash_from_customer":[],"cash_to_customer":[],"handover":[[15,16],[16,18]],"person_in_doorway":[[2.5,5.5]],"at_safe":[],"using_computer":[],"id_document":[[9.5,15]]},"i":{"cash_from_customer":[[16,18]],"handover":[[8,9.5]],"id_document":[[8,9.5],[15,16]]},"v":[[6.5,-1]]},
 "Х-17": {"a":{"cashier_seated":[[0,-1]],"customer_present":[[5.5,9.5]],"room_occupied":[[0,-1]],"safe_open":[],"screen_on":[],"bag_on_desk":[[7.5,-1]],"counting_cash":[],"cash_from_customer":[],"cash_to_customer":[],"handover":[[7,9]],"person_in_doorway":[[2,5],[9,12.5]],"at_safe":[],"using_computer":[],"id_document":[]},"i":{"cash_from_customer":[[7,9]]},"v":[[5.5,9.5]]},
 "Х-18": {"a":{"cashier_seated":[[0,11.5],[13.8,-1]],"customer_present":[[7.5,-1]],"room_occupied":[[0,-1]],"safe_open":[],"screen_on":[],"counting_cash":[[9.5,11.5]],"cash_from_customer":[[7,9.5]],"cash_to_customer":[],"handover":[[7,9.5],[20.5,21.8]],"person_in_doorway":[[1.5,4.5],[16,19]],"at_safe":[],"using_computer":[],"id_document":[]},"i":{"counting_cash":[[11.5,14]],"cash_from_customer":[[20.5,21.8]],"id_document":[[20.5,21.8]]},"v":[[7.5,-1],[19,-1]]},
 "Х-19": {"a":{"cashier_seated":[[0,-1]],"customer_present":[[7.5,43.5],[53,-1]],"room_occupied":[[0,-1]],"safe_open":[[37,41]],"screen_on":[[26.5,-1]],"counting_cash":[[10.5,12.5],[21,26]],"cash_from_customer":[[8.5,10.5]],"cash_to_customer":[],"handover":[[8.5,10.5],[55,-1]],"person_in_doorway":[[1.5,4.5],[43,47.5],[50,52.5]],"at_safe":[[34.5,37.5],[37.5,40],[40,43]],"using_computer":[[26,34.5]],"id_document":[]},"i":{"counting_cash":[[12.5,14.5]],"cash_from_customer":[[55,-1]],"id_document":[[55,-1]]},"v":[[7.5,43.5],[53,-1]]}
}"""


# --------------------------------------------------------------------------------------------- questions

@dataclass(frozen=True, slots=True)
class Question:
    qid: str
    text: str
    key: str | None              # timeline key this question is evidence for in fusion
    sign: int = 1                # -1: a "yes" is evidence against the key
    extra: bool = False          # asked in addition to the API's own questions for that view
    region: str | None = None    # regions view: which crop
    score_as: str | None = None  # annotated key to score an auxiliary question against

    @property
    def target(self) -> str | None:
        return self.key or self.score_as


def _extras(rows, region=None) -> tuple[Question, ...]:
    return tuple(Question(qid, text, key, sign, True, region, score_as) for qid, text, key, sign, score_as in rows)


BASE_Q = tuple(Question(p.key, p.question, p.key) for p in PROBES)
BASE_EXTRA_Q = _extras((
    ("counting_cash~hand", "Is the cashier counting money by hand right now?", "counting_cash", 1, None),
    ("machine_counting", "Is the banknote counting machine being loaded or emptied?", None, 1, "counting_cash"),
    ("handover~desk", "Is something being passed across the desk between the customer and the cashier?",
     "handover", 1, None),
    ("cash_from_customer~hand", "Is money moving from the customer's hand to the cashier's hand?",
     "cash_from_customer", 1, None),
    ("cash_to_customer~hand", "Is money moving from the cashier's hand to the customer's hand?",
     "cash_to_customer", 1, None),
    ("person_in_doorway~door", "Is someone opening the glass door or stepping through the doorway?",
     "person_in_doorway", 1, None),
    ("door_open!", "Is the glass door fully closed?", "door_open", -1, None),
    ("safe_open!", "Is the safe door closed?", "safe_open", -1, None),
    ("room_occupied!", "Is the room empty, with nobody inside it?", "room_occupied", -1, None),
    ("customer_present~2", "Is a second person, besides the cashier, sitting or standing at the desk?",
     "customer_present", 1, None),
    ("cashier_seated!", "Is the cashier standing up?", "cashier_seated", -1, None),
    ("cashier_at_station!", "Has the cashier left the desk area?", "cashier_at_station", -1, None),
    ("at_safe~touch", "Is someone touching the safe or reaching into it?", "at_safe", 1, None),
    ("eating~mouth", "Is the cashier holding food or a cup near the mouth?", "eating", 1, None),
    ("id_document~exam", "Is the cashier examining an identity card or a passport?", "id_document", 1, None),
    ("using_computer~keys", "Are the cashier's hands on the laptop keyboard or touchpad?", "using_computer", 1, None),
    ("screen_on!", "Is the laptop screen dark?", "screen_on", -1, None),
    ("key_in_safe~hang", "Is a key or a bunch of keys hanging from the safe door?", "key_in_safe", 1, None),
    ("stamps_on_desk~stamp", "Is a rubber stamp or a seal lying on the desk?", "stamps_on_desk", 1, None),
    ("bag_on_desk~sack", "Is a cash bag or a fabric sack lying on the desk?", "bag_on_desk", 1, None),
    ("cash_on_desk~any", "Is any money visible on the desk surface?", "cash_on_desk", 1, None),
    ("personal_items~bag", "Is a handbag or a wallet lying on the desk?", "personal_items", 1, None),
    ("lights_off", "Are the room lights switched off?", None, 1, None),
    ("two_customers", "Are two or more customers in the room at the same time?", None, 1, None),
))

_AUXILIARY = {"cash_in_hands": ("counting_cash", 1), "laptop_closed": ("screen_on", -1)}
REGION_Q = tuple(
    Question(p.key, p.question, p.key if p.key in FUSED_KEYS else None,
             _AUXILIARY.get(p.key, (None, 1))[1], region=region, score_as=_AUXILIARY.get(p.key, (None, 1))[0])
    for region, probes in REGION_PROBES.items() for p in probes
)
REGION_EXTRA_Q = tuple(
    Question(qid, text, key, sign, True, region, score_as) for region, qid, text, key, sign, score_as in (
        ("desk", "stamps_on_desk~stamp", "Is a rubber stamp, a stamp pad or a seal lying on the desk?",
         "stamps_on_desk", 1, None),
        ("desk", "cash_on_desk!", "Is the desk free of banknotes?", "cash_on_desk", -1, None),
        ("desk", "phone_on_desk", "Is a mobile phone lying on the desk?", None, 1, None),
        ("desk_hands", "cash_from_customer~hands", "Is the customer handing banknotes to the cashier?",
         "cash_from_customer", 1, None),
        ("desk_hands", "cash_to_customer~hands", "Is the cashier handing banknotes to the customer?",
         "cash_to_customer", 1, None),
        ("desk_hands", "machine_counting~hands", "Are banknotes being put into or taken out of the counting machine?",
         None, 1, "counting_cash"),
        ("desk_hands", "using_computer~hands", "Is someone typing on the laptop?", "using_computer", 1, None),
        ("safe", "safe_open!", "Is the safe door closed?", "safe_open", -1, None),
        ("laptop", "using_computer~laptop", "Are a person's hands on the laptop keyboard?", "using_computer", 1, None),
        ("laptop", "screen_on!", "Is the laptop screen dark or switched off?", "screen_on", -1, None),
        ("door", "door_open!", "Is the glass door closed?", "door_open", -1, None),
        ("door", "person_in_doorway~stand", "Is a person standing at or passing the glass door?",
         "person_in_doorway", 1, None),
    )
)
HANDS_Q = tuple(Question(p.key, p.question, p.key if p.key in FUSED_KEYS else None,
                         score_as="counting_cash" if p.key == "cash_in_hands" else None) for p in HAND_PROBES) + _extras((
    ("eating~hands", "Is a person holding food or a drink?", "eating", 1, None),
    ("phone~hands", "Is a person holding a mobile phone?", "phone", 1, None),
))
CLIP_HANDS_Q = (
    Question("counting_cash", "Across these frames, is someone counting banknotes by hand?", "counting_cash"),
    Question("handover", "Across these frames, is money or a document passed from one person's hand to "
                         "another person's hand?", "handover"),
    Question("cash_from_customer", "Across these frames, is the customer handing banknotes to the cashier?",
             "cash_from_customer"),
    Question("cash_to_customer", "Across these frames, is the cashier handing banknotes to the customer?",
             "cash_to_customer"),
    Question("id_document", "Across these frames, is someone showing or holding an identity card or passport?",
             "id_document"),
    Question("eating", "Across these frames, is someone eating or drinking?", "eating"),
    Question("phone", "Across these frames, is someone using a mobile phone?", "phone"),
    Question("using_computer", "Across these frames, is someone typing on the laptop?", "using_computer"),
    Question("machine_counting", "Across these frames, are banknotes put into or taken out of the counting machine?",
             None, score_as="counting_cash"),
)
CLIP_DOOR_Q = (
    Question("person_in_doorway", "Across these frames, does a person walk through the doorway?", "person_in_doorway"),
    Question("door_open", "Is the glass door open in the last frame?", "door_open"),
    Question("door_moving", "Across these frames, is the door being opened or closed?", None,
             score_as="person_in_doorway"),
)
CLIP_FULL_Q = (
    Question("person_in_doorway", "Across these frames, does someone enter or leave the room through the door?",
             "person_in_doorway"),
    Question("at_safe", "Across these frames, is someone opening, closing or reaching into the safe?", "at_safe"),
    Question("handover", "Across these frames, is something passed from one person to another?", "handover"),
    Question("counting_cash", "Across these frames, is the cashier counting banknotes?", "counting_cash"),
    Question("eating", "Across these frames, is the cashier eating or drinking?", "eating"),
)
CLIP_CONTEXT = ("These are {n} consecutive frames, 0.5 seconds apart, from a ceiling security camera above a bank "
                "cash desk. The cashier works behind the desk with a laptop, a cash counting machine and a safe; "
                "customers enter through the glass door and sit across the desk.")
CROP_CLIP_CONTEXT = ("These are {n} consecutive zoomed crops, 0.5 seconds apart, from a ceiling security camera "
                     "above a bank cash desk.")


@dataclass(frozen=True, slots=True)
class View:
    name: str
    kind: str                         # frame | regions | hands | clip
    note: str
    questions: tuple[Question, ...]
    tokens: int = 256
    fps: float = 1.0
    crop: str | None = None           # Scene.regions key for frame and clip views
    offsets: tuple[int, ...] = (0,)   # clip frames, in 2-fps grid steps around the probe time
    context: str = SCENE_CONTEXT
    needs: tuple[str, ...] = ()


# Priority order: when the time budget runs out, later views are the ones left out.
VIEWS = {view.name: view for view in (
    View("full256", "frame", "API full-frame probes at 256 image tokens, plus extra and negated questions",
         BASE_Q + BASE_EXTRA_Q),
    View("regions", "regions", "API zoomed crops (desk, hands, safe, laptop, door), plus extra and negated questions",
         REGION_Q + REGION_EXTRA_Q, needs=("scene",)),
    View("clip_hands", "clip", "3 frames 0.5 s apart, desk and hands crop: hand actions", CLIP_HANDS_Q, tokens=160,
         crop="desk_hands", offsets=(-1, 0, 1), context=CROP_CLIP_CONTEXT, needs=("scene",)),
    View("hands", "hands", "crop around the wrists over the desk, located by body keypoints", HANDS_Q,
         tokens=HAND_TOKENS, context=REGION_CONTEXT, needs=("scene", "pose")),
    View("clip_door", "clip", "3 frames 0.5 s apart, door crop", CLIP_DOOR_Q, tokens=128, crop="door",
         offsets=(-1, 0, 1), context=CROP_CLIP_CONTEXT, needs=("scene",)),
    View("full448", "frame", "full frame at 448 image tokens (native resolution)", BASE_Q, tokens=448),
    View("active320", "frame", "crop without the empty foreground, 320 image tokens", BASE_Q, tokens=320,
         crop="active", needs=("scene",)),
    View("clip_full", "clip", "3 full frames 0.5 s apart: entering, safe, handover", CLIP_FULL_Q, tokens=192,
         offsets=(-1, 0, 1), context=CLIP_CONTEXT),
    View("full128", "frame", "full frame at 128 image tokens (cheap)", BASE_Q, tokens=128),
)}
CPU_PHASES = ("meta", "motion")
GPU_PHASES = ("pose", "scene", *VIEWS)


# ------------------------------------------------------------------------------------------------ helpers

def read_json(path: Path):
    # Windows' locale encoding can turn UTF-8 Cyrillic Х into the two characters РҐ.
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, value, indent: int | None = 1) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=indent) + "\n", encoding="utf-8")
    temporary.replace(path)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def video_key(name: str) -> str:
    """Latin X-1 and Cyrillic Х-15 both become the ASCII id X-1 / X-15."""
    stem = Path(name).stem.casefold().replace("х", "x")
    match = re.fullmatch(r"x[-_ ]*0*(\d+)", stem)
    return f"X-{int(match[1])}" if match else re.sub(r"[^A-Za-z0-9_-]", "_", Path(name).stem)


def number(key: str) -> int:
    match = re.search(r"(\d+)$", key)
    return int(match[1]) if match else 0


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def openable(path: Path) -> bool:
    capture = cv2.VideoCapture(str(path))
    try:
        return capture.isOpened() and capture.read()[0]
    finally:
        capture.release()


def pct(value, digits: int = 1) -> str:
    return "-" if value is None or (isinstance(value, float) and math.isnan(value)) else f"{100 * value:.{digits}f}%"


def num(value, digits: int = 2) -> str:
    return "-" if value is None or (isinstance(value, float) and math.isnan(value)) else f"{value:.{digits}f}"


def clock(seconds: float) -> str:
    seconds = max(0, int(seconds))
    return f"{seconds // 3600}h{seconds % 3600 // 60:02d}m" if seconds >= 3600 else f"{seconds // 60}m{seconds % 60:02d}s"


def as_spans(raw, duration: float) -> list[tuple[float, float]]:
    return [(float(start), float(duration if end == -1 else end)) for start, end in raw]


def covered(times: np.ndarray, spans) -> np.ndarray:
    mask = np.zeros(len(times), bool)
    for start, end in spans:
        mask |= (times >= start - 1e-6) & (times <= end + 1e-6)
    return mask


def merge(spans, gap: float) -> list[tuple[float, float]]:
    result: list[list[float]] = []
    for start, end in sorted(spans):
        if result and start <= result[-1][1] + gap:
            result[-1][1] = max(result[-1][1], end)
        else:
            result.append([start, end])
    return [(a, b) for a, b in result]


def overlap(a, b) -> float:
    return min(a[1], b[1]) - max(a[0], b[0])


def auc(scores: np.ndarray, labels: np.ndarray) -> float:
    positives, negatives = int(labels.sum()), int((~labels).sum())
    if not positives or not negatives:
        return float("nan")
    order = np.argsort(scores, kind="mergesort")
    ranks = np.empty(len(scores))
    ranks[order] = np.arange(1, len(scores) + 1)
    # Average ranks over ties so constant scores give 0.5.
    for value in np.unique(scores):
        tied = scores == value
        if tied.sum() > 1:
            ranks[tied] = ranks[tied].mean()
    return float((ranks[labels].sum() - positives * (positives + 1) / 2) / (positives * negatives))


def otsu(values: np.ndarray, bins: int = 64) -> tuple[float, float]:
    """Threshold and between-class share of variance (1.0 = perfectly bimodal); as eval/tuning/calibrate.py."""
    if len(values) < 4 or values.var() <= 0:
        return 0.0, 0.0
    hist, edges = np.histogram(values, bins=bins)
    centres = (edges[:-1] + edges[1:]) / 2
    weight = hist.cumsum()
    mean = (hist * centres).cumsum()
    total, grand = weight[-1], mean[-1]
    between = np.zeros(len(hist))
    for i in range(len(hist) - 1):
        w0, w1 = weight[i], total - weight[i]
        if w0 and w1:
            between[i] = w0 * w1 * (mean[i] / w0 - (grand - mean[i]) / w1) ** 2
    best = int(np.argmax(between))
    return float(edges[best + 1]), float(between[best] / (total ** 2 * values.var()))


class Printer:
    """Prints a line and keeps it for SUMMARY.txt."""

    def __init__(self) -> None:
        self.lines: list[str] = []

    def __call__(self, text: str = "") -> None:
        print(text, flush=True)
        self.lines.append(text)

    def section(self, title: str) -> None:
        self("")
        self("=" * 100)
        self(title)
        self("=" * 100)


# -------------------------------------------------------------------------------------------- VLM calls

def probe(vlm: QuestionVLM, image: np.ndarray, questions: list[str], context: str, tokens: int, batch: int) -> list[float]:
    try:
        return vlm.probe(image, questions, context, tokens, max_batch=batch)
    except torch.OutOfMemoryError:
        torch.cuda.empty_cache()
        return vlm.probe(image, questions, context, tokens, max_batch=4)


@torch.inference_mode()
def probe_images(vlm: QuestionVLM, images: list[np.ndarray], captions: list[str], questions: list[str],
                 context: str, tokens: int, batch: int) -> list[float]:
    """QuestionVLM.probe for several images in one prompt: the shared image prefix is encoded once and every
    question reads its Yes/No logits from the cached keys and values."""
    content = []
    for caption in captions:
        content += [{"type": "text", "text": caption}, {"type": "image"}]
    content.append({"type": "text", "text": "\n" + context + "\n"})
    text = vlm._processor.apply_chat_template([{"role": "user", "content": content}], add_generation_prompt=False)
    text = text[: text.rindex("<|im_end|>")]
    with vlm._lock:
        inputs = vlm._processor(
            text=[text], images=[fit_tokens(image, tokens) for image in images], return_tensors="pt",
            images_kwargs={"size": {"shortest_edge": 1024, "longest_edge": 1 << 26}},
        ).to(vlm.device)
        vlm._model.model.rope_deltas = None
        prefix = vlm._model.model(**inputs, use_cache=True).past_key_values
        weights = vlm._model.lm_head.weight[vlm._answer_ids]
        result: list[float] = []
        for start in range(0, len(questions), batch):
            chunk = questions[start:start + batch]
            suffixes = [vlm._tokenizer.encode(f"Question: {question} Answer Yes or No.<|im_end|>\n"
                                              "<|im_start|>assistant\n") for question in chunk]
            ids = torch.full((len(suffixes), max(map(len, suffixes))), vlm._pad_id, dtype=torch.long)
            for row, suffix in enumerate(suffixes):
                ids[row, :len(suffix)] = torch.tensor(suffix)
            cache = copy.deepcopy(prefix) if start + batch < len(questions) else prefix
            cache.batch_repeat_interleave(len(suffixes))
            hidden = vlm._model.model(input_ids=ids.to(vlm.device), past_key_values=cache,
                                      use_cache=True).last_hidden_state
            del cache
            last = torch.tensor([len(suffix) - 1 for suffix in suffixes], device=vlm.device)
            states = hidden[torch.arange(len(suffixes), device=vlm.device), last]
            probabilities = torch.softmax((states @ weights.T).float(), dim=-1)
            yes = probabilities[:, :vlm._yes_count].sum(-1)
            no = probabilities[:, vlm._yes_count:].sum(-1)
            result.extend((yes / (yes + no)).tolist())
        vlm._model.model.rope_deltas = None
    return result


class TimedModel:
    """QuestionVLM.structured with a generation time and token limit, recording every call's outcome."""

    def __init__(self, vlm: QuestionVLM, seconds: float, max_tokens: int) -> None:
        self.vlm, self.seconds, self.max_tokens = vlm, seconds, max_tokens
        self.name = vlm.name
        self.calls: list[dict] = []

    @torch.inference_mode()
    def structured(self, prompt, schema, images=None, image_tokens=256, max_new_tokens=1024):
        vlm = self.vlm
        content = [{"type": "image"} for _ in images or []]
        content.append({"type": "text", "text": prompt + "\nReturn only a JSON object matching this schema:\n"
                        + json.dumps(schema.model_json_schema())})
        text = vlm._processor.apply_chat_template([{"role": "user", "content": content}], add_generation_prompt=True)
        record = {"schema": schema.__name__, "images": len(images or []), "ok": False}
        started = perf_counter()
        try:
            with vlm._lock:
                inputs = vlm._processor(
                    text=[text], images=[fit_tokens(image, image_tokens) for image in images] if images else None,
                    return_tensors="pt", images_kwargs={"size": {"shortest_edge": 1024, "longest_edge": 1 << 26}},
                ).to(vlm.device)
                vlm._model.model.rope_deltas = None
                try:
                    output = vlm._model.generate(**inputs, max_new_tokens=min(max_new_tokens, self.max_tokens),
                                                 max_time=self.seconds, do_sample=False)
                finally:
                    vlm._model.model.rope_deltas = None
                generated = output[:, inputs["input_ids"].shape[1]:]
                answer = vlm._processor.batch_decode(generated, skip_special_tokens=True)[0].strip()
            record.update(prompt_tokens=int(inputs["input_ids"].shape[1]), output_tokens=int(generated.shape[1]))
            if answer.startswith("```"):
                answer = answer.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
            record["raw"] = answer[:3000]
            result = schema.model_validate_json(answer)
            record["ok"] = True
            return result
        except Exception as error:
            record["error"] = f"{type(error).__name__}: {str(error)[:400]}"
            raise
        finally:
            record["seconds"] = round(perf_counter() - started, 2)
            self.calls.append(record)


# ---------------------------------------------------------------------------------------------- the lab

@dataclass
class Item:
    label: str      # file name in the label file, e.g. "Х-15.mov"
    key: str        # ASCII id used for caches, e.g. "X-15"
    path: Path      # a path OpenCV can open
    expected: str


@dataclass
class Data:
    """Everything cached for one video, loaded for scoring."""
    item: Item
    meta: dict
    video: DecodedVideo
    scene: Scene | None
    pose: PoseSequence | None
    views: dict[str, dict[str, tuple[np.ndarray, np.ndarray]]]
    seconds: dict[str, float] = field(default_factory=dict)  # GPU seconds spent per phase
    signals: Signals | None = None
    motion_ready: bool = False

    @property
    def grid(self) -> np.ndarray:
        return self.video.times


class CachedSignals(Signals):
    """Signals.at() is called for every key on every evaluation; the grid never changes per video."""

    def at(self, key, times, reduce="mean", window=0.5):
        memo = self.__dict__.setdefault("_memo", {})
        index = (key, reduce, window, len(times), float(times[0]) if len(times) else 0.0)
        if index not in memo:
            memo[index] = Signals.at(self, key, times, reduce, window)
        return memo[index]


def add_motion_signals(signals: Signals) -> None:
    """Pose evidence combined with local patch motion, normalised per video (label-free)."""
    values = signals.values

    def active(series: np.ndarray, z: float = 2.0) -> np.ndarray:
        median = np.median(series)
        spread = 1.4826 * np.median(np.abs(series - median)) + 1e-6
        return 1 / (1 + np.exp(-((series - median) / spread - z)))

    people = (values["persons"] > 0).astype(float)
    # Counting: wrists over the desk and the desk patches change between frames.
    values["desk_active"] = np.clip(values["hands_on_desk"], 0, 1) * active(values["desk_motion"])
    # Doorway: a person at the door, or optical flow at the door while someone is in the room.
    values["door_active"] = np.maximum(values["person_in_doorway"], active(values["door_motion"]) * people)
    # Safe: a wrist in reach of the safe and flow on the safe.
    values["safe_active"] = values["at_safe"] * active(values["safe_motion"])


class Lab:
    def __init__(self, args) -> None:
        self.args = args
        self.out: Path = args.out
        self.cache = self.out / "cache"
        self.reports = self.out / "reports"
        self.say = Printer()
        self.failures: list[dict] = []
        self._vlm: QuestionVLM | None = None
        self._pose: PoseEstimator | None = None
        self.deadline = math.inf
        self.labels = {name: value for name, value in read_json(args.labels).items() if not name.startswith("_")}
        catalog = read_json(EVAL / "dataset_labels.json")
        self.catalog = {video_key(entry["video"]): entry for entry in catalog["videos"]}
        self.truth = self._load_truth()
        self.items = self._resolve_items()
        self.data: dict[str, Data] = {}
        self.bias: dict[tuple[str, str], float] = {}
        self.separation: dict[tuple[str, str], float] = {}
        self.input_cache: dict[tuple, tuple] = {}

    # ------------------------------------------------------------------------------------ setup

    def _load_truth(self) -> dict[str, dict]:
        truth = {}
        for name, entry in json.loads(IDEAL_TIMELINE).items():
            truth[video_key(name)] = {"attributes": dict(entry["a"]), "ignore": dict(entry["i"]),
                                      "visits": entry["v"], "source": dict.fromkeys(entry["a"], "ideal_timeline_v1")}
        annotations = read_json(EVAL / "reconstruction_annotations.json")
        for name, entry in annotations.items():
            if name.startswith("_"):
                continue
            target = truth.setdefault(video_key(name), {"attributes": {}, "ignore": {}, "visits": None, "source": {}})
            for key, spans in entry["attributes"].items():
                target["attributes"][key] = spans
                target["ignore"][key] = entry.get("ignore", {}).get(key, [])
                target["source"][key] = "reconstruction_annotations"
        return truth

    def _resolve_items(self) -> list[Item]:
        directory = self.args.videos_dir
        if not directory.is_dir():
            raise SystemExit(f"Video directory not found: {directory}. Pass --videos-dir.")
        wanted = None
        if self.args.videos:
            wanted = {video_key(name) for name in self.args.videos}
        elif self.args.quick:
            wanted = {video_key(name) for name in QUICK}
        files = {}
        for path in directory.iterdir():
            if path.is_file() and path.suffix.casefold() in {".mov", ".mp4", ".m4v", ".mkv", ".avi"}:
                files.setdefault(video_key(path.name), []).append(path)
        items, missing = [], []
        for label, expected in self.labels.items():
            key = video_key(label)
            if wanted is not None and key not in wanted:
                continue
            paths = files.get(key, [])
            if len(paths) != 1:
                missing.append(f"{label} ({'ambiguous' if paths else 'missing'})")
                continue
            items.append(Item(label, key, paths[0], expected))
        if missing:
            raise SystemExit(f"Cannot use {len(missing)} labelled videos in {directory}: {', '.join(missing)}")
        if not items:
            raise SystemExit("No videos selected.")
        for item in items:
            if not openable(item.path):
                # OpenCV on Windows may not open non-ASCII paths; an ASCII copy always works.
                copy_path = self.cache / "videos" / f"{item.key}{item.path.suffix}"
                if not copy_path.exists():
                    copy_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(item.path, copy_path)
                if not openable(copy_path):
                    raise SystemExit(f"OpenCV cannot read {item.path}")
                item.path = copy_path
        return sorted(items, key=lambda item: number(item.key))

    def vlm(self) -> QuestionVLM:
        if self._vlm is None:
            started = perf_counter()
            args = self.args
            print(f"Loading {args.model_path or MODEL_IDS.get(args.model, args.model)} on {args.device} "
                  f"(quantization {args.quantization}) ...", flush=True)
            self._vlm = QuestionVLM(args.model, args.model_path, args.device, args.quantization,
                                    local_files_only=not args.allow_download)
            memory = (f", {torch.cuda.memory_allocated() / 2**30:.1f} GiB GPU memory"
                      if torch.cuda.is_available() else "")
            print(f"Model loaded in {perf_counter() - started:.0f}s{memory}", flush=True)
        return self._vlm

    def pose_estimator(self) -> PoseEstimator:
        if self._pose is None:
            self._pose = PoseEstimator(self.args.pose_device)
        return self._pose

    def model_name(self) -> str:
        return self._vlm.name if self._vlm else MODEL_IDS.get(self.args.model, self.args.model)

    # ---------------------------------------------------------------------------- cache paths

    def path(self, phase: str, item: Item) -> Path:
        suffix = {"motion": ".npz"}.get(phase, ".json")
        folder = self.cache / ("views/" + phase if phase in VIEWS else phase)
        return folder / f"{item.key}{suffix}"

    def done(self, phase: str, item: Item) -> bool:
        return self.path(phase, item).exists()

    def ready(self, phase: str, item: Item) -> bool:
        needs = VIEWS[phase].needs if phase in VIEWS else {"scene": (), "pose": ()}.get(phase, ())
        return all(self.done(need, item) for need in needs)

    # ----------------------------------------------------------------------------- observation phases

    def run_phases(self, phases: list[str]) -> None:
        """Phase-major order: each phase covers every video before the next one starts."""
        for phase in phases:
            todo = [item for item in self.items if not self.done(phase, item)]
            if not todo:
                continue
            blocked = [item for item in todo if not self.ready(phase, item)]
            todo = [item for item in todo if self.ready(phase, item)]
            if blocked:
                print(f"[{phase}] skipping {len(blocked)} videos whose prerequisites failed: "
                      f"{', '.join(i.key for i in blocked)}", flush=True)
            total = sum(self.duration(item) for item in todo)
            spent = covered_seconds = 0.0
            print(f"\n[{phase}] {len(todo)} videos, {total:.0f}s of video", flush=True)
            for index, item in enumerate(todo, start=1):
                if phase not in CPU_PHASES and time.time() > self.deadline:
                    print(f"[{phase}] GPU time budget reached; continuing with what is cached", flush=True)
                    self.deadline = -math.inf
                    return
                started = perf_counter()
                try:
                    getattr(self, f"_phase_{VIEWS[phase].kind if phase in VIEWS else phase}")(phase, item)
                except KeyboardInterrupt:
                    raise
                except Exception as error:
                    detail = f"{type(error).__name__}: {error}"
                    self.failures.append({"phase": phase, "video": item.key, "error": detail})
                    logger.error("%s %s failed\n%s", phase, item.key, traceback.format_exc())
                    print(f"[{phase}] {item.key} FAILED: {detail}", flush=True)
                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()
                    continue
                elapsed = perf_counter() - started
                spent += elapsed
                covered_seconds += self.duration(item)
                rate = spent / max(covered_seconds, 1e-6)
                print(f"[{phase}] {index}/{len(todo)} {item.key:6s} {elapsed:6.1f}s "
                      f"({rate:.2f}s per video second, phase ETA {clock(rate * (total - covered_seconds))})",
                      flush=True)
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()

    def duration(self, item: Item) -> float:
        meta = self.path("meta", item)
        if meta.exists():
            return read_json(meta)["duration"]
        capture = cv2.VideoCapture(str(item.path))
        try:
            fps = capture.get(cv2.CAP_PROP_FPS) or 30.0
            return capture.get(cv2.CAP_PROP_FRAME_COUNT) / fps
        finally:
            capture.release()

    def _phase_meta(self, phase: str, item: Item) -> None:
        started = perf_counter()
        video = decode(item.path, GRID_FPS)
        write_json(self.path(phase, item), {
            "video": item.label, "path": str(item.path), "sha256": sha256(item.path), "duration": video.duration,
            "native_fps": video.native_fps, "width": video.width, "height": video.height,
            "times": video.times.tolist(), "frame_indices": video.frame_indices,
            "seconds": round(perf_counter() - started, 2),
        })

    def _phase_motion(self, phase: str, item: Item) -> None:
        started = perf_counter()
        target = self.path(phase, item)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(target.stem + ".tmp.npz")
        patch_motion(item.path, MOTION_FPS).save(temporary)
        temporary.replace(target)
        self._timing(phase, item, perf_counter() - started)

    def _phase_pose(self, phase: str, item: Item) -> None:
        started = perf_counter()
        sequence = detect_people(item.path, self.pose_estimator(), POSE_FPS)
        write_json(self.path(phase, item), sequence.to_json() | {
            "fps": POSE_FPS, "device": self.pose_estimator().device, "seconds": round(perf_counter() - started, 2)},
            indent=None)

    def _phase_scene(self, phase: str, item: Item) -> None:
        started = perf_counter()
        scene = locate(self.vlm(), item.path)
        write_json(self.path(phase, item), scene.to_json() | {"seconds": round(perf_counter() - started, 2)})
        # Picture of the grounded layout, to check the crops by eye.
        image = median_background(item.path)
        h, w = image.shape[:2]
        colours = {"desk": (0, 200, 0), "desk_hands": (0, 255, 255), "safe": (0, 0, 255), "laptop": (255, 0, 0),
                   "door": (255, 0, 255), "active": (200, 200, 200)}
        for name, (x0, y0, x1, y1) in scene.regions.items():
            if name in colours:
                cv2.rectangle(image, (int(x0 * w), int(y0 * h)), (int(x1 * w), int(y1 * h)), colours[name], 2)
                cv2.putText(image, name, (int(x0 * w) + 3, int(y0 * h) + 14), cv2.FONT_HERSHEY_SIMPLEX, 0.45,
                            colours[name], 1)
        for name, (x0, y0, x1, y1) in scene.boxes.items():
            cv2.rectangle(image, (int(x0 * w), int(y0 * h)), (int(x1 * w), int(y1 * h)), (255, 255, 255), 1)
        ok, encoded = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 80])
        if ok:
            self.path(phase, item).with_suffix(".jpg").write_bytes(encoded.tobytes())

    def _scene(self, item: Item) -> Scene:
        return Scene.from_json(read_json(self.path("scene", item)))

    def _store_view(self, phase: str, item: Item, view: View, series: dict, calls: int, started: float,
                    extra: dict | None = None) -> None:
        write_json(self.path(phase, item), {
            "view": view.name, "video": item.label, "model": self.model_name(), "tokens": view.tokens,
            "fps": view.fps, "questions": {q.qid: q.text for q in view.questions},
            "series": series, "calls": calls, "seconds": round(perf_counter() - started, 2), **(extra or {}),
        }, indent=None)

    def _phase_frame(self, phase: str, item: Item) -> None:
        view, vlm, batch = VIEWS[phase], self.vlm(), self.args.probe_batch
        started = perf_counter()
        video = decode(item.path, GRID_FPS)
        box = self._scene(item).regions[view.crop] if view.crop else None
        texts = [q.text for q in view.questions]
        series = {q.qid: {"t": [], "p": []} for q in view.questions}
        calls, due = 0, 0.0
        for moment in video.times:
            if moment + 1e-6 < due:
                continue
            # Same frame choice as perception.pipeline._probe_series.
            due = moment + 1.0 / view.fps - 0.25 / video.sample_fps
            image = video.frame_at(moment)
            answers = probe(vlm, crop(image, box) if box else image, texts, view.context, view.tokens, batch)
            calls += 1
            for q, value in zip(view.questions, answers, strict=True):
                series[q.qid]["t"].append(round(float(moment), 4))
                series[q.qid]["p"].append(round(float(value), 7))
        self._store_view(phase, item, view, series, calls, started)

    def _phase_regions(self, phase: str, item: Item) -> None:
        view, vlm, batch = VIEWS[phase], self.vlm(), self.args.probe_batch
        started = perf_counter()
        video = decode(item.path, GRID_FPS)
        boxes = self._scene(item).regions
        by_region = {region: [q for q in view.questions if q.region == region] for region in REGION_PROBES}
        series = {q.qid: {"t": [], "p": []} for q in view.questions}
        calls, due = 0, dict.fromkeys(by_region, 0.0)
        for moment in video.times:
            frame = None
            for region, questions in by_region.items():
                if moment + 1e-6 < due[region]:
                    continue
                # Same frame choice as perception.pipeline._region_series.
                due[region] = moment + 1.0 / RATES[region] - 0.25 / video.sample_fps
                frame = video.frame_at(moment) if frame is None else frame
                answers = probe(vlm, crop(frame, boxes[region]), [q.text for q in questions], REGION_CONTEXT,
                                TOKENS[region], batch)
                calls += 1
                for q, value in zip(questions, answers, strict=True):
                    series[q.qid]["t"].append(round(float(moment), 4))
                    series[q.qid]["p"].append(round(float(value), 7))
        self._store_view(phase, item, view, series, calls, started, {"rates": RATES, "region_tokens": TOKENS})

    def _phase_hands(self, phase: str, item: Item) -> None:
        view, vlm, batch = VIEWS[phase], self.vlm(), self.args.probe_batch
        started = perf_counter()
        video = decode(item.path, GRID_FPS)
        scene = self._scene(item)
        pose = PoseSequence.from_json(read_json(self.path("pose", item)))
        texts = [q.text for q in view.questions]
        series = {q.qid: {"t": [], "p": []} for q in view.questions}
        boxes, calls, due = [], 0, 0.0
        for moment in video.times:
            if moment + 1e-6 < due:
                continue
            due = moment + 1.0 / view.fps - 0.25 / video.sample_fps
            people = pose.people[int(np.argmin(np.abs(pose.times - moment)))] if len(pose.times) else []
            box = hand_box(people, scene)
            boxes.append(box)
            if box is None:
                answers = [None] * len(texts)  # no hands over the desk: nothing to look at
            else:
                answers = probe(vlm, crop(video.frame_at(moment), box), texts, view.context, view.tokens, batch)
                calls += 1
            for q, value in zip(view.questions, answers, strict=True):
                series[q.qid]["t"].append(round(float(moment), 4))
                series[q.qid]["p"].append(None if value is None else round(float(value), 7))
        self._store_view(phase, item, view, series, calls, started, {"boxes": boxes})

    def _phase_clip(self, phase: str, item: Item) -> None:
        view, vlm, batch = VIEWS[phase], self.vlm(), self.args.probe_batch
        started = perf_counter()
        video = decode(item.path, GRID_FPS)
        box = self._scene(item).regions[view.crop] if view.crop else None
        texts = [q.text for q in view.questions]
        context = view.context.format(n=len(view.offsets))
        series = {q.qid: {"t": [], "p": []} for q in view.questions}
        calls, due = 0, 0.0
        for index, moment in enumerate(video.times):
            if moment + 1e-6 < due:
                continue
            due = moment + 1.0 / view.fps - 0.25 / video.sample_fps
            picks = [min(len(video.times) - 1, max(0, index + offset)) for offset in view.offsets]
            images = []
            for pick in picks:
                frame = cv2.imdecode(np.frombuffer(video.images[pick], np.uint8), cv2.IMREAD_COLOR)
                images.append(crop(frame, box) if box else frame)
            captions = [f"Frame {n} ({video.times[pick]:.1f}s):" for n, pick in enumerate(picks, start=1)]
            try:
                answers = probe_images(vlm, images, captions, texts, context, view.tokens, batch)
            except torch.OutOfMemoryError:
                torch.cuda.empty_cache()
                answers = probe_images(vlm, images, captions, texts, context, view.tokens, 4)
            calls += 1
            for q, value in zip(view.questions, answers, strict=True):
                series[q.qid]["t"].append(round(float(moment), 4))
                series[q.qid]["p"].append(round(float(value), 7))
        self._store_view(phase, item, view, series, calls, started, {"offsets": view.offsets})

    def _timing(self, phase: str, item: Item, seconds: float) -> None:
        timings = self.cache / "timings.json"
        saved = read_json(timings) if timings.exists() else {}
        saved.setdefault(phase, {})[item.key] = round(seconds, 2)
        write_json(timings, saved)

    # ------------------------------------------------------------------------------------ loading

    def load(self) -> None:
        self.data = {}
        for item in self.items:
            if not self.done("meta", item):
                continue
            meta = read_json(self.path("meta", item))
            video = DecodedVideo(item.path, meta["duration"], meta["native_fps"], meta["width"], meta["height"],
                                 GRID_FPS, np.asarray(meta["times"]), meta["frame_indices"], [])
            seconds = {}
            scene = pose = None
            if self.done("scene", item):
                stored = read_json(self.path("scene", item))
                scene, seconds["scene"] = Scene.from_json(stored), stored.get("seconds", 0.0)
            if self.done("pose", item):
                stored = read_json(self.path("pose", item))
                pose, seconds["pose"] = PoseSequence.from_json(stored), stored.get("seconds", 0.0)
            views = {}
            for name, view in VIEWS.items():
                if not self.done(name, item):
                    continue
                stored = read_json(self.path(name, item))
                seconds[name] = stored.get("seconds", 0.0)
                series = {}
                for qid, values in stored["series"].items():
                    times = np.asarray(values["t"], float)
                    probabilities = np.asarray([np.nan if p is None else p for p in values["p"]], float)
                    series[qid] = (times, probabilities)
                if name == "hands" and "id_document" in series and "cash_in_hands" in series:
                    # As perception.hands.hand_evidence: a card held without banknotes.
                    times, card = series["id_document"]
                    series["id_document"] = (times, card * (1 - series["cash_in_hands"][1]))
                views[name] = series
            data = Data(item, meta, video, scene, pose, views, seconds)
            data.motion_ready = self.done("motion", item)
            self.data[item.key] = data

    def signals(self, data: Data) -> Signals | None:
        if data.signals is None and data.scene is not None and data.pose is not None and data.motion_ready:
            motion = PatchMotion.load(self.path("motion", data.item))
            raw = compute_signals(data.scene, data.pose, motion, FeatureConfig(),
                                  data.video.height / data.video.width)
            data.signals = CachedSignals(raw.times, raw.values, raw.people)
            add_motion_signals(data.signals)
        return data.signals

    def calibrate(self) -> None:
        """Label-free per-question decision point: Otsu threshold on the pooled logits of every frame."""
        pooled: dict[tuple[str, str], list[np.ndarray]] = {}
        for data in self.data.values():
            for view, series in data.views.items():
                for qid, (_, values) in series.items():
                    pooled.setdefault((view, qid), []).append(values[~np.isnan(values)])
        for index, parts in pooled.items():
            values = logit(np.concatenate(parts)) if parts else np.zeros(0)
            threshold, separation = otsu(values)
            self.separation[index] = separation
            self.bias[index] = round(threshold, 2) if separation >= 0.6 else 0.0

    # ----------------------------------------------------------------------------------- scoring

    def source(self, data: Data, view: str, qid: str, calibrate: bool) -> np.ndarray | None:
        """A question's logit on the analysis grid, minus its calibration threshold."""
        series = data.views.get(view, {}).get(qid)
        if series is None:
            return None
        times, values = series
        bias = self.bias.get((view, qid), 0.0) if calibrate else 0.0
        raw = logit(values)
        missing = np.isnan(values)
        if missing.all():
            return None
        if missing.any():
            # Unprobed hand-crop frames: no hands over the desk, moderate evidence of absence.
            raw = np.where(missing, bias - 3.0, raw)
        return np.interp(data.grid, times, raw) - bias

    def pooled(self, data: Data, views, key: str, approach) -> np.ndarray | None:
        parts = []
        for view in views:
            if view not in data.views:
                continue
            for q in VIEWS[view].questions:
                if q.key != key:
                    continue
                if q.extra and not ((q.sign > 0 and view in approach.extras) or (q.sign < 0 and view in approach.contrast)):
                    continue
                value = self.source(data, view, q.qid, approach.calibrate)
                if value is not None:
                    parts.append(q.sign * value)
        return np.mean(parts, axis=0) if parts else None

    def machine(self, data: Data, views, approach) -> np.ndarray | None:
        parts = [self.source(data, view, q.qid, approach.calibrate) for view in views if view in data.views
                 for q in VIEWS[view].questions if q.qid.startswith("machine_counting")]
        parts = [part for part in parts if part is not None]
        return np.mean(parts, axis=0) if parts else None

    def inputs(self, approach, data: Data) -> tuple[dict, dict]:
        signature = (approach.base_views, approach.region_views, tuple(sorted(approach.pool.items())),
                     tuple(sorted(approach.pick.items())), approach.calibrate, approach.extras, approach.contrast,
                     approach.machine_count, data.item.key)
        if signature in self.input_cache:
            return self.input_cache[signature]
        base, regions = {}, {}
        for key in FUSED_KEYS:
            value = self.pooled(data, approach.base_views, key, approach)
            if value is not None:
                base[key] = value
            if key in approach.pick:
                view, qid, sign = approach.pick[key]
                value = self.source(data, view, qid, approach.calibrate)
                value = None if value is None else sign * value
            else:
                value = self.pooled(data, approach.pool.get(key, approach.region_views), key, approach)
            if value is not None:
                regions[key] = value
        if approach.machine_count:
            for target, views in ((base, approach.base_views),
                                  (regions, approach.pool.get("counting_cash", approach.region_views))):
                machine = self.machine(data, views, approach)
                if machine is not None and "counting_cash" in target:
                    target["counting_cash"] = np.maximum(target["counting_cash"], machine)
        result = ({k: sigmoid(v) for k, v in base.items()}, {k: sigmoid(v) for k, v in regions.items()})
        self.input_cache[signature] = result
        return result

    def judge(self, approach, data: Data, video: DecodedVideo | None = None) -> dict:
        video = video or data.video
        with settings(approach):
            if approach.exact_api:
                base = {k: v for k, v in data.views["full256"].items() if k in {p.key for p in PROBES}}
                originals = {q.qid for q in REGION_Q}
                regions = {k: v for k, v in data.views.get("regions", {}).items() if k in originals}
                motion = PatchMotion.load(self.path("motion", data.item)) if data.motion_ready else None
                observed = Observations(video, base, regions, data.scene, data.pose, motion, self.model_name())
                recon = reconstruct(observed, PerceptionConfig())
                fused = {key: np.asarray([o.probability for o in track.observations]) for key, track in recon.tracks.items()}
            else:
                base, regions = self.inputs(approach, data)
                weights = dict(DEFAULT_WEIGHTS) | {k: tuple(v) for k, v in approach.weights.items()}
                for key in regions:
                    wb, wr, wc = weights.get(key, (1.0, 0.0, 0.0))
                    if wr == 0 and key not in approach.weights:
                        weights[key] = (wb, 1.0, wc)
                if not approach.cv:
                    for key, (wb, wr, wc) in list(weights.items()):
                        if wb == 0 and wr == 0:
                            weights[key] = (1.0, wr, wc)
                config = FusionConfig(offsets=dict(approach.offsets), weights=weights)
                signals = self.signals(data) if approach.cv else None
                probes = [replace(p, dwell=approach.dwell.get(p.key, p.dwell)) for p in PERCEPTION_PROBES]
                fused = fuse(video.times, base, regions, signals, FUSED_KEYS, config)
                tracks = {p.key: AttributeTrack(p, [Observation(float(t), float(v))
                                                    for t, v in zip(video.times, fused[p.key], strict=True)])
                          for p in probes}
                decode_tracks(video, tracks)
                recon = Reconstruction(video, tracks, self.model_name())
            graph = build_timeline(recon)
        report = evaluate(REGISTRY, graph, "shadow")
        findings = finding_dicts(reportable(report, STRICT if approach.policy == "strict" else SHADOW))
        return {"graph": graph, "fused": fused, "findings": findings}

    def covers(self, approach, data: Data) -> bool:
        if any(view not in data.views for view in approach.views()):
            return False
        return not approach.cv or self.signals(data) is not None

    def score(self, item: Item, findings: list[dict]) -> dict:
        entry = self.catalog.get(item.key, {})
        visual = [a for a in entry.get("aspects", []) if a["observability"] != "external_only"]
        targets = {rule for a in visual for rule in a["any_of_rules"]}
        rules = sorted({f["rule_id"] for f in findings})
        moment = entry.get("timestamp_sec")
        relevant = [f for f in findings if f["rule_id"] in targets]
        return {
            "video": item.label, "key": item.key, "expected": item.expected,
            "predicted": "violation" if findings else "no_violation",
            "correct": ("violation" if findings else "no_violation") == item.expected, "rules": rules,
            "aspects_total": len(visual), "aspects_hit": sum(bool(set(rules) & set(a["any_of_rules"])) for a in visual),
            "time_error": min(abs(f["time"] - moment) for f in relevant) if relevant and moment is not None else None,
            "off_target": sum(f["rule_id"] not in targets for f in findings),
            "findings": findings,
        }

    def run(self, approach, keep: bool = False, timeline: bool = True) -> dict:
        rows, tl, kept = [], [], {}
        for key, data in self.data.items():
            if not self.covers(approach, data):
                continue
            judged = self.judge(approach, data)
            row = self.score(data.item, judged["findings"])
            if timeline and key in self.truth:
                row["timeline"] = timeline_scores(judged["graph"], self.truth[key], data.video.duration)
                tl.append(row["timeline"])
            rows.append(row)
            if keep:
                kept[key] = judged
        return {"approach": approach, "rows": rows, "metrics": verdict_metrics(rows),
                "timeline": timeline_summary(tl), "kept": kept, "coverage": len(rows)}


@contextlib.contextmanager
def settings(approach):
    """Timeline constants live at module level in reconstruction.graph and .derived; CV sources in fusion."""
    saved = (graph_module.KNOWN_CONFIDENCE, graph_module.EVENT_CONFIDENCE, derived_module.LEFT_OPEN_SEC,
             dict(fusion_module.CV_KEYS))
    graph_module.KNOWN_CONFIDENCE, graph_module.EVENT_CONFIDENCE = approach.known, approach.event
    derived_module.LEFT_OPEN_SEC = approach.left_open
    fusion_module.CV_KEYS.update(approach.cv_map)
    try:
        yield
    finally:
        graph_module.KNOWN_CONFIDENCE, graph_module.EVENT_CONFIDENCE, derived_module.LEFT_OPEN_SEC = saved[:3]
        fusion_module.CV_KEYS.clear()
        fusion_module.CV_KEYS.update(saved[3])


def finding_dicts(findings) -> list[dict]:
    return [{"rule_id": f.rule_id, "outcome": f.outcome, "kind": f.unknown_kind, "time": round(f.timecode_sec, 2),
             "start": round(f.start_sec, 2), "end": round(f.end_sec, 2), "reason": f.reason,
             "events": f.event_ids, "tracks": f.state_track_ids} for f in findings]


# ------------------------------------------------------------------------------------------- approaches

@dataclass
class Approach:
    name: str
    note: str
    group: str = "C"
    base_views: tuple[str, ...] = ("full256",)
    region_views: tuple[str, ...] = ("regions",)
    pool: dict[str, tuple[str, ...]] = field(default_factory=dict)        # per-key region sources
    pick: dict[str, tuple[str, str, int]] = field(default_factory=dict)   # per-key single (view, qid, sign)
    calibrate: bool = True
    cv: bool = True
    extras: tuple[str, ...] = ()       # views whose extra questions are averaged into their keys
    contrast: tuple[str, ...] = ()     # views whose negated questions are averaged in
    machine_count: bool = False
    cv_map: dict[str, str] = field(default_factory=dict)
    weights: dict[str, tuple[float, float, float]] = field(default_factory=dict)
    offsets: dict[str, float] = field(default_factory=dict)
    dwell: dict[str, float] = field(default_factory=dict)
    known: float = 0.6
    event: float = 0.8
    left_open: float = 3.0
    policy: str = "shadow"
    exact_api: bool = False
    oracle: bool = False

    def views(self) -> set[str]:
        if self.exact_api:
            return {"full256", "regions"}
        return ({*self.base_views, *self.region_views} | {v for views in self.pool.values() for v in views}
                | {view for view, _, _ in self.pick.values()})


HAND_KEYS = ("counting_cash", "handover", "cash_from_customer", "cash_to_customer", "id_document", "eating",
             "phone", "using_computer")
DOOR_KEYS = ("person_in_doorway", "door_open")
CLIP_FULL_KEYS = ("person_in_doorway", "at_safe", "handover", "counting_cash", "eating")
ZOOM_KEYS = ("id_document", "counting_cash", "eating", "phone")
NEW_WEIGHTS = {"cash_from_customer": (0.5, 1.0, 0.0), "cash_to_customer": (0.5, 1.0, 0.0),
               "using_computer": (0.5, 0.5, 0.5)}
# Final offsets tuned on the 2B caches (var/accuracy_benchmark_20261018); the probe thresholds are model-specific.
TWO_B_OFFSETS = {"key_in_safe": -2.0, "screen_unlocked": 1.0, "personal_items": -2.0, "eating": 2.0}
CV_MOTION = {"counting_cash": "desk_active", "person_in_doorway": "door_active", "at_safe": "safe_active"}


def approaches() -> list[Approach]:
    def pool(keys, views):
        return dict.fromkeys(keys, views)

    every = tuple(VIEWS)
    combined_pool = (pool(HAND_KEYS, ("regions", "clip_hands", "clip_full", "hands"))
                     | pool(DOOR_KEYS, ("regions", "clip_door", "clip_full")) | {"at_safe": ("regions", "clip_full")})
    return [
        Approach("api_default", "the API today with this model: full256 + regions + pose/motion, uncalibrated", "A",
                 calibrate=False, exact_api=True),
        Approach("calibrated", "api_default + label-free Otsu calibration of every question", "A"),
        Approach("calib_2b_offsets", "calibrated + the fusion offsets tuned for 2B", "A", offsets=TWO_B_OFFSETS),
        Approach("no_cv", "calibrated without pose/motion (VLM only)", "B", cv=False),
        Approach("no_regions", "calibrated without region crops (full frame + pose/motion)", "B", region_views=()),
        Approach("full256_only", "full frame at 256 tokens alone", "B", region_views=(), cv=False),
        Approach("full128_only", "full frame at 128 tokens alone", "B", base_views=("full128",), region_views=(), cv=False),
        Approach("full448_only", "full frame at 448 tokens alone", "B", base_views=("full448",), region_views=(), cv=False),
        Approach("active320_only", "active-area crop alone", "B", base_views=("active320",), region_views=(), cv=False),
        Approach("base_full448", "calibrated, full-frame source at 448 tokens", base_views=("full448",)),
        Approach("base_active320", "calibrated, full-frame source = active-area crop", base_views=("active320",)),
        Approach("base_ensemble", "calibrated, full-frame source = mean(full256, full448, active320)",
                 base_views=("full256", "full448", "active320")),
        Approach("paraphrases", "calibrated + extra full-frame questions averaged in", extras=("full256",)),
        Approach("negations", "calibrated + negated questions averaged in", contrast=("full256", "regions")),
        Approach("region_extras", "calibrated + extra crop questions (cash direction, typing, stamps)",
                 extras=("regions",), weights=NEW_WEIGHTS),
        Approach("clip_hands_mean", "hand actions = mean(hand crop, 3-frame hand clip)",
                 pool=pool(HAND_KEYS, ("regions", "clip_hands")), weights=NEW_WEIGHTS),
        Approach("clip_hands_only", "hand actions from the 3-frame hand clip alone",
                 pool=pool(HAND_KEYS, ("clip_hands",)), weights=NEW_WEIGHTS),
        Approach("clip_door_mean", "door and doorway = mean(door crop, 3-frame door clip)",
                 pool=pool(DOOR_KEYS, ("regions", "clip_door"))),
        Approach("clip_full_mean", "actions = mean(crops, 3-frame full clip)",
                 pool=pool(CLIP_FULL_KEYS, ("regions", "clip_full"))),
        Approach("hand_zoom", "hand-held items = mean(hand crop, pose-guided wrist crop)",
                 pool=pool(ZOOM_KEYS, ("regions", "hands")), extras=("hands",)),
        Approach("cv_motion", "pose evidence gated by local patch motion (desk, door, safe)", cv_map=CV_MOTION),
        Approach("machine_count", "counting-machine use counts as counting", machine_count=True),
        Approach("combined", "all views averaged per key + extras + negations + motion gating + machine count",
                 base_views=("full256", "full448", "active320"), pool=combined_pool, extras=every, contrast=every,
                 cv_map=CV_MOTION, machine_count=True, weights=NEW_WEIGHTS),
    ]


# ----------------------------------------------------------------------------------------------- metrics

def verdict_metrics(rows: list[dict]) -> dict:
    tp = sum(r["expected"] == "violation" and r["predicted"] == "violation" for r in rows)
    tn = sum(r["expected"] == "no_violation" and r["predicted"] == "no_violation" for r in rows)
    fp = sum(r["expected"] == "no_violation" and r["predicted"] == "violation" for r in rows)
    fn = sum(r["expected"] == "violation" and r["predicted"] == "no_violation" for r in rows)
    errors = [r["time_error"] for r in rows if r["time_error"] is not None]
    aspects = sum(r["aspects_total"] for r in rows)
    return {
        "videos": len(rows), "correct": tp + tn, "accuracy": (tp + tn) / len(rows) if rows else None,
        "tp": tp, "tn": tn, "fp": fp, "fn": fn,
        "precision": tp / (tp + fp) if tp + fp else None, "recall": tp / (tp + fn) if tp + fn else None,
        "f1": 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else None,
        "aspect_hits": sum(r["aspects_hit"] for r in rows), "aspects": aspects,
        "aspect_recall": sum(r["aspects_hit"] for r in rows) / aspects if aspects else None,
        "time_within_3s": sum(e <= 3 for e in errors), "time_within_5s": sum(e <= 5 for e in errors),
        "median_time_error": float(np.median(errors)) if errors else None,
        "alarms_on_clean": sum(len(r["findings"]) for r in rows if r["expected"] == "no_violation"),
        "off_target_alarms": sum(r["off_target"] for r in rows if r["expected"] == "violation"),
        "wrong": [r["key"] for r in rows if not r["correct"]],
    }


def predicted_spans(graph, key: str) -> tuple[list, list, list]:
    """(strict, loose, unknown) spans of a key as the rules see it. Strict: bounded true states and
    non-hypothesis events. Loose: hypotheses too."""
    if key in ACTION_EVENTS:
        action = ACTION_EVENTS[key][0]
        events = [e for e in graph.events if e.action == action]
        loose = [(e.time.start_sec - PAD, e.time.end_sec + PAD) for e in events]
        strict = [(e.time.start_sec - PAD, e.time.end_sec + PAD) for e in events if e.inference_status != "hypothesis"]
        return strict, loose, []
    track = next((t for t in graph.state_tracks if t.id == f"st_{key}"), None)
    if track is None:
        return [], [], []
    strict = [(i.start_sec, i.end_sec) for i in track.intervals
              if i.value == "true" and i.knowledge == "bounded_by_observations"]
    unknown = [(i.start_sec, i.end_sec) for i in track.intervals if i.value is None or i.knowledge == "unknown"]
    return strict, strict, unknown


def segment_errors(truth_spans, ignore, predicted) -> dict:
    truth_segments = merge(truth_spans, STEP)
    predicted_segments = merge(predicted, 0.5)
    missed, fake, onset, offset = [], [], [], []
    for segment in truth_segments:
        hits = [p for p in predicted_segments if overlap(p, segment) > 0.01]
        if hits:
            onset.append(hits[0][0] - segment[0])
            offset.append(hits[-1][1] - segment[1])
        else:
            missed.append(segment)
    for segment in predicted_segments:
        if not any(overlap(segment, t) > 0.01 for t in truth_segments) and not any(overlap(segment, g) > 0.01 for g in ignore):
            fake.append(segment)
    return {"true_segments": len(truth_segments), "missed": missed, "fake": fake, "onset": onset, "offset": offset}


def timeline_scores(graph, truth: dict, duration: float) -> dict:
    times = np.arange(0.0, duration, STEP)
    scores = {}
    for key, raw in truth["attributes"].items():
        if key not in FUSED_KEYS:
            continue
        positive, ignore = as_spans(raw, duration), as_spans(truth["ignore"].get(key, []), duration)
        label, valid = covered(times, positive), ~covered(times, ignore)
        strict, loose, unknown = predicted_spans(graph, key)
        hit, loose_hit, unsure = covered(times, strict), covered(times, loose), covered(times, unknown)
        scores[key] = {
            "tp": int(np.sum(valid & label & hit)), "fp": int(np.sum(valid & ~label & hit)),
            "fn": int(np.sum(valid & label & ~hit)), "tn": int(np.sum(valid & ~label & ~hit)),
            "loose_tp": int(np.sum(valid & label & loose_hit)), "loose_fp": int(np.sum(valid & ~label & loose_hit)),
            "unknown_pos": int(np.sum(valid & label & unsure)), "unknown_neg": int(np.sum(valid & ~label & unsure)),
            "strict": segment_errors(positive, ignore, strict), "loose": segment_errors(positive, ignore, loose),
            "source": truth["source"].get(key),
        }
    visits = (as_spans(truth["visits"], duration) if truth.get("visits") is not None
              else as_spans(truth["attributes"].get("customer_present", []), duration)
              if "customer_present" in truth["attributes"] else None)
    if visits is not None:
        found = [(e.start_sec, duration if e.end_sec is None else e.end_sec)
                 for e in graph.procedure_episodes if e.kind == "customer_visit"]
        scores["_visits"] = {"true": len(visits), "predicted": len(found),
                             "matched": sum(any(overlap(v, f) > 0.01 for f in found) for v in visits)}
    return scores


def timeline_summary(videos: list[dict]) -> dict:
    pooled: dict[str, dict] = {}
    visits = {"videos": 0, "exact": 0, "true": 0, "predicted": 0, "matched": 0}
    for scores in videos:
        for key, value in scores.items():
            if key == "_visits":
                visits["videos"] += 1
                visits["exact"] += value["true"] == value["predicted"]
                for name in ("true", "predicted", "matched"):
                    visits[name] += value[name]
                continue
            entry = pooled.setdefault(key, {"tp": 0, "fp": 0, "fn": 0, "tn": 0, "loose_tp": 0, "loose_fp": 0,
                                            "unknown_pos": 0, "unknown_neg": 0, "true_segments": 0, "missed": 0,
                                            "fake": 0, "loose_missed": 0, "loose_fake": 0, "onset": [], "offset": []})
            for name in ("tp", "fp", "fn", "tn", "loose_tp", "loose_fp", "unknown_pos", "unknown_neg"):
                entry[name] += value[name]
            entry["true_segments"] += value["strict"]["true_segments"]
            entry["missed"] += len(value["strict"]["missed"])
            entry["fake"] += len(value["strict"]["fake"])
            entry["loose_missed"] += len(value["loose"]["missed"])
            entry["loose_fake"] += len(value["loose"]["fake"])
            entry["onset"] += value["strict"]["onset"]
            entry["offset"] += value["strict"]["offset"]
    keys = {}
    for key, e in sorted(pooled.items()):
        positives, negatives = e["tp"] + e["fn"], e["tn"] + e["fp"]
        tpr = e["tp"] / positives if positives else None
        tnr = e["tn"] / negatives if negatives else None
        keys[key] = e | {
            "f1": 2 * e["tp"] / (2 * e["tp"] + e["fp"] + e["fn"]) if 2 * e["tp"] + e["fp"] + e["fn"] else None,
            "balanced_accuracy": (tpr + tnr) / 2 if tpr is not None and tnr is not None else None,
            "recall": tpr, "specificity": tnr,
            "loose_recall": e["loose_tp"] / positives if positives else None,
            "median_onset": float(np.median(np.abs(e["onset"]))) if e["onset"] else None,
            "median_offset": float(np.median(np.abs(e["offset"]))) if e["offset"] else None,
            "positives": positives, "negatives": negatives,
        }
    f1s = [v["f1"] for v in keys.values() if v["positives"] and v["f1"] is not None]
    bas = [v["balanced_accuracy"] for v in keys.values() if v["balanced_accuracy"] is not None]
    return {"keys": keys, "macro_f1": float(np.mean(f1s)) if f1s else None,
            "macro_balanced_accuracy": float(np.mean(bas)) if bas else None,
            "true_segments": sum(v["true_segments"] for v in keys.values()),
            "missed": sum(v["missed"] for v in keys.values()), "fake": sum(v["fake"] for v in keys.values()),
            "visits": visits, "videos": len(videos)}


# ------------------------------------------------------------------------------------------ text output

STATE_ORDER = ["cashier_seated", "cashier_at_station", "customer_present", "room_occupied", "person_in_doorway",
               "door_open", "at_safe", "safe_open", "key_in_safe", "using_computer", "screen_on", "screen_unlocked",
               "counting_cash", "cash_from_customer", "cash_to_customer", "handover", "id_document", "cash_on_desk",
               "bag_on_desk", "stamps_on_desk", "personal_items", "food_on_desk", "eating", "phone"]


def ruler(duration: float) -> str:
    width = int(math.ceil(duration / CHAR))
    line = [" "] * width
    for second in range(0, int(duration) + 1, 5):
        position = int(second / CHAR)
        for offset, char in enumerate(f"|{second}"):
            if position + offset < width:
                line[position + offset] = char
    return "".join(line)


def strip(duration: float, char_at) -> str:
    return "".join(char_at((i + 0.5) * CHAR) for i in range(int(math.ceil(duration / CHAR))))


def state_char(intervals, moment: float) -> str:
    inside = [i for i in intervals if i.start_sec - 1e-6 <= moment <= i.end_sec + 1e-6]
    if not inside:
        return " "
    interval = max(inside, key=lambda i: i.end_sec - i.start_sec)
    if interval.value == "transitioning":
        return "~"
    if interval.value is None or interval.knowledge == "unknown":
        return "?"
    return "#" if interval.value == "true" else "."


def action_char(events, moment: float) -> str:
    inside = [e for e in events if e.time.start_sec - PAD <= moment <= e.time.end_sec + PAD]
    if any(e.inference_status != "hypothesis" for e in inside):
        return "#"
    return "+" if inside else "."


def digits(times: np.ndarray, values: np.ndarray, duration: float, reach: float = 0.75) -> str:
    def char(moment):
        if not len(times):
            return " "
        index = int(np.argmin(np.abs(times - moment)))
        if abs(times[index] - moment) > reach or np.isnan(values[index]):
            return " "
        return str(min(9, int(values[index] * 10)))
    return strip(duration, char)


# ------------------------------------------------------------------------------------------------ tuning

class TimeUp(Exception):
    pass


class Tuner:
    """Coordinate descent over offsets and timeline settings with stratified k-fold validation, as
    eval/tuning/tune.py. Each evaluated setting is memoised as a per-video correctness vector."""

    OFFSET_KEYS = ("cash_on_desk", "bag_on_desk", "safe_open", "key_in_safe", "screen_on", "stamps_on_desk",
                   "door_open", "personal_items", "eating", "counting_cash", "id_document", "cash_to_customer",
                   "cash_from_customer", "room_occupied", "cashier_at_station", "customer_present")

    def __init__(self, lab: Lab, base: Approach, deadline: float) -> None:
        self.lab, self.base, self.deadline = lab, base, deadline
        self.keys = [key for key, data in lab.data.items() if lab.covers(base, data)]
        self.memo: dict[tuple, np.ndarray] = {}
        self.knobs = [(f"offset:{k}", (-2.0, -1.0, 0.0, 1.0, 2.0), base.offsets.get(k, 0.0)) for k in self.OFFSET_KEYS]
        self.knobs += [("known", (0.5, 0.6, 0.7), base.known), ("event", (0.6, 0.7, 0.8, 0.9), base.event),
                       ("left_open", (2.0, 3.0, 4.0, 6.0), base.left_open),
                       ("dwell:counting_cash", (3.0, 6.0, 10.0), base.dwell.get("counting_cash", 6.0)),
                       ("dwell:id_document", (2.0, 3.0, 6.0), base.dwell.get("id_document", 3.0)),
                       ("dwell:customer_present", (6.0, 12.0, 20.0), base.dwell.get("customer_present", 12.0))]
        self.defaults = {name: default for name, _, default in self.knobs}
        self.current: dict = {}

    def approach(self, state: dict) -> Approach:
        offsets, dwell, values = dict(self.base.offsets), dict(self.base.dwell), {}
        for name, value in state.items():
            kind, _, key = name.partition(":")
            if kind == "offset":
                offsets[key] = value
            elif kind == "dwell":
                dwell[key] = value
            else:
                values[kind] = value
        return replace(self.base, name=f"{self.base.name}+tuned", note="tuned in-sample (optimistic)", group="D",
                       offsets=offsets, dwell=dwell, **values)

    def changes(self, state: dict) -> dict:
        return {name: value for name, value in state.items() if value != self.defaults[name]}

    def correct(self, state: dict, force: bool = False) -> np.ndarray:
        state = self.changes(state)
        index = tuple(sorted(state.items()))
        if index not in self.memo:
            if time.time() > self.deadline and not force:
                raise TimeUp
            approach = self.approach(state)
            scores = []
            for key in self.keys:
                row = self.lab.score(self.lab.data[key].item, self.lab.judge(approach, self.lab.data[key])["findings"])
                scores.append(row["correct"] + 0.01 * (row["aspects_hit"] / row["aspects_total"] if row["aspects_total"] else 0))
            self.memo[index] = np.asarray(scores)
        return self.memo[index]

    def descend(self, mask: np.ndarray, rounds: int) -> dict:
        state: dict = {}
        self.current = state
        for _ in range(rounds):
            changed = False
            for name, values, default in self.knobs:
                current = state.get(name, default)
                best, best_score = current, self.correct(state | {name: current})[mask].sum()
                for value in values:
                    score = self.correct(state | {name: value})[mask].sum()
                    if score > best_score + 1e-9:
                        best, best_score = value, score
                changed |= best != current
                state[name] = best
            if not changed:
                break
        return self.changes(state)

    def folds(self, count: int) -> list[np.ndarray]:
        """Stratified folds; exact duplicate videos always share a fold."""
        groups: dict[str, list[int]] = {}
        for index, key in enumerate(self.keys):
            groups.setdefault(self.lab.data[key].meta["sha256"], []).append(index)
        ordered = sorted(groups.values(), key=lambda g: (self.lab.data[self.keys[g[0]]].item.expected, g[0]))
        assignment = np.empty(len(self.keys), int)
        for position, group in enumerate(ordered):
            assignment[group] = position % count
        return [assignment == fold for fold in range(count)]

    def validate(self, folds: int, rounds: int) -> dict:
        everything = np.ones(len(self.keys), bool)
        result = {"videos": len(self.keys), "folds": folds, "complete": False}
        held_out, done = np.zeros(len(self.keys)), np.zeros(len(self.keys), bool)
        try:
            state = self.descend(everything, rounds)
            result |= {"state": state, "in_sample": float(np.floor(self.correct(state)).sum())}
            for test in self.folds(folds):
                if not test.any():
                    continue
                held_out[test] = np.floor(self.correct(self.descend(~test, rounds))[test])
                done |= test
            result["complete"] = True
        except TimeUp:
            result["stopped"] = "time limit"
            if "state" not in result:
                # Out of time during the all-video descent: report the settings reached so far.
                state = self.changes(self.current)
                result |= {"state": state, "in_sample": float(np.floor(self.correct(state, force=True)).sum()),
                           "partial_descent": True}
        if done.any():
            result |= {"held_out": float(held_out[done].sum()), "held_out_videos": int(done.sum())}
        result["evaluations"] = len(self.memo)
        return result


# -------------------------------------------------------------------------------------------- reporting

def approach_table(say: Printer, results: list[dict], costs: dict[str, float]) -> None:
    say(f"{'approach':22s} {'videos':>6s} {'acc':>6s} {'P':>6s} {'R':>6s} {'F1':>6s} {'FP':>3s} {'FN':>3s} "
        f"{'type':>5s} {'<=5s':>4s} {'alarm':>5s} {'tlF1':>6s} {'tlBA':>6s} {'miss':>9s} {'fake':>4s} "
        f"{'visits':>7s} {'cost':>5s}")
    for result in results:
        m, t, a = result["metrics"], result["timeline"], result["approach"]
        cost = sum(costs.get(view, 0.0) for view in a.views()) + (costs.get("pose", 0) + costs.get("motion", 0) if a.cv else 0)
        visits = t["visits"]
        say(f"{a.name:22s} {m['videos']:>6d} {pct(m['accuracy']):>6s} {pct(m['precision'], 0):>6s} "
            f"{pct(m['recall'], 0):>6s} {pct(m['f1'], 0):>6s} {m['fp']:>3d} {m['fn']:>3d} "
            f"{m['aspect_hits']:>2d}/{m['aspects']:<2d} {m['time_within_5s']:>4d} "
            f"{m['alarms_on_clean']:>2d}/{m['off_target_alarms']:<2d} {pct(t['macro_f1']):>6s} "
            f"{pct(t['macro_balanced_accuracy']):>6s} {t['missed']:>4d}/{t['true_segments']:<4d} {t['fake']:>4d} "
            f"{visits['exact']:>3d}/{visits['videos']:<3d} {cost:>5.1f}")


def timeline_table(say: Printer, result: dict) -> None:
    say(f"{'key':20s} {'F1':>6s} {'BA':>6s} {'recall':>6s} {'(loose)':>7s} {'spec':>6s} {'unk+':>5s} "
        f"{'segments':>8s} {'missed':>6s} {'(loose)':>7s} {'fake':>4s} {'(loose)':>7s} {'onset':>5s} {'offset':>6s}  frames+/-")
    for key, v in result["timeline"]["keys"].items():
        unknown = v["unknown_pos"] / v["positives"] if v["positives"] else None
        say(f"{key:20s} {pct(v['f1'], 0):>6s} {pct(v['balanced_accuracy'], 0):>6s} {pct(v['recall'], 0):>6s} "
            f"{pct(v['loose_recall'], 0):>7s} {pct(v['specificity'], 0):>6s} {pct(unknown, 0):>5s} "
            f"{v['true_segments']:>8d} {v['missed']:>6d} {v['loose_missed']:>7d} {v['fake']:>4d} {v['loose_fake']:>7d} "
            f"{num(v['median_onset'], 1):>5s} {num(v['median_offset'], 1):>6s}  {v['positives']}/{v['negatives']}")


def rule_table(say: Printer, lab: Lab, result: dict) -> list[dict]:
    rows = result["rows"]
    rules = sorted({rule for row in rows for rule in row["rules"]} | {r.rule_id for r in REGISTRY.rules if r.status != "disabled"})
    stats = []
    for rule in rules:
        fired = [row for row in rows if rule in row["rules"]]
        on_target = [r for r in fired if r["expected"] == "violation" and any(
            rule in a["any_of_rules"] for a in lab.catalog.get(r["key"], {}).get("aspects", []))]
        clean = [r for r in fired if r["expected"] == "no_violation"]
        other = [r for r in fired if r not in on_target and r not in clean]
        without = [row for row in rows if not (set(row["rules"]) - {rule}) and row["predicted"] == "violation"]
        # Accuracy change if this rule were switched off: videos it alone flags flip to no_violation.
        delta = sum((1 if r["expected"] == "no_violation" else -1) for r in without)
        targets = [k for k, entry in lab.catalog.items() if k in lab.data and any(rule in a["any_of_rules"] for a in entry.get("aspects", []))]
        stats.append({"rule": rule, "fired": len(fired), "on_target": len(on_target), "clean": len(clean),
                      "other_violation": len(other), "target_videos": len(targets),
                      "missed_targets": sorted(set(targets) - {r["key"] for r in on_target}),
                      "accuracy_change_if_disabled": delta, "clean_videos": [r["key"] for r in clean]})
    say(f"{'rule':44s} {'fired':>5s} {'target':>7s} {'clean':>5s} {'other':>5s} {'off':>4s}  missed targets / false alarms")
    for s in stats:
        if not s["fired"] and not s["target_videos"]:
            continue
        say(f"{s['rule']:44s} {s['fired']:>5d} {s['on_target']:>3d}/{s['target_videos']:<3d} {s['clean']:>5d} "
            f"{s['other_violation']:>5d} {s['accuracy_change_if_disabled']:>+4d}  "
            f"missed {','.join(s['missed_targets']) or '-'}; FP {','.join(s['clean_videos']) or '-'}")
    return stats


def probe_quality(lab: Lab, kept: dict[str, dict[str, dict]]) -> dict:
    """AUC of every question (and CV signal, and fused score) against the annotated frames."""
    pooled: dict[tuple[str, str], list] = {}

    def add(source, qid, key, times, scores, data, sign=1):
        truth = lab.truth.get(data.item.key)
        if truth is None or key not in truth["attributes"]:
            return
        duration = data.video.duration
        label = covered(times, as_spans(truth["attributes"][key], duration))
        valid = ~covered(times, as_spans(truth["ignore"].get(key, []), duration)) & ~np.isnan(scores)
        entry = pooled.setdefault((source, qid), [[], [], set(), key, sign])
        entry[0].extend(scores[valid])
        entry[1].extend(label[valid])
        entry[2].add(data.item.key)

    for data in lab.data.values():
        for view, series in data.views.items():
            for q in VIEWS[view].questions:
                if q.target is None or q.qid not in series:
                    continue
                times, values = series[q.qid]
                add(view, q.qid, q.target, times, values if q.sign > 0 else 1 - values, data, q.sign)
        signals = lab.signals(data)
        if signals is not None:
            for key, name in [*fusion_module.CV_KEYS.items(), *CV_MOTION.items()]:
                if name in signals.values:
                    add("cv", name, key, signals.times, np.asarray(signals.values[name], float), data)
        for approach, judged in kept.items():
            if data.item.key in judged:
                for key, values in judged[data.item.key]["fused"].items():
                    add(f"fused:{approach}", key, key, data.grid, np.asarray(values, float), data)
    result = {}
    for (source, qid), (scores, labels, videos, key, sign) in pooled.items():
        scores, labels = np.asarray(scores, float), np.asarray(labels, bool)
        view = source if source in VIEWS else None
        bias = lab.bias.get((view, qid), 0.0) if view else 0.0
        # The calibrated decision point; a negated question's score is 1 - p.
        cut = float(sigmoid(np.asarray(bias))) if view else 0.5
        threshold = scores >= (cut if sign > 0 else 1 - cut)
        tpr = float(np.mean(threshold[labels])) if labels.any() else None
        tnr = float(np.mean(~threshold[~labels])) if (~labels).any() else None
        result[f"{source}|{qid}"] = {
            "source": source, "qid": qid, "key": key, "auc": auc(scores, labels), "positives": int(labels.sum()),
            "negatives": int((~labels).sum()), "videos": len(videos),
            "balanced_accuracy": (tpr + tnr) / 2 if tpr is not None and tnr is not None else None,
            "mean_pos": float(scores[labels].mean()) if labels.any() else None,
            "mean_neg": float(scores[~labels].mean()) if (~labels).any() else None,
            "bias": bias, "separation": lab.separation.get((view, qid)) if view else None,
        }
    return result


def best_per_key(lab: Lab, quality: dict) -> Approach:
    """Oracle: each annotated key takes the single question with the best AUC (uses the annotations)."""
    pick = {}
    for key in FUSED_KEYS:
        candidates = [v for v in quality.values() if v["source"] in VIEWS and v["key"] == key
                      and any(q.qid == v["qid"] and q.key == key for q in VIEWS[v["source"]].questions)
                      and v["positives"] >= 8 and v["negatives"] >= 8 and not math.isnan(v["auc"])]
        if candidates:
            best = max(candidates, key=lambda v: v["auc"])
            sign = next(q.sign for q in VIEWS[best["source"]].questions if q.qid == best["qid"])
            pick[key] = (best["source"], best["qid"], sign)
    weights = {key: (0.0, 1.0, 0.0) for key in pick}
    return Approach("best_per_key", "ORACLE: per key the question with the best annotated AUC (optimistic)",
                    "C", pick=pick, weights=weights, oracle=True)


def timeline_file(lab: Lab, approach: Approach, data: Data, judged: dict, row: dict, refined: dict | None = None) -> str:
    graph, fused, duration = judged["graph"], judged["fused"], data.video.duration
    entry = lab.catalog.get(data.item.key, {})
    truth = lab.truth.get(data.item.key)
    aspects = "; ".join(f"{a['name']} ({', '.join(a['any_of_rules'])}, {a['observability']})"
                        for a in entry.get("aspects", [])) or "none"
    lines = [
        f"{data.item.label}  expected={data.item.expected}  label time={entry.get('timestamp_sec')}  "
        f"label text: {entry.get('label_text') or '-'}",
        f"labelled aspects: {aspects}",
        f"approach {approach.name}: {approach.note}",
        f"PREDICTED {row['predicted']}  ({'CORRECT' if row['correct'] else 'WRONG'})  rules: {', '.join(row['rules']) or '-'}"
        f"  type hits {row['aspects_hit']}/{row['aspects_total']}  time error "
        f"{num(row['time_error'], 1) if row['time_error'] is not None else '-'}s",
        f"duration {duration:.1f}s; one character = {CHAR}s.  pred: # true/observed, . false, ? unknown, ~ changing, "
        "+ hypothesis event (ignored by rules)",
        "truth: # true, . false, blank = ambiguous or not annotated.  p: fused probability 0-9 that the HMM decoded.",
        "", f"{'':31s}{ruler(duration)}",
    ]
    tracks = {t.id: t for t in graph.state_tracks}
    times = np.arange(0.0, duration, STEP)
    for key in STATE_ORDER:
        if key in ACTION_EVENTS:
            events = [e for e in graph.events if e.action == ACTION_EVENTS[key][0]]
            line = strip(duration, lambda m, events=events: action_char(events, m))
        elif f"st_{key}" in tracks:
            line = strip(duration, lambda m, track=tracks[f"st_{key}"]: state_char(track.intervals, m))
        else:
            continue
        lines.append(f"{key:31s}{line}")
        if truth and key in truth["attributes"]:
            positive = as_spans(truth["attributes"][key], duration)
            ignore = as_spans(truth["ignore"].get(key, []), duration)
            lines.append(f"{'  truth':31s}" + strip(duration, lambda m: " " if covered(np.array([m]), ignore)[0]
                                                     else "#" if covered(np.array([m]), positive)[0] else "."))
        if key in fused:
            lines.append(f"{'  p':31s}{digits(data.grid, np.asarray(fused[key]), duration)}")
    derived = [t for t in graph.state_tracks if t.id.removeprefix("st_") not in FUSED_KEYS]
    if derived:
        lines.append("derived states (what the rules check):")
        for track in derived:
            lines.append(f"{track.id[:30]:31s}" + strip(duration, lambda m, track=track: state_char(track.intervals, m)))
    lines += ["", "raw calibrated scores per view (0-9; blank = not sampled):"]
    for key in STATE_ORDER:
        for view, series in data.views.items():
            for q in VIEWS[view].questions:
                if q.key == key and q.qid in series:
                    t, values = series[q.qid]
                    calibrated = sigmoid(q.sign * (logit(values) - lab.bias.get((view, q.qid), 0.0)))
                    lines.append(f"{(key + ' ' + view + ('' if q.qid == key else ' ' + q.qid.split(key)[-1]))[:30]:31s}"
                                 f"{digits(t, np.where(np.isnan(values), np.nan, calibrated), duration)}")
    lines += ["", "events:"]
    for event in graph.events:
        who = ",".join(f"{p.role}={p.entity_id}" for p in event.participants)
        lines.append(f"  {event.time.start_sec:6.1f}-{event.time.end_sec:6.1f}s {event.action:30s} "
                     f"{event.inference_status:28s} {who}")
    lines.append("customer visits:")
    for episode in graph.procedure_episodes:
        lines.append(f"  {episode.id}: {episode.start_sec:.1f}-{num(episode.end_sec, 1)}s ({episode.end_boundary_status}) "
                     f"events {', '.join(episode.event_ids)}")
    lines += ["", "reported findings:"]
    for finding in row["findings"]:
        lines.append(f"  {finding['time']:6.1f}s {finding['rule_id']} {finding['outcome']}"
                     f"{'/' + finding['kind'] if finding['kind'] else ''}: {finding['reason']}")
    if not row["findings"]:
        lines.append("  none")
    if "timeline" in row:
        lines += ["", "timeline errors against the annotations (strict = what the rules use):"]
        for key, value in row["timeline"].items():
            if key == "_visits":
                lines.append(f"  customer visits: true {value['true']}, predicted {value['predicted']}, matched {value['matched']}")
                continue
            s = value["strict"]
            missed = ", ".join(f"{a:.1f}-{b:.1f}" for a, b in s["missed"]) or "-"
            fake = ", ".join(f"{a:.1f}-{b:.1f}" for a, b in s["fake"]) or "-"
            lines.append(f"  {key:20s} [{value['source']}] segments {s['true_segments']}, MISSED {missed}; FAKE {fake}; "
                         f"frames tp {value['tp']} fp {value['fp']} fn {value['fn']}")
    if refined:
        lines += ["", "follow-up refinement:"]
        for check in refined.get("followups", {}).get("checks", []):
            question, answer = check["question"], check.get("answer")
            lines.append(f"  Q {question['rule_id']} {question['window']['start_sec']:.1f}-{question['window']['end_sec']:.1f}s: "
                         f"{question['reason']}")
            lines.append(f"    -> {answer['status'] + ': ' + answer['explanation'] if answer else 'ERROR ' + str(check.get('error'))}")
        for event in refined.get("temporal", {}).get("events", []):
            lines.append(f"  cash provenance: {event['action']} {event['time']['start_sec']:.1f}-{event['time']['end_sec']:.1f}s "
                         f"{event['inference_status']}: {event.get('note', '')}")
        for name in ("findings_temporal", "findings_followups"):
            if name in refined:
                lines.append(f"  {name}: {', '.join(sorted({f['rule_id'] for f in refined[name]})) or 'none'}")
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------------------------- main flow

def environment(args) -> dict:
    info = {"python": sys.version, "platform": platform.platform(), "torch": torch.__version__,
            "cuda": torch.version.cuda, "args": {k: str(v) for k, v in vars(args).items()}}
    with contextlib.suppress(Exception):
        import transformers
        info["transformers"] = transformers.__version__
    if torch.cuda.is_available():
        info["gpu"] = torch.cuda.get_device_name(0)
        info["gpu_memory_gib"] = round(torch.cuda.get_device_properties(0).total_memory / 2**30, 1)
    with contextlib.suppress(Exception):
        info["git"] = subprocess.run(["git", "-C", str(BACKEND), "rev-parse", "HEAD"], capture_output=True,
                                     text=True, timeout=10).stdout.strip()
    sources = sorted((BACKEND / "src").rglob("*.py")) + sorted((BACKEND / "src").rglob("*.yaml")) + [Path(__file__)]
    info["source_sha256"] = {str(p.relative_to(BACKEND)): sha256(p)[:16] for p in sources}
    return info


def view_costs(lab: Lab) -> dict[str, float]:
    """GPU seconds per second of video for every phase."""
    costs, timings = {}, (read_json(lab.cache / "timings.json") if (lab.cache / "timings.json").exists() else {})
    for phase in ("pose", "scene", *VIEWS):
        measured = [(data.seconds[phase], data.video.duration) for data in lab.data.values() if phase in data.seconds]
        if measured:
            costs[phase] = sum(s for s, _ in measured) / sum(d for _, d in measured)
    seconds = sum(timings.get("motion", {}).values())
    duration = sum(d.video.duration for d in lab.data.values() if d.item.key in timings.get("motion", {}))
    if duration:
        costs["motion"] = seconds / duration
    return costs


def refine_phase(lab: Lab, approach: Approach) -> None:
    args = lab.args
    folder = lab.cache / "refine" / approach.name
    todo = [data for data in lab.data.values() if not (folder / f"{data.item.key}.json").exists()
            and lab.covers(approach, data)]
    if not todo:
        return
    model = TimedModel(lab.vlm(), args.call_seconds, args.structured_tokens)
    total = sum(d.video.duration for d in todo)
    spent = done = 0.0
    print(f"\n[refine] {approach.name}: cash provenance scan + up to {args.followup_calls} JSON follow-ups, "
          f"{len(todo)} videos", flush=True)
    for index, data in enumerate(todo, start=1):
        if time.time() > lab.deadline:
            print("[refine] GPU time budget reached", flush=True)
            return
        started, first_call = perf_counter(), len(model.calls)
        record: dict = {"approach": approach.name, "video": data.item.label}
        try:
            video = decode(data.item.path, GRID_FPS)
            if len(video.times) != len(data.grid):
                raise ValueError("decoded frame times differ from the cached grid")
            graph = lab.judge(approach, data, video)["graph"]
            try:
                temporal = observe_cash_provenance(graph, video, model)
                graph = temporal.graph
                record["temporal"] = {"calls": temporal.calls, "errors": temporal.errors,
                                      "events": [e.model_dump(mode="json") for e in graph.events
                                                 if e.id.startswith("cash_temporal")]}
            except Exception as error:
                record["temporal"] = {"failed": f"{type(error).__name__}: {error}"}
            record["findings_temporal"] = finding_dicts(reportable(evaluate(REGISTRY, graph, "shadow"), SHADOW))
            if args.followup_calls > 0:
                result = refine(REGISTRY, graph, video, model, "shadow", args.followup_calls, args.followup_frames,
                                verify_positive=True)
                record["followups"] = {"calls": result.calls, "semantic_errors": result.semantic_errors,
                                       "checks": [check.model_dump(mode="json") for check in result.checks]}
                record["findings_followups"] = finding_dicts(reportable(result.report, SHADOW))
        except KeyboardInterrupt:
            raise
        except Exception as error:
            record["failed"] = f"{type(error).__name__}: {error}"
            logger.error("refine %s failed\n%s", data.item.key, traceback.format_exc())
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        record["model_calls"] = model.calls[first_call:]
        record["seconds"] = round(perf_counter() - started, 2)
        write_json(folder / f"{data.item.key}.json", record)
        spent += record["seconds"]
        done += data.video.duration
        ok = sum(c["ok"] for c in record["model_calls"])
        print(f"[refine] {index}/{len(todo)} {data.item.key:6s} {record['seconds']:6.1f}s, "
              f"{len(record['model_calls'])} JSON calls ({ok} valid){' FAILED ' + record['failed'] if 'failed' in record else ''}"
              f", ETA {clock(spent / max(done, 1e-6) * (total - done))}", flush=True)


def refined_results(lab: Lab, approach: Approach, base_rows: dict[str, dict]) -> tuple[list[dict], str]:
    folder = lab.cache / "refine" / approach.name
    records = {data.item.key: read_json(folder / f"{data.item.key}.json") for data in lab.data.values()
               if (folder / f"{data.item.key}.json").exists()}
    results = []
    for stage, label in (("findings_temporal", "+cash_scan"), ("findings_followups", "+cash_scan+followups")):
        rows, base = [], []
        for key, record in records.items():
            if stage in record and key in base_rows:
                rows.append(lab.score(lab.data[key].item, record[stage]))
                base.append(base_rows[key])
        if rows:
            results.append({"approach": replace(approach, name=approach.name + label, group="E",
                                                note=f"{approach.note}; GPU {label[1:]}"),
                            "rows": rows, "metrics": verdict_metrics(rows), "baseline": verdict_metrics(base),
                            "timeline": timeline_summary([]), "kept": {}, "coverage": len(rows)})
    calls = [call for record in records.values() for call in record.get("model_calls", [])]
    by_schema: dict[str, list] = {}
    for call in calls:
        by_schema.setdefault(call["schema"], []).append(call)
    summary = f"JSON calls: {len(calls)} total; " + "; ".join(
        f"{name} {sum(c['ok'] for c in group)}/{len(group)} valid, {np.mean([c['seconds'] for c in group]):.1f}s avg"
        for name, group in by_schema.items())
    failed = [key for key, record in records.items() if "failed" in record]
    if failed:
        summary += f"; failed videos: {', '.join(failed)}"
    return results, summary


def bundle(lab: Lab) -> Path:
    target = lab.out / "send_me.zip"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(lab.out.rglob("*")):
            relative = path.relative_to(lab.out)
            parts = relative.parts
            if (not path.is_file() or path == target or path.suffix == ".tmp" or ".tmp" in path.name
                    or parts[:2] in (("cache", "motion"), ("cache", "videos"))):
                continue
            archive.write(path, relative.as_posix())
    return target


def analyse(lab: Lab) -> None:
    say, args = lab.say, lab.args
    lab.load()
    if not lab.data:
        raise SystemExit("Nothing cached yet: run without --report-only first.")
    lab.calibrate()
    costs = view_costs(lab)
    say.section(f"DATA  ({lab.model_name()})")
    present = {name: sum(name in d.views for d in lab.data.values()) for name in VIEWS}
    say(f"videos {len(lab.data)} ({sum(d.item.expected == 'violation' for d in lab.data.values())} violation), "
        f"timeline-annotated {sum(k in lab.truth for k in lab.data)}; "
        f"pose {sum(d.pose is not None for d in lab.data.values())}, motion {sum(d.motion_ready for d in lab.data.values())}, "
        f"scene {sum(d.scene is not None for d in lab.data.values())}")
    for name, view in VIEWS.items():
        say(f"  {name:11s} {present[name]:>3d}/{len(lab.data)} videos  {num(costs.get(name), 2):>5s} GPU s per video s  {view.note}")
    say(f"  pose {num(costs.get('pose'), 2)}, motion {num(costs.get('motion'), 2)}, scene grounding {num(costs.get('scene'), 2)} s per video s")
    grounded = [d.scene.grounded for d in lab.data.values() if d.scene is not None]
    if grounded:
        say("  grounding fell back to default boxes: " + ", ".join(
            f"{name} {sum(not g.get(name, False) for g in grounded)}" for name in grounded[0]))
    if lab.failures:
        say(f"  {len(lab.failures)} failed steps this run (see run.log): " +
            "; ".join(f"{f['phase']} {f['video']}" for f in lab.failures[:12]))

    # Every approach, then the oracle built from the probe AUCs.
    say.section("APPROACHES  (verdicts on all covered videos; timeline on the annotated ones)")
    say("acc/P/R/F1: violation verdicts.  type: labelled violation types found.  <=5s: right type within 5 s.")
    say("alarm: alarms on clean videos / off-type alarms on violation videos.  tlF1/tlBA: timeline frame F1 and")
    say("balanced accuracy (macro over keys, as the rules see it).  miss: true segments with no detection / all true")
    say("segments.  fake: detections with no true segment.  visits: videos with the right customer-visit count.")
    say("cost: GPU seconds per video second of the views it uses.")
    results = []
    listed = approaches()
    for approach in listed:
        started = perf_counter()
        result = lab.run(approach, keep=approach.name in ("api_default", "calibrated"))
        result["seconds"] = perf_counter() - started
        results.append(result)
    kept = {r["approach"].name: r["kept"] for r in results if r["kept"]}
    quality = probe_quality(lab, kept)
    oracle = lab.run(best_per_key(lab, quality))
    results.append(oracle)
    for group, title in (("A", "A. API structure"), ("B", "B. single sources and ablations"),
                         ("C", "C. new techniques on top of 'calibrated'")):
        say(f"\n{title}")
        approach_table(say, [r for r in results if r["approach"].group == group and r["coverage"]], costs)
    skipped = [r["approach"].name for r in results if not r["coverage"]]
    if skipped:
        say(f"\nnot run (views missing): {', '.join(skipped)}")

    # Parity: the fast path must reproduce the API path exactly when given the same settings.
    api, fast = results[0], lab.run(replace(listed[0], name="api_fast", exact_api=False), keep=True, timeline=False)
    same = sum(a["rules"] == b["rules"] for a, b in zip(api["rows"], fast["rows"]))
    diffs = [float(np.max(np.abs(np.asarray(api["kept"][k]["fused"][key]) - np.asarray(fast["kept"][k]["fused"][key]))))
             for k in api["kept"] for key in FUSED_KEYS if k in fast["kept"]]
    say(f"\nparity check (fast scorer vs API reconstruct): same rules on {same}/{len(api['rows'])} videos, "
        f"max fused difference {max(diffs, default=0):.2e}")

    complete = [r for r in results if not r["approach"].oracle and r["coverage"] == len(lab.data)
                and r["approach"].group in "ABC"]
    best = max(complete or results[:1], key=lambda r: (r["metrics"]["correct"], r["metrics"]["f1"] or 0,
                                                       r["metrics"]["aspect_hits"], r["timeline"]["macro_f1"] or 0))
    best_approach = best["approach"]

    # Probe quality table.
    say.section("PROBE QUALITY  (AUC of the main question per view on annotated frames; 0.5 = chance, 1.0 = perfect)")
    columns = [name for name in VIEWS if present[name]] + ["cv", "fused:api_default", "fused:calibrated"]
    names = {"fused:api_default": "F:api", "fused:calibrated": "F:cal"}
    say(f"{'key':20s} {'pos/neg':>10s} " + " ".join(f"{names.get(c, c)[:9]:>9s}" for c in columns))
    keys = sorted({v["key"] for v in quality.values()})
    for key in keys:
        cells, counts = [], ""
        for column in columns:
            entry = quality.get(f"{column}|{key}")
            if entry is None and column == "cv":
                entry = next((v for v in quality.values() if v["source"] == "cv" and v["key"] == key), None)
            if entry and not counts and column in VIEWS:
                counts = f"{entry['positives']}/{entry['negatives']}"
            cells.append(f"{num(entry['auc'], 3) if entry else '':>9s}")
        say(f"{key:20s} {counts:>10s} " + " ".join(cells))
    say("\nExtra and negated questions (AUC; compare with the main question of the same view):")
    for key in keys:
        extras = sorted((v for v in quality.values() if v["key"] == key and v["source"] in VIEWS and v["qid"] != key),
                        key=lambda v: -(v["auc"] if not math.isnan(v["auc"]) else 0))
        for v in extras[:6]:
            main = quality.get(f"{v['source']}|{key}")
            say(f"  {key:20s} {v['source']:10s} {v['qid']:28s} AUC {num(v['auc'], 3)} "
                f"(main {num(main['auc'], 3) if main else '-'})")
    if "cv" in {v["source"] for v in quality.values()}:
        say("\nPose / motion signals:")
        for v in sorted((v for v in quality.values() if v["source"] == "cv"), key=lambda v: v["key"]):
            say(f"  {v['key']:20s} {v['qid']:18s} AUC {num(v['auc'], 3)}  balanced acc {pct(v['balanced_accuracy'], 0)}")

    # Best approach in detail.
    say.section(f"BEST: {best_approach.name}  ({best_approach.note})")
    for row in best["rows"]:
        error = f" dt={row['time_error']:.1f}s" if row["time_error"] is not None else ""
        say(f"  {'ok ' if row['correct'] else 'BAD'} {row['key']:6s} {row['expected']:13s} "
            f"{', '.join(r.split('-')[0] for r in row['rules']) or '-'}  type {row['aspects_hit']}/{row['aspects_total']}{error}")
    say(f"\nTimeline per key, {best_approach.name} ({best['timeline']['videos']} annotated videos):")
    timeline_table(say, best)
    say("\nTimeline per key, api_default:")
    timeline_table(say, results[0])
    say(f"\nRules, {best_approach.name}  (target: fired on its labelled videos / labelled videos; off: accuracy change if disabled)")
    rules = rule_table(say, lab, best)

    # GPU refinement on the best approach, then CPU tuning.
    refined = []
    if not args.report_only and args.followup_calls >= 0 and time.time() < lab.deadline:
        try:
            refine_phase(lab, best_approach)
        except KeyboardInterrupt:
            print("\nInterrupted; reporting what is cached.", flush=True)
    refined, calls = refined_results(lab, best_approach, {r["key"]: r for r in best["rows"]})
    if refined:
        say.section(f"GPU REFINEMENT on {best_approach.name}")
        say(f"  {calls}")
        for result in refined:
            m, b = result["metrics"], result["baseline"]
            say(f"  {result['approach'].name:40s} {m['correct']}/{m['videos']} correct (same videos without it: "
                f"{b['correct']}/{b['videos']}), FP {m['fp']} FN {m['fn']}, type {m['aspect_hits']}/{m['aspects']}")

    tuning = None
    if args.tune_minutes > 0 and len(lab.data) >= 10:
        say.section(f"TUNING  {best_approach.name}: offsets + timeline settings, {args.folds}-fold validation, "
                    f"<= {args.tune_minutes} min")
        tuner = Tuner(lab, best_approach, time.time() + 60 * args.tune_minutes)
        tuning = tuner.validate(args.folds, args.tune_rounds)
        say(f"  in-sample {num(tuning.get('in_sample'), 0)}/{tuning['videos']}, held-out "
            f"{num(tuning.get('held_out'), 0)}/{tuning.get('held_out_videos', 0)} "
            f"({'complete' if tuning['complete'] else tuning.get('stopped', 'incomplete')}), "
            f"{tuning['evaluations']} settings evaluated")
        say(f"  chosen: {json.dumps(tuning.get('state', {}))}")
        if "state" in tuning:
            tuned = lab.run(tuner.approach(tuning["state"]))
            results.append(tuned)
            approach_table(say, [best, tuned], costs)

    # Files.
    say.section("FILES")
    selected = {"api_default": results[0]["approach"], best_approach.name: best_approach}
    if tuning and "state" in tuning:
        selected[results[-1]["approach"].name] = results[-1]["approach"]
    refine_records = lab.cache / "refine" / best_approach.name
    for name, approach in selected.items():
        result = lab.run(approach, keep=True)
        for row in result["rows"]:
            data = lab.data[row["key"]]
            path = refine_records / f"{row['key']}.json"
            refined_record = read_json(path) if name == best_approach.name and path.exists() else None
            text = timeline_file(lab, approach, data, result["kept"][row["key"]], row, refined_record)
            write_text(lab.reports / "timelines" / name / f"{row['key']}.txt", text)
    matrix = ["video   expected       " + " ".join(f"{r['approach'].name[:14]:>14s}" for r in results)]
    for item in lab.items:
        cells = []
        for result in results:
            row = next((r for r in result["rows"] if r["key"] == item.key), None)
            cell = "-" if row is None else ("ok " if row["correct"] else "BAD ") + (
                ",".join(rule.split("-")[0] for rule in row["rules"]) or "-")
            cells.append(f"{cell[:14]:>14s}")
        matrix.append(f"{item.key:7s} {item.expected:14s} " + " ".join(cells))
    write_text(lab.reports / "verdict_matrix.txt", "\n".join(matrix) + "\n")
    quality_lines = [f"{'source':22s} {'question':30s} {'key':20s} {'AUC':>6s} {'BA':>5s} {'pos':>5s} {'neg':>5s} "
                     f"{'videos':>6s} {'bias':>6s} {'sep':>5s}  text"]
    texts = {(view.name, q.qid): q.text for view in VIEWS.values() for q in view.questions}
    for v in sorted(quality.values(), key=lambda v: (v["key"], v["source"], v["qid"])):
        quality_lines.append(f"{v['source']:22s} {v['qid']:30s} {v['key']:20s} {num(v['auc'], 3):>6s} "
                             f"{pct(v['balanced_accuracy'], 0):>5s} {v['positives']:>5d} {v['negatives']:>5d} "
                             f"{v['videos']:>6d} {num(v['bias'], 2):>6s} {num(v['separation'], 2):>5s}  "
                             f"{texts.get((v['source'], v['qid']), '')}")
    write_text(lab.reports / "probe_quality.txt", "\n".join(quality_lines) + "\n")
    serial = []
    for result in results + refined:
        a = result["approach"]
        serial.append({"approach": {k: v for k, v in vars(a).items()}, "metrics": result["metrics"],
                       "timeline": result["timeline"], "coverage": result["coverage"],
                       "rows": [{k: v for k, v in row.items()} for row in result["rows"]]})
    write_json(lab.reports / "results.json", json.loads(json.dumps({
        "model": lab.model_name(), "best": best_approach.name, "approaches": serial, "probe_quality": quality,
        "rules": rules, "tuning": tuning, "costs": costs, "calibration": {f"{v}|{q}": b for (v, q), b in lab.bias.items()},
        "failures": lab.failures,
    }, default=lambda o: list(o) if isinstance(o, (set, tuple)) else str(o))))
    say(f"  {lab.reports / 'SUMMARY.txt'}        everything printed above")
    say(f"  {lab.reports / 'timelines'}          per-video timeline strips for {', '.join(selected)}")
    say(f"  {lab.reports / 'verdict_matrix.txt'}  every approach x every video")
    say(f"  {lab.reports / 'probe_quality.txt'}   every question in every view")
    say(f"  {lab.reports / 'results.json'}        all numbers")
    write_text(lab.reports / "SUMMARY.txt", "\n".join(say.lines) + "\n")
    archive = bundle(lab)
    print(f"\nSend this file back: {archive}  ({archive.stat().st_size / 2**20:.1f} MB)", flush=True)


def arguments():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model", default=os.environ.get("MODEL") or "32b",
                        help="alias (2b, 4b, 32b) or Hugging Face id (default: $MODEL or 32b)")
    parser.add_argument("--model-path", type=Path, default=os.environ.get("MODEL_PATH") or None,
                        help="local checkpoint folder with config.json and safetensors (default: $MODEL_PATH)")
    parser.add_argument("--device", default=os.environ.get("MODEL_DEVICE") or None,
                        help="cuda, mps or cpu (default: $MODEL_DEVICE, else best available)")
    parser.add_argument("--quantization", default=os.environ.get("MODEL_QUANTIZATION") or None,
                        help="none or 4bit (default: $MODEL_QUANTIZATION, else 4bit for 32B on CUDA)")
    parser.add_argument("--allow-download", action="store_true", help="let transformers download the model")
    parser.add_argument("--pose-device", help="device for Keypoint R-CNN (default: the model device)")
    parser.add_argument("--videos-dir", type=Path, default=BACKEND.parent / "data" / "open" / "videos")
    parser.add_argument("--labels", type=Path, default=EVAL / "expected_api_verdicts.json")
    parser.add_argument("--videos", nargs="*", help="only these videos, e.g. Х-15 X-1")
    parser.add_argument("--quick", action="store_true", help=f"smoke test on {', '.join(QUICK)}")
    parser.add_argument("--out", type=Path, help="output folder (default var/experiments/<model>)")
    parser.add_argument("--skip", nargs="*", default=[], help=f"phases to skip: {', '.join(GPU_PHASES)}")
    parser.add_argument("--hours", type=float, default=10.0, help="GPU time budget; the rest is reported as missing")
    parser.add_argument("--report-only", action="store_true", help="score the caches without loading a model")
    parser.add_argument("--probe-batch", type=int, default=24, help="questions per forward pass")
    parser.add_argument("--followup-calls", type=int, default=4, help="JSON follow-ups per video (-1: no refinement)")
    parser.add_argument("--followup-frames", type=int, default=8)
    parser.add_argument("--call-seconds", type=float, default=60.0, help="generation time limit per JSON call")
    parser.add_argument("--structured-tokens", type=int, default=768, help="output token limit per JSON call")
    parser.add_argument("--tune-minutes", type=float, default=30.0, help="CPU minutes for tuning (0 = skip)")
    parser.add_argument("--tune-rounds", type=int, default=2)
    parser.add_argument("--folds", type=int, default=7)
    args = parser.parse_args()
    if args.quantization not in (None, "none", "4bit"):
        parser.error(f"quantization must be none or 4bit, got {args.quantization!r}")
    if args.model_path is not None and not args.report_only and not (args.model_path / "config.json").exists():
        parser.error(f"no config.json in model path {args.model_path}")
    if args.device is None:
        args.device = "cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu"
    if args.quantization is None:
        # 32B BF16 weights (~64 GB) do not fit a 48 GB card.
        large = "32b" in f"{args.model} {args.model_path or ''}".lower()
        args.quantization = "4bit" if args.device.startswith("cuda") and large else "none"
    args.pose_device = args.pose_device or args.device
    if args.out is None:
        tag = MODEL_IDS.get(args.model, args.model).split("/")[-1]
        if args.model_path and not re.fullmatch(r"[0-9a-f]{40}", args.model_path.name):
            tag = args.model_path.name  # a Hugging Face snapshots/<hash> folder keeps the alias name
        args.out = BACKEND / "var" / "experiments" / re.sub(r"[^A-Za-z0-9_.-]", "_", f"{tag}-{args.quantization}")
    unknown = set(args.skip) - set(GPU_PHASES)
    if unknown:
        parser.error(f"unknown phases in --skip: {', '.join(sorted(unknown))}")
    return args


def main() -> None:
    with contextlib.suppress(Exception):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    args = arguments()
    args.out.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(args.out / "run.log", encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logging.basicConfig(level=logging.INFO, handlers=[handler])
    with contextlib.suppress(Exception):
        import transformers
        transformers.logging.set_verbosity_error()
    lab = Lab(args)
    started = time.time()
    write_json(args.out / "manifest.json", environment(args) | {"started": time.strftime("%Y-%m-%d %H:%M:%S"),
                                                                "videos": [i.label for i in lab.items]})
    total = sum(lab.duration(item) for item in lab.items)
    print(f"{len(lab.items)} videos, {total:.0f}s of video -> {args.out}", flush=True)
    print(f"model {args.model_path or args.model} on {args.device} ({args.quantization}), pose on {args.pose_device}",
          flush=True)
    lab.run_phases(list(CPU_PHASES))
    if not args.report_only:
        phases = [phase for phase in GPU_PHASES if phase not in args.skip]
        todo = {phase: sum(not lab.done(phase, item) for item in lab.items) for phase in phases}
        print("GPU work left (videos per phase): " + ", ".join(f"{p} {n}" for p, n in todo.items()), flush=True)
        lab.deadline = started + 3600 * args.hours
        try:
            lab.run_phases(phases)
        except KeyboardInterrupt:
            print("\nInterrupted; analysing what is cached. Rerun the same command to continue.", flush=True)
            lab.deadline = -math.inf
    analyse(lab)
    print(f"Total time {clock(time.time() - started)}", flush=True)


if __name__ == "__main__":
    main()
