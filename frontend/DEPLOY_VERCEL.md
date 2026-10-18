# Deploy the frontend on Vercel

Vercel serves the React frontend and proxies `/api/v1/analyze` and
`/api/v1/jobs/{id}` to the Windows GPU API over its HTTPS ngrok URL. The
API key is added by Vercel's CDN routing configuration and is never compiled
into the browser bundle. Inference continues on Windows.

## Project settings

Import `self-contradictory/datathon_26_xin_chao` from the `main` branch.

| Setting            | Value                           |
| ------------------ | ------------------------------- |
| Project name       | `datathon-26-xin-chao-frontend` |
| Root directory     | `frontend`                      |
| Application preset | Other                           |
| Install command    | `bun install --frozen-lockfile` |
| Build command      | `bun run build`                 |
| Output directory   | `dist`                          |

The commands and output directory are also specified in `vercel.json`.

Add these environment variables for Production and Preview:

| Variable  | Value                                                                 |
| --------- | --------------------------------------------------------------------- |
| `API_URL` | The Windows ngrok HTTPS origin, without `/api/v1` or a trailing slash |
| `API_KEY` | The same `xc_...` key configured in Windows `API_KEYS`                |

Leave `BUN_PUBLIC_API_URL`, `BUN_PUBLIC_API_KEY` and
`BUN_PUBLIC_DATA_SOURCE` unset. Values with the `BUN_PUBLIC_` prefix are
intended for browser code; keep the API key in `API_KEY`.

Click Deploy. Keep both the Windows Python API and ngrok processes running.
The public frontend lets visitors submit videos to the GPU API. Use
deployment protection if the deployment is for invited testers only.

## Verify the deployed connection

Replace the example deployment URL:

```sh
curl -i --max-time 15 https://YOUR-PROJECT.vercel.app/api/v1/jobs/connection-check
```

An HTTP 404 with JSON `{"detail":"Job connection-check not found"}`
confirms that Vercel reached the API with the matching key. HTTP 401 means
the API key differs. HTML from ngrok or an upstream connection error means
the tunnel needs attention. Upload one video in the deployed frontend to
verify the full upload path and wait for the Windows job result.

The CDN route proxies uploads directly to the backend; there is no Vercel
Function handling the video body. This avoids the 4.5 MB Function payload
limit. External proxy requests still have a 120-second timeout, so the
backend returns a job ID after receiving the upload and inference runs
asynchronously. Hosting and ngrok transfer quotas still apply.

If the ngrok origin or API key changes, update the corresponding Vercel
environment variable and redeploy. A frontend deployment does not make the
Windows computer stay awake or restart its API automatically.

References:

- [Vercel route destinations and request-header transforms](https://vercel.com/docs/project-configuration/vercel-json#using-environment-variables-in-routes)
- [Vercel external rewrites](https://vercel.com/docs/rewrites)
- [Vercel Function payload limits](https://vercel.com/docs/functions/limitations)
