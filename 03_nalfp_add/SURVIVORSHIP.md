# Survivorship Bias — Stage 09 Universe

*Required treatment for Goal 1. Read alongside `GOALS.md` and the frozen
`artifacts/manifests/universe_manifest.json`.*

## What the bias is

Survivorship bias is the distortion that arises when a backtest's universe is
chosen using information that was only available *after* the fact — typically,
"coins that are still alive and large today." Dead and delisted coins are
silently dropped, so the sample over-represents winners and **inflates returns,
Sharpe, and the apparent reliability of any factor** estimated on it. In crypto
the effect is severe: the mortality rate of tokens is far higher than equities,
and the survivors are exactly the names that went *up*.

## Where it enters our pipeline (two distinct places)

**1. The candidate pool itself (`Coins.md`).** The pool is a CoinGecko
market-cap snapshot dated **2026-05-08** — i.e. it is already conditioned on
survival and size *as of today*. Coins that were large in 2021–22 but have since
collapsed or delisted (e.g. most of the dead-alt long tail; centralized-exchange
tokens that blew up) are simply absent. This is the largest, and least
removable, source of bias, because it is upstream of everything we do. We did
not construct this snapshot; we inherit it.

**2. The estimation backbone.** By construction the backbone requires ≥5 years
of continuous history *to today*, so it **is a survivor set**. Every backbone
coin is, definitionally, one that lived through 2021–25 without dying. Returns
measured on the backbone are upward-biased and must not be read as achievable
premia.

## How the Stage 09 design *reduces* it

The key design choice — made explicit on the user's instruction — is that the
**trading universe is point-in-time, not a fixed survivor set**:

- A coin becomes eligible in week *t* as soon as it has enough trailing history
  to compute its characteristics (`trading_min_trailing_weeks`), and it leaves
  the universe when its data ends. Coins **enter and exit** over time.
- This means a coin that was investable and ranked highly in, say, 2022 but later
  faded is included **for the period it was actually live and tradable** — which
  is precisely the realistic experience of a portfolio rebalancing each week. We
  do not retroactively delete it for failing to survive to 2026.
- Market-cap ranking is done with **point-in-time market cap** (real where
  available, reconstructed `price × supply` otherwise), not with today's cap, so
  the universe membership at week *t* reflects what was big *at week t*.

This converts the trading test from "how would today's survivors have done" into
"how would a weekly rebalance over the live cross-section have done" — the
correct, much less biased question.

## Residual bias we cannot remove with current data, and its direction

- **Delisting / death is still under-captured.** Because the candidate pool is a
  2026 snapshot, tokens that died *before* 2026 and never appear in `Coins.md`
  are missing even from the point-in-time universe. Binance-delisted pairs also
  simply end. Net direction: **returns remain biased upward**; the bias is
  largest in the earliest part of the sample (most pre-2026 deaths) and in the
  small-cap leg (where mortality concentrates).
- **The backbone is fully survivor-conditioned** and is used *only* for
  estimating latent-factor structure (loadings, communities), **not** for
  making return-premium claims.

## Mitigations applied and recommended

Applied now:
1. Point-in-time, entry/exit trading universe (above).
2. Separation of the survivor-set backbone (structure estimation only) from the
   point-in-time trading universe (performance evaluation).
3. Reconstructed point-in-time market cap for ranking, so membership is not set
   by today's sizes.
4. Honest reporting: every performance figure on this universe is to be labelled
   as resting on a 2026-snapshot candidate pool.

Recommended (future work, needs additional data):
5. Source a **point-in-time universe that includes delisted tokens** (e.g.
   CoinMetrics/Kaiko historical constituents) to restore the dead names and
   bound the residual bias.
6. Report a **delisting-return assumption** stress test (e.g. −100% on the final
   observation for coins whose data ends mid-sample) to put a conservative floor
   under the small-cap leg.

## Bottom line

The Stage 09 design removes the *worst* form of the bias — evaluating on a frozen
set of today's survivors — by trading a point-in-time, entry/exit universe ranked
on point-in-time market cap. A residual upward bias remains because the candidate
pool is a present-day snapshot that cannot contain coins that already died; this
is disclosed, its direction (upward, concentrated early and in small caps) is
known, and the path to bounding it is identified.
