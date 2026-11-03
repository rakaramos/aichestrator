// usage: node cdp.mjs <wsUrl> <js expression (may return a promise)>
const [ws, expr] = process.argv.slice(2);
const sock = new WebSocket(ws);
sock.onopen = () => sock.send(JSON.stringify({ id: 1, method: "Runtime.evaluate", params: { expression: expr, awaitPromise: true, returnByValue: true } }));
sock.onmessage = (m) => { const d = JSON.parse(m.data); if (d.id === 1) { console.log(JSON.stringify(d.result?.result?.value ?? d.result ?? d.error)); sock.close(); } };
sock.onerror = (e) => { console.error("ws error", e.message); process.exit(1); };
