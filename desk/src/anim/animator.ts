export const easeInOutCubic = (t: number) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);

interface Anim { start: number; duration: number; update: (p: number) => void; done?: () => void; ease: (t: number) => number }

/** Keyed tweens. Playing a key that is already running replaces it: callers capture their "from" values when they
 *  call play(), so a retarget starts from wherever the object is now (smooth under rapid input). */
export class Animator {
  private anims = new Map<string, Anim>();

  play(key: string, duration: number, update: (p: number) => void, now: number, opts: { done?: () => void; ease?: (t: number) => number } = {}) {
    if (duration <= 0) { this.anims.delete(key); update(1); opts.done?.(); return; }
    this.anims.set(key, { start: now, duration, update, done: opts.done, ease: opts.ease ?? easeInOutCubic });
  }

  step(now: number): boolean {
    for (const [key, a] of [...this.anims]) {
      const p = Math.min(1, Math.max(0, (now - a.start) / a.duration));
      a.update(a.ease(p));
      if (p >= 1) { this.anims.delete(key); a.done?.(); }
    }
    return this.anims.size > 0;
  }

  cancel(key: string) { this.anims.delete(key); }
  get busy() { return this.anims.size > 0; }
}
