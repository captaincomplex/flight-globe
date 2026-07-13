# Flight Globes

Interactive 3D globes that visualise the flights in `flights.json`, closely following
[James Harding's flight globes](https://jameshard.ing/pilot/globes/). Built with
[globe.gl](https://github.com/vasturiano/globe.gl) loaded from CDN — no build step.

## The five globes

| Page | What it shows |
|---|---|
| `all.html` | Every route at once, animated traffic along each arc |
| `sequential.html` | Flights light up one at a time in date order |
| `countries.html` | Countries visited, extruded by visit count |
| `destinations.html` | Bars or a heat gradient at each destination |
| `timeline.html` | Replay with play/pause, scrubber, and per-flight info card |

`index.html` is the landing page linking to all five.

## Viewing

The pages fetch `flights.json`, so they must be served over HTTP (opening the files
directly won't work). From the repo directory:

```sh
python3 -m http.server 8000
```

then open <http://localhost:8000>. Works as-is on GitHub Pages.

## Flight data

Edit `flights.json` to add flights. Each entry is:

```json
{
  "time": "16/06/2011T12:35Z",
  "from": [52.0407981873, -1.09555995464],
  "to": [52.6758003235, 1.28278005123],
  "from_code": "EGKK",
  "to_code": "LEPA"
}
```

`time` is `DD/MM/YYYY` followed by `T HH:MM Z`; `from`/`to` are `[latitude, longitude]`
in decimal degrees. `from_code`/`to_code` are optional airport codes — when present,
the globes show them in tooltips and the timeline info card.

### Importing from CrewLounge PILOTLOG

Export your logbook: in the desktop app open the **Query** page, leave the search
fields empty, click **Search**, then the **CSV** (or Excel) button — or on
[my.crewlounge.center](https://my.crewlounge.center/) go to **Apps → PilotLog →
Export Database**. Then run:

```sh
python3 tools/pilotlog_to_flights.py ~/Downloads/YourExport.csv
```

It matches PILOTLOG's column names (`PILOTLOG_DATE`, `AF_DEP`, `AF_ARR`, `TIME_DEP`),
resolves ICAO/IATA/FAA airport codes to coordinates using the bundled
[OurAirports](https://ourairports.com/data/) database (`tools/airports.csv`, public
domain), and rewrites `flights.json` sorted by date. Generic column names from other
logbook apps (date/from/to etc.) work too; pass `--mdy` if your dates are month-first.

## Assets & credits

- Globe rendering: [globe.gl](https://github.com/vasturiano/globe.gl) (MIT) by Vasco Asturiano
- `assets/earth-night-hd.jpg` (8192×4096), `assets/earth-day-hd.jpg` and
  `assets/night-sky.png` (4096×2048): NASA-derived Earth imagery (public domain),
  the same files James Harding serves on his globes
- `data/countries.geojson`: Natural Earth 1:110m admin-0 countries (public domain),
  as used by globe.gl's examples — provides both the hex-polygon landmasses and the
  country shapes
- Design and techniques: [James Harding](https://jameshard.ing) — the hex-polygon
  landmasses, the single-dash sequential animation trick, colour ramps, and camera
  behaviour are ported from his globes
