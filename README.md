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
- The current frontend uses Vite 8.3.4 for development and production builds.
- Frontend deployment target: Vercel.

Use [Bun's installation instructions](https://bun.com/docs/installation) to install Bun. Update an existing standalone installation with `bun upgrade --stable`. For a Homebrew installation, use `brew update` and `brew upgrade bun`.

## Run

### Backend

```sh
cd backend
uv sync --locked
uv run --locked backend
```

### Frontend

From the repository root:

```sh
cd frontend
bun install --frozen-lockfile
bun run dev
```

Open [localhost:5173](http://localhost:5173), or the URL printed by Vite if that port is busy. Edit `frontend/src/App.tsx` to change the page. Tailwind CSS is imported in `frontend/src/index.css` and enabled through `@tailwindcss/vite` in `frontend/vite.config.ts`.

Run checks and preview a production build from `frontend/`:

```sh
bun run typecheck
bun run lint
bun run build
bun run preview
```

The build also runs TypeScript checks and writes static files to `frontend/dist/`. Preview serves those files at [localhost:4173](http://localhost:4173). Stop either server with Ctrl+C.

Keep `frontend/package.json` and `frontend/bun.lock` together when changing dependencies. Use `bun add <package>` for application dependencies or `bun add --dev <package>` for development tools. Dependency folders, build output, and local environment files stay out of Git.
