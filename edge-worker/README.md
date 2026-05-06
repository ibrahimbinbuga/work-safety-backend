# Edge worker (Node on your PC → Render API)

Render cannot open `100.x` Tailscale URLs. This process runs **where your phone stream is reachable** (your laptop on Tailscale), then **POSTs** violations to the hosted API.

## 1. Render (backend)

1. In the Render dashboard → your Web Service → **Environment**:
   - Add `WORKER_API_KEY` = a long random string (e.g. `openssl rand -hex 32`).
2. Redeploy so `POST /api/worker/violations` is live.

## 2. Database

- Note the **camera `id`** that should receive violations (same company as production). Put it in `CAMERA_ID`.

## 3. On your PC

```bash
cd edge-worker
copy .env.example .env
# edit .env: RENDER_API_URL, WORKER_API_KEY (match Render), CAMERA_ID, MJPEG_STREAM_URL

npm install
npm start
```

- `MJPEG_STREAM_URL` = full URL including `http://user:pass@100.86.37.92:8081/video`.
- Optional: `DEMO_VIOLATION_INTERVAL_SEC=60` to verify DB + notifications until real AI is wired.

## 4. Wire real detection

In `worker.mjs`, inside the `for await (const jpeg …)` loop, run your model on `jpeg` (Buffer) and call:

```js
await postViolations(['fallen'], workerId, snapshotPath);
```

Allowed types match the API consumer: `head`, `vest`, `person`, `sitting`, `fallen`, `standing`, `fall`.

## 5. Live dashboard video

The in-app MJPEG route still expects a **process on the same host** as OpenCV. On Render that won’t read Tailscale. Options:

- Show **snapshots** uploaded from the worker (future `POST /api/worker/snapshot`), or  
- Open the **phone URL** only on LAN in the browser (not via Render), or  
- Run a **relay** (advanced).

For many teams, **violations + timelines on Render** plus **local preview** is enough for v1.
