import { seededRandom, type Side } from "./layout";

export const TYPED_INK = "#24201c";
export const FONTS = { typed: "'Special Elite'", hand: "'Caveat'" } as const;

export async function loadFonts(caveat: string, specialElite: string): Promise<void> {
  const faces = [new FontFace("Caveat", `url(${caveat})`), new FontFace("Special Elite", `url(${specialElite})`)];
  for (const f of faces) { await f.load(); document.fonts.add(f); }
}

/** Paper colour with faint fibres; drawn once per texture. */
export function drawPaper(ctx: CanvasRenderingContext2D, w: number, h: number, base: string, seed: string) {
  ctx.fillStyle = base; ctx.fillRect(0, 0, w, h);
  const r = seededRandom(seed + ":paper");
  for (let i = 0; i < (w * h) / 900; i++) { ctx.fillStyle = `rgba(120,100,70,${r() * 0.035})`; ctx.fillRect(r() * w, r() * h, 1.5, 1.5); }
}

/** Draw one side of a card. Units: layout is in mm, pxPerUnit converts to canvas pixels; (padX, padY) in mm. */
export function drawSide(ctx: CanvasRenderingContext2D, side: Side, ink: string, seed: string, pxPerUnit: number, padX = 6, padY = 6) {
  const rnd = seededRandom(seed);
  for (const l of side) {
    const px = l.size * pxPerUnit, x = padX * pxPerUnit, y = (padY + l.y) * pxPerUnit - l.size * 0.3 * pxPerUnit;
    ctx.save();
    if (l.layer === "hand") {
      const slant = (rnd() - 0.5) * 2 * 1.2 * Math.PI / 180, scale = 1 + (rnd() - 0.5) * 0.08;
      ctx.translate(x, y); ctx.rotate(slant); ctx.scale(scale, scale);
      ctx.globalAlpha = 0.82 + rnd() * 0.18; ctx.fillStyle = l.ink ?? ink;
      ctx.font = `${px * 1.25}px ${FONTS.hand}`;      // Caveat runs small; 1.25 matches typed x-height
      ctx.fillText(l.text, 0, 0);
      if (l.underline) { ctx.fillRect(0, px * 0.18, ctx.measureText(l.text).width, Math.max(1, px * 0.06)); }
    } else {
      ctx.fillStyle = TYPED_INK; ctx.globalAlpha = 0.9 + rnd() * 0.1; ctx.font = `${px}px ${FONTS.typed}`;
      ctx.fillText(l.text, x, y);
      if (l.underline) {                                   // B style: the pen underlines the typed title
        const w = ctx.measureText(l.text).width; ctx.globalAlpha = 0.85; ctx.fillStyle = l.ink ?? ink;
        ctx.beginPath(); ctx.moveTo(x, y + px * 0.25);
        for (let t = 0; t <= 1.0001; t += 0.1) ctx.lineTo(x + w * t, y + px * 0.25 + Math.sin(t * 6 + rnd()) * px * 0.04);
        ctx.lineWidth = Math.max(1, px * 0.07); ctx.strokeStyle = l.ink ?? ink; ctx.stroke();
      }
    }
    ctx.restore();
  }
}

/** Canvas-backed measure for layoutSides (uses the loaded fonts). */
export function canvasMeasure(): (text: string, layer: "typed" | "hand", size: number) => number {
  const ctx = document.createElement("canvas").getContext("2d")!;
  return (text, layer, size) => { ctx.font = `${layer === "hand" ? size * 1.25 : size}px ${FONTS[layer]}`; return ctx.measureText(text).width; };
}
