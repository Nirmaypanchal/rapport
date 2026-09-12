Escalations to the owner. One Markdown file per request, named `YYYY-MM-DD-<slug>.md`, first line `# Title`.
The `needs-human` workflow opens an issue for each new file, assigned to @Nirmaypanchal. Resolved files move to `done/`.
This README is ignored by the workflow.

The workflow runs `scripts/needs_human_issues.py`, which files each file exactly once: every issue it opens carries a
`<!-- needs-human-file: <file name> -->` marker, and a later run recognises its own work by that marker rather than by
searching issue titles (the search index missed #3 and the same request was filed again as #6). Don't edit the marker
out of an issue, and check what would happen before adding a file with `scripts/needs_human_issues.py --dry-run`.
