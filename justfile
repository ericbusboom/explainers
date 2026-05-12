default: serve

# Run the Hugo dev server with drafts and live reload.
serve PORT="1317":
    hugo server -D --disableFastRender --port {{PORT}}

# Production build into ./public.
build:
    rm -rf public
    HUGO_ENVIRONMENT=production hugo --minify

# Build as it will deploy to GitHub Pages (override URL with BASE=...).
build-pages BASE="https://example.github.io/explainers/":
    rm -rf public
    HUGO_ENVIRONMENT=production hugo --minify --baseURL "{{BASE}}"

clean:
    rm -rf public resources/_gen .hugo_build.lock
