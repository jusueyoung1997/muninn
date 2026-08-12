---
title: Welcome to Muninn
description: What this knowledge base is and how it works.
date: 2026-08-12
tags: [meta]
---

Welcome! This is my personal knowledge base — a place for writing, ideas,
and things worth remembering.

## How it works

- Every note is a plain Markdown file in the `content/` directory.
- Subfolders become URL paths automatically (e.g. `content/tech/git-tips.md`
  becomes `/notes/tech/git-tips`).
- Frontmatter fields: `title`, `description`, `date`, `updated`, `tags`,
  `draft`.
- Set `draft: true` to keep a note out of the published build.

## Writing workflow

1. Create a Markdown file anywhere under `content/`.
2. Fill in the frontmatter.
3. Commit and push — GitHub Actions rebuilds and deploys the site.
