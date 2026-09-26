# Package, documentation, and citation publishing

This page records the repository-side setup for distribution and archived
documentation. It also lists the account settings that must be completed
before any public package or DOI is created.

## PyPI package

The distribution name is `timoshenko-engine`; the import name is
`timoshenko`. The release workflow is
`.github/workflows/publish.yml`. It runs only when a GitHub Release is
published, runs the test suite, builds a wheel and source distribution, then
publishes with PyPI Trusted Publishing. It does not use a stored PyPI API
token.

Before publishing:

1. Push the reviewed repository changes to `Ayberkrk/timoshenko`.
2. Confirm that the `timoshenko-engine` project name is available, or that you
   control the existing PyPI project.
3. Configure a GitHub Actions Trusted Publisher for owner `Ayberkrk`,
   repository `timoshenko`, workflow `publish.yml`, and GitHub environment
   `pypi`. This pending publisher was registered on PyPI on 2026-09-25.
4. In GitHub repository settings, create the `pypi` environment. Add a
   required reviewer and restrict allowed deployment tags if you want a manual
   approval before uploads.
5. Verify the PyPI account's primary email before the first project creation
   and upload. PyPI requires a verified email for these operations.
6. Publish a GitHub Release for the intended version. The workflow starts from
   that release tag. A release is a public action and will publish to PyPI once
   the Trusted Publisher is active.

PyPI Trusted Publishing uses short-lived OIDC credentials instead of a
long-lived API token. Once configured, the publisher will trust this
repository and this specific workflow, so changes to the workflow should
receive maintainer review.

## Versioned documentation

The repository uses MkDocs Material, with configuration in `mkdocs.yml` and
`.readthedocs.yaml`. Install the optional tools and preview the site with:

```bash
python -m pip install -e ".[docs]"
python -m mkdocs serve
```

After pushing the configuration, import `Ayberkrk/timoshenko` into Read the
Docs and set its project slug to `timoshenko-engine`. Keep the `latest` branch
version enabled and activate release tags as documentation versions. Mark the
latest stable release as `stable`. Pre-release tags can be enabled when their
documentation should be public. Read the Docs reads the repository
configuration and builds these versions separately.

The hosted URL and PyPI `Documentation` metadata link should be updated to the
confirmed Read the Docs URL after the project has been created and its first
build succeeds. Until then, the GitHub documentation links remain canonical.

## Zenodo archive and citation

`CITATION.cff` provides a GitHub citation suggestion. `.zenodo.json` provides
the software metadata Zenodo uses for GitHub release archiving; when both
files exist, Zenodo gives `.zenodo.json` precedence for the archived record.
Keep their title, author, license, and keywords aligned. Update the version in
`CITATION.cff` when preparing a new release. `.zenodo.json` intentionally has
no fixed version, so each archived GitHub release can supply its own version.

After the source changes are on GitHub, connect the GitHub account to Zenodo
and enable only the `Ayberkrk/timoshenko` repository. This installs the
repository integration that receives release events. A DOI is assigned when
the corresponding Zenodo record is published; no DOI is reserved or created
by these repository files.

## Current state

- Releases are published on PyPI as `timoshenko-engine` through the trusted
  publisher for `Ayberkrk/timoshenko`, workflow `publish.yml`, environment
  `pypi`. Each GitHub Release triggers a tested upload, so every release needs
  a new version number.
- The Zenodo GitHub integration is enabled. Each GitHub Release is archived
  with its own DOI; the concept DOI 10.5281/zenodo.22968739 always resolves to
  the latest release. Version 2.0.2 is the first archived release
  (10.5281/zenodo.22968740); earlier releases are not archived retroactively.
- Before the first public push, internal planning notes were removed from the
  Git history, so commit hashes differ from earlier local copies. The `v2.0.0`
  tag points at the rewritten commit with the same source.
- Repository-side PyPI, Read the Docs, and Zenodo configuration is present.
- No Read the Docs project has been created yet.
