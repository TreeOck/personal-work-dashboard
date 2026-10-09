"""Local settings from config.json (gitignored). See config.example.json."""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
_path = os.path.join(HERE, "config.json")
if not os.path.exists(_path):
    sys.exit("missing %s -- copy config.example.json to config.json and fill it in" % _path)
with open(_path) as f:
    _cfg = json.load(f)

ROOT = os.path.expanduser(_cfg["root"])           # folder containing your git repos
AUTHOR_EMAILS = list(_cfg["author_emails"])       # every email you commit as
if not AUTHOR_EMAILS:
    sys.exit("config.json: author_emails is empty")
