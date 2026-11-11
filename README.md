# VERLTRIX TIRES

This repository holds two things:

- **Inventory app** — a React client and a Node.js (Express) API in one npm workspace.
- **Feed fixer** — a Python command-line tool that fills the gaps in the product feed.

## Structure

```
.
├── client/                 React app (Vite)
│   ├── index.html
│   ├── vite.config.js      Dev server + `/api` proxy to the Express server
│   └── src/
│       ├── main.jsx
│       ├── App.jsx         Inventory shell (list + API status)
│       └── styles.css
├── server/                 Node.js API (Express)
│   ├── src/
│   │   ├── app.js          Express app factory (testable, one store per instance)
│   │   ├── index.js        Server entry point
│   │   └── routes/
│   │       └── inventory.js  Inventory endpoints
│   └── test/
│       └── inventory.test.js API tests (node:test)
├── feed_fixer.py           Python CLI: fills gaps in the feed fix list
├── data/feed_fix_list.csv  The feed fix list the tool works on
├── tests/                  Feed fixer tests (unittest)
├── Dockerfile              `development` and `production` targets
├── package.json            Workspaces and root scripts
└── package-lock.json
```

## Inventory app

### Local development

Requires Node.js 20+.

```bash
npm install
npm run dev
```

- Client: http://localhost:5173
- API: http://localhost:3001 (the client proxies `/api` here)

Other scripts:

| Command | What it does |
| --- | --- |
| `npm run dev:web` | Vite client only |
| `npm run dev:api` | Express API only (watches for changes) |
| `npm run build` | Build the client into `client/dist` |
| `npm start` | Run the API; it also serves `client/dist` when present |
| `npm test` | Run the API tests with Node's built-in test runner |

### Tests

The API tests use Node's built-in test runner (`node:test`), with no extra
dependencies. Each test starts the real Express app via `createApp()` on a random
port and talks to it over HTTP, so every test gets a clean in-memory store.

```bash
npm test                                  # all API tests
npm --workspace server test -- --watch    # re-run on change
```

`server/test/inventory.test.js` covers creating items, listing them, derived
stock status, input trimming, and the validation failures (missing/blank name or
SKU, negative or non-numeric quantity, duplicate SKU).

### Docker

The Dockerfile has two targets.

```bash
# Development container with both dev servers (ports 5173 and 3001)
docker build --target development -t verltrix-inventory:dev .
docker run --rm -p 3000:5173 -p 3001:3001 -v "$PWD:/app" verltrix-inventory:dev

# Production image: Express serves the API and the built client on port 3000
docker build --target production -t verltrix-inventory .
docker run --rm -p 3000:3000 verltrix-inventory
```

When using the development target with a bind mount, keep the container's
`node_modules` from the image by not mounting over `/app/node_modules`
(the sandbox configuration handles this with a named volume).

### API

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/api/health` | Service health and uptime |
| `GET` | `/api/inventory` | List inventory items |
| `POST` | `/api/inventory` | Create an item (`name`, `sku`, `category`, `quantity`) |

Items are kept in memory for now, so they reset when the API restarts.

### Environment

The app runs with no external credentials. Optional variables:

- `PORT` — API port (default `3001`)
- `API_PROXY_TARGET` — API URL used by the Vite dev proxy (default `http://127.0.0.1:3001`)

## Feed fixer

`feed_fixer.py` fills the gaps reported in the feed fix list and re-validates the feed.

### Requirements

- Python 3.9+ only — there is nothing to install, the tool uses the standard library.
- Run the commands from the repository root, so the paths below resolve as shown.

Check that the tool runs and list its options:

```bash
python3 feed_fixer.py --help
python3 feed_fixer.py fix --help
```

`data/feed_fix_list.csv` is the current fix list: 4,027 rows, 4,005 failing.
- 3,938 rows need **price** and **availability**
- 874 rows need an **image_link**
- 45 TIRELINK rows need both an **image_link** and a **link** (product URL)

### 1. Make a sheet to fill in

```bash
python3 feed_fixer.py template data/feed_fix_list.csv -o out/to_fill.csv
```

This writes only the failing rows, with empty `price`, `availability`, `image_link`, `link` columns.

### 2. Merge your data and re-validate

```bash
python3 feed_fixer.py fix data/feed_fix_list.csv prices.csv images.csv \
    --feed-out out/feed_fixed.csv --report-out out/feed_fix_list_remaining.csv
```

- Source files are matched on `record_id` (also accepted: `id`, `sku`, `item_id`, `offer_id`).
- Column aliases are accepted, e.g. `selling_price`, `stock`, `image_url`, `product_url`.
- When several files supply the same field, the later file wins. Empty cells never overwrite.
- Prices are normalised to `129.99 USD` (`--currency` sets the default for bare numbers).
- Availability accepts `in_stock` / `out_of_stock` / `preorder` / `backorder`, common phrases
  ("In Stock", "sold out"), or a stock count (`>0` = in stock).
- `image_link` and `link` must be `http(s)://` URLs with a host name.
- By default a row is checked only on the fields it originally failed. Use `--require-all`
  to require every field on every row. A value a source *does* supply is always validated,
  even for a field that passed before, so a bad value never ends up in the feed update: the
  cell is left blank (keep the live value) and the row is reported as failing.
- A failing field this tool cannot fill (`price`, `availability`, `image_link`, `link` are the
  only ones it knows) keeps the row failing instead of being silently dropped from the report.

`feed_fixed.csv` is an update sheet, not a complete feed: it holds the values your source
files supplied. A blank cell means "not changed by this run", so keep the value already in
your live feed (the fix list doesn't contain those values). Upload it as a supplemental
feed, or use `--require-all` with complete source files to get a full feed.

The report has the same columns as the input fix list, so you can run it again on the remaining rows.
A fix list with no data rows left is valid: the tool writes empty outputs and exits 0.
Missing output folders are created for you.

### Options

| Option | Command | Meaning |
| --- | --- | --- |
| `-o`, `--out PATH` | `template` | Where to write the fill-in sheet (default `out/to_fill.csv`). |
| `--feed-out PATH` | `fix` | Feed update file (default `out/feed_fixed.csv`). |
| `--report-out PATH` | `fix` | Remaining-rows report (default `out/feed_fix_list_remaining.csv`). |
| `--currency CODE` | `fix` | Currency for prices without one (default `USD`). |
| `--require-all` | `fix` | Require every field on every row, not just the ones that failed. |

Exit codes: `0` when every row passes, `1` when any row still fails, so the command can gate
a feed upload in a script or CI job.

### Tests

The suite needs only Python 3.9+ (no packages), writes to temporary folders, and never
modifies `data/feed_fix_list.csv`.

```bash
# Everything: unit tests and integration tests
python3 -m unittest discover -s tests -v

# Only the integration tests
python3 -m unittest discover -s tests -p "test_integration.py" -v

# A single integration test class, or a single test
python3 -m unittest tests.test_integration.FixIntegrationTests -v
python3 -m unittest tests.test_integration.TemplateTests.test_template_from_sample -v
```

`tests/test_feed_fixer.py` — unit tests for price, availability and URL normalisation, for
merging sources into the fix list, and for the fill-in sheet.

`tests/test_integration.py` — runs `python3 feed_fixer.py` in a subprocess against the sample
files in `tests/fixtures/` (`sample_fix_list.csv`, `sources/prices.csv`,
`sources/images.csv`) and checks the real result: exit codes, stdout, and the feed and report
CSVs written to disk. It covers column aliases, quoted titles containing commas, padded
record ids, unknown failing fields, unusable values, source precedence, `--require-all`,
re-running on the previous report, default output paths, and the error cases (missing fix
list, missing columns, unusable source file).

Both files also run in CI (`.github/workflows/pylint.yml`, Python 3.11-3.13) after Pylint.
