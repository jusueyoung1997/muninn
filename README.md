# muninn

A personal knowledge base for writing, ideas, and things worth remembering.
Built with [Astro](https://astro.build) and deployed to GitHub Pages.

## Writing notes

Notes are plain Markdown files in the [`content/`](content/) directory.
Subfolders are supported and become part of the note's URL path —
`content/tech/git-tips.md` is published at `/notes/tech/git-tips/`.

Each note needs frontmatter:

```md
---
title: Git Tips
description: Everyday Git commands I keep forgetting.
date: 2026-08-12
tags: [git, reference]
---
```

Available fields: `title` (required), `description`, `date` (required),
`updated`, `tags`, and `draft` (set to `true` to exclude from the published
build).

## Development

```sh
npm install
npm run dev
```

Then open http://localhost:4321.

```sh
npm run build    # build static site to dist/
npm run preview  # preview the production build
```

## Deployment

The site deploys automatically to GitHub Pages via
`.github/workflows/deploy.yml` whenever the default branch is updated.

One-time setup in the GitHub repository:

1. Go to **Settings → Pages**.
2. Under **Build and deployment**, set **Source** to **GitHub Actions**.

The site is published at <https://jusueyoung1997.github.io/muninn/>.
If you rename the repo or use a custom domain, update `site` and `base` in
[`astro.config.mjs`](astro.config.mjs).

## Project structure

```
content/            # knowledge base notes (Markdown)
public/             # static assets served as-is
src/
  layouts/          # shared page layout
  pages/            # routes (home, notes, tags)
  styles/           # global CSS
  content.config.ts # content collection (loads ./content)
.github/workflows/  # GitHub Pages deployment
astro.config.mjs    # Astro configuration
```

## License

[MIT](LICENSE)
