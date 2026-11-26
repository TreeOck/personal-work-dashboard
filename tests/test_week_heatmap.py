"""1.1.0: the Week view gets the same day-by-day heatmap as the Month view.

The functions are cut out of the built page and run in node, so this tests the code that ships."""
import json
import re
import shutil
import subprocess

import pytest

from test_build import site  # noqa: F401  (fixture)

pytestmark = pytest.mark.skipif(not shutil.which("node"), reason="node not installed")


def _fn(html, start, end):
    a = html.index(start)
    return html[a:html.index(end, a)]


def _run(site, expr):
    assert site().returncode == 0
    html = (site.dir / "dashboard.html").read_text(encoding="utf-8")
    js = "\n".join([
        re.search(r"const addDays = .*", html).group(0),
        _fn(html, "function heatmap(ts, days)", "const highlights = ts =>"),
        "console.log(JSON.stringify(" + expr + "));",
    ])
    r = subprocess.run(["node", "-e", js], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def _cells(html):
    return re.findall(r'<div data-l="(\d)" data-day="([\d-]+)"[^>]*>(\d+)</div>', html)


T = lambda date, n: {"date": date, "cs": [0] * n}


def test_week_has_seven_days_monday_first_no_padding(site):
    html = _run(site, 'heatmap([], weekDays("2026-11-23"))')      # a Monday
    cells = _cells(html)
    assert [d for _, d, _ in cells] == ["2026-11-%d" % d for d in range(23, 30)]
    assert "visibility:hidden" not in html                         # week starts on Monday: nothing to pad
    assert all(l == "0" for l, _, _ in cells)                     # empty week renders, all unshaded


def test_week_crossing_a_month_boundary(site):
    cells = _cells(_run(site, 'heatmap([], weekDays("2026-11-30"))'))
    assert [d for _, d, _ in cells][0] == "2026-11-30" and [d for _, d, _ in cells][-1] == "2026-12-06"
    assert [n for _, _, n in cells] == ["30", "1", "2", "3", "4", "5", "6"]


def test_week_shading_is_relative_to_the_busiest_day_and_sums_tasks(site):
    ts = [T("2026-11-23", 8), T("2026-11-25", 1), T("2026-11-25", 1), T("2026-11-27", 4)]
    lv = {d: l for l, d, _ in _cells(_run(site, "heatmap(%s, weekDays('2026-11-23'))" % json.dumps(ts)))}
    assert lv["2026-11-23"] == "4"          # peak
    assert lv["2026-11-27"] == "2"          # 4/8 -> ceil(2)
    assert lv["2026-11-25"] == "1"          # two tasks of 1 commit = 2/8 -> 1
    assert lv["2026-11-24"] == "0"
    assert 'aria-label="2026-11-25: 2 commits. Open day"' in _run(site, "heatmap(%s, weekDays('2026-11-23'))" % json.dumps(ts))


def test_month_unchanged_lead_padding_and_length(site):
    html = _run(site, 'heatmap([], monthDays("2026-11"))')       # 1 Nov 2026 is a Sunday -> 6 blanks
    assert html.count("visibility:hidden") == 6
    assert len(_cells(html)) == 30
    assert len(_cells(_run(site, 'heatmap([], monthDays("2028-02"))'))) == 29   # leap year


def test_week_view_renders_the_heatmap(site):
    assert site().returncode == 0
    html = (site.dir / "dashboard.html").read_text(encoding="utf-8")
    assert ': heatmap(ts, weekDays(k));' in html
