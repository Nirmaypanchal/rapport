# Let GitHub Actions create pull requests, so the sprint can merge its own work again

**Why:** The `sprint-merge` workflow is the only way an agent's work reaches `main`. Its first step,
`gh pr create`, fails on this repository with `GraphQL: GitHub Actions is not permitted to create or approve pull
requests (createPullRequest)` — a repository setting that is off by default. The step ends in `|| true`, so the
workflow reports **success**, opens nothing, merges nothing, and says nothing. It has now failed silently twice:
once on your `sprint/developers-doc-tests` branch and once on this run's `sprint/summary-templates`
([run 34345755395](https://github.com/Nirmaypanchal/rapport/actions/runs/34345755395)). Until the setting is
flipped, every Build run produces a green branch that sits unmerged, and each run has to notice and merge by hand.

Today's work is not blocked — this run opened and squash-merged
[PR #1](https://github.com/Nirmaypanchal/rapport/pull/1) manually (commit `f5ce250`) after CI passed on all three
jobs. Your `sprint/developers-doc-tests` branch is still open and still unmerged; it is green, so it will merge on
its own once this setting is on and CI runs again.

**What to do:**

1. Open <https://github.com/Nirmaypanchal/rapport/settings/actions>.
2. Under **Workflow permissions**, tick **Allow GitHub Actions to create and approve pull requests**, and save.
   Leave **Read and write permissions** as it is; the workflow already asks for what it needs.
3. If the repository belongs to an organisation rather than your personal account, the same box exists at the
   organisation level and wins over the repository one: Organisation → Settings → Actions → General.
4. To confirm, push any commit to a `sprint/*` branch (or re-run CI on `sprint/developers-doc-tests`). When CI goes
   green a pull request should appear and merge itself within a minute.

There is a second, smaller thing worth doing but it is code, not a setting, so a Build run can do it if you would
rather not: drop the `|| true` from that step in `.github/workflows/sprint-merge.yml`, or follow it with a check
that a pull request now exists. As written, the workflow cannot tell "no pull request was needed" from "I was not
allowed to open one", which is why this went unnoticed. It is on the backlog under **Next**.

**Blocked:** nothing today, but every future Build, Release and Research run that pushes a `sprint/*` branch has to
merge it by hand until this is on — which is exactly the manual step the loop exists to avoid.
