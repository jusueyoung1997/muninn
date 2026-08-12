---
title: Git Tips
description: Everyday Git commands I keep forgetting.
date: 2026-08-12
tags: [git, reference]
---

Commands I keep reaching for.

## Undo the last commit, keep changes

```sh
git reset --soft HEAD~1
```

## Sync a fork with upstream

```sh
git fetch upstream
git merge upstream/main
```

## Find when a line changed

```sh
git blame -L 10,20 -- path/to/file
```
