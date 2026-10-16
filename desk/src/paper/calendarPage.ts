import type { DayTally } from "../data/model";
import { drawPaper, FONTS } from "./render";

/** What a day's calendar page says. Dates are whole days, so they are read in UTC to stay on the right day. */
export function calendarFace(d: DayTally) {
  const at = new Date(d.ymd + "T00:00:00Z"), f = (o: Intl.DateTimeFormatOptions) => at.toLocaleDateString("en-GB", { timeZone: "UTC", ...o });
  return { month: f({ month: "long" }).toUpperCase(), day: at.getUTCDate(), weekday: f({ weekday: "long" }),
    tally: d.commits ? `${d.commits} commit${d.commits === 1 ? "" : "s"}` : "no commits" };
}

const W = 130, H = 110;                                      // mm, the page size
/** A printed day page (month in red, a big date, the weekday) with the day's commits jotted in pencil underneath. */
export function renderCalendarPage(d: DayTally, px: number): HTMLCanvasElement {
  const c = document.createElement("canvas"); c.width = W * px; c.height = H * px; const g = c.getContext("2d")!, f = calendarFace(d);
  drawPaper(g, c.width, c.height, "#ece5d6", "cal:" + d.ymd); g.textAlign = "center";
  g.fillStyle = "#7a1414"; g.font = `${9 * px}px ${FONTS.typed}`; g.fillText(f.month, W / 2 * px, 27 * px);
  g.fillStyle = "#231a14"; g.font = `bold ${46 * px}px Georgia, serif`; g.fillText(String(f.day), W / 2 * px, 70 * px);
  g.font = `${9 * px}px ${FONTS.hand}`; g.fillText(f.weekday, W / 2 * px, 86 * px);
  g.globalAlpha = 0.75; g.fillStyle = "#4a4540"; g.font = `${7 * px}px ${FONTS.hand}`; g.fillText(f.tally, W / 2 * px, 101 * px);
  return c;
}
