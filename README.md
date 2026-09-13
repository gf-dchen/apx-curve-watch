# apx-curve-watch

Stores the current ERCOT operating hour's dispatch schedule bid curve, as APX
MarketSuite holds it for us, and logs when any point on it moves. Zero tolerance:
any MW or price change on any segment counts, not just a "material" one.

Runs as a standalone, unattended poll loop -- not a notebook panel, so it keeps
watching whether or not anyone has `live_monitor.py` open.

## What it does each tick

1. Fetch the participant's `PRE`-stage energy book for today via
   `gfem.foundry.bidding.apx_bids.fetch_bidset` (the same call `live_monitor.py`
   uses).
2. Take the cumulative MW->$ ladder (`apx_bids.ladder`) for the *current*
   hour-ending, per resource.
3. Diff it against the last snapshot stored for that (date, hour-ending).
4. If anything moved: print it and log a warning line.
5. Archive the new snapshot either way, so the store is a full history, not
   just a change log.

## Running it

```bash
uv sync
uv run apx-curve-watch
```

Requires `APX_CLIENT_ID` / `APX_SECRET` / `APX_USERNAME` / `APX_PASSWORD` (plus
optional `APX_ENV`) to be resolvable by `gfem.env` -- see `.env.example`. Because
`gfem` is installed here as an editable sibling checkout, it will normally pick
these up from `../gfem-data/.env` automatically; you don't need your own `.env`
unless that's not where credentials live for you.

Config knobs (all optional, see `.env.example` for defaults):

- `APX_MARKET_PARTICIPANT` -- defaults to `QGFEN`.
- `APX_CURVE_WATCH_RESOURCES` -- comma-separated resource names to watch;
  empty means every resource in the book.
- `APX_CURVE_WATCH_POLL_SECONDS` -- poll interval; default 30s. Each tick is a
  full APX round-trip, so don't set this too aggressively.
- `APX_CURVE_WATCH_STORAGE_DIR` -- where snapshots are archived; default `./curves`.
- `TEAMS_WEBHOOK_URL` -- optional. Unset means console + log only; set it and every
  change announcement also posts to that Teams incoming webhook.

## Today's curve, as a table

```bash
uv run apx-curve-watch --table
```

Prints today's full-day energy ladder, HE01..HE24 + Total, one resource section
at a time -- the same shape as the APX MarketSuite bid-curve page, minus its
`Submit`/`Energy-Market` grouping chrome. **Energy only**: AS-Market products
(ECRS etc.) aren't included, because `gfem`'s parser doesn't extract them (see
`apx_bids.parse_bidset`'s `ProductType != "Energy"` filter) -- pulling those in
would mean extending that shared parser, a separate change on its own branch.

## Storage layout

```
{storage_dir}/{fordate}/HH{he}/latest.json
{storage_dir}/{fordate}/HH{he}/{timestamp}.json   # one per observed change in shape, full history
```

Each file carries the full per-resource ladder for that hour as of that
observation.

## Not yet done

- No retention/pruning of old snapshots yet.
- Deploying this as an always-running background process (systemd timer, etc.)
  isn't set up -- right now it's `uv run apx-curve-watch` in a terminal.

## Development

```bash
uv run ruff check .
uv run ruff format .
uv run pytest
```
