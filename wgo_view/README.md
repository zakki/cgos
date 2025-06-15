# WGo CGOS Viewer

This directory contains a customized build of [WGo.js](http://wgo.waltheri.net) and small utilities for browsing SGF files on CGOS.

## Building

1. Install Node.js
2. Run `npm install` once to fetch the development dependencies.
3. Execute `npm run build` or simply `make` to generate the minified JavaScript in `dist/`.

## Deployment

Running `make install` copies the generated files and HTML pages into `/home/cgosboar/public_html/` for use on the server.
