# Contributing to Timoshenko Engine

Thank you for helping. Timoshenko is a small library whose outputs feed
engineering review, so correctness and clear limits matter more than feature
count. This page explains how to set up a checkout, what a pull request needs
to pass, and how to report a problem.

## Where to start

- Issues labelled
  [good first issue](https://github.com/Ayberkrk/timoshenko/labels/good%20first%20issue)
  are small and self-contained, with the files to touch named in the issue.
- For a bug, open an issue with a minimal script that reproduces it before
  sending a fix, unless the fix is a one-line typo.
- For a new feature or a change in engineering behavior, open an issue first so
  the scope and the reference used for verification can be agreed on.

## Development setup

Python 3.10 or newer is required. Use a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
python -m pip install -e ".[test,lint,docs]"
```

## Checks

Every pull request runs these on GitHub Actions. Run them locally first:

```bash
python -m pytest --cov             # tests on Python 3.10 to 3.14 in CI
python -m ruff check .             # lint
python -m ruff format --check .    # formatting
python -m mypy                     # type check of src/timoshenko
python -m mkdocs build --strict    # documentation, if you changed docs/
```

The package ships a `py.typed` marker, so type annotations on public functions
and classes are part of the API. Keep them accurate when you change a
signature.

## What a good pull request contains

- **One change per pull request.** Separate refactors from behavior changes.
- **A test.** A bug fix adds a test that fails before the fix and passes after
  it. New calculations are checked against a closed-form solution, a textbook
  example, or an independent tool, and the test names the reference.
- **Units and limits.** Public functions take and return SI units and validate
  their inputs. State the ideal assumptions in the docstring, as the existing
  functions do.
- **Documentation.** Update the matching page in `docs/` and add a line to the
  top section of `docs/changelog.md` for any user-visible change.
- **No new required dependencies.** The core depends only on NumPy. Optional
  integrations go behind an extra in `pyproject.toml`, like `mqtt`.

## Engineering changes

Changes to formulas, modal identification, model updating, or health
assessment can alter engineering decisions made with the library. For these,
describe in the pull request how the result was verified, including the
reference and the tolerance used. A change that alters existing numerical
results must say so explicitly and is listed under "Changed" in the changelog.

## Reporting a bug

Use the bug report template. Include the Timoshenko, Python, and NumPy
versions, a minimal script, and the expected and actual results. For a
numerical discrepancy, give the reference value and where it comes from.

## Releases

Maintainers publish releases from GitHub Releases. The release workflow tests
the tagged source, builds the distributions, and uploads them to PyPI through
trusted publishing. Zenodo archives each release with its own DOI.

## License

By contributing, you agree that your contributions are licensed under the
[Apache License 2.0](LICENSE).
