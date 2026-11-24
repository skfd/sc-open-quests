// Share-card render benchmark, local only (run.py). ?i=<case>&w=<width>; /noop is the baseline.
// Timed from outside: a Worker's own clock stands still while it computes.
import { initWasm, Resvg } from "@resvg/resvg-wasm";
import wasm from "@resvg/resvg-wasm/index_bg.wasm";
import ui from "./fonts/ui.ttf";
import cjk from "./fonts/cjk.ttf";

// name, and whether the CJK font is loaded
const CASES = [["Toronto", 0], ["Agincourt South-Malvern West and a Very Long Second Half", 0], ["Нижний Новгород", 0],
               ["القاهرة", 0], ["北京市 東京都", 1], ["北京市", 0]];
let ready;

export default {
  async fetch(request) {
    const url = new URL(request.url);
    if (url.pathname === "/noop") return new Response("ok");
    ready ||= initWasm(wasm);
    await ready;
    const [name, big] = CASES[Number(url.searchParams.get("i") || 0)];
    const rows = [0, 1, 2].map((k) => `<circle cx="90" cy="${350 + k * 80}" r="30" fill="#fff"/>` +
      `<text x="145" y="${362 + k * 80}" font-size="34" fill="#fff">quest type ${k + 1}</text>`).join("");
    const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" font-family="${big ? "SimHei" : "Segoe UI"}">` +
      `<rect width="1200" height="630" fill="#4141ba"/><text x="60" y="190" font-size="72" fill="#fff">${name}</text>${rows}</svg>`;
    const r = new Resvg(svg, {
      fitTo: { mode: "width", value: Number(url.searchParams.get("w") || 1200) },
      font: { fontBuffers: [new Uint8Array(ui), ...(big ? [new Uint8Array(cjk)] : [])], loadSystemFonts: false },
    });
    return new Response(r.render().asPng(), { headers: { "Content-Type": "image/png" } });
  },
};
