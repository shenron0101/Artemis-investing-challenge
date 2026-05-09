# Artemis Track #1 Research Consolidation

Source bundle: `/home/omegashenr01n/Desktop/resources-20260508-163423`

Related prior note: `/home/omegashenr01n/Desktop/resources-20260508-163423/notes/research_paper_review.md`

Challenge scope:
- Artemis Quant Competition
- Track #1 only
- Crypto Factor Rebalancing Strategy
- Not Track #2

---

## 1. What this document is trying to do

This is not a short summary of the downloaded material.

The goal here is to turn the papers, webpages, and repo into a usable research map for Artemis Track #1. That means three things:

1. extract what each source is actually claiming
2. decide which claims are useful for a crypto factor rebalancing system
3. turn those claims into a concrete research and backtesting plan with data, factors, portfolio construction, and validation logic

The useful question is not “which paper is smartest?”

The useful question is: which ideas survive contact with a live, investable, cross-sectional crypto portfolio under realistic data and implementation constraints?

---

## 2. Source inventory used for this consolidation

### 2.1 Papers / webpages reviewed

1. Bitcoin price direction prediction using on-chain data and feature selection — Dubey & Enke (2025), *Machine Learning with Applications* — **full PDF now available**
2. Systematic Trend-Following with Adaptive Portfolio Construction: Enhancing Risk-Adjusted Alpha in Cryptocurrency Markets
3. Meta-Learning Reinforcement Learning for Crypto-Return Prediction
4. A Time-Varying Network for Cryptocurrencies
5. To Trade Or Not To Trade: Cascading Waterfall Round Robin Rebalancing Mechanism for Cryptocurrencies
6. Beyond Trading Data: The Hidden Influence of Public Awareness and Interest on Cryptocurrency Volatility
7. Dynamic Latent-Factor Model with High-Dimensional Asset Characteristics
8. Crypto Pricing with Hidden Factors
9. The Surprising Irrelevance of Total-Value-Locked on Cryptocurrency Returns
10. Ranked Asset Allocation Model (RAAM) — CMT Association practitioner paper — **new addition**

### 2.2 Non-paper material reviewed

1. `awesome-quant-ai/README.md`
2. `awesome-quant-ai/think/AI-Agent Trading.md`
3. `awesome-quant-ai/think/HMM Quantitative Trading Strategy An Overview.md`
4. `awesome-quant-ai/think/Markov-Switching Model Application.md`
5. `awesome-quant-ai/book/Systematic Trading A unique new method for designing trading and investing systems.md`
6. `rank.md` — Ranked Asset Allocation Model clipping from CMT Association
7. prior Artemis notes in vault:
   - `Artemis Quant Competition - Kanban.md`
   - `Data Sources Reference.md`
   - `Data Groupings.md`

### 2.3 Important note on source quality

The local ScienceDirect HTML file for the Bitcoin on-chain paper was previously a broken cached error page. The full peer-reviewed PDF (`1-s2.0-S266682702500057X-main.pdf`) is now available and section 5.1 has been updated accordingly.

Some sources here are polished empirical papers, some are working papers, some are conceptual frameworks, and some are practitioner notes. They should not be weighted equally.

---

## 3. Artemis Track #1: what the challenge actually rewards

The challenge is not asking for a beautiful single-asset predictor. It is asking for a defendable crypto factor rebalancing strategy.

That shifts the emphasis away from isolated predictive accuracy and toward:

- cross-sectional ranking power
- robustness across regimes
- investable universe design
- turnover control
- reasonable cost assumptions
- portfolio construction discipline
- economic intuition for why the factors should exist

That framing immediately changes how the downloaded research should be used.

For Artemis Track #1:

- direction-prediction papers are useful mainly as feature ideas, not as final submission templates
- factor-pricing papers are useful mainly for deciding which variables are real factors versus mere exposure proxies
- trend-following papers are useful for portfolio construction, universe filtering, and regime adaptation
- rebalancing papers are useful because net performance depends heavily on execution discipline
- multimodal AI papers are useful for exploratory overlays and post-trade critique, but they are not automatically the best first submission architecture

The best Artemis strategy will probably be less exotic than the most exotic paper in this bundle.

---

## 4. Cross-source synthesis: the major ideas that keep repeating

### 4.1 Raw activity is noisy; quality-adjusted activity matters more

This is one of the cleanest themes across the material.

The Artemis data notes show explicit real-vs-gamed distinctions such as:
- adjusted transactions
- adjusted volume
- percent gamed transactions
- percent gamed volume

The Bitcoin on-chain paper also found that certain economically meaningful on-chain feature groups were more predictive than a generic pile of blockchain variables.

Implication for Artemis:
- do not use raw usage growth blindly
- favor adjusted / real activity
- treat gamed-share metrics as penalties or quality screens
- prefer “growth in economically meaningful usage” over “growth in anything countable on-chain”

This is likely one of the highest-value lessons in the entire bundle.

### 4.2 TVL is context, not alpha

Two papers push in the same direction:
- `The Surprising Irrelevance of Total-Value-Locked on Cryptocurrency Returns`
- `Crypto Pricing with Hidden Factors`

Both imply that TVL alone is weak as a standalone return predictor once common crypto factors and latent risks are controlled for.

Implication for Artemis:
- TVL should not be a primary factor by itself
- TVL is better used as context, denominator, clustering variable, or capital-efficiency input
- more useful constructs are likely fees/TVL, revenue/TVL, or TVL quality rather than raw TVL level

If we build a portfolio around “high TVL tokens outperform,” we are probably building an expensive way to rediscover crypto beta.

### 4.3 Crypto factors are partly crypto-native and partly cross-asset

`Crypto Pricing with Hidden Factors` is important because it argues that crypto expected returns are not fully self-contained. Some equity-related risks appear to matter as well.

Implication for Artemis:
- factor claims should be tested with latent/common-risk controls
- avoid confusing a token-specific “fundamental” factor with broad risk-on tech exposure
- it is worth tracking external state variables such as sentiment, alt rotation, or macro liquidity when evaluating crypto factors

For portfolio research this means:
- a factor may look good in raw returns but disappear once market, size, momentum, and regime exposures are accounted for
- factor attribution matters almost as much as headline Sharpe

### 4.4 Regime dependence is real

Several sources converge here:
- AdaptiveTrend explicitly adapts thresholds and allocation to market conditions
- HMM and Markov-switching notes center regime detection as a first-class design problem
- the multimodal volatility paper argues that public awareness, search, and sentiment affect crypto behavior
- Meta-RL-Crypto highlights different performance across market regimes

Implication for Artemis:
- a single static factor weight is unlikely to be optimal across all periods
- at minimum, use regime diagnostics even if the final strategy remains simple
- a practical regime filter could use stablecoin liquidity, market breadth, volatility, or Fear & Greed as conditioning variables

### 4.5 Network structure and diversification are underused edges

`A Time-Varying Network for Cryptocurrencies` adds something most simple factor papers ignore: crypto assets are linked through evolving communities.

Implication for Artemis:
- portfolio construction should not assume every token is an independent bet
- community/sector/chain clustering can be used to prevent overconcentration in one narrative bubble
- diversification in crypto is not just “hold more names”; it is “hold names from different dependency clusters”

This is especially useful for a rebalancing challenge because it improves portfolio design without requiring a prediction model that is too clever for its own good.

### 4.6 Rebalancing itself is a source of alpha leakage

The rebalancing mechanism paper is not a return-prediction paper, but it matters. In crypto, turnover, gas, slippage, and size thresholds can easily destroy a signal that looked strong before costs.

Implication for Artemis:
- the factor model and the rebalancing rule should be designed together
- tolerance bands, minimum trade thresholds, and partial rebalance logic may materially improve net results
- if two strategies have similar gross Sharpe, the one with lower turnover is probably more believable

### 4.7 Multimodal / LLM / RL systems are promising, but should be second-stage research

Meta-RL-Crypto and the AI-agent repo materials are interesting, but they are not the best place to start if the goal is a defensible competition submission.

Why:
- they add many degrees of freedom
- leakage risk is higher
- reproducibility is lower
- the economic story is harder to communicate
- they can outperform in experiments while still being fragile in live-like validation

Implication for Artemis:
- use them as research overlays, model-comparison tools, or post-trade critics
- do not make them the only strategy unless simpler baselines are already beaten cleanly

### 4.8 Multi-factor composite ranking with volatility and correlation penalties is a proven practical architecture

The RAAM paper (section 5.10) demonstrates that combining momentum, GARCH volatility, and average pairwise correlation into a single composite rank — then selecting only the top-N ranked assets and substituting cash for any with negative momentum — produces a robust, defensible allocation system.

This architecture mirrors what the academic factor papers are recommending from a different direction. It adds two key practitioner refinements:
- low-volatility assets are rewarded (not just penalized for risk)
- low-correlation assets are rewarded (diversification as a scoring input, not just a post-hoc constraint)

Implication for Artemis:
- the composite rank approach (rank each factor separately, sum the ranks, select top-N) is directly implementable
- weighting the rank components (wM, wV, wC) is a low-parameter tuning problem suitable for a simple walk-forward
- applying the ATR Trend/Breakout System as a multiplier or veto gate on the composite rank maps well to crypto regime filtering
- the cash-substitution rule (replace any negative-momentum winner with a risk-free or stablecoin allocation) is a clean drawdown-control mechanism appropriate for Track #1

---

## 5. Paper-by-paper extraction and Artemis relevance

## 5.1 Bitcoin price direction prediction using on-chain data and feature selection

Source type:
- **Full peer-reviewed PDF now available**: Dubey, R. & Enke, D. (2025). *Machine Learning with Applications*, 20, 100674. DOI: 10.1016/j.mlwa.2025.100674
- Open access (CC BY-NC-ND 4.0)
- Missouri University of Science and Technology, Laboratory for Investment and Financial Engineering

### Goal
The paper asks whether Bitcoin on-chain data can predict next-day price direction, and whether feature selection can improve both predictive accuracy and trading outcomes.

### Methodology
Core steps:
- source: Glassnode daily Bitcoin on-chain dataset, 196 features, 12/13/2012 to 05/14/2023
- classify all features into five economically meaningful categories: **Activity**, **Realized Value**, **Unrealized Value**, **Stationarity**, and **Exchange Balance**
- reduce dimensionality using L1 regression (Lasso), Boruta (Random Forest-based), and PCA
- in-sample period: 12/13/2012 to 04/13/2021 (80% train / 20% test, randomization off to preserve temporal order)
- out-of-sample validation period: 04/19/2021 to 05/14/2023
- train deep sequence models: CNN-LSTM and Temporal Convolutional Network (TCN)
- compare model combinations on both classification accuracy and trading simulation returns

### Main results
Reported headline findings:
- **Boruta + CNN-LSTM** was the best combination: **82.03% test accuracy**
- Realized Value and Unrealized Value feature categories had the highest correlation with the directional target; Stationarity also ranked high
- Activity and Exchange Balance categories showed lower raw predictive correlation
- Top correlated features surfaced by Table 2 of the paper include UTXO-based and MVRV-type metrics
- Long-Short trading simulation with CNN-LSTM: **annualized return 1,682.7%, Sharpe Ratio 6.47**
- All trading results are gross — no transaction costs included

### What the paper is really telling us
The most portable lesson is not the exact CNN-LSTM architecture.

The portable lesson is that **feature family membership predicts predictive power**. Realized-value and unrealized-value features (MVRV, SOPR, realized cap ratios) are substantially more informative than raw activity counts. This is a principled finding, not a coincidence: those features capture whether existing holders are in profit or loss, which has macro-momentum implications even at daily resolution.

The secondary lesson: Boruta (which tests features against random noise probes using Random Forest) outperformed Lasso and PCA as a selection mechanism. This favors non-linear interaction detection over simple shrinkage.

### How to use it for Artemis
Use this paper to justify an on-chain factor-engineering workflow:
- group Artemis / on-chain variables into economic families matching the paper's taxonomy
- build composite growth measures within each family
- run feature screening (Boruta-style importance ranking is feasible) before final scoring
- weight realized-value and unrealized-value analogues most heavily in the initial factor candidate set

Useful groups for Artemis mapping:
- **adoption / activity**: adjusted txns, DAU, buyers, sellers (maps to Activity category)
- **quality / gamed-share**: real/total ratios, percent gamed (quality screen, no direct paper equivalent)
- **monetization / realized value**: fees, revenue, active revenue, fees/TVL (closest to Realized Value category)
- **capital deployment / unrealized value**: TVL, market cap / TVL ratio (closest to Unrealized Value category)
- **exchange flow**: exchange net flows, stablecoin ratios (maps to Exchange Balance category)

### How to retest it properly
For Track #1, do not retest this as a next-day BTC classifier only.

Instead:
1. convert the feature family philosophy into cross-sectional features across many tokens
2. compare screened vs unscreened factor sets using Boruta importance as a selector
3. test weekly and monthly rebalancing, not just daily prediction
4. include fees/slippage and turnover in the simulation layer
5. compare against a simple price momentum baseline
6. specifically test whether MVRV/realized-value analogues are the strongest cross-sectional predictors, as the paper implies they would be

### Data / code we can reuse
Explicitly surfaced in the paper:
- Glassnode as primary on-chain data source (196 raw features documented in Appendix A)
- No public code repository identified

Operational substitute for Artemis:
- use Artemis adjusted metrics instead of raw blockchain metrics
- use DeFiLlama for TVL and fee/revenue data (realized-value analogues)
- use CoinGecko for market cap and supply data (unrealized-value analogues)

### Caveat
The reported trading returns (1,682.7% annualized, Sharpe 6.47) are Bitcoin-only, long-short, gross of costs, and derived from a single in-sample/out-of-sample split. They should be treated as an existence proof that the feature family approach works directionally, not as a realistic return target. In a cross-sectional multi-asset setting with real costs, figures will be far lower.

---

## 5.2 Systematic Trend-Following with Adaptive Portfolio Construction

### Goal
Build a crypto trend-following system that adapts to volatility and changing universe composition, and outperform static trend-following and buy-and-hold benchmarks on a risk-adjusted basis.

### Methodology
The paper proposes `AdaptiveTrend`, a three-stage framework:
1. signal generation
2. portfolio selection
3. capital allocation

Important details:
- 6-hour OHLCV data
- monthly threshold optimization
- ATR-based trailing stops
- monthly rebalance
- market-cap filter plus rolling-Sharpe ranking
- 70/30 long-short allocation, equal-weight inside each side
- robustness checks on costs, regime, parameters, and timeframe

### Main results
Reported outcomes:
- Sharpe about 2.41
- max drawdown about -12.7%
- Calmar about 3.18
- clear outperformance versus benchmark trend systems and equal-weighted buy-and-hold in the reported sample

### What the paper is really telling us
This paper is less about “trend works” and more about “trend works better when the universe and allocation engine are designed properly.”

That is very relevant to Artemis Track #1.

### How to use it for Artemis
Use this as the main benchmark architecture, even if the final factor stack differs.

What to borrow:
- universe filtering before scoring
- explicit treatment of frequency choice
- adaptive thresholds rather than one eternal cutoff
- volatility-aware exits or weight scaling
- regime-by-regime evaluation

How to adapt it:
- replace pure trend score with a composite factor score
- keep trend as one leg of the factor mix
- use long-only submission version unless rules explicitly encourage shorting/leverage
- add Artemis adjusted-usage and DeFiLlama monetization features on top of momentum

### How to retest it properly
1. reproduce a simple trend-only baseline on a broad liquid universe
2. test daily vs weekly vs monthly rebalance
3. compare equal-weight, inverse-vol, and capped score-weight allocation
4. test whether adding on-chain quality and monetization beats trend alone
5. separate large-cap and mid-cap subsets

### Data / code we can reuse
Explicitly surfaced:
- 6-hour OHLCV across 150+ pairs
- no public repo surfaced in the extracted source

Operational substitute for Artemis:
- Binance OHLCV for clean listed-asset returns
- CoinGecko for broader universe and metadata

### Caveat
Monthly threshold tuning can drift toward overfitting if the walk-forward protocol is weak. Keep the adaptation bounded.

---

## 5.3 Meta-Learning Reinforcement Learning for Crypto-Return Prediction

### Goal
Create a self-improving crypto forecasting/trading agent that learns from multimodal inputs without requiring human-labeled reward supervision.

### Methodology
The framework uses one LLM in three roles:
- actor
- judge
- meta-judge

Inputs include:
- market data
- on-chain data
- news
- sentiment

Reward channels include:
- return
- Sharpe-like risk objective
- drawdown control
- liquidity/slippage awareness
- sentiment alignment

The judge evaluates actions; the meta-judge updates the evaluation policy to reduce reward drift.

### Main results
The paper reports outperformance versus:
- classic time-series baselines like Informer and PatchTST
- indicator baselines like MACD
- multiple LLM baselines

The paper also emphasizes stronger relative performance in difficult regimes, especially bearish conditions.

### What the paper is really telling us
The valuable idea is not “use an LLM and it wins.”

The valuable idea is that crypto prediction may benefit from:
- multimodal data fusion
- multi-objective evaluation
- self-critique loops
- explicit reward shaping around implementation risk, not just raw return

### How to use it for Artemis
Not as the first-line submission model.

Better uses:
1. post-trade reviewer for simpler factor strategies
2. scenario critic for regime-aware factor weighting
3. meta-layer that evaluates whether a signal is still behaving as expected
4. optional sentiment overlay for high-conviction names

A practical Artemis use would be:
- baseline factor portfolio generates candidate buys/sells
- meta-agent reviews whether sentiment/liquidity/regime conditions argue for scaling those trades up or down

### How to retest it properly
1. use fully timestamped data with zero tolerance for leakage
2. compare against non-LLM multimodal baselines first
3. hold transaction-cost assumptions fixed across models
4. test whether the RL layer adds value after costs, not just before costs
5. inspect whether performance comes from real skill or simply more market beta

### Data / code we can reuse
Explicitly surfaced:
- CoinMarketCap
- Dune Analytics
- GNews
- SimHash-based deduplication idea
- no public repo identified in the extracted source

Operational substitute for Artemis:
- CoinGecko / Binance / Artemis / DeFiLlama for structured data
- optional news later if needed

### Caveat
This is a high-complexity architecture with many silent failure modes. It should be downstream of simpler proven baselines, not upstream of them.

---

## 5.4 A Time-Varying Network for Cryptocurrencies

### Goal
Model evolving relationships among cryptocurrencies and use that structure for diversification and cross-sectional trading.

### Methodology
Key pieces:
- 182 cryptocurrencies over 2016 to 2018
- rolling regressions on lagged standardized returns
- adaptive Lasso to build directed return network
- technology covariates such as hashing algorithm and proof type
- dynamic covariate-assisted spectral clustering for community detection
- portfolio tests using community-based momentum and diversification logic

### Main results
The paper reports that:
- community structure reveals meaningful segmentation and risk propagation
- diversification improves when assets are chosen from different communities
- an inter-crypto momentum strategy based on communities earned about 1.08% average daily return in the sample
- the effect was not explained away by several behavioral controls

### What the paper is really telling us
Crypto cross-sections have structure. A portfolio that ignores that structure will often double-count the same thematic bet.

### How to use it for Artemis
This is one of the most useful papers for portfolio construction.

Use cases:
1. community-aware diversification constraints
2. sector/chain/community caps
3. cluster-relative momentum instead of marketwide momentum only
4. cluster risk monitoring during rebalances

A clean Artemis implementation could be:
- rank assets by factor score
- before final portfolio selection, apply a community diversification rule so one chain/protocol family cannot dominate

### How to retest it properly
1. rebuild the network on a modern sample
2. compare return-only clustering vs return-plus-fundamental clustering
3. test whether cluster diversification improves Sharpe or just lowers gross return
4. include turnover and liquidity cost penalties
5. examine stability of cluster assignments through time

### Data / code we can reuse
Explicitly surfaced:
- CryptoCompare API in the paper
- no public code surfaced in the extracted source

Operational substitute for Artemis:
- use CoinGecko/Binance returns
- add Artemis/DeFiLlama covariates for chain, protocol, sector, and business activity

### Caveat
Older sample period. The structural idea is useful; the exact communities from 2016-2018 are not.

---

## 5.5 To Trade Or Not To Trade: Cascading Waterfall Round Robin Rebalancing Mechanism

### Goal
Design a rebalancing mechanism that determines whether to trade, how much to trade, and how many trades to split into, while respecting crypto-specific frictions.

### Methodology
Main design choices:
- use weight bands: minimum, ideal, maximum
- determine asset capacity from risk/return and flow context
- allocate capital through cascading waterfall / round-robin logic
- enforce minimum and maximum trade sizes
- trade only when bands are breached
- emphasize gas and slippage trade-offs

### Main results
The paper is more of a mechanism design framework than a strong broad-sample empirical asset-pricing result. It shows how thresholded rebalancing can improve execution logic under blockchain frictions.

### What the paper is really telling us
A smart signal can still lose if the rebalance engine is dumb.

### How to use it for Artemis
This is very relevant for the final portfolio layer.

Recommended use:
- define target weights from factor scores
- introduce no-trade bands around current weights
- only rebalance positions when drift exceeds a threshold
- add minimum trade size and liquidity constraints
- possibly stagger trades if the portfolio rotates too hard

That is especially important if mid-cap tokens enter the universe.

### How to retest it properly
1. compare fixed periodic rebalance vs tolerance bands
2. compare full rebalance vs partial rebalance
3. compare net performance after turnover costs
4. test if lower turnover preserves most of the gross alpha
5. stress test on volatility spikes and illiquid names

### Data / code we can reuse
Explicitly surfaced:
- numerical examples only
- no public data repo or code repo identified

Operational substitute for Artemis:
- use Binance quote volume, trade count, and CoinGecko volume to proxy trade frictions

### Caveat
This paper is best treated as an execution overlay, not a source of predictive factors.

---

## 5.6 Beyond Trading Data: The Hidden Influence of Public Awareness and Interest on Cryptocurrency Volatility

### Goal
Improve Bitcoin volatility forecasting by adding non-price information such as public awareness, search interest, and blockchain activity.

### Methodology
The paper proposes `CoMForE`, a multimodal AdaBoost-LSTM ensemble using:
- historical trading data
- tweet sentiment
- search-interest signals
- blockchain activity such as hash rate and difficulty

It evaluates point prediction and distribution-related volatility behavior.

### Main results
Reported outcome:
- about 19.29% improvement over prior forecasting methods
- multimodal inputs outperform trading-only inputs
- external attention variables materially improve volatility modeling

### What the paper is really telling us
Public attention is not just noise. It can matter for volatility and therefore for risk management.

### How to use it for Artemis
This is better suited to risk control than primary alpha.

Possible uses:
1. volatility-aware position scaling
2. regime filter for when factor aggressiveness should be reduced
3. crowding / hype indicator for meme-heavy subuniverses
4. stress overlay during abnormal attention spikes

### How to retest it properly
1. compare price-only and multimodal volatility models
2. evaluate calibration, not only point accuracy
3. test whether the volatility forecast improves realized portfolio drawdown control
4. extend beyond BTC to large liquid altcoins
5. test if search/sentiment signals are most useful only in retail-dominated regimes

### Data / code we can reuse
Explicitly surfaced:
- historical trading data
- tweet sentiment
- search volumes
- blockchain data such as hash rate and difficulty
- extracted source says open-source implementation exists, but exact repo URL was not exposed

Operational substitute for Artemis:
- if external attention data is unavailable, stablecoin liquidity, gamed activity, and market breadth can play a similar regime-filter role

### Caveat
Volatility forecasting can improve risk management without improving alpha ranking. Keep those two jobs separate.

---

## 5.7 Dynamic Latent-Factor Model with High-Dimensional Asset Characteristics

### Goal
Estimate dynamic latent factors when the feature set is high-dimensional relative to sample size, while preserving valid inference.

### Methodology
The paper proposes the Double Selection Lasso Factor Model (`DSLFM`):
- model time-varying loadings as functions of many characteristics
- run double-selection Lasso to remove weak features
- apply PCA to the selected characteristic-time structure
- use soft-thresholding to zero out weak characteristic rows
- provide asset-pricing inference and test nontradable factor premia

### Main results
The paper reports:
- competitive out-of-sample pricing and risk-adjusted performance in crypto
- exchange inflows/outflows matter in the empirical application
- inflation-mimicking portfolio premium is positive and significant
- selected characteristics can remain informative even in short, noisy crypto panels

### What the paper is really telling us
This is probably the most important paper in the bundle for factor-discipline.

It gives a principled way to handle the exact situation Artemis creates:
- many candidate crypto characteristics
- short history
- unstable relationships
- high overfit risk

### How to use it for Artemis
Use it as a feature-screening and factor-validation engine.

Practical role:
1. build a broad characteristic library
2. use sparse selection to identify robust predictors
3. compare selected factors across subperiods
4. then feed the retained factors into a simpler portfolio score

This is a good bridge between academic asset pricing and practical feature engineering.

### How to retest it properly
1. rebuild the panel on later data
2. compare DSLFM against PCA-only and simpler factor regressions
3. test whether selected features remain stable across subperiods
4. compare weekly vs monthly horizons
5. track whether selection keeps choosing usage quality and monetization rather than noisy TVL proxies

### Data / code we can reuse
Explicitly surfaced:
- code repo: `https://github.com/adambaybutt/crypto_asset_pricing`
- author research page: `http://www.adambaybutt.org/research.html`

This is one of the few sources with directly reusable code infrastructure.

### Caveat
This is excellent for research screening, but the final competition story should still remain interpretable. Sparse econometrics is easier to defend than a giant black box.

---

## 5.8 Crypto Pricing with Hidden Factors

### Goal
Estimate crypto risk premia while controlling for omitted latent factors, and test whether crypto returns are driven only by crypto-native exposures or also by broader equity-related risks and state variables.

### Methodology
The paper uses the Giglio-Xiu three-pass latent-factor framework with:
- weekly top-100-like crypto universe
- market, size, momentum, and TVL-related crypto factors
- traditional stock/equity factors
- state variables such as Fear & Greed, Altcoin Season, hacked value
- comparison against standard Fama-MacBeth estimates

### Main results
Reported findings:
- crypto market risk is positively priced
- crypto size effect is strongly negative in this sample
- some equity-industry and profitability-related risks matter
- Fear & Greed has explanatory power
- Altseason weakens under latent-factor control
- hacked-value shocks are not priced in the sample
- TVL evidence is weak once hidden factors are controlled for

### What the paper is really telling us
This paper is a warning label against naive factor storytelling.

A variable that looks intuitive may just be a shadow of hidden common risk.

### How to use it for Artemis
Three main uses:
1. validate factors after controlling for common risks
2. use sentiment/state variables as regime conditioners, not necessarily standalone alpha
3. be careful about size and small-cap exposure masquerading as “fundamental alpha”

### How to retest it properly
1. reproduce on post-2024 data
2. test different universe definitions and weighting rules
3. compare factor premia with and without latent controls
4. use the result to decide whether our factor stack adds something beyond market/size/momentum

### Data / code we can reuse
Explicitly surfaced:
- CoinMarketCap API
- DeFiLlama
- thecvx.com
- CoinMarketCap Altcoin Season data
- CoinMarketCap Fear & Greed data
- Kenneth French data library
- no public code repo identified

Operational substitute for Artemis:
- CoinGecko + DeFiLlama + Artemis cover most of the same research intent

### Caveat
The paper is a preliminary draft. Treat it as a strong idea source, not final law.

---

## 5.9 The Surprising Irrelevance of Total-Value-Locked on Cryptocurrency Returns

### Goal
Test whether high TVL or high TVL growth actually predicts returns after standard crypto factor controls.

### Methodology
The paper forms portfolios sorted by:
- TVL / market cap
- change in TVL / market cap
- total TVL
- cleaner “simple TVL” variants

It then tests whether the return patterns survive crypto market and multi-factor controls.

### Main results
The message is blunt:
- alpha is insignificant across TVL-formed portfolios
- a simple crypto market factor often explains the returns sufficiently
- three-factor models improve fit a bit, but not enough to rescue TVL as a standalone factor
- the result is robust across raw and cleaned TVL definitions

### What the paper is really telling us
TVL is one of the most over-interpreted metrics in crypto.

### How to use it for Artemis
This paper should directly shape factor design.

Recommended response:
- do not use raw TVL rank as a core signal
- use TVL as denominator, context, or screen
- prefer capital-efficiency and monetization-efficiency measures such as:
  - fees / TVL
  - revenue / TVL
  - fees / market cap
  - revenue / market cap

### How to retest it properly
1. rerun on later DeFi cycles
2. compare raw TVL, simple TVL, and utilization-based alternatives
3. test whether the useful information is in change, interaction, or quality-adjusted forms rather than levels
4. measure whether TVL merely loads on market beta or DeFi sector beta

### Data / code we can reuse
Explicitly surfaced:
- CoinMarketCap API
- DeFiLlama
- no public code repo identified

Operational substitute for Artemis:
- DeFiLlama gives enough to reconstruct TVL-based tests
- CoinGecko/Artemis can supply the market and activity side

### Caveat
This paper does not say “ignore TVL completely.” It says “TVL by itself is not the clean alpha story people think it is.”

---

## 5.10 Ranked Asset Allocation Model (RAAM)

Source type:
- Practitioner paper / clipping: CMT Association website, `rank.md`
- Author not identified in the saved clipping; practitioner-academic style
- No specific publication date; backtested July 2004 to November 2017
- **New addition to this consolidation**

### Goal
Demonstrate that a passive-ETF portfolio (the 7Twelve Portfolio) can be transformed into an outperforming active strategy by applying a multi-factor ranking model to determine monthly asset selection and weighting.

### Methodology
The paper builds the Ranked Asset Allocation Model (RAAM) on top of the 7Twelve Portfolio (12 ETFs across 7 asset classes: US Equities, non-US Equities, Real Estate, Resources/Commodities, US Bonds, non-US Bonds, Cash).

The four scoring components are:

1. **(M) Absolute Momentum**: 4-month Rate of Change (ROC) on daily returns. Higher momentum = higher rank.
2. **(V) Volatility Model**: modified GARCH(1,1) using RiskMetrics (lambda=0.94) on daily OHLC. Lower volatility = higher rank.
3. **(C) Average Relative Correlation**: 4-month average pairwise correlation on daily returns across all ETFs. Lower average correlation = higher rank (better diversifier).
4. **(T) ATR Trend/Breakout System**: proprietary breakout model using a 42-period Average True Range. Upper Band breach = Long signal (+2); Lower Band breach = Neutral/Short (-2). Used as a multiplier/veto on the composite rank, not a standalone ranking component.

The composite Total Rank formula:

```
Total Rank = wM * Rank(M) + wV * Rank(V) + wC * Rank(C) + T * x
```

- each component ranked 1 to 11 (higher = better) across all non-cash ETFs
- weights wM, wV, wC are tunable parameters
- `x` is a small offset applied to Absolute Momentum rank to break ties

Portfolio construction rules:
- select the **5 ETFs with the best Total Rank** as candidates
- for each candidate: **include if Absolute Momentum is positive**, otherwise replace weight with Cash (SHY)
- in extreme case where all 5 candidates have negative momentum: 100% Cash
- allocation is **monthly** based on prior month's end-of-month ranks
- backtest used daily and monthly returns, no transaction costs included

Compared against:
- Salient Risk Parity Index (10% Volatility Targeting)
- Core 7Twelve Portfolio (equal-weight, passive)
- SPDR S&P 500 ETF

### Main results
Backtested July 2004 to November 2017:
- RAAM outperformed all three benchmarks on both absolute and risk-adjusted return
- the model allocated dynamically across asset classes depending on momentum, volatility, and diversification conditions
- Cash weighting increased meaningfully during bear markets, functioning as an automatic drawdown brake

### What the paper is really telling us
This is one of the cleaner practitioners' cases for why composite ranking beats single-factor selection.

Three principles stand out:

1. **Punish risk, not just reward return.** Including the Volatility Model as a ranking component means that a high-momentum but high-volatility asset is ranked lower than a moderate-momentum, low-volatility asset. This is not mean-variance optimization -- it is a simpler, more transparent approximation.

2. **Reward diversification at selection time.** The Average Relative Correlation component directly penalizes assets that move with everything else. This builds diversification into the scoring function rather than treating it as a portfolio-construction afterthought.

3. **Use trend as a gate, not just a score.** The ATR Trend/Breakout System functions as a binary veto or multiplier rather than a smoothly blended rank component. Positive trend = proceed; negative trend = reduce or zero out. That two-layer logic (rank first, then gate by trend) is more robust than averaging trend into a single continuous score.

### How to use it for Artemis

This paper is one of the most directly actionable in the entire bundle for Track #1.

The ranking model maps almost directly onto crypto factor construction:

| RAAM Component | Artemis Crypto Analogue |
|---|---|
| Absolute Momentum (M) | 30D / 90D price momentum on Binance OHLCV |
| Volatility Model (V) | GARCH or EWMA realized vol from daily close; lower = better |
| Avg Relative Correlation (C) | 60D rolling pairwise correlation across universe; lower = better diversifier |
| ATR Trend/Breakout (T) | ATR breakout on daily crypto prices, or AdaptiveTrend-style threshold |
| Cash substitution rule | Replace negative-momentum selections with stablecoin or reduce weight |
| Top-N selection | Select top decile or top 10-15 tokens by composite rank |

Recommended Artemis adaptation:

1. compute ranks M, V, C for all universe members at each rebalance period
2. add a fourth rank component from on-chain quality (adjusted usage growth, monetization efficiency) -- not present in the original RAAM
3. form Total Rank = wM * Rank(M) + wV * Rank(V) + wC * Rank(C) + wQ * Rank(Quality)
4. select top-N ranked names
5. apply the ATR Trend/Breakout signal or a regime veto (stablecoin liquidity regime, market breadth) to reduce/zero positions when macro trend is bearish
6. substitute any selected asset with negative Absolute Momentum with stablecoin or cash
7. rebalance monthly with tolerance bands

The weight parameters (wM, wV, wC, wQ) should be estimated with a short walk-forward, not tuned in-sample. Keep the number of tuning parameters small.

### How to retest it properly
1. reproduce the RAAM logic on crypto with Binance OHLCV
2. compare against momentum-only rank
3. test whether adding V (volatility penalty) and C (correlation penalty) improves Sharpe or just lowers gross return
4. test whether the ATR gate reduces drawdown at acceptable cost in gross return
5. add the Artemis quality component and measure its marginal contribution
6. include transaction costs and turnover in all comparisons

### Data / code we can reuse
Explicitly surfaced:
- Yahoo Finance (original equity-ETF backtest)
- daily OHLC data for all components
- RStudio for preprocessing; Metastock for indicators; Excel for ranking model

Operational substitute for Artemis:
- Binance OHLCV for M, V, T components
- DeFiLlama + Artemis for the Quality component
- rolling correlation computed in Python from daily returns matrix

### Caveat
The original RAAM backtest covers equity and bond ETFs in a 2004-2017 window that is entirely pre-DeFi and has substantially lower volatility than crypto. The mechanism is sound but weight calibration (wM, wV, wC) from the equity backtest should not be borrowed directly. Walk-forward calibration on crypto-specific data is required. Transaction costs are excluded from all RAAM results; in crypto these must be explicitly modeled.

---

## 6. What the awesome-quant-ai repo contributes

Repo path:
`/home/omegashenr01n/Desktop/resources-20260508-163423/awesome-quant-ai`

This repo is not a single strategy implementation. It is a map of methods, tools, and thinking styles.

### 6.1 Main value to Artemis

The repo contributes four useful things:

1. a disciplined systematic-research mindset
2. regime-aware strategy design ideas
3. references for AI/multimodal/agentic extensions
4. pointers to implementation and prototyping tools

### 6.2 HMM and Markov-switching notes

The HMM and Markov-switching files push a common idea:
- identify hidden regimes
- adapt allocation/risk by regime
- do not assume one signal weight works everywhere

For Artemis this suggests:
- keep a regime layer separate from the alpha layer
- condition risk and exposure on volatility / liquidity / breadth regime
- consider 3- or 4-state market classification only if it improves decisions materially

### 6.3 AI-agent trading note

The AI-agent trading note describes multi-agent LLM frameworks such as TradingAgents and FinAgent.

Useful takeaways:
- specialized agents can structure different information channels
- reflection and memory loops are useful for critique
- tool-augmented research agents can improve workflow

Best Artemis use:
- research assistant or reviewer, not first-pass alpha engine

### 6.4 Systematic Trading book notes

The most useful repo-adjacent material may be the boring part: the systematic trading notes.

The repeated lessons are:
- keep rules objective
- avoid overfitting
- do not confuse complexity with edge
- design the portfolio and risk framework as carefully as the signal itself
- use rolling or expanding windows, not time machines
- pool evidence across instruments where sensible

That fits Artemis exactly.

### 6.5 Practical tools surfaced by the repo

The README mentions tool categories and examples around:
- factor research
- supervised learning
- unsupervised learning
- reinforcement learning
- risk management
- multi-strategy construction

The repo also contains a notebook `tools/pybroker.ipynb`, which may be useful as a quick prototyping reference, though it is not itself a complete competition framework.

### 6.6 Bottom line on the repo

The repo is not the source of the core factor thesis.

It is the source of method scaffolding:
- how to think systematically
- how to add regime awareness
- how to keep a roadmap from simple to complex

---

## 7. Best research directions for Artemis Track #1

Based on the full bundle, the strongest submission path is not a single monolithic model.

It is a layered factor portfolio.

### 7.1 Recommended factor families

#### A. Price momentum
Source layer:
- Binance
- CoinGecko

Candidate constructs:
- 7D, 30D, 90D momentum
- skip-short-horizon momentum to avoid short-term reversal noise
- rolling Sharpe / return-to-vol ratio

Why it belongs:
- supported indirectly by AdaptiveTrend and broader crypto literature
- simple, strong benchmark that every fancy model must beat

#### B. Usage-quality momentum
Source layer:
- Artemis

Candidate constructs:
- growth in adjusted txns
- growth in adjusted volume
- growth in cumulative buyers / sellers
- real/total ratio
- penalty for percent gamed txns and percent gamed volume

Why it belongs:
- aligns with the Bitcoin on-chain feature-selection paper
- aligns with Artemis’ strongest proprietary differentiation: quality-adjusted on-chain usage

#### C. Monetization quality
Source layer:
- Artemis
- DeFiLlama

Candidate constructs:
- fees / market cap
- revenue / market cap
- 30D and 90D growth in fees or revenue
- active revenue vs passive revenue where available

Why it belongs:
- stronger economic intuition than raw attention metrics
- likely more meaningful than TVL level alone

#### D. Capital efficiency
Source layer:
- DeFiLlama
- optionally Artemis monetization metrics

Candidate constructs:
- fees / TVL
- revenue / TVL
- change in fees / TVL
- chain diversification of TVL

Why it belongs:
- uses TVL as context rather than alpha by itself
- consistent with the anti-TVL paper’s warning

#### E. Regime / liquidity filter
Source layer:
- DeFiLlama stablecoins
- Artemis stablecoin data
- market-wide volatility / breadth

Candidate constructs:
- stablecoin market cap growth
- stablecoin inflow momentum
- realized market volatility
- market breadth or cross-sectional hit rate

Why it belongs:
- allows exposure scaling rather than pretending every week is the same week

#### F. Community / concentration control
Source layer:
- Artemis breakdowns
- DeFiLlama sector/chain grouping
- return-based clustering

Candidate constructs:
- HHI of chain concentration
- category concentration
- portfolio max weight per cluster
- diversification bonus for cross-community selection

Why it belongs:
- directly motivated by the time-varying network paper

### 7.2 Factor families to de-prioritize

1. raw TVL level by itself
2. raw transaction counts without quality adjustment
3. high-complexity RL/LLM architectures before baselines are proven
4. sentiment-heavy pipelines if data coverage and timestamp quality are weak

---

## 8. Proposed Artemis strategy architecture

## 8.1 Universe

Primary universe recommendation:
- top 50 to 100 non-stable crypto assets by market cap
- exclude stablecoins
- exclude wrapped duplicates where possible
- exclude clear bridged duplicates and non-primary listings
- require minimum liquidity threshold
- keep a listed-on-Binance subset for stronger execution realism if needed

If the competition rewards broader coverage, use CoinGecko for universe definition and Binance for the traded subset.

## 8.2 Data stack

Use the existing data-source mapping already prepared in the vault.

### Market layer
- CoinGecko: market cap, price, volume, supply, tags, categories
- Binance: OHLCV, quote volume, trade count, realized-vol inputs

### Usage-quality layer
- Artemis: txns, real_txns, volume, real_volume, buyers, sellers, percent_gamed metrics, DAU, active addresses

### Business / capital layer
- DeFiLlama: TVL, chain TVL, fees, revenue, stablecoin data, treasury where relevant

## 8.3 Example composite factor score

A practical first score could be:

`Composite Score = 0.35 * price momentum + 0.25 * adjusted usage growth + 0.20 * monetization quality + 0.10 * capital efficiency + 0.10 * breadth quality - quality penalty`

Where:
- `price momentum` = blended z-score of 30D and 90D returns, optionally skipping most recent few days
- `adjusted usage growth` = z-score of growth in adjusted txns, adjusted volume, buyers/sellers
- `monetization quality` = z-score of fees/mcap and revenue/mcap
- `capital efficiency` = z-score of fees/TVL and revenue/TVL
- `breadth quality` = reward broad chain/facilitator/category usage instead of concentration
- `quality penalty` = function of percent gamed txns and volume

This is only a starting point. The DSLFM / sparse-selection paper should be used to decide whether these weights and features survive screening.

## 8.4 Portfolio construction

Primary submission candidate:
- long-only
- select top decile or top 10-15 names
- equal-weight or inverse-vol capped weight
- single-name cap and cluster cap
- weekly or biweekly rebalance

Research variant:
- market-neutral or 70/30 long-short version for internal testing
- useful as a diagnostic, but not necessarily the cleanest competition submission

## 8.5 Rebalancing logic

Recommended rule set:
- periodic rebalance on schedule
- tolerance bands around target weights
- no-trade zone for small drifts
- minimum liquidity and trade-size thresholds
- optional partial rebalance when turnover spike would be too costly

This is where the cascading-waterfall paper is useful.

## 8.6 Risk controls

Minimum controls:
- cap per asset
- cap per chain / cluster / sector
- rolling volatility target
- liquidity floor
- regime-aware gross exposure scale-down when stablecoin/liquidity regime weakens or volatility spikes

---

## 9. Recommended validation ladder

The research bundle strongly suggests a staged process.

### Stage 1: establish naive baselines

1. equal-weight universe
2. pure momentum rank
3. pure size or liquidity screens
4. trend-following baseline from AdaptiveTrend logic

### Stage 2: add factor families one at a time

1. momentum + usage quality
2. momentum + monetization quality
3. momentum + usage quality + monetization
4. add capital efficiency
5. add regime filter

### Stage 3: portfolio-construction upgrades

1. equal weight vs inverse vol
2. full rebalance vs banded rebalance
3. unconstrained vs cluster-capped

### Stage 4: econometric validation

1. sparse characteristic screening
2. latent-factor attribution
3. check if excess returns survive market/size/momentum controls

### Stage 5: optional advanced overlays

1. sentiment / public-awareness regime layer
2. meta-agent or RL review layer
3. network-based dynamic clustering

That order matters. Otherwise the research process turns into decorative complexity.

---

## 10. Retest plan by research theme

## 10.1 On-chain predictive features

Retest question:
Does adjusted on-chain activity add alpha beyond price momentum?

Test:
- compare momentum-only vs momentum + adjusted usage growth vs momentum + raw usage growth
- weekly rebalance
- common cost assumptions

Desired answer:
Adjusted metrics should beat raw metrics if the Artemis quality filters are real.

## 10.2 Monetization and capital efficiency

Retest question:
Do fees/revenue-based factors outperform raw TVL factors?

Test:
- TVL rank
- TVL growth
- fees/TVL
- revenue/TVL
- fees/mcap
- revenue/mcap

Desired answer:
Efficiency ratios should dominate level metrics.

## 10.3 Regime conditioning

Retest question:
Does a stablecoin-liquidity or volatility regime filter improve drawdown-adjusted returns?

Test:
- portfolio always on
- portfolio scaled down in adverse regimes
- compare Sharpe, max drawdown, turnover, and crash behavior

## 10.4 Cluster-aware diversification

Retest question:
Does community-aware selection improve portfolio efficiency?

Test:
- unconstrained top-K
- sector-neutral / chain-capped top-K
- return-network-cluster-capped top-K

## 10.5 Rebalancing logic

Retest question:
Does banded rebalancing preserve alpha while reducing turnover?

Test:
- weekly full rebalance
- weekly tolerance-band rebalance
- biweekly full rebalance
- monthly full rebalance

---

## 11. Best external data/code bases surfaced by the bundle

### High-value data sources

1. Artemis
   - adjusted transactions
   - adjusted volume
   - real vs gamed splits
   - buyers/sellers
   - stablecoin activity
   - flows

2. CoinGecko
   - broad universe
   - market cap, price, supply, categories, tags

3. Binance
   - cleaner OHLCV and exchange liquidity proxies

4. DeFiLlama
   - TVL
   - fees
   - revenue
   - stablecoin macro
   - treasury and capital structure context

5. optional external state series
   - Fear & Greed
   - Altcoin Season
   - equity factor context if needed

### High-value code/resources

1. `https://github.com/adambaybutt/crypto_asset_pricing`
   - best direct code lead from the downloaded papers
   - useful for factor-pricing and characteristic-model work

2. local repo `awesome-quant-ai/`
   - useful for method references and prototyping direction

3. Binance public bulk data
   - `https://data.binance.vision/`

4. DeFiLlama API docs
   - `https://api-docs.defillama.com/`

### What we do not currently have cleanly surfaced

- an explicit released repo for the Bitcoin on-chain feature-selection paper
- an explicit released repo for AdaptiveTrend
- an explicit released repo for Meta-RL-Crypto
- an exact surfaced repo URL for the CoMForE volatility paper despite mention of open-source code

That means our implementation should assume we are reconstructing ideas, not cloning a finished benchmark.

---

## 12. Recommended final thesis for the Artemis submission

If we want a submission that is both strong and defensible, the best thesis from this bundle is probably:

1. crypto price momentum matters
2. but it should be filtered by real economic usage, not raw activity
3. monetization efficiency matters more than TVL level
4. quality penalties are necessary because crypto metrics are easy to game
5. regime-aware exposure and smarter rebalancing improve net performance
6. diversification should respect crypto community structure, not just ticker count

That leads to a submission story like this:

“We build a quality-adjusted crypto factor rebalancing strategy that combines momentum, real on-chain usage growth, and monetization efficiency. We penalize synthetic activity using Artemis’ gamed-activity diagnostics, avoid naive TVL worship by using capital-efficiency ratios instead of raw TVL, and use disciplined rebalancing plus diversification constraints to preserve net returns under realistic trading frictions.”

That is a much better story than:
- “we used a giant model”
- or “we sorted by TVL”
- or “we predicted next-day returns with an LLM”

---

## 13. Priority order: what to build first

### Tier 1: must-build

1. clean investable universe
2. baseline momentum portfolio
3. Artemis adjusted-usage factors
4. DeFiLlama monetization and capital-efficiency factors
5. weekly backtest with costs and turnover

### Tier 2: high-value upgrades

1. gamed-activity penalty
2. stablecoin liquidity regime filter
3. cluster / chain / sector concentration constraints
4. banded rebalancing

### Tier 3: research extensions

1. sparse latent-factor screening using the Baybutt framework
2. network/community-based portfolio construction
3. multimodal sentiment/attention overlay
4. meta-agent critique or RL layer

---

## 14. What to avoid

1. using raw TVL as a headline factor
2. using raw tx count growth without adjusted-quality controls
3. building a black-box architecture before simple baselines are beaten
4. optimizing too many hyperparameters on a short crypto history
5. reporting gross returns without turnover and cost analysis
6. letting one narrative cluster dominate the portfolio
7. confusing predictive accuracy on one asset with cross-sectional portfolio usefulness

---

## 15. Bottom line

From the full research bundle, the strongest Artemis Track #1 direction is not a single fancy model.

It is a layered, quality-aware, economically interpretable factor portfolio:
- momentum for market persistence
- adjusted usage growth for real adoption
- monetization efficiency for economic productivity
- capital-efficiency ratios instead of raw TVL worship
- regime and quality filters for robustness
- disciplined rebalancing and diversification for implementability

If this research is turned into an actual build plan, the first serious backtest should compare:

1. momentum only
2. momentum + adjusted usage
3. momentum + adjusted usage + monetization efficiency
4. the same composite with gamed-activity penalty and banded rebalancing

That comparison will tell us quickly whether the downloaded research produced a real edge or just a pile of respectable PDFs.
