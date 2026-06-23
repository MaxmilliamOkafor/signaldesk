# docs/ — the live demo

`index.html` is a fully self-contained, in-browser port of the engine. It is
published via GitHub Pages (see `.github/workflows/pages.yml`) at:

**https://maxmilliamokafor.github.io/signaldesk/**

- `index.html` — the interactive demo (no backend, no install)
- `preview.svg` — the static preview shown in the root README (links to the demo)

To preview locally: `python -m http.server -d docs` then open
<http://localhost:8000>.
