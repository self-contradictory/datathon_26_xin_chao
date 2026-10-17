# Run on Windows with an RTX A6000

These commands use PowerShell and the Hugging Face version of
`Qwen/Qwen3-VL-32B-Instruct`. Replace the example project and model paths with
the paths on your PC.

The RTX A6000 has 48 GB of GPU memory. A 32B model's BF16 weights alone need
roughly 64 GB, so use the optional 4-bit loader below. Inference also needs
memory for images, activations, and the KV cache. Close any other application
that has loaded the model onto the GPU before starting this backend.

## Copy the current code

Copy the current `steg-implementation` folder, including its uncommitted
changes. A fresh clone of `main` does not contain the current implementation.
Include `backend/src`, `backend/eval`, `backend/pyproject.toml`,
`backend/uv.lock`, `frontend`, and `data/open/videos`.

Exclude the Mac's `backend/.venv`, `frontend/node_modules`, and `__pycache__`
directories. They need to be recreated on Windows. Existing `backend/var`
results are optional. The commands below set the model path and test API key
in the terminal, so you do not need to copy the Mac's `.env`.

The model directory should contain `config.json`, all of the model's
`.safetensors` shards and their index, and its processor/tokenizer files.
If it is in the Hugging Face cache, use the actual `snapshots/<revision>`
directory as the model path, not the parent `models--Qwen--...` directory.
GGUF files for Ollama or LM Studio cannot be loaded by this code.

## Install uv and Python packages

Install uv if it is missing:

```powershell
winget install --id astral-sh.uv -e
```

If WinGet is unavailable, the official installer is:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Open a new PowerShell window after installation. Then run:

```powershell
cd "D:\projects\steg-implementation\backend"
uv --version
nvidia-smi
$env:PYTHONUTF8 = "1"

uv python install 3.14.8
uv sync --locked --python 3.14.8

# Windows PyPI builds are CPU-only. Select a CUDA build for the installed driver.
uv pip install --torch-backend=auto --reinstall-package torch --reinstall-package torchvision "torch==2.14.1" "torchvision==0.29.1"
uv pip install accelerate bitsandbytes

.\.venv\Scripts\python.exe -c "import torch; print('Torch:', torch.__version__); print('CUDA runtime:', torch.version.cuda); print('CUDA available:', torch.cuda.is_available()); assert torch.cuda.is_available(), 'CUDA is unavailable'; print('GPU:', torch.cuda.get_device_name(0)); print('VRAM GiB:', round(torch.cuda.get_device_properties(0).total_memory / 1024**3, 1))"
```

Continue only when this prints `CUDA available: True` and the A6000's name.
If `nvidia-smi` fails, install or repair the NVIDIA driver first. If automatic
selection cannot find a compatible build, use the
[PyTorch installation selector](https://pytorch.org/get-started/locally/) for
Windows, Pip, and the CUDA version supported by the driver. Install that build
into this `.venv` using `uv pip install`.

Keep Python 3.14.8 for this project, as specified in its lockfile. These steps
use the environment's Python executable directly, so PowerShell does not need
to activate a script. You do not need to install MLX or FlashAttention.

The CUDA packages and quantization dependencies are installed locally after
the locked sync. Run the direct Python commands below afterward. Running
`uv sync`, `uv run backend`, or `bun run start` can sync away those extra
packages or restore the CPU build. If you sync again, repeat the two `uv pip
install` commands above.

## Test the model before a full video

From the same backend directory:

```powershell
$modelPath = "D:\models\Qwen3-VL-32B-Instruct"
Test-Path "$modelPath\config.json"

.\.venv\Scripts\python.exe -B eval\smoke_vlm.py --model 32b --model-path "$modelPath" --device cuda --quantization 4bit --video "..\data\open\videos\Х-15.mov"
```

`Test-Path` should print `True`. The smoke test loads the local weights, runs
the yes/no probe, generates a JSON description of the first frame, and checks
the video generation path with a pair of repeated frames. A successful run
ends with JSON containing `"status": "ok"` and the peak allocated GPU memory.
This verifies inference, not detection accuracy or temporal understanding.
The loader uses `local_files_only=True`; missing model files cause an error
instead of a fresh download.

The `Х` in `Х-15.mov` is Cyrillic. Copy the name exactly or use another video's
actual path.

## Run and score the pipeline

Start with one video and the question baseline:

```powershell
.\.venv\Scripts\python.exe -B eval\compare_windows.py --model 32b --model-path "$modelPath" --device cuda --quantization 4bit --videos "Х-15" --approaches questions
```

Then compare all four existing approaches on the two default test videos:

```powershell
.\.venv\Scripts\python.exe -B eval\compare_windows.py --model 32b --model-path "$modelPath" --device cuda --quantization 4bit --videos "Х-15" "Х-3"
.\.venv\Scripts\python.exe -B eval\score_windows.py
```

Results are saved under `backend/var/compare_windows/32b-4bit/`, with tracks,
the evidence graph, rule reports, and runtime per approach. Finished runs are
skipped. To force a fresh run after changing weights or prompts, add a new
output path such as `--out var\compare_windows_retry`. Score that path with
`eval\score_windows.py var\compare_windows_retry`.

The benchmark command sets its own model options; it does not read the API's
`MODEL_*` settings. Do not run the benchmark and API at the same time on one
GPU, since each process loads its own model.

## Start the backend API

After the benchmark process exits, run from the backend directory:

```powershell
$env:PYTHONUTF8 = "1"
$env:MODEL = "32b"
$env:MODEL_PATH = "D:\models\Qwen3-VL-32B-Instruct"
$env:MODEL_DEVICE = "cuda"
$env:MODEL_QUANTIZATION = "4bit"
$env:JOB_WORKERS = "1"
$env:API_KEYS = '{"windows-test":"local-test-key"}'

.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Wait for `Application startup complete`. The API documentation is at
<http://127.0.0.1:8000/docs>. To upload a video without the frontend, open a
second PowerShell window and run this from the backend directory:

```powershell
curl.exe -X POST "http://127.0.0.1:8000/api/v1/analyze" -H "X-API-Key: local-test-key" -F "file=@../data/open/videos/Х-15.mov"
```

The response contains a `job_id`. Substitute it below and repeat the GET
until the job finishes:

```powershell
curl.exe "http://127.0.0.1:8000/api/v1/jobs/PASTE_JOB_ID_HERE" -H "X-API-Key: local-test-key"
```

The key above is an example for testing on localhost.

## Start the frontend

Install Bun if it is missing:

```powershell
powershell -c "irm bun.sh/install.ps1 | iex"
```

In a new PowerShell window, with the backend still running:

```powershell
cd "D:\projects\steg-implementation\frontend"
bun --version
bun install --frozen-lockfile
$env:API_URL = "http://127.0.0.1:8000"
$env:API_KEY = "local-test-key"
bun run dev
```

Open <http://127.0.0.1:3000> and upload a short video. Use the normal live
upload flow; `?demo` displays existing demo fixtures.

## Code changes included

- `backend/src/backend/reconstruction/vlm.py` adds the `32b` alias and optional
  NF4 loading with bitsandbytes. It places the quantized model directly on the
  selected CUDA GPU. The output head stays unquantized because the question
  probe reads its weights directly.
- `backend/src/backend/config.py` and `dependencies.py` expose
  `MODEL_QUANTIZATION=4bit` to the API.
- `backend/eval/compare_windows.py` accepts `--device` and `--quantization` and
  saves quantized runs separately from the BF16 runs.
- `backend/eval/smoke_vlm.py` checks the model without running the full pipeline.

Quantization defaults to `none`, so the existing Mac configuration continues
to use the previous loading behavior.

The Python code and loader configuration were checked on the Mac. Windows
installation and CUDA inference must be verified on the A6000 with the smoke
test above.

References: [uv installation](https://docs.astral.sh/uv/getting-started/installation/),
[uv CUDA selection](https://docs.astral.sh/uv/guides/integration/pytorch/#automatic-backend-selection),
[bitsandbytes Windows support](https://huggingface.co/docs/bitsandbytes/main/en/installation),
[Transformers quantization](https://huggingface.co/docs/transformers/main/en/quantization/bitsandbytes),
[RTX A6000 specifications](https://www.nvidia.com/en-us/products/workstations/rtx-a6000/),
[Bun installation](https://bun.com/docs/installation).
