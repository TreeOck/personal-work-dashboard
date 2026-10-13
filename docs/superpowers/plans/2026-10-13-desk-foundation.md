# 3D Desk, Plan 1 of 4: Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Running `tracker desk` opens a photoreal walnut desk, viewed from a static seated overview in daylight, showing your real in-progress index cards, to-do sticky notes, done stack, project pens, calendar, notepad and three binders, with no flicker anywhere.

**Architecture:**
- A Vite + TypeScript project in `desk/` builds one self-contained `desk-template.html`, with three.js, textures, models, HDRIs and fonts inlined as data URLs.
- `build.py` injects the same DATA blob it already builds for the dashboard, plus a resolved project-to-ink map, and writes `desk.html`.
- Pure logic (view-models, text layout, depth rule) is separated from three.js code so it can be unit-tested.

**Tech Stack:** TypeScript 7.0.2, Vite 8.3.4, vite-plugin-singlefile 2.3.3, three 0.186.1, vitest 5.0.4, Node 22; Python 3.9 (stdlib) + pytest for the pipeline.

**Spec:** `docs/superpowers/specs/2026-10-13-3d-desk-design.md`

**Later plans (not in this one):**
- 2: Interactions (camera director, focus, flip, page-curl, binders opening, pen filter, keyboard).
- 3: Living light (clock schedule, lamp, override).
- 4: Edit mode (`deskserver.py`, drag-to-done with undo, sticky-to-mat).

In Plan 1 the lamp model is present but switched off, and lighting is fixed daylight. Deferred on purpose:
- Plan 2: the overflow pile of cards beyond 6 and sticky notes beyond 8 (Plan 1 computes `cardOverflow` / `stickyOverflow` but doesn't draw them) and high-resolution re-rendering of the focused card.
- Plan 3: the midnight rollover of the calendar and "today".

## Global Constraints

- `desk.html` at or under 25 MB. It must open from disk (`file://`) offline, with no network requests at runtime.
- No coplanar surfaces: anything resting on a surface sits `MIN_GAP` (0.6 mm) above it via `restOn()`, stacked sheets are separated by at least 0.6 mm, and paper materials use `polygonOffset`. Camera near and far planes are 0.05 m and 4 m. (Verified cause of the mockup flicker: a model resting at exactly desk height; on GPU renders, lifting it 0.6 mm cut changed pixels in the area from 14.85% to 0.77%.)
- Renderer: `AgXToneMapping`, `PCFSoftShadowMap`, a GTAO pass, pixel ratio capped at 2, rendering on demand (no continuous loop when idle).
- Scale is real-world metres. The desk is 1.6 × 0.8 m.
- Text style "B": a typed layer in Special Elite, near-black `#24201c`; a handwritten layer in Caveat, in the project ink.
- Inks come from `desk/src/data/inks.json` (12 inks), which is the only place they're defined. Python and TypeScript both read it.
- Assets come only from `desk/assets.lock.json` (CC0 Poly Haven, plus Google Fonts files with their licence files). `desk/assets/` is gitignored.
- No personal data in committed files. `inks.json` (the assignments), `desk.html`, `desk-template.html` and `desk/dev-data.json` are gitignored.
- If `desk-template.html` is missing, `build.py` skips the desk and the dashboard is unaffected.
- Caps: 6 in-progress cards on the mat, 8 sticky notes, 7 pens in the cup.

## Review Focus

1. **A task title of 300+ characters, or with emoji or CJK characters.** The card must wrap, shrink to its minimum size and then continue on a second side. Nothing is drawn off the card, and nothing is silently dropped. Pinned in Task 6.
2. **A first refresh after a brand-new project appears.** It gets the next unused ink, existing projects keep theirs, and a 13th project reuses an ink with `variant: 1`. Pinned in Task 1.
3. **A to-do item with `project: null`.** It still appears as a card or sticky note, written in the fallback ink (`take-sumi`), and nothing crashes. Pinned in Task 5.
4. **A build with one asset file missing or corrupted.** `npm run build` fails, naming the file and the `npm run assets` command; it never produces a desk with holes. Pinned in Task 4.
5. **The data placeholder being minified away by Vite.** `build.py` would then inject nothing. A test asserts the placeholder survives the production build. Pinned in Task 3.

---

## File Structure

| File | Responsibility |
|---|---|
| `inks.py` | Assign inks to projects (stable, next unused, overflow variant); CLI `set` to pin one |
| `build.py` (modify) | Render both templates; add `inks` to DATA; write `desk/dev-data.json` |
| `bin/tracker` (modify) | `tracker desk` and `tracker desk refresh` |
| `tests/test_inks.py`, `tests/test_build.py` | pytest for the above |
| `desk/package.json`, `desk/tsconfig.json`, `desk/vite.config.ts`, `desk/index.html` | Project scaffold and single-file build |
| `desk/assets.lock.json`, `desk/scripts/fetch-assets.mjs`, `desk/scripts/check-assets.mjs` | Pinned assets, download and verify |
| `desk/src/assets.ts` | Single import point for every inlined asset |
| `desk/src/data/types.ts`, `desk/src/data/inks.json`, `desk/src/data/model.ts` | DATA types, ink palette, view-models |
| `desk/src/paper/layout.ts`, `desk/src/paper/render.ts` | Text layout (pure) and canvas drawing |
| `desk/src/scene/depth.ts`, `desk/src/scene/layout.ts` | Depth precision rule and object placement constants |
| `desk/src/scene/renderer.ts`, `desk/src/scene/environment.ts`, `desk/src/scene/materials.ts`, `desk/src/scene/models.ts` | three.js setup |
| `desk/src/objects/*.ts` | One builder per desk object |
| `desk/src/main.ts` | Boot, loading screen, WebGL fallback, render-on-demand |
| `desk/test/*.test.ts` | vitest |

---

### Task 1: Ink palette and assignment (Python)

**Files:**
- Create: `desk/src/data/inks.json`
- Create: `inks.py`
- Test: `tests/test_inks.py`

**Interfaces:**
- Produces: `inks.assign(projects: list[str], existing: dict[str, dict]) -> dict[str, dict]`, where each value is `{"ink": str, "variant": int}`.
- Produces: `inks.resolve(assignment) -> dict[str, dict]`, where each value is `{"ink": str, "name": str, "hex": str, "variant": int}`.
- Produces: `inks.load_palette() -> list[dict]`, read from `desk/src/data/inks.json`.
- Produces the constant `FALLBACK = "take-sumi"`.

- [ ] **Step 1: Create the palette (the single source for both languages)**

`desk/src/data/inks.json`:
```json
[
 {"id": "shin-kai",         "name": "Shin-kai · deep sea",            "hex": "#1f3a5c"},
 {"id": "yama-budo",        "name": "Yama-budo · crimson grape",      "hex": "#7a1f3d"},
 {"id": "shin-ryoku",       "name": "Shin-ryoku · forest green",      "hex": "#2e5a3a"},
 {"id": "ku-jaku",          "name": "Ku-jaku · peacock",              "hex": "#1d6670"},
 {"id": "yama-guri",        "name": "Yama-guri · wild chestnut",      "hex": "#5c3a26"},
 {"id": "murasaki-shikibu", "name": "Murasaki-shikibu · purple",      "hex": "#4b2f6b"},
 {"id": "kon-peki",         "name": "Kon-peki · azure",               "hex": "#1f4f8a"},
 {"id": "tsuki-yo",         "name": "Tsuki-yo · moonlight",           "hex": "#24414f"},
 {"id": "momiji",           "name": "Momiji · autumn leaves",         "hex": "#9a2a2a"},
 {"id": "chiku-rin",        "name": "Chiku-rin · bamboo forest",      "hex": "#4f5e22"},
 {"id": "fuyu-syogun",      "name": "Fuyu-syogun · old man winter",   "hex": "#47525c"},
 {"id": "take-sumi",        "name": "Take-sumi · bamboo charcoal",    "hex": "#2d2b29"}
]
```
Hex values are approximations of each ink on cream paper. Every one has a contrast of at least 4.5:1 against `#f1ebde`, in daylight and under the lamp tint `#ffc68a` (checked when this plan was written; re-asserted in Task 5).

- [ ] **Step 2: Write the failing tests**

`tests/test_inks.py`:
```python
import inks

PAL = [i["id"] for i in inks.load_palette()]


def test_palette_has_12_unique_inks_and_fallback_last():
    assert len(PAL) == 12 and len(set(PAL)) == 12
    assert PAL[-1] == inks.FALLBACK


def test_existing_assignments_never_change():
    existing = {"b": {"ink": "momiji", "variant": 0}}
    out = inks.assign(["a", "b"], existing)
    assert out["b"] == {"ink": "momiji", "variant": 0}


def test_new_projects_get_next_unused_ink_in_sorted_order():
    existing = {"b": {"ink": PAL[0], "variant": 0}}
    out = inks.assign(["c", "a", "b"], existing)
    assert out["a"]["ink"] == PAL[1] and out["c"]["ink"] == PAL[2]


def test_fallback_ink_is_not_handed_out_until_others_are_used():
    out = inks.assign([f"p{i:02d}" for i in range(11)], {})
    assert inks.FALLBACK not in {v["ink"] for v in out.values()}


def test_overflow_reuses_inks_with_a_new_variant():
    names = [f"p{i:02d}" for i in range(13)]
    out = inks.assign(names, {})
    assert out["p11"] == {"ink": inks.FALLBACK, "variant": 0}
    assert out["p12"] == {"ink": PAL[0], "variant": 1}


def test_resolve_adds_name_and_hex():
    r = inks.resolve({"a": {"ink": "momiji", "variant": 0}})
    assert r["a"] == {"ink": "momiji", "name": "Momiji · autumn leaves", "hex": "#9a2a2a", "variant": 0}


def test_unknown_ink_in_existing_file_falls_back(capsys):
    r = inks.resolve({"a": {"ink": "no-such-ink", "variant": 0}})
    assert r["a"]["ink"] == inks.FALLBACK
```

- [ ] **Step 3: Run them to confirm they fail**

Run: `.venv/bin/python -m pytest tests/test_inks.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'inks'`

- [ ] **Step 4: Implement `inks.py`**

```python
#!/usr/bin/env python3
"""Project -> fountain-pen ink assignments (inks.json, gitignored).

  python3 inks.py set <project> <ink-id>   # pin one project's ink
  python3 inks.py list                     # show assignments

Assignments never change once made; new projects take the next unused ink
(palette order, fallback ink last); past 12 projects inks repeat with variant+1.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PALETTE_PATH = os.path.join(HERE, "desk", "src", "data", "inks.json")
ASSIGN_PATH = os.path.join(HERE, "inks.json")
FALLBACK = "take-sumi"


def load_palette():
    with open(PALETTE_PATH) as f:
        return json.load(f)


def assign(projects, existing):
    order = [i["id"] for i in load_palette()]
    out = {p: dict(v) for p, v in existing.items()}
    for p in sorted(set(projects) - set(out)):
        used = [(v["ink"], v["variant"]) for v in out.values()]
        variant = 0
        while True:
            free = [i for i in order if (i, variant) not in used]
            if free:
                out[p] = {"ink": free[0], "variant": variant}
                break
            variant += 1
    return out


def resolve(assignment):
    pal = {i["id"]: i for i in load_palette()}
    res = {}
    for p, v in assignment.items():
        ink = v["ink"] if v["ink"] in pal else FALLBACK
        res[p] = {"ink": ink, "name": pal[ink]["name"], "hex": pal[ink]["hex"], "variant": v.get("variant", 0)}
    return res


def load_assignments():
    if not os.path.exists(ASSIGN_PATH):
        return {}
    with open(ASSIGN_PATH) as f:
        return json.load(f)


def save_assignments(a):
    with open(ASSIGN_PATH + ".tmp", "w") as f:
        json.dump(a, f, indent=1, sort_keys=True)
    os.replace(ASSIGN_PATH + ".tmp", ASSIGN_PATH)


def main(argv):
    if argv[:1] == ["set"] and len(argv) == 3:
        if argv[2] not in {i["id"] for i in load_palette()}:
            sys.exit("unknown ink %r; choose from: %s" % (argv[2], ", ".join(i["id"] for i in load_palette())))
        a = load_assignments(); a[argv[1]] = {"ink": argv[2], "variant": 0}; save_assignments(a)
        print("%s -> %s" % (argv[1], argv[2]))
    elif argv[:1] == ["list"]:
        for p, v in sorted(resolve(load_assignments()).items()):
            print("%-32s %s (%s)%s" % (p, v["name"], v["hex"], " variant %d" % v["variant"] if v["variant"] else ""))
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
```

- [ ] **Step 5: Run the tests to confirm they pass**

Run: `.venv/bin/python -m pytest tests/test_inks.py -q`
Expected: `7 passed`

- [ ] **Step 6: Gitignore the assignments and commit**

Append to `.gitignore`:
```
# desk: personal assignments and generated output
inks.json
desk.html
desk-template.html
desk/node_modules/
desk/assets/
desk/dev-data.json
```
```bash
git add .gitignore inks.py desk/src/data/inks.json tests/test_inks.py
git commit   # message shown to the user for approval first (CLAUDE.md §6)
```

---

### Task 2: build.py renders both pages; `tracker desk`

**Files:**
- Modify: `build.py` (whole file; currently 30 lines)
- Modify: `bin/tracker`
- Test: `tests/test_build.py`

**Interfaces:**
- Consumes: `inks.assign`, `inks.resolve`, `inks.load_assignments`, `inks.save_assignments` (Task 1).
- Produces: DATA gains the key `inks: {project: {ink, name, hex, variant}}`, covering every project in commits, tasks and todo.
- Produces: `desk.html`, written only when `desk-template.html` exists; `desk/dev-data.json` is always written (gitignored, for `npm run dev`).

- [ ] **Step 1: Write the failing tests**

`tests/test_build.py`:
```python
import json
import shutil
import subprocess
import sys

import pytest

from conftest import REPO


@pytest.fixture
def site(tmp_path):
    for f in ("build.py", "links.py", "inks.py", "template.html"):
        shutil.copy(f"{REPO}/{f}", tmp_path / f)
    (tmp_path / "desk" / "src" / "data").mkdir(parents=True)
    shutil.copy(f"{REPO}/desk/src/data/inks.json", tmp_path / "desk/src/data/inks.json")
    (tmp_path / "commits.json").write_text(json.dumps({"generated_at": "2026-10-13T10:00:00+05:30", "since": "2026-10-01",
        "author_pattern": "me@example.com", "commits": [{"sha": "a" * 40, "date": "2026-10-12T10:00:00+05:30",
        "project": "alpha", "repo": "alpha-be", "repo_path": "alpha/alpha-be", "subject": "s", "body": "", "files": [], "ins": 1, "del": 0}]}))
    (tmp_path / "tasks.json").write_text(json.dumps({"tasks": []}))
    (tmp_path / "todo.json").write_text(json.dumps({"items": [{"id": "t-0001", "title": "x", "project": "beta", "repo": None,
        "status": "todo", "created_at": "2026-10-12T10:00:00+05:30", "updated_at": "2026-10-12T10:00:00+05:30",
        "started_at": None, "closed_at": None, "plan": None, "notes": []}]}))
    run = lambda: subprocess.run([sys.executable, str(tmp_path / "build.py")], capture_output=True, text=True)
    run.dir = tmp_path
    return run


def test_without_desk_template_only_dashboard_is_built(site):
    r = site()
    assert r.returncode == 0, r.stderr
    assert (site.dir / "dashboard.html").exists()
    assert not (site.dir / "desk.html").exists()
    assert "skipped desk" in r.stdout


def test_with_desk_template_both_pages_get_the_same_data(site):
    (site.dir / "desk-template.html").write_text("<script>window.__DESK_DATA__=/*__DATA__*/null;</script>")
    assert site().returncode == 0
    desk = (site.dir / "desk.html").read_text()
    blob = json.loads(desk.split("window.__DESK_DATA__=")[1].split(";</script>")[0])
    assert set(blob["inks"]) == {"alpha", "beta"}
    assert blob["inks"]["alpha"]["hex"].startswith("#")


def test_inks_are_persisted_and_stable_across_builds(site):
    site()
    first = json.loads((site.dir / "inks.json").read_text())
    site()
    assert json.loads((site.dir / "inks.json").read_text()) == first


def test_dev_data_written_for_vite(site):
    site()
    d = json.loads((site.dir / "desk" / "dev-data.json").read_text())
    assert "commits" in d and "inks" in d
```

- [ ] **Step 2: Run them to confirm they fail**

Run: `.venv/bin/python -m pytest tests/test_build.py -q`
Expected: FAIL (`desk.html` / `inks.json` / `dev-data.json` aren't produced, and "skipped desk" doesn't appear in stdout).

- [ ] **Step 3: Replace `build.py`**

```python
#!/usr/bin/env python3
"""Inline commits.json + tasks.json + todo.json into the page templates.

template.html      -> dashboard.html   (always)
desk-template.html -> desk.html        (only if the desk has been built: `cd desk && npm run build`)
"""
import fcntl, json, os
from datetime import datetime
from links import link
import inks
HERE = os.path.dirname(os.path.abspath(__file__))
def load(n):
    with open(os.path.join(HERE, n)) as f:
        return json.load(f)
# Serialise builds: concurrent `tracker` calls each rebuild; the last one to run
# reads the newest todo.json, so the pages never end up stale.
_lock = open(os.path.join(HERE, "build.lock"), "w")
fcntl.flock(_lock, fcntl.LOCK_EX)
data = load("commits.json")
data["tasks"] = load("tasks.json")["tasks"]
data["todo"] = load("todo.json")["items"] if os.path.exists(os.path.join(HERE, "todo.json")) else []
_now = datetime.now().astimezone()
for it in data["todo"]:  # commits made while each current-task was open (computed fresh every build)
    it["linked"] = [c["repo_path"] + ":" + c["sha"] for c in link(it, data["commits"], _now)]
projects = {c["project"] for c in data["commits"]} | {t["project"] for t in data["tasks"]} | {i["project"] for i in data["todo"] if i.get("project")}
_assigned = inks.assign(sorted(projects), inks.load_assignments())
inks.save_assignments(_assigned)
data["inks"] = inks.resolve(_assigned)
blob = json.dumps(data).replace("</", "<\\/")  # keep commit text from closing the script tag


def render(template, out):
    with open(os.path.join(HERE, template)) as f:
        html = f.read()
    assert "/*__DATA__*/null" in html, "%s has no data slot" % template
    path = os.path.join(HERE, out)
    with open(path + ".tmp", "w") as f:
        f.write(html.replace("/*__DATA__*/null", blob))
    os.replace(path + ".tmp", path)
    return path


print("built", render("template.html", "dashboard.html"), "(%d commits, %d tasks)" % (len(data["commits"]), len(data["tasks"])))
if os.path.exists(os.path.join(HERE, "desk-template.html")):
    print("built", render("desk-template.html", "desk.html"))
else:
    print("skipped desk (no desk-template.html; run: cd desk && npm run build)")
os.makedirs(os.path.join(HERE, "desk"), exist_ok=True)
with open(os.path.join(HERE, "desk", "dev-data.json"), "w") as f:
    json.dump(data, f)
```

- [ ] **Step 4: Run the full Python suite**

Run: `.venv/bin/python -m pytest tests -q`
Expected: `38 passed` (the 27 existing tests, plus 7 in `test_inks.py`, plus 4 in `test_build.py`).

- [ ] **Step 5: Add `tracker desk` and `tracker desk refresh`**

In `bin/tracker`, replace the `case` block with:
```bash
case "$1" in
  ""|open) open "$D/dashboard.html" ;;
  refresh) echo "Refreshing (about a minute)..."; "$D/refresh.sh" && tail -4 "$D/refresh.log"; open "$D/dashboard.html" ;;
  desk)
    if [ "$2" = "refresh" ]; then echo "Refreshing (about a minute)..."; "$D/refresh.sh" && tail -4 "$D/refresh.log"; fi
    if [ ! -f "$D/desk.html" ]; then echo "desk not built yet: cd $D/desk && npm install && npm run assets && npm run build && python3 $D/build.py"; exit 1; fi
    open "$D/desk.html" ;;
  *) exec python3 "$D/todo.py" "$@" ;;
esac
```
Check by hand: `tracker desk` prints the "desk not built yet" hint and exits with code 1. That's expected until Task 10.

- [ ] **Step 6: Seed the agreed inks locally (not committed)**

Pin the project-to-ink mapping the user approved in the brainstorming conversation, using `python3 inks.py set <project> <ink-id>` once per project. Project names are private, so they aren't written in this public plan. Then confirm with `python3 inks.py list`.

- [ ] **Step 7: Commit**

```bash
git add build.py bin/tracker tests/test_build.py
git commit   # message shown to the user for approval first
```

---

### Task 3: Vite project scaffold with a data slot that survives the build

**Files:**
- Create: `desk/package.json`, `desk/tsconfig.json`, `desk/vite.config.ts`, `desk/index.html`, `desk/src/main.ts` (stub, replaced in Task 8)
- Create: `desk/src/data/types.ts`
- Test: `desk/test/build-slot.test.ts`

**Interfaces:**
- Produces: `readData(): DeskData`, from `desk/src/data/types.ts`. It returns `window.__DESK_DATA__` when it isn't null, otherwise `null`; in dev, `main.ts` falls back to fetching `/dev-data.json`.
- Produces: the types `DeskData`, `Commit`, `Task`, `TodoItem`, `InkRef`.

- [ ] **Step 1: Scaffold the project**

`desk/package.json`:
```json
{
  "name": "personal-work-desk",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite",
    "assets": "node scripts/fetch-assets.mjs",
    "build": "node scripts/check-assets.mjs && tsc --noEmit && vite build",
    "test": "vitest run"
  },
  "dependencies": { "three": "0.186.1" },
  "devDependencies": {
    "@types/three": "0.186.0",
    "typescript": "7.0.2",
    "vite": "8.3.4",
    "vite-plugin-singlefile": "2.3.3",
    "vitest": "5.0.4"
  }
}
```

`desk/tsconfig.json`:
```json
{
  "compilerOptions": {
    "target": "ES2022", "module": "ESNext", "moduleResolution": "Bundler",
    "strict": true, "noUnusedLocals": true, "resolveJsonModule": true,
    "lib": ["ES2022", "DOM", "DOM.Iterable"], "types": ["vite/client"], "skipLibCheck": true
  },
  "include": ["src", "test", "vite.config.ts"]
}
```

`desk/vite.config.ts`:
```ts
import { defineConfig } from "vite";
import { viteSingleFile } from "vite-plugin-singlefile";
import { renameSync } from "node:fs";
import { resolve } from "node:path";

// One self-contained file, written to the repo root as desk-template.html,
// where build.py injects the data.
export default defineConfig({
  plugins: [viteSingleFile({ removeViteModuleLoader: true }),
    { name: "rename-output", closeBundle() { renameSync(resolve(__dirname, "dist/index.html"), resolve(__dirname, "../desk-template.html")); } }],
  build: { outDir: "dist", assetsInlineLimit: Number.MAX_SAFE_INTEGER, chunkSizeWarningLimit: 30000, target: "es2022" },
  test: { environment: "node" },
});
```

`desk/index.html`:
```html
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Desk</title>
<style>
  html, body { margin: 0; height: 100%; background: #0d0b09; overflow: hidden; }
  #desk { display: block; width: 100vw; height: 100vh; }
  #loading { position: fixed; inset: 0; display: grid; place-items: center; color: #d9c9ad; font: 15px Georgia, serif; letter-spacing: .04em; transition: opacity .6s; }
  #fallback { position: fixed; inset: 0; display: none; place-items: center; color: #d9c9ad; font: 16px Georgia, serif; text-align: center; padding: 24px; }
  #fallback a { color: #f0d9a8; }
</style>
</head>
<body>
<canvas id="desk"></canvas>
<div id="loading">Setting out the desk…</div>
<div id="fallback">This browser couldn't start 3D graphics (WebGL).<br><a href="dashboard.html">Open the dashboard instead</a></div>
<script>window.__DESK_DATA__ = /*__DATA__*/null;</script>
<script type="module" src="/src/main.ts"></script>
</body>
</html>
```

`desk/src/data/types.ts`:
```ts
export interface Commit { sha: string; date: string; project: string; repo: string; repo_path: string; subject: string; body: string; files: string[]; ins: number; del: number; }
export interface Task { id: string; date: string; project: string; kind: "feature" | "fix" | "infra" | "docs"; thread?: string; title: string; summary: string; details: string[]; commits: string[]; }
export interface Note { at: string; text: string; }
export interface TodoItem { id: string; title: string; project: string | null; repo: string | null; status: "todo" | "in_progress" | "done" | "dropped";
  created_at: string; updated_at: string; started_at?: string | null; closed_at: string | null; plan: string | null; notes: Note[]; linked?: string[]; }
export interface InkRef { ink: string; name: string; hex: string; variant: number; }
export interface DeskData { generated_at: string; commits: Commit[]; tasks: Task[]; todo: TodoItem[]; inks: Record<string, InkRef>; }

declare global { interface Window { __DESK_DATA__: DeskData | null; } }

export function readData(): DeskData | null {
  return typeof window !== "undefined" && window.__DESK_DATA__ ? window.__DESK_DATA__ : null;
}
```

`desk/src/main.ts` (stub):
```ts
import { readData } from "./data/types";
console.log("desk data present:", !!readData());
```

- [ ] **Step 2: Write the failing test that the slot survives a production build**

`desk/test/build-slot.test.ts`:
```ts
import { execSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { expect, test } from "vitest";

test("production build keeps the /*__DATA__*/null slot verbatim", () => {
  execSync("npx vite build", { cwd: resolve(__dirname, ".."), stdio: "pipe" });
  const html = readFileSync(resolve(__dirname, "../../desk-template.html"), "utf8");
  expect(html).toContain("window.__DESK_DATA__ = /*__DATA__*/null;");
  expect(html).not.toMatch(/<script[^>]+src=/);   // everything inlined
}, 120_000);
```

- [ ] **Step 3: Install and run it**

Run: `cd desk && npm install && npx vitest run test/build-slot.test.ts`
Expected: PASS. (The test runs the real build; if Vite ever starts rewriting classic inline scripts, it fails here.)

- [ ] **Step 4: Commit**

```bash
git add desk/package.json desk/package-lock.json desk/tsconfig.json desk/vite.config.ts desk/index.html desk/src/main.ts desk/src/data/types.ts desk/test/build-slot.test.ts
git commit   # message shown to the user for approval first
```

---

### Task 4: Pinned assets: fetch, verify, inline

**Files:**
- Create: `desk/assets.lock.json` (copy `docs/superpowers/plans/2026-10-13-desk-assets.lock.json` exactly; 22 files, 15.1 MB)
- Create: `desk/scripts/fetch-assets.mjs`, `desk/scripts/check-assets.mjs`, `desk/scripts/verify.mjs`
- Create: `desk/src/assets.ts`
- Test: `desk/test/check-assets.test.ts`

**Interfaces:**
- Produces: `verify(dir: string, lock: Record<string, {url, md5, size}>): { missing: string[]; bad: string[] }`, from `desk/scripts/verify.mjs`.
- Produces: the `ASSETS` object from `desk/src/assets.ts`, with keys:
  - `walnut.{map,normal,rough}` and `leather.{map,normal,rough}` (data URLs);
  - `hdri.{blinds,cabin}` (data URLs);
  - `models.lamp` and `models.plant`, each `{ gltf: string /* json text */, files: Record<string,string> /* relative path → data URL */ }`;
  - `fonts.{caveat,specialElite}` (data URLs).

- [ ] **Step 1: Copy the lock file**

Run: `cp docs/superpowers/plans/2026-10-13-desk-assets.lock.json desk/assets.lock.json`

- [ ] **Step 2: Write the failing test**

`desk/test/check-assets.test.ts`:
```ts
import { mkdtempSync, mkdirSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { createHash } from "node:crypto";
import { expect, test } from "vitest";
import { verify } from "../scripts/verify.mjs";

const md5 = (s: string) => createHash("md5").update(s).digest("hex");

test("reports missing and corrupted files, accepts good ones", () => {
  const dir = mkdtempSync(join(tmpdir(), "assets-"));
  mkdirSync(join(dir, "fonts"));
  writeFileSync(join(dir, "fonts/good.ttf"), "good");
  writeFileSync(join(dir, "fonts/bad.ttf"), "tampered");
  const lock = {
    "fonts/good.ttf": { url: "u", md5: md5("good"), size: 4 },
    "fonts/bad.ttf": { url: "u", md5: md5("original"), size: 8 },
    "fonts/missing.ttf": { url: "u", md5: md5("x"), size: 1 },
  };
  expect(verify(dir, lock)).toEqual({ missing: ["fonts/missing.ttf"], bad: ["fonts/bad.ttf"] });
});
```

- [ ] **Step 3: Run it to confirm it fails**

Run: `cd desk && npx vitest run test/check-assets.test.ts`
Expected: FAIL (`Cannot find module '../scripts/verify.mjs'`)

- [ ] **Step 4: Implement the scripts**

`desk/scripts/verify.mjs`:
```js
import { createHash } from "node:crypto";
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";

export function verify(dir, lock) {
  const missing = [], bad = [];
  for (const [rel, { md5 }] of Object.entries(lock)) {
    const p = join(dir, rel);
    if (!existsSync(p)) { missing.push(rel); continue; }
    if (createHash("md5").update(readFileSync(p)).digest("hex") !== md5) bad.push(rel);
  }
  return { missing, bad };
}
```

`desk/scripts/fetch-assets.mjs`:
```js
// Downloads every asset in assets.lock.json into desk/assets/ and verifies md5.
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { verify } from "./verify.mjs";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const lock = JSON.parse(readFileSync(join(root, "assets.lock.json"), "utf8"));
const out = join(root, "assets");
const { missing, bad } = verify(out, lock);
for (const rel of [...missing, ...bad]) {
  const res = await fetch(lock[rel].url, { headers: { "User-Agent": "Mozilla/5.0 personal-work-desk" } });
  if (!res.ok) throw new Error(`${rel}: HTTP ${res.status} from ${lock[rel].url}`);
  mkdirSync(dirname(join(out, rel)), { recursive: true });
  writeFileSync(join(out, rel), Buffer.from(await res.arrayBuffer()));
  console.log("fetched", rel);
}
const after = verify(out, lock);
if (after.missing.length || after.bad.length) { console.error("still wrong:", after); process.exit(1); }
console.log(`all ${Object.keys(lock).length} assets present and verified`);
```

`desk/scripts/check-assets.mjs`:
```js
// Build guard: fail loudly instead of producing a desk with missing textures.
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { verify } from "./verify.mjs";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const { missing, bad } = verify(join(root, "assets"), JSON.parse(readFileSync(join(root, "assets.lock.json"), "utf8")));
if (missing.length || bad.length) {
  for (const f of missing) console.error("missing asset:", f);
  for (const f of bad) console.error("corrupted asset (md5 mismatch):", f);
  console.error("run: npm run assets");
  process.exit(1);
}
```

- [ ] **Step 5: Run the test, then fetch for real**

Run: `cd desk && npx vitest run test/check-assets.test.ts && npm run assets`
Expected: the test passes; the fetch prints `all 22 assets present and verified`.

- [ ] **Step 6: Create the single asset import point**

`desk/src/assets.ts`:
```ts
// Every asset the desk uses, inlined at build time as data URLs (?inline) or text (?raw).
// File names match desk/assets.lock.json.
import walnutMap from "../assets/textures/american_walnut_veneer_diffuse.jpg?inline";
import walnutNormal from "../assets/textures/american_walnut_veneer_nor_gl.jpg?inline";
import walnutRough from "../assets/textures/american_walnut_veneer_rough.jpg?inline";
import leatherMap from "../assets/textures/brown_leather_diffuse.jpg?inline";
import leatherNormal from "../assets/textures/brown_leather_nor_gl.jpg?inline";
import leatherRough from "../assets/textures/brown_leather_rough.jpg?inline";
import blinds from "../assets/hdri/blinds.hdr?inline";
import cabin from "../assets/hdri/cabin.hdr?inline";
import lampGltf from "../assets/models/desk_lamp_arm_01/desk_lamp_arm_01.gltf?raw";
import lampBin from "../assets/models/desk_lamp_arm_01/desk_lamp_arm_01.bin?inline";
import lampDiff from "../assets/models/desk_lamp_arm_01/textures/desk_lamp_arm_01_diff_1k.jpg?inline";
import lampNor from "../assets/models/desk_lamp_arm_01/textures/desk_lamp_arm_01_nor_gl_1k.jpg?inline";
import lampArm from "../assets/models/desk_lamp_arm_01/textures/desk_lamp_arm_01_arm_1k.jpg?inline";
import plantGltf from "../assets/models/potted_plant_04/potted_plant_04.gltf?raw";
import plantBin from "../assets/models/potted_plant_04/potted_plant_04.bin?inline";
import plantDiff from "../assets/models/potted_plant_04/textures/potted_plant_04_diff_1k.jpg?inline";
import plantNor from "../assets/models/potted_plant_04/textures/potted_plant_04_nor_gl_1k.jpg?inline";
import plantArm from "../assets/models/potted_plant_04/textures/potted_plant_04_arm_1k.jpg?inline";
import caveat from "../assets/fonts/Caveat.ttf?inline";
import specialElite from "../assets/fonts/SpecialElite.ttf?inline";

export const ASSETS = {
  walnut: { map: walnutMap, normal: walnutNormal, rough: walnutRough },
  leather: { map: leatherMap, normal: leatherNormal, rough: leatherRough },
  hdri: { blinds, cabin },
  models: {
    lamp: { gltf: lampGltf, files: { "desk_lamp_arm_01.bin": lampBin, "textures/desk_lamp_arm_01_diff_1k.jpg": lampDiff,
      "textures/desk_lamp_arm_01_nor_gl_1k.jpg": lampNor, "textures/desk_lamp_arm_01_arm_1k.jpg": lampArm } },
    plant: { gltf: plantGltf, files: { "potted_plant_04.bin": plantBin, "textures/potted_plant_04_diff_1k.jpg": plantDiff,
      "textures/potted_plant_04_nor_gl_1k.jpg": plantNor, "textures/potted_plant_04_arm_1k.jpg": plantArm } },
  },
  fonts: { caveat, specialElite },
};
```
Before relying on the plant's file names, confirm them with: `node -e "const g=require('./desk/assets/models/potted_plant_04/potted_plant_04.gltf');console.log(g.buffers.map(b=>b.uri),g.images.map(i=>i.uri))"`. They must match the keys above exactly, the same way the lamp's were checked when this plan was written.

- [ ] **Step 7: Commit**

```bash
git add desk/assets.lock.json desk/scripts desk/src/assets.ts desk/test/check-assets.test.ts
git commit   # message shown to the user for approval first
```

---

### Task 5: View-models from DATA

**Files:**
- Create: `desk/src/data/model.ts`
- Test: `desk/test/model.test.ts`, `desk/test/fixture.ts`

**Interfaces:**
- Consumes: `DeskData` and `TodoItem` (Task 3), and `inks.json` (Task 1).
- Produces: `buildModel(data: DeskData, now: Date): DeskModel`, where:
  ```ts
  interface Ink { hex: string; name: string; variant: number }
  interface CardVM { id: string; title: string; where: string; ink: Ink; notes: Note[]; commits: Commit[]; started: string | null }
  interface DeskModel {
    cards: CardVM[]; cardOverflow: CardVM[];        // in_progress, 6 on the mat, rest in the pile
    stickies: CardVM[]; stickyOverflow: CardVM[];   // todo, 8 visible
    done: CardVM[];                                 // done in the last 7 days, newest first
    pens: { project: string; ink: Ink }[];          // one per project, sorted by name
    today: { ymd: string; day: number; monthName: string; weekday: string };
    week: { commits: number; tasks: number; activeDays: number };
  }
  ```
- Produces: `inkFor(project: string | null, data: DeskData): Ink`; it falls back to `take-sumi` for a null or unknown project.
- Produces: `istYmd(iso: string): string` (YYYY-MM-DD in Asia/Kolkata).

- [ ] **Step 1: Write the fixture and the failing tests**

`desk/test/fixture.ts`:
```ts
import type { DeskData, TodoItem } from "../src/data/types";

export const NOW = new Date("2026-10-13T12:00:00+05:30");
export function item(id: string, status: TodoItem["status"], extra: Partial<TodoItem> = {}): TodoItem {
  return { id, title: `Task ${id}`, project: "alpha", repo: "alpha-be", status, created_at: "2026-10-10T09:00:00+05:30",
    updated_at: "2026-10-10T09:00:00+05:30", started_at: null, closed_at: null, plan: null, notes: [], linked: [], ...extra };
}
export function data(todo: TodoItem[], extra: Partial<DeskData> = {}): DeskData {
  return { generated_at: "2026-10-13T11:00:00+05:30", commits: [], tasks: [], todo,
    inks: { alpha: { ink: "shin-kai", name: "Shin-kai · deep sea", hex: "#1f3a5c", variant: 0 } }, ...extra };
}
```

`desk/test/model.test.ts`:
```ts
import { describe, expect, test } from "vitest";
import { buildModel, inkFor, istYmd } from "../src/data/model";
import inks from "../src/data/inks.json";
import { NOW, data, item } from "./fixture";

describe("buildModel", () => {
  test("caps cards at 6 and stickies at 8, overflow keeps the rest", () => {
    const todo = [...Array(9)].map((_, i) => item(`p${i}`, "in_progress")).concat([...Array(11)].map((_, i) => item(`t${i}`, "todo")));
    const m = buildModel(data(todo), NOW);
    expect([m.cards.length, m.cardOverflow.length, m.stickies.length, m.stickyOverflow.length]).toEqual([6, 3, 8, 3]);
  });
  test("done = last 7 days only, newest first; dropped excluded", () => {
    const m = buildModel(data([
      item("old", "done", { closed_at: "2026-10-05T10:00:00+05:30" }),
      item("a", "done", { closed_at: "2026-10-12T10:00:00+05:30" }),
      item("b", "done", { closed_at: "2026-10-13T09:00:00+05:30" }),
      item("x", "dropped", { closed_at: "2026-10-13T09:00:00+05:30" }),
    ]), NOW);
    expect(m.done.map(c => c.id)).toEqual(["b", "a"]);
  });
  test("item with null project still renders, in the fallback ink", () => {
    const m = buildModel(data([item("n", "todo", { project: null, repo: null })]), NOW);
    expect(m.stickies[0].ink.hex).toBe("#2d2b29");
    expect(m.stickies[0].where).toBe("no project");
  });
  test("empty data gives an empty desk, not an error", () => {
    const m = buildModel(data([]), NOW);
    expect([m.cards, m.stickies, m.done, m.pens]).toEqual([[], [], [], []]);
  });
  test("today is computed in IST even near UTC midnight", () => {
    expect(buildModel(data([]), new Date("2026-10-12T19:00:00Z")).today.ymd).toBe("2026-10-13");
  });
  test("week tallies count commits, tasks and active days Mon-Sun (IST)", () => {
    const c = (date: string) => ({ sha: date, date, project: "alpha", repo: "r", repo_path: "alpha/r", subject: "s", body: "", files: [], ins: 1, del: 0 });
    const d = data([], { commits: [c("2026-10-12T10:00:00+05:30"), c("2026-10-13T10:00:00+05:30"), c("2026-10-11T10:00:00+05:30")],
      tasks: [{ id: "k", date: "2026-10-12", project: "alpha", kind: "feature", title: "t", summary: "s", details: [], commits: [] }] });
    expect(buildModel(d, NOW).week).toEqual({ commits: 2, tasks: 1, activeDays: 2 });
  });
});

test("inkFor falls back for unknown projects", () => {
  expect(inkFor("nope", data([])).hex).toBe("#2d2b29");
  expect(inkFor("alpha", data([])).hex).toBe("#1f3a5c");
});
test("istYmd handles UTC 'Z' timestamps", () => { expect(istYmd("2026-10-05T18:57:40Z")).toBe("2026-10-06"); });

// Spec §4: every ink legible on paper (≥ 4.5:1) in daylight and under the evening lamp.
test("every ink keeps ≥ 4.5:1 contrast on paper in both lights", () => {
  const lin = (c: number) => { c /= 255; return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4; };
  const lum = ([r, g, b]: number[]) => 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
  const rgb = (h: string) => [1, 3, 5].map(i => parseInt(h.slice(i, i + 2), 16));
  const ratio = (a: number[], b: number[]) => { const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p); return (x + 0.05) / (y + 0.05); };
  const lamp = [1, 198 / 255, 138 / 255], tint = (c: number[]) => c.map((v, i) => v * lamp[i]);
  const paper = rgb("#f1ebde");
  for (const ink of inks) {
    expect(ratio(rgb(ink.hex), paper), ink.id).toBeGreaterThanOrEqual(4.5);
    expect(ratio(tint(rgb(ink.hex)), tint(paper)), ink.id + " under lamp").toBeGreaterThanOrEqual(4.5);
  }
});
```

- [ ] **Step 2: Run them to confirm they fail**

Run: `cd desk && npx vitest run test/model.test.ts`
Expected: FAIL (`Cannot find module '../src/data/model'`)

- [ ] **Step 3: Implement `model.ts`**

```ts
import type { Commit, DeskData, Note, TodoItem } from "./types";
import palette from "./inks.json";

export interface Ink { hex: string; name: string; variant: number }
export interface CardVM { id: string; title: string; where: string; ink: Ink; notes: Note[]; commits: Commit[]; started: string | null }
export interface DeskModel {
  cards: CardVM[]; cardOverflow: CardVM[]; stickies: CardVM[]; stickyOverflow: CardVM[]; done: CardVM[];
  pens: { project: string; ink: Ink }[];
  today: { ymd: string; day: number; monthName: string; weekday: string };
  week: { commits: number; tasks: number; activeDays: number };
}
export const CAPS = { cards: 6, stickies: 8 } as const;
const FALLBACK = palette.find(p => p.id === "take-sumi")!;
const TZ = "Asia/Kolkata";

export const istYmd = (iso: string | Date) => new Date(iso).toLocaleDateString("en-CA", { timeZone: TZ });
const addDays = (ymd: string, n: number) => { const d = new Date(ymd + "T12:00:00Z"); d.setUTCDate(d.getUTCDate() + n); return d.toISOString().slice(0, 10); };
const weekStart = (ymd: string) => addDays(ymd, -((new Date(ymd + "T12:00:00Z").getUTCDay() + 6) % 7));

export function inkFor(project: string | null, data: DeskData): Ink {
  const r = project ? data.inks[project] : undefined;
  return r ? { hex: r.hex, name: r.name, variant: r.variant } : { hex: FALLBACK.hex, name: FALLBACK.name, variant: 0 };
}

export function buildModel(data: DeskData, now: Date): DeskModel {
  const byKey = new Map(data.commits.map(c => [c.repo_path + ":" + c.sha, c]));
  const vm = (i: TodoItem): CardVM => ({ id: i.id, title: i.title, where: [i.project, i.repo].filter(Boolean).join(" / ") || "no project",
    ink: inkFor(i.project, data), notes: i.notes, commits: (i.linked ?? []).map(k => byKey.get(k)).filter((c): c is Commit => !!c),
    started: i.started_at ?? null });
  const prog = data.todo.filter(i => i.status === "in_progress").sort((a, b) => a.created_at.localeCompare(b.created_at)).map(vm);
  const todo = data.todo.filter(i => i.status === "todo").sort((a, b) => a.created_at.localeCompare(b.created_at)).map(vm);
  const cutoff = now.getTime() - 7 * 864e5;
  const done = data.todo.filter(i => i.status === "done" && i.closed_at && new Date(i.closed_at).getTime() >= cutoff)
    .sort((a, b) => b.closed_at!.localeCompare(a.closed_at!)).map(vm);
  const projects = [...new Set([...data.commits.map(c => c.project), ...data.tasks.map(t => t.project),
    ...data.todo.map(i => i.project).filter((p): p is string => !!p)])].sort();
  const ymd = istYmd(now), ws = weekStart(ymd), we = addDays(ws, 6);
  const inWeek = (d: string) => d >= ws && d <= we;
  const weekCommits = data.commits.filter(c => inWeek(istYmd(c.date)));
  return {
    cards: prog.slice(0, CAPS.cards), cardOverflow: prog.slice(CAPS.cards),
    stickies: todo.slice(0, CAPS.stickies), stickyOverflow: todo.slice(CAPS.stickies),
    done,
    pens: projects.map(project => ({ project, ink: inkFor(project, data) })),
    today: { ymd, day: Number(ymd.slice(8)), monthName: now.toLocaleDateString("en-GB", { timeZone: TZ, month: "long" }).toUpperCase(),
      weekday: now.toLocaleDateString("en-GB", { timeZone: TZ, weekday: "long" }) },
    week: { commits: weekCommits.length, tasks: data.tasks.filter(t => inWeek(t.date)).length,
      activeDays: new Set(weekCommits.map(c => istYmd(c.date))).size },
  };
}
```

- [ ] **Step 4: Run the tests to confirm they pass**

Run: `cd desk && npx vitest run test/model.test.ts`
Expected: `9 passed`

- [ ] **Step 5: Commit**

```bash
git add desk/src/data/model.ts desk/test/model.test.ts desk/test/fixture.ts
git commit   # message shown to the user for approval first
```

---

### Task 6: Paper typesetter (layout pure, drawing on canvas)

**Files:**
- Create: `desk/src/paper/layout.ts`, `desk/src/paper/render.ts`
- Test: `desk/test/layout.test.ts`

**Interfaces:**
- Produces: `type Block = { layer: "typed" | "hand"; text: string; size: number; minSize: number; gapBefore: number; underline?: boolean }`.
- Produces: `layoutSides(blocks: Block[], measure: (text: string, layer: Block["layer"], size: number) => number, box: { width: number; height: number }): Side[]`.
  - `Side = Line[]`, and `Line = { layer; text; size; y; underline?: boolean }`.
  - The algorithm wraps by words, shrinks a block's size down to `minSize` if the whole block can then fit on the current side, otherwise spills onto further sides. A word longer than the width is broken by characters. Text is never dropped.
- Produces: `cardBlocks(c: CardVM, kind: "card" | "sticky"): Block[]`, using the B style: the typed title, where-line and commit lines; the handwritten notes and the started remark.
- Produces: `drawSide(ctx: CanvasRenderingContext2D, side: Side, ink: string, seed: string, pxPerUnit: number): void`. It draws the typed layer in `#24201c` Special Elite, and the hand layer in the ink with Caveat, using a seeded per-line jitter of ±1.2° slant, ±4% size and 0.82–1.0 alpha.
- Produces: `seededRandom(seed: string): () => number` (mulberry32 over an FNV-1a hash).

- [ ] **Step 1: Write the failing tests**

`desk/test/layout.test.ts`:
```ts
import { describe, expect, test } from "vitest";
import { layoutSides, seededRandom, type Block } from "../src/paper/layout";

// Monospace stand-in: every character is 0.6 × size wide.
const measure = (t: string, _l: Block["layer"], size: number) => t.length * size * 0.6;
const box = { width: 100, height: 60 };
const b = (text: string, extra: Partial<Block> = {}): Block => ({ layer: "typed", text, size: 10, minSize: 7, gapBefore: 0, ...extra });
const allText = (sides: ReturnType<typeof layoutSides>) => sides.flat().map(l => l.text).join(" ").replace(/\s+/g, " ").trim();

describe("layoutSides", () => {
  test("short text fits on one side at full size", () => {
    const s = layoutSides([b("hello world")], measure, box);
    expect(s).toHaveLength(1);
    expect(s[0][0]).toMatchObject({ text: "hello world", size: 10 });
  });
  test("a block shrinks toward minSize before spilling", () => {
    const words = Array(14).fill("abcd").join(" ");          // too tall at 10, fits at 8
    const s = layoutSides([b(words)], measure, box);
    expect(s).toHaveLength(1);
    expect(s[0][0].size).toBeLessThan(10);
    expect(s[0][0].size).toBeGreaterThanOrEqual(7);
  });
  test("300-char title spills onto further sides and loses nothing", () => {
    const long = Array(60).fill("lorem").join(" ");
    const s = layoutSides([b(long)], measure, box);
    expect(s.length).toBeGreaterThan(1);
    expect(allText(s)).toBe(long);
    for (const side of s) for (const l of side) expect(measure(l.text, l.layer, l.size)).toBeLessThanOrEqual(box.width + 1e-9);
  });
  test("a single word wider than the box is broken by characters", () => {
    const s = layoutSides([b("x".repeat(40))], measure, box);
    expect(allText(s).replace(/ /g, "")).toBe("x".repeat(40));
    for (const l of s.flat()) expect(measure(l.text, l.layer, l.size)).toBeLessThanOrEqual(box.width + 1e-9);
  });
  test("emoji and CJK survive intact", () => {
    const t = "Fix 🔥 upload — 日本語 テスト ✓";
    expect(allText(layoutSides([b(t)], measure, box))).toBe(t);
  });
  test("lines never overflow the box height", () => {
    const s = layoutSides([b(Array(80).fill("word").join(" ")), b("tail", { layer: "hand", gapBefore: 4 })], measure, box);
    for (const side of s) for (const l of side) expect(l.y).toBeLessThanOrEqual(box.height);
  });
});

test("seededRandom is deterministic per seed", () => {
  const a = seededRandom("t-0019"), b2 = seededRandom("t-0019"), c = seededRandom("t-0020");
  const xs = [a(), a(), a()];
  expect([b2(), b2(), b2()]).toEqual(xs);
  expect(c()).not.toBe(xs[0]);
});
```

- [ ] **Step 2: Run them to confirm they fail**

Run: `cd desk && npx vitest run test/layout.test.ts`
Expected: FAIL (`Cannot find module '../src/paper/layout'`)

- [ ] **Step 3: Implement `layout.ts`**

```ts
import type { CardVM } from "../data/model";

export interface Block { layer: "typed" | "hand"; text: string; size: number; minSize: number; gapBefore: number; underline?: boolean }
export interface Line { layer: Block["layer"]; text: string; size: number; y: number; underline?: boolean }
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
      sides[sides.length - 1].push({ layer: blk.layer, text, size, y, underline: blk.underline });
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
```

- [ ] **Step 4: Run the tests to confirm they pass**

Run: `cd desk && npx vitest run test/layout.test.ts`
Expected: `7 passed`

- [ ] **Step 5: Implement `render.ts` (canvas drawing; checked visually in Task 10)**

```ts
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
      ctx.globalAlpha = 0.82 + rnd() * 0.18; ctx.fillStyle = ink;
      ctx.font = `${px * 1.25}px ${FONTS.hand}`;      // Caveat runs small; 1.25 matches typed x-height
      ctx.fillText(l.text, 0, 0);
      if (l.underline) { ctx.fillRect(0, px * 0.18, ctx.measureText(l.text).width, Math.max(1, px * 0.06)); }
    } else {
      ctx.fillStyle = TYPED_INK; ctx.globalAlpha = 0.9 + rnd() * 0.1; ctx.font = `${px}px ${FONTS.typed}`;
      ctx.fillText(l.text, x, y);
      if (l.underline) {                                   // B style: the pen underlines the typed title
        const w = ctx.measureText(l.text).width; ctx.globalAlpha = 0.85; ctx.fillStyle = ink;
        ctx.beginPath(); ctx.moveTo(x, y + px * 0.25);
        for (let t = 0; t <= 1.0001; t += 0.1) ctx.lineTo(x + w * t, y + px * 0.25 + Math.sin(t * 6 + rnd()) * px * 0.04);
        ctx.lineWidth = Math.max(1, px * 0.07); ctx.strokeStyle = ink; ctx.stroke();
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
```

- [ ] **Step 6: Commit**

```bash
git add desk/src/paper desk/test/layout.test.ts
git commit   # message shown to the user for approval first
```

---

### Task 7: Depth rule and object placement (anti-flicker)

**Files:**
- Create: `desk/src/scene/depth.ts`, `desk/src/scene/layout.ts`
- Test: `desk/test/depth.test.ts`

**Interfaces:**
- Produces: `CAMERA = { near: 0.05, far: 4, fov: 32 }`.
- Produces: `depthResolutionAt(distance: number, near: number, far: number, bits = 24): number`. This is the smallest separation in metres the depth buffer can resolve at that distance: `distance² · (far − near) / (far · near · 2^bits)`.
- Produces: `MIN_GAP = 0.0006`, plus the placement constants `DESK`, `MAT`, `CARD_SIZE`, `STICKY_SIZE`, `SHEET_SIZE`, `TRAY`, `CUP`, `BINDER`, `CALENDAR`, `NOTEPAD`, `PAPER_T` and `OVERVIEW` (camera position and target). These are the ones `objects/*` must use.
- Produces: `stackY(base: number, index: number, thickness: number): number`, which returns `base + index * (thickness + MIN_GAP)`.

- [ ] **Step 1: Write the failing test**

`desk/test/depth.test.ts`:
```ts
import { expect, test } from "vitest";
import { CAMERA, MIN_GAP, OVERVIEW, PAPER_T, depthResolutionAt, restOn, stackY } from "../src/scene/depth";

const farthest = Math.hypot(...OVERVIEW.position) + 1.0;  // the overview position plus the far edge of the desk, generously

test("MIN_GAP beats depth-buffer resolution at the farthest viewing distance by ≥ 4×", () => {
  expect(MIN_GAP).toBeGreaterThan(4 * depthResolutionAt(farthest, CAMERA.near, CAMERA.far));
});
test("stacked sheets are separated by thickness + MIN_GAP", () => {
  expect(stackY(0, 3, PAPER_T) - stackY(0, 2, PAPER_T)).toBeCloseTo(PAPER_T + MIN_GAP, 10);
});
// Confirmed cause of the mockup flicker (GPU renders, 14.85% -> 0.77% changed pixels): a model resting at
// exactly the desk height. Anything resting on a surface must sit MIN_GAP above it.
test("objects resting on a surface are never coplanar with it", () => {
  expect(restOn(0) - 0).toBe(MIN_GAP);
  expect(restOn(0.003) - 0.003).toBeCloseTo(MIN_GAP, 12);
});
```

- [ ] **Step 2: Run it to confirm it fails**

Run: `cd desk && npx vitest run test/depth.test.ts`
Expected: FAIL (`Cannot find module '../src/scene/depth'`)

- [ ] **Step 3: Implement `depth.ts` and `layout.ts`**

`desk/src/scene/depth.ts`:
```ts
export const CAMERA = { near: 0.05, far: 4, fov: 32 } as const;
export const MIN_GAP = 0.0006;      // metres between any stacked/overlapping surfaces
export const PAPER_T = 0.0003;      // sheet thickness
export const OVERVIEW = { position: [0.05, 0.62, 0.95] as [number, number, number], target: [-0.02, 0, -0.02] as [number, number, number] };

export function depthResolutionAt(distance: number, near: number, far: number, bits = 24): number {
  return (distance * distance * (far - near)) / (far * near * 2 ** bits);
}
export const stackY = (base: number, index: number, thickness: number) => base + index * (thickness + MIN_GAP);
/** Height for the underside of anything resting on a surface: never exactly coplanar (that is what flickered in the mockup). */
export const restOn = (surfaceY: number) => surfaceY + MIN_GAP;
```

`desk/src/scene/layout.ts`:
```ts
// Where everything sits on the desk (metres; desk top is y = 0, you sit at +z).
export const DESK = { w: 1.6, d: 0.8, h: 0.03 } as const;
export const MAT = { w: 0.72, d: 0.42, t: 0.003, x: -0.05, z: 0.12 } as const;
export const CARD_SIZE = { w: 0.148, d: 0.105 } as const;          // A6 index card
export const STICKY_SIZE = { w: 0.076, d: 0.076 } as const;        // 3" sticky note
export const SHEET_SIZE = { w: 0.21, d: 0.297 } as const;          // A4
export const TRAY = { x: 0.5, z: 0.08, w: 0.25, d: 0.34, h: 0.06, wall: 0.008, rotY: 0.1 } as const;
export const CUP = { x: 0.21, z: -0.2, r: 0.038, h: 0.1 } as const;
export const BINDER = { x: -0.42, z: -0.2, w: 0.24, d: 0.3, h: 0.045, rotY: 0.18 } as const;
export const CALENDAR = { x: -0.1, z: -0.26, w: 0.13, d: 0.08, h: 0.11 } as const;
export const NOTEPAD = { x: 0.33, z: 0.27, w: 0.1, d: 0.14 } as const;
export const STICKY_AREA = { x: 0.48, z: -0.18, cols: 4 } as const;
export const LAMP = { x: -0.66, z: -0.24, rotY: 0.9 } as const;
export const PLANT = { x: 0.68, z: -0.3, scale: 0.55 } as const;
export { CAMERA, MIN_GAP, PAPER_T, OVERVIEW, stackY, restOn } from "./depth";
```

- [ ] **Step 4: Run the tests to confirm they pass**

Run: `cd desk && npx vitest run test/depth.test.ts`
Expected: `3 passed`

- [ ] **Step 5: Commit**

```bash
git add desk/src/scene/depth.ts desk/src/scene/layout.ts desk/test/depth.test.ts
git commit   # message shown to the user for approval first
```

---

### Task 8: Renderer, environment, materials, models, boot

**Files:**
- Create: `desk/src/scene/renderer.ts`, `desk/src/scene/environment.ts`, `desk/src/scene/materials.ts`, `desk/src/scene/models.ts`
- Replace: `desk/src/main.ts`

**Interfaces:**
- Consumes: `ASSETS` (Task 4); `CAMERA`, `OVERVIEW`, `DESK`, `MAT`, `LAMP`, `PLANT` (Task 7); `readData` (Task 3); `buildModel` (Task 5); `loadFonts` (Task 6).
- Produces: `createRenderer(canvas): { renderer, scene, camera, composer, requestRender(): void }`. Rendering is on demand: `requestRender` schedules exactly one frame via `requestAnimationFrame`.
- Produces: `loadEnvironment(renderer, scene, which: "day" | "evening"): Promise<void>`. It sets `scene.environment`, plus `scene.background` with blurriness 0.55.
- Produces: `materials(renderer)`, returning `{ walnut, leather, paper(map?), brass, penBody(hex) }`. Paper materials have `polygonOffset: true, polygonOffsetFactor: -1, polygonOffsetUnits: -1`.
- Produces: `loadModel(spec: { gltf: string; files: Record<string,string> }): Promise<THREE.Group>`. It uses `GLTFLoader.parse` with a `LoadingManager.setURLModifier` that maps relative URIs to the inlined data URLs.
- Produces: `placeOnDesk(obj, x, z, rotY): void`, which sets y so the object's bounding-box bottom sits at y = 0.

- [ ] **Step 1: Implement `renderer.ts`**

```ts
import * as THREE from "three";
import { EffectComposer } from "three/addons/postprocessing/EffectComposer.js";
import { RenderPass } from "three/addons/postprocessing/RenderPass.js";
import { GTAOPass } from "three/addons/postprocessing/GTAOPass.js";
import { OutputPass } from "three/addons/postprocessing/OutputPass.js";
import { CAMERA, OVERVIEW } from "./depth";

export function createRenderer(canvas: HTMLCanvasElement) {
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, powerPreference: "high-performance" });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.AgXToneMapping;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(CAMERA.fov, 1, CAMERA.near, CAMERA.far);
  camera.position.set(...OVERVIEW.position); camera.lookAt(...OVERVIEW.target);
  const composer = new EffectComposer(renderer);
  composer.addPass(new RenderPass(scene, camera));
  const gtao = new GTAOPass(scene, camera);
  gtao.updateGtaoMaterial({ radius: 0.08, distanceExponent: 1.4, thickness: 0.6, scale: 1.0 });
  composer.addPass(gtao);
  composer.addPass(new OutputPass());
  let pending = false;
  const requestRender = () => { if (pending) return; pending = true; requestAnimationFrame(() => { pending = false; composer.render(); }); };
  const resize = () => { const w = canvas.clientWidth, h = canvas.clientHeight; renderer.setSize(w, h, false); composer.setSize(w, h);
    camera.aspect = w / h; camera.updateProjectionMatrix(); requestRender(); };
  new ResizeObserver(resize).observe(canvas); resize();
  return { renderer, scene, camera, composer, requestRender };
}
```

- [ ] **Step 2: Implement `environment.ts`, `materials.ts` and `models.ts`**

`desk/src/scene/environment.ts`:
```ts
import * as THREE from "three";
import { HDRLoader } from "three/addons/loaders/HDRLoader.js";
import { ASSETS } from "../assets";

export async function loadEnvironment(renderer: THREE.WebGLRenderer, scene: THREE.Scene, which: "day" | "evening") {
  const tex = await new HDRLoader().loadAsync(which === "day" ? ASSETS.hdri.blinds : ASSETS.hdri.cabin);
  tex.mapping = THREE.EquirectangularReflectionMapping;
  const pmrem = new THREE.PMREMGenerator(renderer);
  scene.environment = pmrem.fromEquirectangular(tex).texture;
  scene.background = tex; scene.backgroundBlurriness = 0.55; scene.backgroundIntensity = 0.8; scene.environmentIntensity = 1.0;
  pmrem.dispose();
  // Plan 1 daylight key: window sun through the blinds direction.
  const sun = new THREE.DirectionalLight(0xfff1e0, 2.2);
  sun.position.set(1.4, 1.6, 0.6); sun.castShadow = true; sun.shadow.mapSize.set(2048, 2048); sun.shadow.radius = 10; sun.shadow.bias = -0.0002;
  Object.assign(sun.shadow.camera, { left: -1, right: 1, top: 1, bottom: -1, near: 0.1, far: 5 });
  scene.add(sun);
}
```

`desk/src/scene/materials.ts`:
```ts
import * as THREE from "three";
import { ASSETS } from "../assets";

export function materials(renderer: THREE.WebGLRenderer) {
  const aniso = renderer.capabilities.getMaxAnisotropy();
  const tl = new THREE.TextureLoader();
  const tex = (url: string, srgb: boolean, rx: number, ry: number) => { const t = tl.load(url); if (srgb) t.colorSpace = THREE.SRGBColorSpace;
    t.wrapS = t.wrapT = THREE.RepeatWrapping; t.repeat.set(rx, ry); t.anisotropy = aniso; return t; };
  const walnut = new THREE.MeshPhysicalMaterial({ map: tex(ASSETS.walnut.map, true, 1.6, 0.8), normalMap: tex(ASSETS.walnut.normal, false, 1.6, 0.8),
    roughnessMap: tex(ASSETS.walnut.rough, false, 1.6, 0.8), roughness: 1, clearcoat: 0.6, clearcoatRoughness: 0.18 });
  const leather = new THREE.MeshPhysicalMaterial({ map: tex(ASSETS.leather.map, true, 1.5, 0.75), normalMap: tex(ASSETS.leather.normal, false, 1.5, 0.75),
    roughnessMap: tex(ASSETS.leather.rough, false, 1.5, 0.75), sheen: 0.4, sheenRoughness: 0.6, sheenColor: new THREE.Color(0x6b4a33) });
  const fibre = fibreNormal();
  const paper = (map?: THREE.Texture, color = 0xefe8da) => new THREE.MeshPhysicalMaterial({ map: map ?? null, color: map ? 0xffffff : color,
    roughness: 0.92, normalMap: fibre, normalScale: new THREE.Vector2(0.35, 0.35), sheen: 0.25, sheenRoughness: 0.9,
    polygonOffset: true, polygonOffsetFactor: -1, polygonOffsetUnits: -1 });
  const brass = new THREE.MeshPhysicalMaterial({ color: 0xc9a46a, metalness: 1, roughness: 0.32, anisotropy: 0.7, clearcoat: 0.2, side: THREE.DoubleSide });
  const penBody = (hex: string) => new THREE.MeshPhysicalMaterial({ color: hex, roughness: 0.25, clearcoat: 1, clearcoatRoughness: 0.08 });
  return { walnut, leather, paper, brass, penBody };
}

function fibreNormal(): THREE.Texture {
  const c = document.createElement("canvas"); c.width = c.height = 512; const g = c.getContext("2d")!;
  g.fillStyle = "rgb(128,128,255)"; g.fillRect(0, 0, 512, 512);
  for (let i = 0; i < 9000; i++) { const x = Math.random() * 512, y = Math.random() * 512, a = Math.random() * Math.PI, l = 3 + Math.random() * 14;
    g.strokeStyle = `rgba(${110 + Math.random() * 40},${110 + Math.random() * 40},255,0.35)`; g.lineWidth = 0.6;
    g.beginPath(); g.moveTo(x, y); g.lineTo(x + Math.cos(a) * l, y + Math.sin(a) * l); g.stroke(); }
  const t = new THREE.CanvasTexture(c); t.wrapS = t.wrapT = THREE.RepeatWrapping; return t;
}
```

`desk/src/scene/models.ts`:
```ts
import * as THREE from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { restOn } from "./depth";

export function loadModel(spec: { gltf: string; files: Record<string, string> }): Promise<THREE.Group> {
  const manager = new THREE.LoadingManager();
  manager.setURLModifier(url => { const key = Object.keys(spec.files).find(k => url.endsWith(k)); return key ? spec.files[key] : url; });
  return new Promise((resolve, reject) => new GLTFLoader(manager).parse(spec.gltf, "", g => {
    g.scene.traverse(n => { if ((n as THREE.Mesh).isMesh) n.castShadow = n.receiveShadow = true; });
    resolve(g.scene);
  }, reject));
}

export function placeOnDesk(obj: THREE.Object3D, x: number, z: number, rotY = 0) {
  obj.position.set(x, 0, z); obj.rotation.y = rotY; obj.updateMatrixWorld(true);
  const box = new THREE.Box3().setFromObject(obj); obj.position.y += restOn(0) - box.min.y;   // never coplanar with the desk
}
```

- [ ] **Step 3: Replace `main.ts` (boot with WebGL fallback; objects are added in Task 9)**

```ts
import * as THREE from "three";
import { ASSETS } from "./assets";
import { readData, type DeskData } from "./data/types";
import { buildModel } from "./data/model";
import { loadFonts } from "./paper/render";
import { createRenderer } from "./scene/renderer";
import { loadEnvironment } from "./scene/environment";
import { materials } from "./scene/materials";
import { loadModel, placeOnDesk } from "./scene/models";
import { DESK, MAT, LAMP, PLANT } from "./scene/layout";
import { buildObjects } from "./objects";

async function getData(): Promise<DeskData> {
  return readData() ?? (await (await fetch("/dev-data.json")).json());    // dev server fallback
}

function webglOK(): boolean {
  try { return !!document.createElement("canvas").getContext("webgl2"); } catch { return false; }
}

async function boot() {
  const canvas = document.getElementById("desk") as HTMLCanvasElement;
  if (!webglOK()) { document.getElementById("loading")!.remove(); (document.getElementById("fallback")!).style.display = "grid"; return; }
  const [data] = await Promise.all([getData(), loadFonts(ASSETS.fonts.caveat, ASSETS.fonts.specialElite)]);
  const model = buildModel(data, new Date());
  const { renderer, scene, requestRender } = createRenderer(canvas);
  canvas.addEventListener("webglcontextlost", e => { e.preventDefault(); });
  canvas.addEventListener("webglcontextrestored", () => location.reload());
  const m = materials(renderer);

  const desk = new THREE.Mesh(new THREE.BoxGeometry(DESK.w, DESK.h, DESK.d), m.walnut);
  desk.position.y = -DESK.h / 2; desk.receiveShadow = true; scene.add(desk);
  const mat = new THREE.Mesh(new THREE.BoxGeometry(MAT.w, MAT.t, MAT.d), m.leather);
  mat.position.set(MAT.x, MAT.t / 2, MAT.z); mat.receiveShadow = mat.castShadow = true; scene.add(mat);

  const [lamp, plant] = await Promise.all([loadModel(ASSETS.models.lamp), loadModel(ASSETS.models.plant), loadEnvironment(renderer, scene, "day")]);
  placeOnDesk(lamp, LAMP.x, LAMP.z, LAMP.rotY); scene.add(lamp);
  plant.scale.setScalar(PLANT.scale); placeOnDesk(plant, PLANT.x, PLANT.z); scene.add(plant);

  buildObjects(scene, model, m, MAT.t);
  requestRender();
  const loading = document.getElementById("loading")!;
  loading.style.opacity = "0"; setTimeout(() => loading.remove(), 700);
  (window as any).__deskReady = true;   // browser checks wait on this
}
boot().catch(err => { console.error(err); document.getElementById("loading")!.textContent = "The desk failed to load: " + err.message; });
```

- [ ] **Step 4: Type-check (objects come in Task 9, so expect exactly that error)**

Run: `cd desk && npx tsc --noEmit`
Expected: one error, `Cannot find module './objects'`, and nothing else.

---

### Task 9: Desk objects

**Files:**
- Create: `desk/src/objects/slots.ts` (pure placement), `desk/src/objects/index.ts`, `desk/src/objects/paperObjects.ts` (cards, stickies, done tray), `desk/src/objects/pens.ts`, `desk/src/objects/stationery.ts` (calendar, notepad, binders)
- Test: `desk/test/objects.test.ts` (placement only, no WebGL needed)

**Interfaces:**
- Consumes: `DeskModel` (Task 5); `cardBlocks`, `layoutSides` (Task 6); `drawPaper`, `drawSide`, `canvasMeasure` (Task 6); layout constants (Task 7); `materials` (Task 8).
- Produces: `buildObjects(scene, model, m, matTop): void`.
- Produces: `cardSlots(n: number): { x: number; z: number; rotY: number }[]`, `stickySlots(n: number)` and `trayStack(n: number): { y: number; jitterX: number; jitterZ: number; rotY: number }[]`. These are pure functions, tested here.

- [ ] **Step 1: Write the failing placement tests**

`desk/test/objects.test.ts`:
```ts
import { expect, test } from "vitest";
import { cardSlots, stickySlots, trayStack } from "../src/objects/slots";
import { CARD_SIZE, MAT, MIN_GAP, PAPER_T, STICKY_SIZE } from "../src/scene/layout";

test("up to 6 card slots, all fully on the leather mat, not overlapping", () => {
  const s = cardSlots(6);
  for (const p of s) {
    expect(Math.abs(p.x - MAT.x) + CARD_SIZE.w / 2).toBeLessThanOrEqual(MAT.w / 2);
    expect(Math.abs(p.z - MAT.z) + CARD_SIZE.d / 2).toBeLessThanOrEqual(MAT.d / 2);
  }
  for (let i = 0; i < s.length; i++) for (let j = i + 1; j < s.length; j++)
    expect(Math.abs(s[i].x - s[j].x) >= CARD_SIZE.w * 0.95 || Math.abs(s[i].z - s[j].z) >= CARD_SIZE.d * 0.95).toBe(true);
});
test("sticky slots don't overlap", () => {
  const s = stickySlots(8);
  for (let i = 0; i < s.length; i++) for (let j = i + 1; j < s.length; j++)
    expect(Math.abs(s[i].x - s[j].x) >= STICKY_SIZE.w || Math.abs(s[i].z - s[j].z) >= STICKY_SIZE.d).toBe(true);
});
test("tray stack: every sheet clears the one below by ≥ MIN_GAP; empty tray = no sheets", () => {
  expect(trayStack(0)).toEqual([]);
  const s = trayStack(25);
  for (let i = 1; i < s.length; i++) expect(s[i].y - s[i - 1].y).toBeGreaterThanOrEqual(PAPER_T + MIN_GAP - 1e-12);
});
```

- [ ] **Step 2: Run it to confirm it fails**

Run: `cd desk && npx vitest run test/objects.test.ts`
Expected: FAIL (`Cannot find module '../src/objects/slots'`)

- [ ] **Step 3: Implement the slots (pure)**

`desk/src/objects/slots.ts`:
```ts
import { CARD_SIZE, MAT, PAPER_T, STICKY_AREA, STICKY_SIZE, TRAY, stackY } from "../scene/layout";
import { seededRandom } from "../paper/layout";

export function cardSlots(n: number) {
  const cols = 3, gapX = 0.022, gapZ = 0.03, r = seededRandom("cards");
  const x0 = MAT.x - (cols - 1) / 2 * (CARD_SIZE.w + gapX), z0 = MAT.z - (CARD_SIZE.d + gapZ) / 2;
  return [...Array(Math.min(n, 6))].map((_, i) => ({ x: x0 + (i % cols) * (CARD_SIZE.w + gapX), z: z0 + Math.floor(i / cols) * (CARD_SIZE.d + gapZ),
    rotY: (r() - 0.5) * 0.05 }));
}
export function stickySlots(n: number) {
  const r = seededRandom("stickies"), gap = 0.012;
  return [...Array(Math.min(n, 8))].map((_, i) => ({ x: STICKY_AREA.x + (i % STICKY_AREA.cols - 1.5) * (STICKY_SIZE.w + gap),
    z: STICKY_AREA.z + Math.floor(i / STICKY_AREA.cols) * (STICKY_SIZE.d + gap), rotY: (r() - 0.5) * 0.12 }));
}
export function trayStack(n: number) {
  const r = seededRandom("tray"), floor = TRAY.wall;
  return [...Array(n)].map((_, i) => ({ y: stackY(floor, i, PAPER_T), jitterX: (r() - 0.5) * 0.006, jitterZ: (r() - 0.5) * 0.006, rotY: (r() - 0.5) * 0.03 }));
}
```

- [ ] **Step 4: Run the tests to confirm they pass**

Run: `cd desk && npx vitest run test/objects.test.ts`
Expected: `3 passed`

- [ ] **Step 5: Implement the object builders**

`desk/src/objects/paperObjects.ts`:
```ts
import * as THREE from "three";
import type { CardVM, DeskModel } from "../data/model";
import { cardBlocks, layoutSides } from "../paper/layout";
import { canvasMeasure, drawPaper, drawSide } from "../paper/render";
import { CARD_SIZE, PAPER_T, SHEET_SIZE, STICKY_SIZE, TRAY } from "../scene/layout";
import type { materials } from "../scene/materials";
import { cardSlots, stickySlots, trayStack } from "./slots";

type M = ReturnType<typeof materials>;
const PX_PER_MM = 6;   // overview resolution; Plan 2 re-renders the focused card at 24 px/mm

function textureFor(c: CardVM, kind: "card" | "sticky" | "sheet", wMm: number, hMm: number, base: string) {
  const canvas = document.createElement("canvas"); canvas.width = Math.round(wMm * PX_PER_MM); canvas.height = Math.round(hMm * PX_PER_MM);
  const ctx = canvas.getContext("2d")!;
  drawPaper(ctx, canvas.width, canvas.height, base, c.id);
  const sides = layoutSides(cardBlocks(c, kind === "sticky" ? "sticky" : "card"), canvasMeasure(), { width: wMm - 12, height: hMm - 12 });
  drawSide(ctx, sides[0], c.ink.hex, c.id, PX_PER_MM);
  const t = new THREE.CanvasTexture(canvas); t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 8;
  return { texture: t, sides: sides.length };
}

function sheet(m: M, w: number, d: number, top: THREE.Texture | null, y: number) {
  const edge = m.paper(undefined), face = m.paper(top ?? undefined);
  const mesh = new THREE.Mesh(new THREE.BoxGeometry(w, PAPER_T, d), [edge, edge, face, edge, edge, edge]);
  mesh.position.y = y; mesh.castShadow = mesh.receiveShadow = true; return mesh;
}

export function addCards(scene: THREE.Scene, model: DeskModel, m: M, matTop: number) {
  cardSlots(model.cards.length).forEach((s, i) => {
    const { texture } = textureFor(model.cards[i], "card", CARD_SIZE.w * 1000, CARD_SIZE.d * 1000, "#f1ebde");
    const card = sheet(m, CARD_SIZE.w, CARD_SIZE.d, texture, matTop + PAPER_T / 2 + 0.0006);
    card.position.x = s.x; card.position.z = s.z; card.rotation.y = s.rotY; card.name = "card:" + model.cards[i].id; scene.add(card);
  });
  if (!model.cards.length && !model.stickies.length) {   // spec §8: an empty desk gets one note
    const note: CardVM = { id: "empty", title: "Nothing on the go", where: "", ink: { hex: "#2d2b29", name: "", variant: 0 }, notes: [], commits: [], started: null };
    const { texture } = textureFor(note, "sticky", 76, 76, "#f4d675");
    const s = sheet(m, STICKY_SIZE.w, STICKY_SIZE.d, texture, matTop + PAPER_T / 2 + 0.0006); s.position.set(-0.05, s.position.y, 0.12); scene.add(s);
  }
}

export function addStickies(scene: THREE.Scene, model: DeskModel, m: M) {
  stickySlots(model.stickies.length).forEach((s, i) => {
    const { texture } = textureFor(model.stickies[i], "sticky", STICKY_SIZE.w * 1000, STICKY_SIZE.d * 1000, "#f4d675");
    const note = sheet(m, STICKY_SIZE.w, STICKY_SIZE.d, texture, PAPER_T / 2 + 0.0006);
    note.position.x = s.x; note.position.z = s.z; note.rotation.y = s.rotY; note.name = "sticky:" + model.stickies[i].id; scene.add(note);
  });
}

export function addTray(scene: THREE.Scene, model: DeskModel, m: M, wood: THREE.Material) {
  const tray = new THREE.Group(); tray.position.set(TRAY.x, 0, TRAY.z); tray.rotation.y = TRAY.rotY; tray.name = "tray";
  const part = (w: number, h: number, d: number, x: number, y: number, z: number) => {
    const p = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), wood); p.position.set(x, y, z); p.castShadow = p.receiveShadow = true; tray.add(p); };
  part(TRAY.w, TRAY.wall, TRAY.d, 0, TRAY.wall / 2, 0);
  part(TRAY.wall, TRAY.h, TRAY.d, -TRAY.w / 2, TRAY.h / 2, 0); part(TRAY.wall, TRAY.h, TRAY.d, TRAY.w / 2, TRAY.h / 2, 0);
  part(TRAY.w, TRAY.h * 0.6, TRAY.wall, 0, TRAY.h * 0.3, -TRAY.d / 2);
  trayStack(model.done.length).forEach((s, i) => {
    const isTop = i === model.done.length - 1;
    const tex = isTop ? textureFor(model.done[0], "sheet", SHEET_SIZE.w * 1000, SHEET_SIZE.d * 1000, "#f5f0e6").texture : null;
    const sh = sheet(m, SHEET_SIZE.w, SHEET_SIZE.d, tex, s.y + PAPER_T / 2);
    sh.position.x = s.jitterX; sh.position.z = s.jitterZ; sh.rotation.y = s.rotY; tray.add(sh);
  });
  scene.add(tray);
}
```

`desk/src/objects/pens.ts`:
```ts
import * as THREE from "three";
import type { DeskModel } from "../data/model";
import { CUP } from "../scene/layout";
import type { materials } from "../scene/materials";

export function addPenCup(scene: THREE.Scene, model: DeskModel, m: ReturnType<typeof materials>) {
  const cup = new THREE.Mesh(new THREE.CylinderGeometry(CUP.r, CUP.r * 0.95, CUP.h, 64, 1, true), m.brass);
  cup.position.set(CUP.x, CUP.h / 2, CUP.z); cup.castShadow = cup.receiveShadow = true; scene.add(cup);
  const base = new THREE.Mesh(new THREE.CircleGeometry(CUP.r * 0.95, 48), m.brass);
  base.rotation.x = -Math.PI / 2; base.position.set(CUP.x, 0.0015, CUP.z); scene.add(base);
  model.pens.forEach((p, i) => {
    const pen = new THREE.Group(); pen.name = "pen:" + p.project;
    const body = new THREE.Mesh(new THREE.CylinderGeometry(0.0055, 0.0055, 0.14, 24), m.penBody(p.ink.hex));
    const capBand = new THREE.Mesh(new THREE.CylinderGeometry(0.0058, 0.0058, 0.004, 24),
      new THREE.MeshPhysicalMaterial({ color: p.ink.variant ? 0xc0c0c0 : 0xd4af6a, metalness: 1, roughness: 0.25 }));   // overflow variants get silver trim
    capBand.position.y = 0.035; body.castShadow = true; pen.add(body, capBand);
    if (i < 7) {
      const a = i * 2.4, r = CUP.r * 0.45;
      pen.position.set(CUP.x + Math.cos(a) * r, 0.1, CUP.z + Math.sin(a) * r); pen.rotation.set(Math.sin(a) * 0.18, a, Math.cos(a) * 0.18);
    } else {                                                                                    // spec §4: overflow pens lie beside the cup
      pen.rotation.set(0, 0.3 + (i - 7) * 0.12, Math.PI / 2); pen.position.set(CUP.x + 0.08, 0.0056 + (i - 7) * 0.0118, CUP.z + 0.03 + (i - 7) * 0.016);
    }
    scene.add(pen);
  });
}
```

`desk/src/objects/stationery.ts`:
```ts
import * as THREE from "three";
import type { DeskModel } from "../data/model";
import { drawPaper } from "../paper/render";
import { BINDER, CALENDAR, NOTEPAD, PAPER_T } from "../scene/layout";
import type { materials } from "../scene/materials";

type M = ReturnType<typeof materials>;
const canvasTex = (w: number, h: number, draw: (g: CanvasRenderingContext2D) => void) => {
  const c = document.createElement("canvas"); c.width = w; c.height = h; draw(c.getContext("2d")!);
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 8; return t; };

export function addCalendar(scene: THREE.Scene, model: DeskModel, m: M) {
  const face = canvasTex(520, 440, g => { drawPaper(g, 520, 440, "#ece5d6", "cal");
    g.fillStyle = "#7a1414"; g.font = "44px 'Special Elite'"; g.textAlign = "center"; g.fillText(model.today.monthName, 260, 90);
    g.fillStyle = "#231a14"; g.font = "bold 210px Georgia, serif"; g.fillText(String(model.today.day), 260, 300);
    g.font = "40px 'Caveat'"; g.fillText(model.today.weekday, 260, 380); });
  const easel = new THREE.Mesh(new THREE.BoxGeometry(CALENDAR.w, CALENDAR.h, 0.004), [m.paper(), m.paper(), m.paper(), m.paper(), m.paper(face), m.paper()]);
  easel.position.set(CALENDAR.x, CALENDAR.h / 2 * Math.cos(0.3), CALENDAR.z); easel.rotation.x = -0.3; easel.castShadow = true; easel.name = "calendar";
  scene.add(easel);
}

export function addNotepad(scene: THREE.Scene, model: DeskModel, m: M) {
  const face = canvasTex(400, 560, g => { drawPaper(g, 400, 560, "#f6efe0", "pad");
    g.strokeStyle = "rgba(110,140,190,.45)"; for (let y = 120; y < 540; y += 52) { g.beginPath(); g.moveTo(24, y); g.lineTo(376, y); g.stroke(); }
    g.fillStyle = "#2d2b29"; g.font = "40px 'Caveat'";
    g.fillText("This week", 30, 100); g.fillText(`commits   ${model.week.commits}`, 30, 164);
    g.fillText(`tasks     ${model.week.tasks}`, 30, 216); g.fillText(`active days  ${model.week.activeDays}`, 30, 268); });
  const pad = new THREE.Group(); pad.name = "notepad";
  for (let i = 0; i < 12; i++) {                                                    // a pad is a stack of real sheets
    const top = i === 11;
    const s = new THREE.Mesh(new THREE.BoxGeometry(NOTEPAD.w, PAPER_T, NOTEPAD.d), top ? [m.paper(), m.paper(), m.paper(face), m.paper(), m.paper(), m.paper()] : m.paper());
    s.position.y = PAPER_T / 2 + i * (PAPER_T + 0.0006); s.castShadow = s.receiveShadow = true; pad.add(s);
  }
  pad.position.set(NOTEPAD.x, 0, NOTEPAD.z); pad.rotation.y = -0.35; scene.add(pad);
}

export function addBinders(scene: THREE.Scene, m: M) {
  const tints = [0x6b2f22, 0x2f4a3a, 0x2c3b58], labels = ["DAY", "WEEK", "MONTH"];
  labels.forEach((label, i) => {
    const cover = m.leather.clone(); cover.color = new THREE.Color(tints[i]);
    const spineLabel = canvasTex(512, 96, g => { drawPaper(g, 512, 96, "#ece5d6", label); g.fillStyle = "#231a14"; g.font = "52px 'Special Elite'";
      g.textAlign = "center"; g.fillText(label, 256, 66); });
    const b = new THREE.Mesh(new THREE.BoxGeometry(BINDER.w, BINDER.h, BINDER.d), [cover, cover, cover, cover, cover, cover]);
    b.position.set(BINDER.x + i * 0.012, BINDER.h / 2 + i * (BINDER.h + 0.0006), BINDER.z - i * 0.01); b.rotation.y = BINDER.rotY - i * 0.06;
    b.castShadow = b.receiveShadow = true; b.name = "binder:" + label.toLowerCase();
    const tag = new THREE.Mesh(new THREE.PlaneGeometry(0.14, 0.026), m.paper(spineLabel));
    tag.position.set(0, 0, BINDER.d / 2 + 0.0006); b.add(tag);                      // label on the spine edge, facing you
    scene.add(b);
  });
}
```

`desk/src/objects/index.ts`:
```ts
import * as THREE from "three";
import type { DeskModel } from "../data/model";
import type { materials } from "../scene/materials";
import { addCards, addStickies, addTray } from "./paperObjects";
import { addPenCup } from "./pens";
import { addBinders, addCalendar, addNotepad } from "./stationery";

export function buildObjects(scene: THREE.Scene, model: DeskModel, m: ReturnType<typeof materials>, matTop: number) {
  addCards(scene, model, m, matTop);
  addStickies(scene, model, m);
  addTray(scene, model, m, m.walnut);
  addPenCup(scene, model, m);
  addCalendar(scene, model, m);
  addNotepad(scene, model, m);
  addBinders(scene, m);
}
```

- [ ] **Step 6: Type-check and run the whole vitest suite**

Run: `cd desk && npx tsc --noEmit && npx vitest run`
Expected: no type errors; `24 passed` (1 build-slot + 1 check-assets + 9 model + 7 layout + 3 depth + 3 objects).

- [ ] **Step 7: Commit (Tasks 8 and 9 together, since Task 8 alone doesn't type-check)**

```bash
git add desk/src
git add desk/test/objects.test.ts
git commit   # message shown to the user for approval first
```

---

### Task 10: Build, verify in the browser, document

**Files:**
- Modify: `README.md` (add "3D desk" section)

**Interfaces:**
- Consumes: everything above.

- [ ] **Step 1: Production build plus data injection**

Run: `cd desk && npm run build && cd .. && python3 build.py && ls -l desk.html`
Expected: `built .../desk.html`. The size must be at most 26,214,400 bytes (25 MB); check with `stat -f %z desk.html`.

- [ ] **Step 2: Browser check from disk (Playwright, or headless Chrome if Playwright is unavailable)**

Serve over a local HTTP server only for automation (`python3 -m http.server 8765 --bind 127.0.0.1`), then:
1. Open `desk.html`.
2. Wait for `window.__deskReady === true`.
3. Assert no console errors.
4. Take a screenshot at 1600×900.
5. Also open `file:///…/desk.html` directly in the user's Chrome (`open desk.html`) and confirm it renders without a server.

Check these, and record the screenshot:
- the cards show their typed titles with ink underlines;
- the sticky notes are yellow, with handwriting in the right inks;
- the tray holds one sheet per done task;
- there's one pen per project, each in its own ink;
- the calendar shows today's IST date, and the notepad shows this week's tallies;
- the binders are labelled DAY / WEEK / MONTH;
- the lamp and plant sit on the desk, not floating or sunk into it.

- [ ] **Step 3: Flicker sweep**

In the browser, step the camera through 60 positions on a slow arc around `OVERVIEW` (±0.15 m in x, ±0.03 m in y), rendering each. Compare consecutive frames over the paper regions (cards, tray, notepad). Fail if any 4×4 pixel block's luminance changes by more than 25% between adjacent positions while its neighbours change by less than 3%; that pattern is z-fighting, not parallax. Record the result. Expected: 0 flagged blocks.

- [ ] **Step 4: Performance and idle**

- **Frame rate:** with the scene static, record frames for 2 s using `performance.now()` around `composer.render` via a temporary counter. Expected: **0 renders** while idle (render on demand).
- **Load time:** time to `__deskReady` from disk. Expected: under 3 s on the user's Mac.

- [ ] **Step 5: Document**

Add to `README.md`, after "Using it":
```markdown
## 3D desk (optional showpiece)

A photoreal desk view of the same data, built with three.js.

    cd desk && npm install && npm run assets && npm run build   # once, and after desk code changes
    tracker desk            # open it (tracker desk refresh: rescan git first)

`build.py` writes `desk.html` next to `dashboard.html` whenever `desk-template.html` exists, so the 5pm refresh keeps it current.
Project inks: `python3 inks.py list` / `python3 inks.py set <project> <ink-id>` (palette in `desk/src/data/inks.json`).
Assets are CC0 from Poly Haven, pinned with checksums in `desk/assets.lock.json`; fonts are Caveat (OFL) and Special Elite (Apache 2.0).
```

- [ ] **Step 6: Full test run, then commit**

Run: `.venv/bin/python -m pytest tests -q && (cd desk && npx vitest run)`
Expected: `38 passed` (pytest) and `24 passed` (vitest).
```bash
git add README.md
git commit   # message shown to the user for approval first, including the test output above
```
Push only with explicit approval (CLAUDE.md §6).
