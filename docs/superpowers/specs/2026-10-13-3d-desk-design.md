# 3D Desk: Design Spec

**Date:** 2026-10-13
**Status:** Draft, awaiting review
**Scope:** A second, showpiece view of the tracker data: a photoreal 3D desk built with three.js. It sits alongside the existing `dashboard.html` and does not replace it.

---

## 1. Goal

A desk you enjoy looking at every day. The same commits, tasks and to-do items the dashboard shows appear as physical objects (index cards, sticky notes, a done tray, binders) on a realistic walnut desk. You read them by having the camera move in close, and you flip pages with real paper animation.

**Success criteria**
- It reads as a photograph of a real desk, not a cartoon. Specifically: physically based (PBR) materials, image-based lighting from a photographed room (HDRI), soft shadows and ambient occlusion.
- Every object maps to real data or a real control. The plant is the only pure decoration.
- No surface flickers (z-fighting) from any camera position.
- It opens offline from a single file, and stays current with no manual steps.

**Non-goals**
- Replacing the dashboard. Standup and report copy, search and filters stay there.
- Mobile-first layout. It must not break at narrow widths, but it isn't designed for phones.
- Editing anything other than to-do status. No text entry, notes or new tasks from the desk.

---

## 2. Decisions so far (from brainstorming)

| Topic | Decision |
|---|---|
| Purpose | Showpiece and daily joy; data extraction stays in the dashboard |
| Relationship to dashboard | Lives alongside it, as a separate `desk.html` built from the same data |
| Art direction | "Warm study": walnut, leather, brass, cream paper; photoreal |
| Lighting | Follows the real clock (IST): daylight → golden hour → lamp at night |
| Text style | Typed cards you annotate. Typed body in near-black typewriter face; handwritten notes, titles' underlines and remarks in the project's ink |
| Inks | Pilot Iroshizuku-inspired palette, one ink per project, stable once assigned |
| Objects | All 8: in-progress cards, to-do sticky notes, done tray, Day/Week/Month binders, flip calendar, notepad, pen cup (one pen per project), desk lamp |
| Editing | Drag a card into the tray marks it done (with undo); drag a sticky note onto the mat starts it. Only works when opened through `tracker desk` |
| Build approach | Vite + TypeScript, built into one self-contained HTML template; `build.py` injects data |

---

## 3. Architecture and data flow

### 3.1 Layout

```
desk/                          Vite + TypeScript project
  src/
    main.ts                    boot: renderer, loading screen, render loop, WebGL fallback
    data/                      DATA types; view-models (cards, stickies, done sheets, binder pages)
    paper/                     typesetter: typed + handwritten layers onto canvas textures
    objects/                   one module per desk object
    camera/                    director: named shots and eased moves between them
    interaction/               picking, hover, focus states, drag & drop, keyboard
    lighting/                  clock-driven day ↔ evening blend
    api/                       client for the local desk server (edit actions)
  assets.lock.json             every CC0 asset: source URL + md5
  scripts/fetch-assets.mjs     downloads + verifies assets into desk/assets/ (gitignored)
deskserver.py                  local edit server for `tracker desk` (see §7)
```

### 3.2 Flow

1. Unchanged: `scan.py` → `summarise.py` → `commits.json` / `tasks.json`, and `todo.py` → `todo.json`.
2. `npm run build` (run only when desk **code** changes) produces `desk-template.html`, with three.js, textures, models, HDRIs and fonts all inlined. It contains the same `/*__DATA__*/null` slot as `template.html`. The output is gitignored.
3. `build.py` writes both `dashboard.html` and `desk.html` from the same data. If `desk-template.html` is missing, it skips the desk and the dashboard is unaffected.
4. **Ink assignment** happens in `build.py`, using a gitignored `inks.json` that maps project to ink. New projects get the next unused ink from the pool, and assignments never change. The resolved map is included in DATA.
5. The 5pm job, `tracker refresh` and every `tracker add/start/done` already call `build.py`, so the desk stays current automatically.
6. New CLI commands: `tracker desk` starts or reuses the local server and opens the desk through it; `tracker desk refresh` refreshes first, then opens.

### 3.3 Assets (all CC0, Poly Haven)

- **Textures:** smoked walnut veneer (diffuse, roughness, normal; chosen 2026-10-13 over American walnut, which read grey under neutral light) and brown leather.
- **HDRIs:** a neutral daylight loft hall (red:blue ≈ 1.1; replaced the original "blinds" room, which was ≈ 4× redder than blue and tinted everything pink) and a dim evening interior, both at 1k.
- **Models:** articulated desk lamp, binder, notepads, stapler and potted plant, at 1k textures.
- **Fonts:** Caveat for handwriting (SIL OFL 1.1) and Special Elite for typewriting (Apache 2.0). Both are bundled, with their licence files kept next to them.
- **Pinning:** URLs and md5 values are recorded in `assets.lock.json`, and the fetch script verifies them. The assets are not committed to git.
- **Size budget:** `desk.html` must stay at or under 25 MB.

---

## 3a. Real-life mechanics (core rule, decided 2026-10-14)

Every object behaves like the real thing:
- **Printed text never changes.** No surface ever has its text swapped while you look at it.
- **More content means more physical paper.** A long task is a thicker stack of single-sided cards, never one card re-printed.
- **Every change is visible motion,** apart from the reduced-motion setting.
- **Physical consistency:** objects rest on surfaces, never pass through each other, and cast shadows when lifted.

| Object | Real-life behaviour |
|---|---|
| In-progress task | A clipped stack of single-sided index cards, one page each, so longer tasks are visibly thicker. Clicking **picks the stack up**: it's held above the mat, and the clip comes off and is left on the mat. Reading **thumbs** it like cards in your hand: the top card slides out and is tucked under the stack, revealing the next, and turning back brings the bottom card up. Turning past the last card restores the order. Leaving thumbs back to the original order, puts the stack down where it was, and re-clips it. (Decided 2026-10-14, replacing the side read pile, which had no free space on the mat.) |
| To-do | A small pad of sticky notes glued along the top edge. It is picked up like a stack; each note lifts up over the glued edge to reveal the next, and leaving lets them fall back. |
| Notepad | A daily tally pad, bound at the top. The top page is today (commits, summarised tasks, to-dos finished, first and last commit time), handwritten. Pages flip over the top binding to go back through earlier days, one page per day, the last 14 days. |
| Calendar | A wire-bound tent flip calendar with one page per day for the past week (7 pages; a coil wrapped round more pages would be unrealistically fat), today on top: the date plus a small handwritten tally of that day's commits. Pages swing over the coil and hang outside the back stand. `Space` flips back a day, `Shift`+`Space` forward, and clicking a page opens the Day binder at that date (decided 2026-10-14; Plan 2b). |
| Done tray | Separate sheets, lifted and turned one by one (Plan 2b). |
| Binders | Ring binders lying stacked: clicking one slides it out (the ones above drop a place), lifts it and opens it in your hands at the current period; the cover swings open on its spine and leaves turn over the D-rings, each hole sliding round the ring. One period per leaf, printed on the front only; long periods continue on the next leaf. Put back, it goes on top of the stack. Each binder keeps the most recent periods (Day 60, Week 26, Month 12). Built 2026-10-16. |
| Pens | Lifted out of the cup and laid down in front of you (Plan 2b). |

## 4. Scene and objects

**Scale and materials**
- Real-world metres. The desk is 1.6 × 0.8 m, made of walnut veneer with a clearcoat lacquer layer.
- A leather mat sits in the middle.
- The background is the HDRI, blurred to suggest a room behind the desk.

**Rendering**
- Neutral tone mapping (keeps material colours true; chosen over AgX, which desaturated warm light into pink), PCF shadows with soft radius, and a GTAO pass for ambient occlusion.
- Light depth of field in focus shots.
- Pixel ratio capped at 2.

**Paper**
- Thin geometry with a procedural fibre normal map, sheen, and a slight edge curl, so it never looks like a flat box.
- **Typesetter** (`paper/`), in two layers:
  - *Typed:* typewriter face in near-black, with slight ink unevenness.
  - *Handwritten:* cursive face in the project's ink. Per-line slant, size and pressure jitter are seeded by the task id, so a card renders the same every time.
- Textures are rendered at a lower resolution for the overview and re-rendered at high resolution only for the focused object.

**Objects and their data**

| # | Object | Data | Caps |
|---|---|---|---|
| 1 | Index cards on the mat | to-do items `in_progress`, each a clipped stack with one card per page of text | 6 visible; the rest go in a pile that fans out on click |
| 2 | Sticky notes | to-do items `todo` | 8 visible; the rest stack |
| 3 | Done tray (wooden out-tray) | items done in the last 7 days, one sheet each, newest on top | Stack height grows with the count; an empty week is just an empty tray |
| 4 | Day / Week / Month binders | summarised tasks grouped by period and thread; the Month binder opens on an inked calendar heatmap | Pages are built on demand |
| 5 | Flip calendar | today's date (IST) | — |
| 6 | Notepad | daily tally pad: today on top, one page per day for the last 14 days (changed 2026-10-14; the full week view lives in the WEEK binder) | 14 pages |
| 7 | Pen cup | one pen per project, in its ink | 7 pens in the cup; the rest lie beside it |
| 8 | Desk lamp | lighting override | — |

**Ink pool:** 12 Iroshizuku-inspired inks. Beyond 12 projects, inks repeat with a different pen body so they stay distinguishable. The hex values are tuned so each ink is legible on cream paper in both lighting moods.

---

## 5. Interactions and animation

**Camera director**
- No free orbit.
- **Overview:** the seated view, with a subtle parallax drift that follows the mouse.
- **Focus shots:** moves take 0.6–0.9 s with ease-in-out on a slight arc.
- `Esc`, a right-click or clicking the empty desk goes back one level.

**Hover:** the object lifts 2–4 mm with a shadow change, a paper label tag appears and the cursor becomes a hand.

| Object | Click | Then |
|---|---|---|
| Card | The stack lifts; the camera moves until the top card fills about 70% of the view | `Space` or a click turns the top page onto the read pile; `Shift`+`Space` turns one back; turning past the last page gathers the stack again; `←` `→` move to neighbouring tasks |
| Sticky note | The pad comes up close | Pages peel off onto a read pile, like a card stack (decided 2026-10-14, replacing "flips like a card") |
| Done tray | The stack slides out and tilts toward you | Drag or `←` `→` to flip sheets with a page-curl |
| Binder | Slides out of the stack and opens in your hands at the current period | Click the right-hand page to turn forward, the left-hand page to turn back (anything you read: right half forward, left half back; decided 2026-10-16); `Space` / `Shift`+`Space` turn single leaves, `←` `→` jump between periods, `Home` back to the current one |
| Calendar | Flips to today, then opens the Day binder there | |
| Notepad | Close-up of today's page | `Space` flips a page over the top binding (one day earlier); `Shift`+`Space` flips it back |
| Pen | Lifts out and lies in front of you | Everything not in its project fades and blurs; click the pen again to clear |
| Lamp | Toggles on or off as an override | Double-click returns to the clock |

**Page-curl:** a vertex-shader cylinder deformation sweeps across the sheet, with self-shadowing.

**Keyboard:** `1`–`8` jump to objects, `←` `→` page, `Esc` goes back, `0` returns to the overview.

**Reduced motion:** when the OS "Reduce motion" setting is on, moves become quick cross-fades.

**Render on demand:** the scene renders only while something animates or the pointer is moving; when idle, it draws one frame and stops.

### 5.1 Drag gestures (edit mode only)

- **Card → tray:** marks the task done. The card animates into the tray and becomes the top sheet. An **Undo** note appears on the tray for 10 s; clicking it re-opens the task (`start`).
- **Sticky note → mat:** starts the task. The note becomes an index card on the mat.
- **What counts:** a gesture fires only when a deliberate drag ends over a valid drop zone, which highlights during the drag. Releasing elsewhere snaps the object back.
- **Read-only mode** (the file opened directly): drag is disabled, and a small note reads "open with `tracker desk` to make changes".

---

## 6. Lighting (follows the real clock, IST)

| Time | State |
|---|---|
| 07:00–16:30 | Daylight HDRI and a window sun through the blinds (striped soft shadows); lamp off |
| 16:30–18:30 | Golden hour: the sun lowers and warms, shadows lengthen, the room fades |
| 18:30–19:15 | Dusk: the lamp turns on with a brief warm-up flicker |
| 19:15–05:30 | Night: lamp only, dim evening HDRI |
| 05:30–07:00 | Dawn: cool window light rises and the lamp fades out |

- **Blending:** every parameter is interpolated (light colour, angle, intensity, environment and background intensity, exposure).
- **Re-evaluation:** the clock is re-checked every minute, and the date rolls over at midnight without a reload.
- **Overrides:** clicking the lamp overrides the schedule until double-click or reload.

---

## 7. Local desk server (`deskserver.py`)

**Purpose:** let drag gestures change to-do status safely, through the exact same code path as the CLI.

**Process**
- Python standard library only, bound to `127.0.0.1` on a free port.
- A random 32-byte token is generated per run and passed to the page in the URL.
- A pidfile lets `tracker desk` reuse a running server. The server exits after 2 h idle.

**Routes**
- `GET /` serves `desk.html`.
- `POST /api/todo/<id>/<action>`, where `action` is either `start` or `done`. It requires the `X-Desk-Token` header and a same-origin `Origin`.
- The handler runs `todo.py <action> <id>`, so it shares the same lock, git rescan and rebuild as the CLI. It returns the updated item as JSON.

**Errors**

| Case | Response |
|---|---|
| Wrong or missing token | 403 |
| Unknown id | 404 |
| Action not allowed | 400 |
| `todo.py` failure | 500, with stderr in the body; the page snaps the object back and shows the message on a note |

**Concurrency:** handled by `todo.py`'s existing file lock.

---

## 8. Edge cases

| Case | Behaviour |
|---|---|
| Nothing in progress or to do | A single handwritten note on the mat: "Nothing on the go" |
| Nothing done this week | An empty tray, with no label |
| Long titles, notes or commit lists | Wrap and shrink to a minimum size, then continue on extra cards in the clipped stack; each card is numbered "n/total"; nothing is truncated silently |
| Unicode, emoji, symbols | Font fallback chain; covered by a dedicated test card |
| More than 7 or more than 12 projects | Pens overflow beside the cup; inks repeat with a different pen body |
| Midnight while open | "Today", the calendar and the Day binder roll over within a minute |
| WebGL unavailable or context lost | A clear message with a link to `dashboard.html`; on context loss, one restore attempt |
| Assets missing during `npm run build` | The build fails, naming the missing file and the fetch command |
| `desk-template.html` missing | `build.py` skips the desk; the dashboard still builds |
| Server down while the page is open | The drag snaps back with a "desk server not running" note; reading still works |
| Double drop or a race between two tabs | `todo.py` lock; "already done" is treated as success |
| Resize, Retina, reduced motion | Handled; pixel ratio capped at 2 |

**Depth rule (anti-flicker):**
- The camera's near and far planes are 0.05 m and 4 m.
- Stacked or overlapping surfaces are separated by at least 0.6 mm, plus `polygonOffset` on paper materials.
- A unit test asserts that every separation exceeds the depth-buffer precision at the farthest camera distance.

---

## 9. Testing (in order; each rung passes before the next)

1. **Unit (vitest):**
   - view-model mapping;
   - typesetter wrapping and overflow;
   - camera director state machine;
   - lighting interpolation at boundaries and midnight;
   - ink colour contrast against paper in both moods;
   - the depth-separation rule;
   - drag state machine (deliberate drag vs click; drop-zone hit testing).
2. **Python (pytest):**
   - ink assignment (stable, next unused, overflow);
   - `build.py` writes both pages, or skips the desk;
   - desk server: token check, Origin check, allowed actions, unknown id, `todo.py` failure, already-done.
3. **Docker:** not applicable. The desk is a static local file plus a stdlib localhost server, with no services.
4. **Browser** (real `desk.html`, both from disk and via `tracker desk`):
   - no console errors;
   - every interaction in §5;
   - lighting at forced times;
   - a flicker sweep: scripted camera moves through every shot, comparing successive frames for flickering pixels on paper regions;
   - drag gestures end-to-end, with `todo.json` changing as expected, and undo;
   - budgets: 60 fps in the overview on the author's Mac, idle when static, `desk.html` at or under 25 MB, interactive in under 3 s from disk.

   Screenshots at each milestone.

---

## 10. Out of scope (possible later)

- Phone layout or touch-first gestures.
- Editing notes or creating tasks from the desk.
- Sound (pen clicks, paper rustle). This would be easy to add later behind a mute toggle.
- Real sunrise and sunset based on location.
