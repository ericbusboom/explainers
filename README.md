# explainers

Web explainers and data analysis. Built with [Hugo](https://gohugo.io) and the
[docuapi](https://themes.gohugo.io/themes/docuapi/) theme (vendored into
`themes/docuapi/`). Deployed to GitHub Pages by `.github/workflows/gh-pages.yml`.

## Adding an explainer

1. Put the self-contained `index.html` (plus any assets) at
   `static/<slug>/index.html`. It will be served at `/<slug>/`.
2. Create a metadata file at `content/posts/<slug>.md` with frontmatter:

   ```yaml
   ---
   title: "Page title"
   date: 2026-05-12
   externalLink: "/<slug>/"
   summary: >
     One-paragraph teaser shown on the homepage.
   ---
   ```

3. The homepage (`layouts/index.html`) auto-lists everything in `content/posts/`,
   newest first.

## Local dev

```sh
hugo server -D
```

Open http://localhost:1313.

## Build

```sh
hugo --minify
```

Output lands in `public/`.
