# Selective project CI for pull requests

## Goal

Run the project build matrix only for top-level static-site projects changed by
a pull request. Keep pushes to `main` as a full-project safety net, and keep the
repo-wide metadata check running for every pull request and push.

## Proposed behavior

| Event/change | Project build matrix | Repo metadata check |
| --- | --- | --- |
| Pull request changing one or more projects | Changed projects only | Runs |
| Pull request changing only repo-admin files | Skipped | Runs |
| Pull request adding a project | New project | Runs |
| Pull request deleting a project | Skipped for the deleted project | Runs |
| Push to `main` | Every project | Runs |

A project remains defined as an immediate child directory containing a
`Makefile`. Changes under a top-level directory that is not a project do not
create a project build.

## Implementation

1. Make the `discover` job event-aware.
   - On `pull_request`, compare the checked-out pull-request tree with
     `github.event.pull_request.base.sha`.
   - Take the first path component of each changed file, deduplicate it, and
     keep only directories that contain a `Makefile` in the pull-request tree.
   - On `push`, retain the current discovery of every `*/Makefile` project.
2. Fetch enough Git history in the discovery checkout to make the base/tree
   comparison reliable for normal and forked pull requests.
3. Emit both the JSON project list and a boolean indicating whether it is
   non-empty. Guard the `build` job with that boolean so a docs/admin-only pull
   request produces a clean skipped build instead of an invalid empty matrix.
4. Leave the `manifest` job unconditional. Changes to project metadata,
   scheduler configuration, repo-admin scripts, or the committed manifest must
   still be checked even when no project build is selected.
5. Update `README.md` and `AGENTS.md` when the workflow change lands so they
   describe selective pull-request builds and full builds on `main` accurately.

## Edge cases and decisions

- Renames between projects select both top-level directories when both still
  exist. A rename out of a deleted project selects only the surviving project.
- A deleted project cannot be built from the pull-request tree; the repo-wide
  check is responsible for catching stale manifest or refresh metadata.
- Workflow-only, documentation-only, and repo-admin-only changes do not fan out
  to every project. The full `main` build remains the backstop for shared CI
  behavior changes.
- Path filtering is done after checkout rather than with workflow `paths`
  filters, because one dynamic matrix must support newly added projects without
  editing the workflow.

## Validation

Before marking the pull request ready for review:

1. Exercise discovery against representative changed-path fixtures: one
   project, multiple projects, a new project, a deleted project, and no project.
2. Validate that project names are emitted as compact JSON and that an empty
   selection skips the matrix job.
3. Run `make check` from the repository root.
4. Validate the workflow YAML and inspect the final diff.
5. Let the draft pull request demonstrate that this planning-only change under
   `.github/` runs the repo metadata job without scheduling project builds once
   the implementation commit is added.

## Rollout

Implement and validate the workflow in this same draft pull request. Keep it in
draft until the selective matrix has been observed on the pull request and the
documentation matches the shipped behavior.
