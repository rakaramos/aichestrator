// usage: node cdp-capture-bearer.mjs <wsUrl> <outFile> -> writes the first bearer token seen in an API request
// to <outFile> (mode 600) and prints only the request URL, never the token.
import { writeFileSync } from "node:fs";
const [ws, outFile] = process.argv.slice(2);
if (!outFile) { console.error("usage: <wsUrl> <outFile>"); process.exit(1); }
const sock = new WebSocket(ws);
let id = 0; const send = (method, params = {}) => sock.send(JSON.stringify({ id: ++id, method, params }));
const timer = setTimeout(() => { console.log("null"); process.exit(2); }, 40000);
sock.onopen = () => { send("Network.enable"); setTimeout(() => send("Page.reload"), 500); };
sock.onmessage = (m) => {
  const d = JSON.parse(m.data);
  if (d.method === "Network.requestWillBeSent" || d.method === "Network.requestWillBeSentExtraInfo") {
    const h = d.params.request?.headers ?? d.params.headers ?? {};
    const a = h.Authorization ?? h.authorization;
    if (a && a.startsWith("Bearer ")) { writeFileSync(outFile, JSON.stringify({ tok: a.slice(7) }), { mode: 0o600 }); console.log(JSON.stringify({ url: d.params.request?.url ?? "" })); clearTimeout(timer); sock.close(); process.exit(0); }
  }
};
