"""1.1.0: theme menu (Auto, Light, Ink + six editor palettes), remembered in localStorage."""
import json
import re

import pytest

from test_build import site  # noqa: F401  (fixture)

DARK = ["ink", "dracula", "nord", "mocha", "tokyo", "gruvbox", "rosepine"]
THEMES = ["light"] + DARK


def _vars(block):
    return dict(re.findall(r"--([a-z0-9-]+):\s*(#[0-9a-f]{6}|#[0-9a-f]{3})\b", block))


def _page(site):
    r = site()
    assert r.returncode == 0, r.stderr
    return (site.dir / "dashboard.html").read_text(encoding="utf-8")


def _blocks(html):
    css = html.split("<style>")[1].split("</style>")[0]
    light = _vars(re.search(r":root\{(.*?)\}", css, re.S).group(1))
    dark = {t: _vars(re.search(r':root\[data-theme="%s"\]\{(.*?)\}' % t, css, re.S).group(1)) for t in DARK}
    auto = _vars(re.search(r':root:not\(\[data-theme\]\)\{(.*?)\}', css, re.S).group(1))
    return css, light, dark, auto


def _lum(h):
    if len(h) == 4:
        h = "#" + "".join(ch * 2 for ch in h[1:])
    c = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def _contrast(a, b):
    hi, lo = sorted([_lum(a), _lum(b)], reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def test_every_dark_theme_defines_every_light_variable(site):
    _, light, dark, _ = _blocks(_page(site))
    assert len(light) >= 20
    for t, v in dark.items():
        assert set(v) == set(light), (t, set(light) ^ set(v))


def test_os_dark_without_a_choice_uses_ink(site):
    _, _, dark, auto = _blocks(_page(site))
    assert auto == dark["ink"]


def test_dark_themes_set_color_scheme_for_native_controls(site):
    css, *_ = _blocks(_page(site))
    for t in DARK:
        assert re.search(r':root\[data-theme="%s"\]\{\s*color-scheme:dark;' % t, css)


def test_old_dark_value_no_longer_styled(site):
    # a stale data-theme="dark" (never saved before, but be safe) falls back to light rather than a half theme
    assert 'data-theme="dark"' not in _page(site)


@pytest.mark.parametrize("theme", THEMES)
def test_text_meets_wcag_aa(site, theme):
    _, light, dark, _ = _blocks(_page(site))
    v = light if theme == "light" else dark[theme]
    for fg in ("text", "muted"):
        for bg in ("bg", "surface", "surface2"):
            assert _contrast(v[fg], v[bg]) >= 4.5, (theme, fg, bg, round(_contrast(v[fg], v[bg]), 2))
    assert _contrast(v["on-accent"], v["accent"]) >= 4.5


def test_menu_and_early_script_agree_on_the_theme_list(site):
    html = _page(site)
    early = html.split("<style>")[0]
    assert 'localStorage.getItem("theme")' in early
    listed = re.search(r"(\[[^\]]*\])\.includes\(t\)", early).group(1)
    assert json.loads(listed) == THEMES                                    # saved value validated before use
    menu = re.search(r'<select[^>]*id="theme".*?</select>', html, re.S).group(0)
    assert re.findall(r'<option value="([a-z]*)"', menu) == [""] + THEMES  # "" = Auto
    assert 'localStorage.setItem("theme", t)' in html and 'localStorage.removeItem("theme")' in html


def test_each_theme_is_visibly_different(site):
    # the first round of dark themes were near-identical greys; keep backgrounds and accents apart
    _, light, dark, _ = _blocks(_page(site))
    names = list(dark)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            d = sum(abs(x - y) for k in ("bg", "accent") for x, y in zip(_rgb(dark[a][k]), _rgb(dark[b][k])))
            assert d >= 60, (a, b, d)


def _rgb(h):
    return [int(h[i:i + 2], 16) for i in (1, 3, 5)]
