# Releasing

The version lives only in `pyproject.toml`. A release is a GitHub release whose tag is `v<version>`; publishing it
runs `.github/workflows/publish.yml`, which builds the package, checks it (`twine check --strict`), refuses a tag that
doesn't match the version, and uploads it to PyPI through trusted publishing (no API tokens anywhere).

## Each release
1. On a branch: bump `version` in `pyproject.toml` (and the two tests that pin it: `tests/test_cli.py`,
   `tests/test_build.py`), add a `CHANGELOG.md` entry; PR, CI green, merge.
2. `gh release create v<version> --target main --title <version> --notes-file <notes>` (or "Draft a new release" on
   GitHub with a new tag `v<version>`), then **Publish**.
3. The `publish` workflow runs; when it is green the version is on https://pypi.org/p/personal-work-dashboard.
   Users update with `pipx upgrade personal-work-dashboard`.

A version uploaded to PyPI can't be replaced (only yanked), so a mistake means a new patch version.

## One-time setup (done once per project)
- PyPI account with two-factor sign-in.
- On PyPI: *Your account → Publishing → Add a new pending publisher* (GitHub tab):
  PyPI project name `personal-work-dashboard`, owner `TreeOck`, repository `personal-work-dashboard`,
  workflow `publish.yml`, environment `pypi`. The first successful upload turns it into the real project.
- On GitHub: *Settings → Environments → New environment* named `pypi` (optionally require your approval for each
  deployment).

## Checking a build locally
```
python -m pip install build twine
python -m build            # dist/personal_work_dashboard-<version>.tar.gz and -py3-none-any.whl
python -m twine check --strict dist/*
```
