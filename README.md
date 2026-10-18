# datathon_26_xin_chao

## Repository layout

```text
backend/   Python backend application and uv project files.
frontend/  React frontend application.
data/      Dataset videos, labels, and the original archive.
docs/      Competition case documentation.
research/  Reference papers.
```

## Requirements

- Backend: Python 3.14.8 and uv 0.13.1.
- Frontend: Bun 1.4.3, React and React DOM 19.3.1, TypeScript 6.0.3, and Tailwind CSS 4.3.3.

## Run

For Windows with Qwen3-VL-32B on an RTX A6000, see [WINDOWS_A6000.md](WINDOWS_A6000.md).
Dataset rule coverage and API accuracy scoring are described in [DATASET_RULES.md](backend/eval/DATASET_RULES.md).

### Backend

```sh
cd backend
uv sync --locked
uv run --locked backend
```

### Frontend

```sh
cd frontend
bun install --frozen-lockfile
bun run dev
```
