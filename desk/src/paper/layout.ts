import type { CardVM } from "../data/model";

export interface Block { layer: "typed" | "hand"; text: string; size: number; minSize: number; gapBefore: number; underline?: boolean; ink?: string }
export interface Line { layer: Block["layer"]; text: string; size: number; y: number; underline?: boolean; ink?: string }
export type Side = Line[];
export type Measure = (text: string, layer: Block["layer"], size: number) => number;
const LINE = 1.3;   // line height as a multiple of font size

export function seededRandom(seed: string): () => number {
  let h = 2166136261;
  for (const ch of seed) { h ^= ch.codePointAt(0)!; h = Math.imul(h, 16777619); }
  let s = h >>> 0;
  return () => { s = (s + 0x6d2b79f5) >>> 0; let t = s; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
}

function wrap(text: string, layer: Block["layer"], size: number, width: number, measure: Measure): string[] {
  const lines: string[] = []; let cur = "";
  const push = (w: string) => {            // break a too-wide word by characters (grapheme-safe)
    let part = "";
    for (const g of Array.from(new Intl.Segmenter().segment(w), s => s.segment)) {
      if (measure(part + g, layer, size) > width && part) { lines.push(part); part = g; } else part += g;
    }
    return part;
  };
  for (const word of text.split(/\s+/).filter(Boolean)) {
    const next = cur ? cur + " " + word : word;
    if (measure(next, layer, size) <= width) { cur = next; continue; }
    if (cur) lines.push(cur);
    cur = measure(word, layer, size) <= width ? word : push(word);
  }
  if (cur) lines.push(cur);
  return lines;
}

export function layoutSides(blocks: Block[], measure: Measure, box: { width: number; height: number }): Side[] {
  const sides: Side[] = [[]]; let y = 0;
  for (const blk of blocks) {
    const room = box.height - y - blk.gapBefore;
    // shrink (in 0.5 steps) until the whole block fits in the room left, but not below minSize
    let size = blk.size;
    while (size - 0.5 >= blk.minSize && wrap(blk.text, blk.layer, size, box.width, measure).length * size * LINE > room) size -= 0.5;
    const lines = wrap(blk.text, blk.layer, size, box.width, measure);
    y += blk.gapBefore;
    for (const text of lines) {
      if (y + size * LINE > box.height && sides[sides.length - 1].length) { sides.push([]); y = 0; }
      y += size * LINE;
      sides[sides.length - 1].push({ layer: blk.layer, text, size, y, underline: blk.underline, ...(blk.ink ? { ink: blk.ink } : {}) });
    }
  }
  return sides;
}

/** Style B: typed record, annotated by hand in the project ink. Units are millimetres on the card. */
export function cardBlocks(c: CardVM, kind: "card" | "sticky"): Block[] {
  const blocks: Block[] = [
    { layer: "typed", text: c.id + " · " + c.where, size: 2.6, minSize: 2.2, gapBefore: 0 },
    { layer: kind === "sticky" ? "hand" : "typed", text: c.title, size: kind === "sticky" ? 7 : 5, minSize: kind === "sticky" ? 4.5 : 3.6, gapBefore: 2, underline: kind === "card" },
  ];
  if (c.started) blocks.push({ layer: "hand", text: "started " + new Date(c.started).toLocaleDateString("en-GB", { day: "numeric", month: "short" }), size: 4.4, minSize: 3.6, gapBefore: 1.5 });
  for (const n of c.notes) blocks.push({ layer: "hand", text: "— " + n.text, size: 4.4, minSize: 3.4, gapBefore: 1.2 });
  for (const m of c.commits) blocks.push({ layer: "typed", text: `${m.sha.slice(0, 7)}  ${m.subject}  +${m.ins} −${m.del}`, size: 2.6, minSize: 2.2, gapBefore: 0.6 });
  return blocks;
}

/** Footer for a card whose content runs past the side drawn on the desk (null when it all fits). */
export const overflowMark = (sides: number) => (sides <= 1 ? null : sides === 2 ? "↷ continued overleaf" : `↷ continued overleaf (${sides} sides)`);

/** Page number for page `index` (0-based) of a `total`-page task; one-page tasks carry no number. */
export const pageFooter = (index: number, total: number): string | null => (total <= 1 ? null : `${index + 1}/${total}`);
