"""Write the tuned perception parameters to src/backend/perception/calibration.json for the API.

    .venv/bin/python -B eval/tuning/export_calibration.py tuning-regions2 --regions regions+regions2

Probe calibration (Otsu logit thresholds) comes from the cached probes, the rest from the chosen
tuning state. Module constants (LEFT_OPEN_SEC and the timeline confidences) are printed so the
code defaults can be updated to match.
"""
import argparse
import json

from backend.perception.settings import CALIBRATION
from calibrate import thresholds
from common import CACHE


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tuning")
    parser.add_argument("--regions", default="regions+regions2")
    parser.add_argument("--model", default="Qwen/Qwen3-VL-2B-Instruct")
    args = parser.parse_args()
    state = json.loads((CACHE / "results" / f"{args.tuning}.json").read_text(encoding="utf-8"))["state"]
    entry = {
        "base_bias": thresholds("base-full"),
        "region_bias": thresholds(args.regions),
        "offsets": {key.split(":", 1)[1]: value for key, value in state.items()
                    if key.startswith("offset:") and value},
        "dwell": {key.split(":", 1)[1]: value for key, value in state.items() if key.startswith("dwell:")},
        "source": f"{args.tuning} with region probes {args.regions}",
    }
    entries = json.loads(CALIBRATION.read_text(encoding="utf-8")) if CALIBRATION.exists() else {}
    entries[args.model] = entry
    CALIBRATION.write_text(json.dumps(entries, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {CALIBRATION}")
    for key in ("left_open_sec", "known_confidence", "event_confidence"):
        print(f"{key} = {state.get(key)}")


if __name__ == "__main__":
    main()
