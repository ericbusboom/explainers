# explainers

Web explainers and data analysis. Built with [Hugo](https://gohugo.io) and the
[beautifulhugo](https://github.com/halogenica/beautifulhugo) theme (vendored
into `themes/beautifulhugo/`). Deployed to GitHub Pages by
`.github/workflows/gh-pages.yml`.

## Adding an explainer

1. Put the self-contained `index.html` (plus any assets) at
   `static/<slug>/index.html`. It will be served at `/<slug>/`.
2. Create a metadata stub at `content/posts/<slug>/index.md` (each explainer
   gets its own directory — a Hugo page bundle — so supporting data, scripts,
   or notebooks can live alongside it) with frontmatter:

   ```yaml
   ---
   title: "Page title"
   date: 2026-05-12
   externalLink: "/<slug>/"
   summary: >
     One-paragraph teaser shown on the homepage.
   ---
   ```

   `externalLink` tells the listing card to link to the static page instead of
   a Hugo-rendered post.
3. The homepage (`layouts/index.html`) auto-lists everything in
   `content/posts/`, newest first.

## Local dev / build

```sh
just serve          # dev server on :1317
just build          # production build to ./public
just build-pages BASE=https://<you>.github.io/explainers/
```
