"""Submit every dataset video to the running API, resume jobs, and score verdicts."""
import argparse
import hashlib
import json
import os
import time
from pathlib import Path

import httpx

from score_api import DEFAULT_EXPECTED, DEFAULT_RESULTS, HERE, load_expected, score, write_json

DEFAULT_API_KEY = "xc_local-test-key"


def run_video(client: httpx.Client, video: Path, destination: Path, poll_seconds: float,
              retry_failed: bool = False) -> None:
    previous = json.loads(destination.read_text(encoding="utf-8-sig")) if destination.exists() else {}
    if previous.get("status") == "done" or previous.get("status") == "failed" and not retry_failed:
        print(f"Reuse {video.name}: {previous['status']} {previous.get('verdict')}", flush=True)
        return
    job_id = previous.get("job_id") if previous.get("status") != "failed" else None
    try:
        if not job_id:
            with video.open("rb") as stream:
                response = client.post("analyze", files={"file": (video.name, stream, "video/quicktime")})
            response.raise_for_status()
            job_id = response.json()["job_id"]
            write_json(destination, {"video": video.name, "job_id": job_id, "status": "processing"})
        while True:
            response = client.get(f"jobs/{job_id}")
            response.raise_for_status()
            job = response.json()
            if job.get("status") not in {"processing", "done", "failed"}:
                raise ValueError("API returned an unknown job status")
            if job["status"] != "processing":
                write_json(destination, job | {"video": video.name})
                print(f"Done {video.name}: {job['status']} {job.get('verdict')}", flush=True)
                return
            time.sleep(poll_seconds)
    except (httpx.HTTPError, ValueError, KeyError, OSError) as error:
        write_json(destination, {"video": video.name, "job_id": job_id,
                                 "status": "client_error", "verdict": None, "error": str(error)})
        print(f"Failed {video.name}: {error}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--videos-dir", type=Path, default=HERE.parent.parent / "data/open/videos")
    parser.add_argument("--videos", nargs="+", help="Optional video stems, for example Х-46")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000/api/v1")
    parser.add_argument("--api-key", default=os.environ.get("API_KEY", DEFAULT_API_KEY))
    parser.add_argument("--expected", type=Path, default=DEFAULT_EXPECTED)
    parser.add_argument("--out", type=Path, default=DEFAULT_RESULTS)
    parser.add_argument("--poll-seconds", type=float, default=5.0)
    parser.add_argument("--retry-failed", action="store_true")
    args = parser.parse_args()
    if args.poll_seconds <= 0:
        parser.error("--poll-seconds must be positive")
    expected = load_expected(args.expected)
    names = list(expected)
    if args.videos:
        wanted = {Path(name).stem for name in args.videos}
        names = [name for name in names if Path(name).stem in wanted]
        if {Path(name).stem for name in names} != wanted:
            parser.error("--videos includes a name absent from the label file")
    missing = [name for name in names if not (args.videos_dir / name).is_file()]
    if missing:
        parser.error("Missing dataset videos: " + ", ".join(missing))
    source = HERE.parent / "src/backend"
    fingerprint = hashlib.sha256()
    for path in sorted(path for path in source.rglob("*") if path.suffix in {".py", ".yaml"}):
        fingerprint.update(str(path.relative_to(source)).encode())
        fingerprint.update(path.read_bytes())
    manifest = {"api_url": args.base_url, "expected": expected,
                "source_sha256": fingerprint.hexdigest(), "videos_dir": str(args.videos_dir.resolve())}
    manifest_path = args.out / "manifest.json"
    if manifest_path.exists() and json.loads(manifest_path.read_text(encoding="utf-8")) != manifest:
        parser.error("This output belongs to different code/labels; use a fresh --out directory")
    write_json(manifest_path, manifest)
    with httpx.Client(base_url=args.base_url.rstrip("/") + "/",
                      headers={"X-API-Key": args.api_key}, timeout=300.0) as client:
        # An authenticated unknown job returns 404. A missing API or wrong key fails before uploads.
        check = client.get("jobs/batch-connection-check")
        if check.status_code != 404:
            check.raise_for_status()
            raise ValueError("Unexpected API response during connection check")
        for index, name in enumerate(names, 1):
            print(f"[{index}/{len(names)}] {name}", flush=True)
            run_video(client, args.videos_dir / name, args.out / f"{name}.json",
                      args.poll_seconds, args.retry_failed)
            score(args.out, expected)
    print("Results:", args.out.resolve())


if __name__ == "__main__":
    main()
