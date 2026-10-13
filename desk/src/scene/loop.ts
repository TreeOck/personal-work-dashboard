/** Render frames only while something is moving; then one final frame, then stop (idle desk = 0 renders). */
export function createLoop(render: () => void, busy: () => boolean) {
  let running = false;
  const frame = () => { const more = busy(); render(); if (more) requestAnimationFrame(frame); else running = false; };
  return { kick() { if (!running) { running = true; requestAnimationFrame(frame); } } };
}
