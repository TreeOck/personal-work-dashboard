import type { CardVM } from "../data/model";
import { cardBlocks, layoutSides, pageFooter, type Side } from "./layout";
import { canvasMeasure, drawPaper, drawSide } from "./render";

export type PaperKind = "card" | "sticky";
export const PAPER: Record<PaperKind, { wMm: number; hMm: number; base: string }> = {
  card: { wMm: 148, hMm: 105, base: "#f1ebde" },
  sticky: { wMm: 76, hMm: 76, base: "#f4d675" },
};

/** Lay out a card's text into pages (one card each), keeping a 6 mm strip at the bottom free for the footer. */
export const cardPages = (c: CardVM, kind: PaperKind): Side[] =>
  layoutSides(cardBlocks(c, kind), canvasMeasure(), { width: PAPER[kind].wMm - 12, height: PAPER[kind].hMm - 18 });

/** Draw one page (one physical, single-sided card) at any resolution; an index beyond the content is plain paper. */
export function renderPage(c: CardVM, kind: PaperKind, pages: Side[], index: number, pxPerMm: number): HTMLCanvasElement {
  const { wMm, hMm, base } = PAPER[kind];
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(wMm * pxPerMm); canvas.height = Math.round(hMm * pxPerMm);
  const ctx = canvas.getContext("2d")!;
  drawPaper(ctx, canvas.width, canvas.height, base, c.id + ":" + index);
  if (index >= pages.length) return canvas;
  drawSide(ctx, pages[index], c.ink.hex, c.id + ":" + index, pxPerMm);
  const footer = pageFooter(index, pages.length);
  if (footer) {
    ctx.save(); ctx.fillStyle = c.ink.hex; ctx.globalAlpha = 0.9; ctx.font = `${4.2 * 1.25 * pxPerMm}px 'Caveat'`; ctx.textAlign = "right";
    ctx.fillText(footer, (wMm - 5) * pxPerMm, (hMm - 4) * pxPerMm); ctx.restore();
  }
  return canvas;
}
