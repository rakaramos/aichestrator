// usage: node cdp-heap-firebase-token.mjs <wsUrl> <outFile> -> writes the newest Firebase ID token found in the JS heap
// to <outFile> (mode 600) and prints only uid and expiry, never the token.
import { writeFileSync } from "node:fs";
const [ws, outFile] = process.argv.slice(2);
if (!outFile) { console.error("usage: <wsUrl> <outFile>"); process.exit(1); }
const sock = new WebSocket(ws);
let buf = "";
sock.onopen = () => { sock.send(JSON.stringify({ id: 1, method: "HeapProfiler.enable" })); sock.send(JSON.stringify({ id: 2, method: "HeapProfiler.takeHeapSnapshot", params: { reportProgress: false } })); };
sock.onmessage = (m) => {
  const d = JSON.parse(m.data);
  if (d.method === "HeapProfiler.addHeapSnapshotChunk") buf += d.params.chunk;
  if (d.id === 2) {
    const found = new Set(buf.match(/eyJhbGciOiJSUzI1NiIs[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+/g) ?? []);
    const out = [];
    for (const t of found) {
      try { const c = JSON.parse(Buffer.from(t.split(".")[1], "base64url")); if (String(c.iss).includes("securetoken")) out.push({ tok: t, uid: c.user_id, exp: c.exp, provider: c.firebase?.sign_in_provider }); } catch {}
    }
    out.sort((a, b) => b.exp - a.exp);
    const best = out[0] ?? null;
    if (best) writeFileSync(outFile, JSON.stringify(best), { mode: 0o600 });
    console.log(JSON.stringify(best ? { uid: best.uid, exp: best.exp, provider: best.provider } : null)); sock.close(); process.exit(0);
  }
};
