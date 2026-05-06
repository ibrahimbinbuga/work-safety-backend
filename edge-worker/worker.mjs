/**
 * Edge worker: runs on your PC (with Tailscale).
 * 1) Optionally reads MJPEG over HTTP (same as Python HttpMjpegCapture).
 * 2) POSTs violations to Render: POST /api/worker/violations
 *
 * Setup: copy .env.example → .env, npm install, npm start
 */

import "dotenv/config";

const RENDER_API_URL = (process.env.RENDER_API_URL || "").replace(/\/$/, "");
const WORKER_API_KEY = process.env.WORKER_API_KEY || "";
const CAMERA_ID = Number(process.env.CAMERA_ID || "0");
const MJPEG_STREAM_URL = process.env.MJPEG_STREAM_URL || "";
const DEMO_INTERVAL = Number(process.env.DEMO_VIOLATION_INTERVAL_SEC || "0");

const dryRun = process.argv.includes("--dry-run");

function hdr() {
  return {
    "Content-Type": "application/json",
    "X-Worker-Key": WORKER_API_KEY,
  };
}

async function healthCheck() {
  const r = await fetch(`${RENDER_API_URL}/api/worker/health`, { headers: hdr() });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(`health ${r.status}: ${JSON.stringify(j)}`);
  return j;
}

/** POST one batch of violations (same shape as on-prem camera_runner queue). */
export async function postViolations(violations, workerId = 0, snapshotPath = null) {
  const body = {
    camera_id: CAMERA_ID,
    violations,
    worker_id: workerId,
    snapshot_path: snapshotPath,
  };
  if (dryRun) {
    console.log("[dry-run] would POST", body);
    return { status: "dry-run" };
  }
  const r = await fetch(`${RENDER_API_URL}/api/worker/violations`, {
    method: "POST",
    headers: hdr(),
    body: JSON.stringify(body),
  });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(`violations ${r.status}: ${JSON.stringify(j)}`);
  return j;
}

/** MJPEG over HTTP: accumulate buffer, extract JPEGs (0xFF 0xD8 … 0xFF 0xD9). */
async function* jpegFramesFromMjpegUrl(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`MJPEG fetch ${res.status}`);
  if (!res.body) throw new Error("No response body");
  const reader = res.body.getReader();
  let buf = Buffer.alloc(0);
  const SOI = Buffer.from([0xff, 0xd8]);
  const EOI = Buffer.from([0xff, 0xd9]);

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf = Buffer.concat([buf, Buffer.from(value)]);
    if (buf.length > 8 * 1024 * 1024) buf = buf.subarray(-4 * 1024 * 1024);

    while (true) {
      const start = buf.indexOf(SOI);
      if (start === -1) break;
      const end = buf.indexOf(EOI, start + 2);
      if (end === -1) {
        buf = buf.subarray(start);
        break;
      }
      const jpeg = buf.subarray(start, end + 2);
      buf = buf.subarray(end + 2);
      yield jpeg;
    }
  }
}

async function main() {
  if (!RENDER_API_URL || !WORKER_API_KEY) {
    console.error("Set RENDER_API_URL and WORKER_API_KEY in .env");
    process.exit(1);
  }
  if (!CAMERA_ID || CAMERA_ID < 1) {
    console.error("Set CAMERA_ID (database id of the camera)");
    process.exit(1);
  }

  console.log("[worker] Render:", RENDER_API_URL, "camera_id:", CAMERA_ID);

  await healthCheck();
  console.log("[worker] API key accepted (health ok)");

  if (DEMO_INTERVAL > 0) {
    console.log("[worker] DEMO: posting test violation every", DEMO_INTERVAL, "s (remove in production)");
    setInterval(() => {
      postViolations(["sitting"]).then((x) => console.log("[worker] demo post", x)).catch((e) => console.error(e));
    }, DEMO_INTERVAL * 1000);
  }

  if (MJPEG_STREAM_URL) {
    console.log("[worker] Streaming MJPEG from phone (Tailscale / LAN)…");
    (async () => {
      try {
        let n = 0;
        for await (const jpeg of jpegFramesFromMjpegUrl(MJPEG_STREAM_URL)) {
          n += 1;
          if (n % 300 === 1) {
            console.log("[worker] jpeg frames received:", n, "(~", (jpeg.length / 1024).toFixed(1), "KB last)");
          }
          // Plug your detector here: ONNX, call local Python, heuristic, etc.
          // await postViolations(['fallen']);
        }
      } catch (e) {
        console.error("[worker] MJPEG loop error:", e.message);
      }
    })();
  } else {
    console.log("[worker] No MJPEG_STREAM_URL — only health + optional DEMO interval.");
  }
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
