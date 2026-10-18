#!/bin/bash
set -euo pipefail
backend_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec "$backend_dir/.venv/bin/python" -u -B "$backend_dir/eval/benchmark_semantics.py" "$@"
