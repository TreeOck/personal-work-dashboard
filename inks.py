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
