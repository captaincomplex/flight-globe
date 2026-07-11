# Flight Globe

An interactive 3D globe that draws animated arcs for a set of flights, inspired by
James Harding's flight-globe. Built with [three.js](https://threejs.org/) and
[three-globe](https://github.com/vasturiano/three-globe), loaded from CDN — no build
step required.

## Viewing

The page fetches `flights.json`, so it must be served over HTTP (opening `index.html`
directly from the filesystem won't work). From the repo directory:

```sh
python3 -m http.server 8000
```

then open <http://localhost:8000>. It also works as-is on GitHub Pages.

## Flight data

Edit `flights.json` to add your own flights. Each entry is:

```json
{
  "time": "16/06/2011T12:35Z",
  "from": [52.0407981873, -1.09555995464],
  "to": [52.6758003235, 1.28278005123]
}
```

`from` and `to` are `[latitude, longitude]` pairs in decimal degrees.

## Controls

- Drag to rotate, scroll to zoom (the globe also auto-rotates slowly)
- Red dashed arcs are flights; yellow dots mark departure and arrival points
