# Research Paper Review

Generated for the resource bundle in `/home/omegashenr01n/Desktop/resources-20260508-163423`.

## Scope
This note reviews the linked research papers with a focus on:
- goals
- methodology
- results
- how we can integrate or extend the work
- how we can retest it
- explicit data/code/resources mentioned in the source

Where a source did not expose an explicit dataset or code link, that is stated directly instead of inferred.

---

## 1) Bitcoin price direction prediction using on-chain data and feature selection
Source: https://www.sciencedirect.com/science/article/pii/S266682702500057X  
Local copy: `webpages/S266682702500057X.html`

### Goals
- Test whether Bitcoin on-chain data can predict next-day price direction.
- Organize and classify on-chain features so their predictive value is easier to interpret.
- Reduce a large feature set before modeling.
- Compare not just classification accuracy, but downstream trading performance.

### Methodology
- Uses Bitcoin on-chain data as the predictive input for next-day direction classification.
- Applies feature-selection or dimensionality-reduction methods including L1 regression, Boruta, and PCA.
- Tests deep sequence models including CNN-LSTM and TCN.
- Compares combinations of feature-selection methods and models.
- Evaluates model outputs through trading simulation rather than stopping at ML metrics.

### Results
- Best reported combination: Boruta + CNN-LSTM with 82.03% test accuracy.
- Realized-value and unrealized-value feature groups were reported as especially predictive.
- The CNN-LSTM long-short simulation reported a 1682.7% annualized return and 6.47 Sharpe ratio.

### How we can integrate or extend it
- Build an on-chain feature pipeline grouped by economic meaning, then run Boruta before sequence modeling.
- Extend from next-day direction to multiple horizons: intraday, 3-day, and 1-week.
- Add execution-aware constraints: fees, slippage, liquidity, and turnover limits.
- Compare against newer sequence models or multimodal models that mix on-chain and market features.

### How to retest it
- Re-run with strict walk-forward splits and multiple market regimes.
- Benchmark against simpler baselines: price-only, technical-only, and no-feature-selection variants.
- Stress test reported trading performance under realistic fees and position sizing.
- Check whether the same feature groups remain predictive in newer market windows.

### Explicit data/code/resources
- Explicit source type: Bitcoin on-chain data.
- No explicit public code repository or named public dataset link was visible in the extracted source.

---

## 2) Systematic Trend-Following with Adaptive Portfolio Construction: Enhancing Risk-Adjusted Alpha in Cryptocurrency Markets
Source: https://arxiv.org/html/2602.11708v1  
Local copy: `webpages/2602.11708v1.html`

### Goals
- Improve crypto trend-following using crypto-specific signal generation, universe selection, and allocation.
- Adapt to volatility regime shifts and a fast-changing tradable universe.
- Beat standard trend-following and buy-and-hold benchmarks on risk-adjusted terms.

### Methodology
- Proposes `AdaptiveTrend`, a 3-stage framework: signal generation, asset selection, and capital allocation.
- Uses 6-hour OHLCV bars and monthly signal-threshold optimization.
- Uses ATR-based dynamic trailing stops for exits.
- Rebalances monthly after filtering by market cap and ranking with rolling Sharpe ratio.
- Allocates capital asymmetrically: 70% long, 30% short, equal-weighted within each side.
- Evaluates out of sample on 150+ crypto pairs over 2022-2024 with robustness checks on parameters, costs, and regimes.

### Results
- Reported annualized Sharpe: 2.41.
- Reported max drawdown: -12.7%.
- Reported Calmar ratio: 3.18.
- The paper reports clear outperformance versus benchmark trend-following and equal-weighted buy-and-hold portfolios.

### How we can integrate or extend it
- Use the H6 signal plus monthly universe filter as a practical crypto-system template.
- Replace equal weights with volatility targeting, risk parity, or correlation-aware sizing.
- Add liquidity, funding-rate, borrow-availability, or perp-basis filters.
- Combine trend signals with on-chain or sentiment overlays.

### How to retest it
- Reproduce using a clearly specified exchange/API data source with delisted assets preserved.
- Re-test under different transaction-cost assumptions, especially for smaller-cap names.
- Run rolling walk-forward optimization to check for monthly overfitting.
- Break results down by regime, frequency, and market-cap bucket.

### Explicit data/code/resources
- Explicit source type: 6-hour OHLCV data across 150+ crypto pairs from 2022-2024.
- No explicit code repository or clearly named market-data provider was visible in the extracted source.

---

## 3) Meta-Learning Reinforcement Learning for Crypto-Return Prediction
Source: https://arxiv.org/pdf/2509.09751  
Local copy: `papers/2509.09751.pdf`

### Goals
- Improve crypto return prediction when data is multimodal and labels are limited.
- Build a self-improving agent that updates both policy and evaluation criteria.
- Fuse on-chain, market, news, and sentiment inputs without extra human supervision.

### Methodology
- Proposes `Meta-RL-Crypto`, a closed-loop system with actor, judge, and meta-judge roles.
- The actor consumes structured multimodal inputs and produces next-day forecasts or actions.
- The judge scores outputs using a multi-objective reward vector: return, Sharpe contribution, drawdown control, liquidity/slippage awareness, and sentiment alignment.
- The meta-judge updates the judge to reduce reward drift or inconsistent scoring.
- Uses CoinMarketCap and Dune Analytics for market/on-chain data, and GNews for off-chain text.
- Adds credibility filtering and SimHash-based deduplication in the news pipeline.

### Results
- The paper reports outperforming classic time-series baselines like Informer and PatchTST, standard indicators like MACD, and several LLM baselines.
- Reported gains were described as especially strong in bear-market conditions.
- The main empirical takeaway is competitive trading performance without extra human-labeled supervision.

### How we can integrate or extend it
- Use the actor/judge/meta-judge loop as a template for self-evaluating financial agents.
- Replace single-asset outputs with portfolio-level objectives.
- Add order-book, perp funding, options-implied, or wallet-flow features.
- Reuse the judge/meta-judge pattern for post-trade critique and automated research iteration.

### How to retest it
- Re-run on fully timestamped data with strict leakage controls.
- Compare against non-LLM multimodal baselines and simpler RL setups.
- Evaluate in paper trading with realistic fees, slippage, and turnover limits.
- Test stability under different reward weights, sentiment sources, and market regimes.

### Explicit data/code/resources
- Explicit data sources: CoinMarketCap, Dune Analytics, and GNews.
- Explicit processing note: SimHash-based deduplication.
- No explicit released code repository was visible in the extracted source.

---

## 4) A Time-Varying Network for Cryptocurrencies
Source: https://arxiv.org/pdf/2108.11921  
Local copy: `papers/2108.11921.pdf`

### Goals
- Model evolving linkages among cryptocurrencies through return cross-predictability and technology similarity.
- Estimate time-varying crypto communities.
- Test whether community structure helps diversification and cross-sectional trading.

### Methodology
- Uses a sample of 182 cryptocurrencies over 2016-01-01 to 2018-12-31.
- Builds a directed return network using rolling regressions on lagged standardized returns with adaptive Lasso.
- Adds technology covariates such as hashing algorithm and proof type.
- Uses dynamic covariate-assisted spectral clustering to estimate community memberships.
- Tests usefulness through diversification analysis and a community-based momentum portfolio.

### Results
- Return-plus-technology community structure helped reveal segmentation and risk propagation.
- Diversification improved when holding assets from different communities.
- The paper reports a community-based inter-crypto momentum strategy earning 1.08% average daily return.
- The paper reports no one-week reversal and says the effect was not explained by several behavioral controls.

### How we can integrate or extend it
- Use community labels as dynamic risk buckets in portfolio construction.
- Add network/community features to alpha models and risk dashboards.
- Extend covariates beyond proof type into on-chain activity, dev activity, bridge exposure, or tokenomics.
- Combine community assignments with momentum or relative-value signals.

### How to retest it
- Rebuild the sample from the same period and rerun the rolling adaptive-Lasso network.
- Compare return-only, tech-only, and combined-network variants.
- Test sensitivity to window length, clustering assumptions, and transaction costs.
- Re-run on post-2018 market structure to test persistence.

### Explicit data/code/resources
- Explicit data source: CryptoCompare API for daily prices, trading volumes, and contract attributes.
- No explicit public code link was surfaced in the extracted source.

---

## 5) To Trade Or Not To Trade: Cascading Waterfall Round Robin Rebalancing Mechanism for Cryptocurrencies
Source: https://arxiv.org/pdf/2407.12150  
Local copy: `papers/2407.12150.pdf`

### Goals
- Design a crypto/DeFi portfolio rebalancing mechanism that decides whether to trade, how much to trade, and how many trades to split into.
- Handle blockchain-specific frictions such as gas fees and slippage.
- Provide a framework that can generalize across frequencies and asset classes.

### Methodology
- Defines minimum, ideal, and maximum asset weights rather than only point targets.
- Computes asset capacity using risk/return properties, cross-asset relationships, and net inflow/outflow.
- Allocates deposits or redemptions via a round-robin cascading waterfall process.
- Adds minimum and maximum trade-size rules to balance gas costs and slippage.
- Uses threshold or boundary-crossing logic so trades happen when ranges are breached.
- Illustrates the mechanism with numerical examples and network-specific discussion.

### Results
- The mechanism is designed to output ideal trade sizes and trade counts while accounting for execution frictions.
- It is intended to benefit from volatility while filtering noise through thresholded execution.
- The extracted source contained numerical examples, but not a strong large-sample empirical benchmark section.

### How we can integrate or extend it
- Implement it as an execution-aware overlay on top of a target-allocation engine.
- Feed real-time gas, liquidity depth, and slippage estimates into the trade-band logic.
- Extend it to cross-chain treasury management, LP/vault rebalancing, or token baskets.
- Compare it with periodic, tolerance-band, and optimization-based rebalancers.

### How to retest it
- Backtest on historical portfolio states plus realized gas/slippage.
- Benchmark turnover, tracking error, and net returns against simpler rebalancing rules.
- Stress test under liquidity droughts, volatility spikes, and chain fee shocks.
- Check whether threshold logic improves post-cost outcomes rather than merely reducing trade count.

### Explicit data/code/resources
- The source explicitly discusses numerical examples.
- No explicit public dataset or code repository was visible in the extracted source.

---

## 6) Beyond Trading Data: The Hidden Influence of Public Awareness and Interest on Cryptocurrency Volatility
Source: https://arxiv.org/pdf/2202.08967  
Local copy: `papers/2202.08967.pdf`

### Goals
- Test whether Bitcoin volatility forecasting improves when non-price signals are added.
- Measure the impact of public sentiment, public interest, and blockchain activity on volatility.
- Produce a forecasting model useful both for prediction and fluctuation-distribution estimation.

### Methodology
- Proposes `CoMForE`, a multimodal AdaBoost-LSTM ensemble for next-day BTC-USD volatility forecasting.
- Combines historical trading data with tweet sentiment, search-interest signals, hash rate, and network difficulty.
- Trains multiple LSTM weak learners on sampled subsets and combines them with AdaBoost-style weighting.
- Evaluates using comparative experiments with reimplemented baselines on the same dataset and period.
- Goes beyond point prediction by estimating volatility or fluctuation distribution.

### Results
- The paper reports a 19.29% improvement over prior forecasting methods.
- Multimodal inputs outperformed trading-data-only setups.
- The source argues that external independent factors materially influence crypto volatility.
- The model is presented as more useful for decisions because it predicts both direction of fluctuation and distribution characteristics.

### How we can integrate or extend it
- Build a multimodal crypto risk model that fuses market, social, search, and on-chain inputs.
- Add modality-level ablations or explainability to determine which channel matters by regime.
- Extend from BTC volatility forecasting into options/risk-management workflows.
- Replace AdaBoost-LSTM with transformers or state-space models while keeping the multimodal stack.

### How to retest it
- Rebuild the multimodal data pipeline and compare trading-only versus multimodal variants.
- Re-run with strict out-of-sample splits and identical baseline implementations.
- Test robustness across market regimes and other coins.
- Check both forecast accuracy and calibration of the predicted fluctuation distribution.

### Explicit data/code/resources
- Explicit data types: historical trading data, tweet sentiment, search volumes, and blockchain data including hash rate and network difficulty.
- The source says an open-source implementation exists on GitHub, but the extracted material did not expose the exact repository URL.

---

## 7) Dynamic Latent-Factor Model with High-Dimensional Asset Characteristics
Source: https://arxiv.org/pdf/2405.15721  
Local copy: `papers/2405.15721.pdf`

### Goals
- Develop estimation and inference for a dynamic latent-factor model when characteristics are high dimensional.
- Use regularization to eliminate weak characteristics without breaking valid asset-pricing inference.
- Apply the framework to crypto and test whether an observable nontradable inflation factor earns a premium.

### Methodology
- Models time-varying loadings as a linear function of high-dimensional characteristics.
- Proposes the Double Selection Lasso Factor Model (`DSLFM`).
- Runs double-selection Lasso in the first stage, then applies PCA to a stacked time-by-characteristic matrix.
- Uses soft-thresholding to zero out weak characteristic rows.
- Builds supporting econometric theory for estimation and inference.
- Extends the framework to test a nontradable-factor risk premium.

### Results
- The paper reports comparable out-of-sample pricing and risk-adjusted returns versus benchmark methods in crypto.
- Searchable source excerpts indicate exchange inflows and outflows were important characteristics in the empirical application.
- One excerpt reports a maximum one-factor out-of-sample Sharpe of about 3.3, versus an IPCA benchmark maximum of 4.07.
- The paper reports a positive and statistically significant inflation-mimicking portfolio premium, translated to roughly 7.3% annual excess return.

### How we can integrate or extend it
- Use DSLFM when the universe is feature rich but history is short, especially in crypto or DeFi panels.
- Use it as a sparse screening layer before nonlinear modeling.
- Extend the nontradable-factor test to sentiment, regulation, stablecoin flows, liquidity, or macro surprises.
- Compare selected characteristics across subperiods as a regime-detection signal.

### How to retest it
- Re-run on later crypto windows and different rebalance frequencies.
- Benchmark directly against PCA, IPCA, and simpler observable-factor models.
- Stress test performance as p, N, and T vary and panels become more unbalanced.
- Re-estimate the inflation-risk result with alternative inflation proxies.

### Explicit data/code/resources
- Explicit code link: https://github.com/adambaybutt/crypto_asset_pricing
- Explicit author page: http://www.adambaybutt.org/research.html
- The retrieved source clearly showed a crypto empirical application, but the extracted portion did not enumerate a full data-source list.

---

## 8) Crypto Pricing with Hidden Factors
Source: https://arxiv.org/pdf/2601.07664  
Local copy: `papers/2601.07664.pdf`

### Goals
- Estimate crypto risk premia while allowing for omitted latent factors.
- Test whether expected crypto returns load only on crypto-native risks or also on traditional equity risks.
- Evaluate state variables tied to sentiment, speculative rotation, and security shocks.

### Methodology
- Uses the Giglio-Xiu three-pass latent-factor approach alongside observed stock and crypto factors.
- Uses weekly data from 2023-01-01 to 2024-12-31 on non-stablecoins that were in the top 100 by market cap at any point.
- Builds tradeable crypto factors: market, SMB, momentum, and a TVL factor orthogonalized to market.
- Adds traditional factors including stock-market, profitability, and selected industry portfolios.
- Studies nontradable state variables including Fear & Greed, Altcoin Season, and hacked value scaled by market capitalization.
- Compares latent-factor estimates with conventional Fama-MacBeth estimates.

### Results
- Expected crypto returns load on both crypto-native and selected equity factors.
- Crypto market risk is positively priced, while crypto SMB is strongly negatively priced.
- Fear & Greed shocks show explanatory power for expected returns.
- Altseason effects weaken under the latent-factor specification.
- Hacked-value shocks are not priced in the sample studied.
- TVL evidence is weak once latent factors are controlled for.

### How we can integrate or extend it
- Add latent-factor controls before trusting observable-factor premia in crypto cross-sectional work.
- Blend crypto-native and selected equity factors in integrated models.
- Treat sentiment/state variables as regime inputs rather than standalone alphas.
- Use this as a template for cross-asset factor decomposition between crypto and equities.

### How to retest it
- Re-run the three-pass procedure on post-2024 data.
- Check robustness to universe cutoffs, weighting schemes, and rolling windows.
- Compare latent-factor results to Fama-MacBeth and pure observable-factor models on the same sample.
- Re-test the state variables around later hacks and stronger alt-rotation regimes.

### Explicit data/code/resources
- Explicit data sources: CoinMarketCap API, DeFiLlama, thecvx.com, CoinMarketCap Altcoin Season data, CoinMarketCap Fear & Greed data, and the Kenneth French data library.
- The arXiv source marks the paper as a preliminary draft and says not to cite without permission.
- No explicit code repository was identified in the extracted source.

---

## 9) The Surprising Irrelevance of Total-Value-Locked on Cryptocurrency Returns
Source: https://arxiv.org/pdf/2506.03287  
Local copy: `papers/2506.03287.pdf`

### Goals
- Test the claim that higher TVL implies higher crypto returns.
- Check whether TVL-sorted portfolios contain alpha after controlling for standard crypto risk factors.
- See whether the conclusion changes when TVL is cleaned up to reduce overstatement.

### Methodology
- Uses weekly returns from 2023-01-02 to 2024-12-31 on cryptocurrencies that were in the top 100 by market cap at any point.
- Excludes Bitcoin and stablecoins.
- Forms value-weighted portfolios sorted by TVL/market cap and by changes in TVL/market cap.
- Runs tests using both total TVL and a cleaner `simple TVL` measure.
- Evaluates both the full sample and a Level 1 subset.
- Tests returns against a one-factor crypto market model and a three-factor crypto model with market, SMB, and momentum.

### Results
- Alpha coefficients are insignificant across TVL-formed portfolios, so the paper finds no distinct TVL alpha.
- A single-factor aggregate crypto market model is reported as sufficient to explain the cross-section of TVL-sorted returns.
- For total-TVL portfolios, factor models explain roughly 73% to 93% of return variation.
- Change-in-TVL portfolios are also explained by factor models, though with lower fit.
- The conclusion is robust across total TVL, simple TVL, and the Level 1 subset.

### How we can integrate or extend it
- Treat TVL mainly as a risk-exposure or ecosystem descriptor, not as a standalone return signal.
- Combine TVL with orthogonal fundamentals such as fees, active users, retention, or protocol revenue quality.
- Use TVL for clustering or protocol classification while relying on broader factor and regime models for prediction.
- Test whether verifiable TVL or utilization measures work better than raw TVL.

### How to retest it
- Re-run the portfolio tests on post-2024 data and later DeFi cycles.
- Test equal-weighted, different breakpoints, and different rebalance frequencies.
- Compare raw TVL, simple TVL, verifiable TVL, and utilization metrics.
- Add transaction costs, turnover analysis, and rolling stability checks.

### Explicit data/code/resources
- Explicit data/resources mentioned: CoinMarketCap API and DeFiLlama.
- The source explicitly defines the exclusions used to construct `simple TVL`.
- No explicit code repository was identified in the extracted source.

---

## Repository snapshot: awesome-quant-ai
Source: https://github.com/leoncuhk/awesome-quant-ai  
Local copy: `awesome-quant-ai/`

### What it is
- A curated awesome-list for AI/ML applications in quantitative finance.
- Not a single strategy repo. More of a map of the field plus notebooks, notes, and references.

### What is inside
- `README.md`: main curated list.
- `book/myquant/`: 8-chapter strategy guide with Python-oriented material.
- `book/`: book notes including systematic trading material.
- `think/`: original essays on HMMs, Markov switching, fuzzy systems, and AI-agent trading.
- `paper/`: academic PDFs.
- `tools/`: notebooks such as `pybroker.ipynb`.
- `assets/`: diagrams and reference images.

### How we can use it
- Use it as a literature and tooling index for follow-up experiments.
- Mine the `think/` and `book/myquant/` sections for implementation ideas and baseline workflows.
- Use the tools/notebooks as a quick starting point for prototyping.
- Treat it as a reference layer that helps connect methods across factor investing, RL, trend following, volatility forecasting, and agentic trading.

### Limits
- It is curated reference material, not a controlled benchmark suite.
- Individual linked resources still need their own reproducibility checks.

---

## Cross-paper takeaways

### What looks most directly usable
1. On-chain feature selection plus sequence models for BTC directional prediction.
2. Adaptive crypto trend-following with explicit universe selection and risk controls.
3. Multimodal pipelines combining market, on-chain, sentiment, and search data.
4. Dynamic network/community structure for portfolio construction and diversification.
5. Factor work showing that TVL alone is weak and latent/common factors matter more.

### Immediate experiments worth running
1. Build a benchmark panel with price, volume, on-chain, TVL, sentiment, and search data.
2. Test three families side by side:
   - trend-following / cross-sectional momentum
   - multimodal volatility or direction forecasting
   - latent-factor / characteristic-sparse cross-sectional models
3. Use TVL as context or risk classification, not as a standalone alpha.
4. Add strict walk-forward validation, delisting-aware universes, and realistic fee/slippage assumptions from day one.

### Data/code surfaced directly from the sources
- CoinMarketCap
- Dune Analytics
- GNews
- CryptoCompare
- DeFiLlama
- Kenneth French data library
- thecvx.com
- `https://github.com/adambaybutt/crypto_asset_pricing`
- local repo: `awesome-quant-ai/`

### Gaps to keep in mind
- Several papers did not expose code links in the retrieved source.
- Some papers reported strong results but need replication under tighter cost and leakage controls.
- One paper (`Crypto Pricing with Hidden Factors`) is explicitly marked as a preliminary draft.
