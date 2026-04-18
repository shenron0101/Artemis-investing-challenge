# AGENTS.md

## Scope

This repo is for Artemis Analytics Quant Competition Track #1: Crypto Factor Rebalancing Strategy.

Primary goal:
- Build a systematic, rules-based crypto portfolio strategy with a reproducible backtest.
- Produce three submission artifacts:
  1. Research report
  2. Reproducible analysis repository
  3. Pitch deck

## Communication Rule

Keep outputs short.

## Project Priorities

Optimize for:
1. Research quality
2. Reproducibility
3. Signal validity
4. Critical evaluation
5. Clear communication

Prefer:
- simple rules over complex ones
- honest results over impressive-looking backtests
- explicit assumptions over hidden choices

## Competition Requirements

The strategy should clearly define:
- the investment universe
- factor or signal logic
- weekly rebalance timing
- portfolio construction rules
- backtest window
- performance metrics

At minimum, report:
- returns
- Sharpe ratio
- max drawdown
- turnover

Also discuss:
- regime dependence
- overfitting risk
- practical risks
- failure modes

## Data Access Rule

- All notebooks (01–10) must assume data is available locally on disk. They must never fetch from APIs.
- Only `notebooks/00_setup.ipynb` is responsible for fetching data from external sources (CoinGecko, Artemis, etc.) and saving it locally.
- If a notebook needs data, it reads from `data/` — it does not call any API.

## Backtest Guardrails

These are mandatory:
- No future data leakage
- No survivorship bias where avoidable
- Clear rebalance timestamp convention
- Mechanical universe selection rules
- Explicit handling of missing data and delistings
- Clear benchmark comparison

If a data field is delayed in the real world, lag it conservatively.

## Universe Standards

Universe selection must be rule-based and documented.

Example style:
- top assets by trailing 7-day USD volume
- exclude stablecoins
- require minimum listing history
- require minimum data coverage

Do not change universe rules just to improve backtest results.

## Factor Standards

Every factor should have:
- economic intuition
- exact definition
- timestamp/lag assumption
- coverage check
- robustness discussion

Prefer a small number of well-motivated signals over many weak ones.

## Evaluation Standards

Always compare against at least one simple baseline, such as:
- equal-weight universe basket
- market-cap-weighted universe basket
- BTC reference when appropriate

Preferred evaluation includes:
- cumulative return
- annualized return
- annualized volatility
- Sharpe ratio
- max drawdown
- turnover
- behavior across different market regimes

## Overfitting Rules

Avoid:
- large parameter sweeps
- repeatedly changing definitions to fit outcomes
- adding factors without strong rationale

Prefer:
- one clear base strategy first
- small, motivated variations
- explicit disclosure of weak or unstable results

## Deliverable Standard

The report should explain:
- thesis
- data sources
- strategy rules
- backtest setup
- results
- limitations
- what would break the strategy

The pitch deck should be understandable to a non-technical audience.

## Workflow

Default order:
1. Confirm data availability and timestamp meaning
2. Define the universe
3. Define the rebalance convention
4. Build a simple baseline
5. Test one well-motivated factor
6. Evaluate honestly
7. Stress test across regimes
8. Prepare report and deck

## What Not To Do

- Do not optimize for Sharpe at the expense of credibility
- Do not hide weak periods
- Do not use future constituent information
- Do not present unreproducible results as final
- Do not overclaim implementability

## Submission Bar

Before considering the project ready, verify:
- results are reproducible
- assumptions are written clearly
- benchmarks are included
- limitations are stated plainly
- the report and deck match the analysis
