# muninn

A personal knowledge base for writing, ideas, and things worth remembering.
Built with [Astro](https://astro.build), with deployment configured for
Cloudflare Workers Static Assets.

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

Use Node.js 22.12 or newer. The `.nvmrc` file selects Node.js 22 for local
version managers and Cloudflare builds.

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

The site is a static build: Cloudflare serves the files in `dist/` without
a Worker script, server-side rendering, or a database.

### Automatic deployment

After committing and pushing this configuration to GitHub:

1. In Cloudflare, open **Workers & Pages → Create application → Import a repository**.
2. Connect GitHub and select `jusueyoung1997/muninn`.
3. Configure the build:

   | Setting | Value |
   | --- | --- |
   | Worker name | `muninn` (must match `wrangler.jsonc`) |
   | Production branch | `main` |
   | Root directory | Repository root |
   | Build command | `npm run build` |
   | Deploy command | `npm run deploy` |

4. Select **Save and Deploy**, then open the `workers.dev` URL returned by Cloudflare.
5. In the Worker's **Settings → Builds**, add a build variable named `SITE_URL`
   with the full public URL, including `https://`, and rebuild. If you later
   attach a custom domain, update this variable to that domain and rebuild.

Cloudflare installs dependencies using the committed package lock. After the
repository is connected, pushes to `main` automatically build and publish the
site. Check build logs in the Cloudflare dashboard if deployment fails.

`SITE_URL` is optional for the first deployment; no placeholder domain is baked
into the site. It is read from the build process environment, so for local builds
you can set it with `SITE_URL=https://your-domain.example npm run build`.
All site paths now start at `/`, without the old `/muninn` prefix.

The previous GitHub Pages workflow has been removed. This stops future workflow
deployments once the change is pushed; it does not unpublish an existing GitHub
Pages site. After verifying Cloudflare, you can unpublish the old site in
GitHub's **Settings → Pages** if it is no longer needed.

### Manual deployment and validation

```sh
npm run build
npm run deploy -- --dry-run  # validate deployment without uploading
npx wrangler login          # required for manual deployment, not Workers Builds
npm run deploy              # upload the existing dist/ build
```

`npm run deploy` does not rebuild the site; always run `npm run build` first.
Workers Builds runs these commands in sequence automatically.

## Project structure

```
content/            # knowledge base notes (Markdown)
public/             # static assets served as-is
src/
  layouts/          # shared page layout
  pages/            # routes (home, notes, tags)
  styles/           # global CSS
  content.config.ts # content collection (loads ./content)
astro.config.mjs    # Astro configuration
wrangler.jsonc      # Cloudflare static asset deployment
```

## License

[MIT](LICENSE)
