"""The `tracker` command."""
import argparse
import contextlib
import sys
import webbrowser
from datetime import date, datetime
from pathlib import Path

from . import __version__, build, config, inks, paths, scan, schedule, server, setup, summarise, todo
from .errors import TrackerError

NO_CONFIG_NEEDED = ("init", "migrate")


def build_parser():
    ap = argparse.ArgumentParser(prog="tracker")
    ap.add_argument("--version", action="version", version="tracker " + __version__)
    sub = ap.add_subparsers(dest="cmd")
    n = sub.add_parser("init", help="create the config (asks for anything you don't pass)")
    n.add_argument("--root", help="folder that contains your git repos"); n.add_argument("--email", action="append", help="an email you commit as (repeatable)")
    n.add_argument("--timezone", help="IANA name for day boundaries, e.g. Europe/London (default: this computer's)")
    n.add_argument("--summariser", help="command that reads a prompt on stdin and prints JSON, e.g. 'claude -p --model sonnet'")
    n.add_argument("--no-summariser", action="store_true"); n.add_argument("--force", action="store_true", help="overwrite an existing config")
    m = sub.add_parser("migrate", help="move data from an old checkout into the data folder")
    m.add_argument("--from", dest="src", help="folder holding the old config.json / todo.json (default: this checkout)")
    a = sub.add_parser("add", help="add a task; prints its id")
    a.add_argument("title"); a.add_argument("-p", "--project"); a.add_argument("-r", "--repo"); a.add_argument("--plan")
    for c in ("start", "done", "drop"):
        sub.add_parser(c).add_argument("id")
    p = sub.add_parser("pause"); p.add_argument("id"); p.add_argument("reason", nargs="?", default="")
    n = sub.add_parser("note"); n.add_argument("id"); n.add_argument("text")
    sub.add_parser("todo").add_argument("--all", action="store_true")
    sub.add_parser("open", help="open the dashboard (through the edit server)")
    sub.add_parser("serve", help="run the edit server in the foreground")
    d = sub.add_parser("desk", help="open the 3D desk"); d.add_argument("refresh", nargs="?", choices=["refresh"])
    r = sub.add_parser("refresh", help="rescan git, summarise, rebuild"); r.add_argument("--quiet", action="store_true")
    s = sub.add_parser("scan"); s.add_argument("--days", type=int, default=14); s.add_argument("--since")
    sub.add_parser("summarise").add_argument("--backfill-threads", action="store_true")
    sub.add_parser("build")
    sc = sub.add_parser("schedule", help="daily refresh: on / off / status")
    sc.add_argument("action", choices=["on", "off", "status"]); sc.add_argument("--at", default="17:00", help="HH:MM, 24-hour (default 17:00)")
    i = sub.add_parser("inks", help="project ink colours for the desk"); i.add_argument("args", nargs="*")
    return ap


class _Tee:
    """Write to refresh.log and, unless quiet, to the terminal."""
    def __init__(self, log, quiet):
        self.log, self.quiet = log, quiet

    def write(self, text):
        self.log.write(text)
        if not self.quiet:
            sys.__stdout__.write(text)
        return len(text)

    def flush(self):
        self.log.flush()


def refresh(quiet=False):
    """scan -> summarise -> build, logged to refresh.log (what the scheduled job runs)."""
    paths.home().mkdir(parents=True, exist_ok=True)
    with open(paths.file("refresh.log"), "a", encoding="utf-8") as log:
        out = _Tee(log, quiet)
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            print("=== %s refresh start" % datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            try:
                scan.run()
            except TrackerError as e:
                print("scan failed: %s" % e)
                raise
            try:
                summarise.run()
            except TrackerError as e:
                print("summarise failed (%s); new commits stay 'unsummarised'" % e)
            build.build()
            print("=== done")


def run_init(args):
    root, emails, tz = args.root, args.email or [], args.timezone
    summariser = [] if args.no_summariser else split_or_none(args.summariser)
    if sys.stdin.isatty():   # ask for whatever wasn't passed
        try:
            root = root or input("Folder that contains your git repos (e.g. ~/code): ")
            emails = emails or input("Email(s) you commit as, comma-separated: ").split(",")
            if tz is None:
                default = setup.detect_timezone()
                tz = input("Timezone for day boundaries [%s] (blank = this computer's zone): " % (default or "this computer's zone")).strip() or default
            if summariser is None:
                default = setup.default_summariser()
                shown = " ".join(default) if default else "none"
                ans = input("Command that writes summaries (prompt on stdin, JSON out), or 'none' [%s]: " % shown).strip()
                summariser = [] if ans.lower() == "none" else setup.split_command(ans) if ans else default
        except EOFError:     # Windows reports isatty() True for NUL, which is what scripts and agents get
            raise TrackerError("--root and --email are required when not running interactively") from None
    elif not root or not emails:
        raise TrackerError("--root and --email are required when not running interactively")
    elif summariser is None:
        summariser = setup.default_summariser()
    path = setup.init(root, emails, tz, summariser or None, args.force)
    print("Wrote %s\nNext: tracker scan --days 30   then   tracker" % path)


def split_or_none(line):
    return setup.split_command(line) if line else None


def run_migrate(args):
    src = Path(args.src) if args.src else setup.default_source()
    names = setup.migrate(src, date.today())
    print("Moved %s from %s to %s\nThe originals were renamed *.migrated-%s so nothing old keeps writing to them." % (
        ", ".join(names), src, paths.home(), date.today().strftime("%Y%m%d")))
    try:
        build.build()
    except TrackerError as e:
        print("warning: couldn't build the dashboard yet (%s)" % e, file=sys.stderr)


def dispatch(args):
    c = args.cmd
    if c == "init":
        run_init(args)
    elif c == "migrate":
        run_migrate(args)
    elif c == "add":
        print(todo.add(args.title, args.project, args.repo, args.plan)["id"])
    elif c in ("start", "done", "drop"):
        it, changed = todo.set_status(args.id, c)
        new = {"start": "in_progress", "done": "done", "drop": "dropped"}[c]
        print(todo.fmt(it) if changed else "already %s: %s" % (new, todo.fmt(it)))
    elif c == "pause":
        it, changed = todo.pause(args.id, args.reason)
        print(todo.fmt(it) if changed else "already paused: " + todo.fmt(it))
    elif c == "note":
        print(todo.fmt(todo.note(args.id, args.text)))
    elif c == "todo":
        print("\n".join(todo.fmt(i) for i in todo.list_items(args.all)) or "no open tasks")
    elif c in (None, "open"):
        server.open_dashboard()
    elif c == "serve":
        server.serve()
    elif c == "desk":
        if args.refresh:
            print("Refreshing (about a minute)...")
            refresh()
        page = paths.file("desk.html")
        if not page.exists():
            raise TrackerError("desk not built yet: cd desk && npm install && npm run assets && npm run build")
        webbrowser.open(page.as_uri())
    elif c == "refresh":
        if not args.quiet:
            print("Refreshing (about a minute)...")
        refresh(args.quiet)
        if not args.quiet:
            server.open_dashboard()
    elif c == "scan":
        scan.run(args.days, args.since)
    elif c == "summarise":
        summarise.run(args.backfill_threads)
    elif c == "build":
        build.build()
    elif c == "schedule":
        if args.action == "on":
            schedule.on(args.at)
        elif args.action == "off":
            schedule.off()
        else:
            print(schedule.status())
    elif c == "inks":
        inks.main(args.args)


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        if args.cmd not in NO_CONFIG_NEEDED:
            config.load()   # every command needs a config; fail with one clear line if there isn't one
        dispatch(args)
    except TrackerError as e:
        print(str(e), file=sys.stderr)
        return 1
    return 0
