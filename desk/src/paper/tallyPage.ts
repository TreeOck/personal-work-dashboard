import type { DayTally } from "../data/model";
import { drawPaper, FONTS } from "./render";

const W = 100, H = 140, INK = "#2d2b29";
export function tallyLines(d: DayTally): string[] {
  if (!d.commits && !d.tasks && !d.todosDone) return [d.label, "a quiet day"];
  return [d.label, `commits  ${d.commits}`, `tasks  ${d.tasks}`, `to-dos done  ${d.todosDone}`, ...(d.first ? [`${d.first} → ${d.last}`] : [])];
}
/** A ruled pad page, handwritten in near-black ink; the date sits small in the corner. */
export function renderTallyPage(d: DayTally, px: number): HTMLCanvasElement {
  const c = document.createElement("canvas"); c.width = W * px; c.height = H * px; const g = c.getContext("2d")!;
  drawPaper(g, c.width, c.height, "#f6efe0", "pad:" + d.ymd);
  g.strokeStyle = "rgba(110,140,190,.45)"; g.lineWidth = Math.max(1, px * 0.15);
  for (let y = 24; y < H - 8; y += 9) { g.beginPath(); g.moveTo(6 * px, y * px); g.lineTo((W - 6) * px, y * px); g.stroke(); }
  g.fillStyle = INK; g.font = `${7 * px}px ${FONTS.hand}`;
  tallyLines(d).forEach((line, i) => g.fillText(line, 8 * px, (i === 0 ? 18 : 22 + i * 9) * px));
  g.globalAlpha = 0.6; g.font = `${3 * px}px ${FONTS.typed}`; g.textAlign = "right"; g.fillText(d.ymd, (W - 6) * px, (H - 5) * px);
  return c;
}
