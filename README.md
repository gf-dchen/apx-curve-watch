# apx-curve-watch

Stores the current ERCOT operating hour's dispatch schedule bid curve, as APX
MarketSuite holds it for us, and announces the new schedule whenever any point on
it moves. Zero tolerance: any MW or price change on any segment counts, not just a
"material" one.

Runs as a standalone, unattended poll loop -- not a notebook panel, so it keeps
watching whether or not anyone has `live_monitor.py` open.

## What it does each tick

1. Fetch the participant's `PRE`-stage energy book for today via
   `gfem.foundry.bidding.apx_bids.fetch_bidset` (the same call `live_monitor.py`
   uses).
2. Take the cumulative MW->$ ladder (`apx_bids.ladder`) for the *current*
   hour-ending, per resource.
3. Diff it against the last snapshot stored for that (date, hour-ending).
4. If anything moved: print the new schedule for each changed resource (not a
   delta description), log a warning line, and post it to Teams if configured.
5. Archive the new snapshot either way, so the store is a full history, not
   just a change log.
6. Once per configured wall-clock time (default every 15/10/5 min from 08:30 to
   10:00 CT, tightening near the DAM deadline), check that *tomorrow's* book
   has something on file and nudge if not.

## Running it

```bash
uv sync
uv run apx-curve-watch
```

Requires `APX_CLIENT_ID` / `APX_SECRET` / `APX_USERNAME` / `APX_PASSWORD` (plus
optional `APX_ENV`) to be resolvable by `gfem.env` -- see `.env.example`. Because
`gfem` is installed here as an editable sibling checkout, it will normally pick
these up from the `gfem-data` checkout's own `.env` automatically; you don't need
your own `.env` for credentials unless that's not where they live for you.

This repo's OWN knobs (below) are separate: they're loaded from a `.env` file at
*this* repo's root (via `python-dotenv`, anchored to this repo regardless of
cwd), not from `gfem-data`'s. Copy `.env.example` to `.env` and fill in the ones
you want to set -- it's gitignored, never committed.

Config knobs (all optional, see `.env.example` for defaults):

- `APX_MARKET_PARTICIPANT` -- defaults to `QGFEN`.
- `APX_CURVE_WATCH_RESOURCES` -- comma-separated resource names to watch;
  empty means every resource in the book.
- `APX_CURVE_WATCH_POLL_SECONDS` -- poll interval; default 30s. Each tick is a
  full APX round-trip, so don't set this too aggressively.
- `APX_CURVE_WATCH_STORAGE_DIR` -- where snapshots are archived; default `./curves`.
- `APX_CURVE_WATCH_LOG_FILE` -- where log output is written, in addition to the
  console; default `apx-curve-watch.log` (relative to wherever you run it from).
  Set it empty to disable file logging and keep console-only.
- `TEAMS_WEBHOOK_URL` -- optional. Unset means console + log only; set it and every
  announcement also posts to that Teams incoming webhook.
- `APX_CURVE_WATCH_NEXT_DAY_CHECK_TIMES` -- Central-time wall clocks at which to
  check that *tomorrow's* energy book has something on file, and nudge if not.
  Default `08:30-09:00:15,09:00-09:30:10,09:30-10:00:5`: every 15 min from
  08:30-09:00, every 10 min from 09:00-09:30, every 5 min from 09:30-10:00 --
  tightening as the DAM deadline approaches. Comma-separated; each entry is
  either a single time (`08:00`, fires once) or a window with a cadence
  (`08:30-09:00:15`). Every resolved time fires at most once per day, on the
  first poll tick at or after it -- not on every tick. With
  `APX_CURVE_WATCH_RESOURCES` set, a resource missing from tomorrow's book is
  named individually; left at "watch everything", only a completely empty book
  is flagged (there's no fixed resource list to check names against).

## Teams webhook

Set up via Teams' **Workflows** app -> the **"Post to a channel when a webhook
request is received"** template -> pick a team + channel -> copy the URL it
gives you into `TEAMS_WEBHOOK_URL` in `.env`.

That template posts an **Adaptive Card**, and its "Post card" action expects
the webhook's request body to itself BE a valid card -- confirmed live against
a real flow, which rejected a plain `{"text": ...}` body with
`Property 'type' must be 'AdaptiveCard'`.

The message is wrapped in a **`CodeBlock`** element (`teams_codeblock.py`),
not a bare `TextBlock` -- a `TextBlock` wraps text and loses alignment (a
single multi-line one even collapses its own newlines), and a real `Table`
element squeezes its columns unreadably thin in Teams' narrow card pane, both
confirmed live. `CodeBlock` (Teams web/desktop only, not mobile) previews only
its first ~10 lines when collapsed, but expanding it reveals the rest via a
real scroll -- nothing is silently lost, it just needs a click. Past ~9 lines,
Teams' line-number gutter has a cosmetic bug where double-digit numbers
overlap the row content; there's no schema property to turn line numbers off.

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

- No retention/pruning of old snapshots yet (expected to stay small: only
  changes, plus one `latest.json` per hour, get archived).
- Deploying this as an always-running background process (systemd timer, etc.)
  isn't set up -- right now it's `uv run apx-curve-watch` in a terminal.

## Development

```bash
uv run ruff check .
uv run ruff format .
uv run pytest
```
