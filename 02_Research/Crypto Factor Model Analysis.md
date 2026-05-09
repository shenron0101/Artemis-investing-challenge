---
title: "Artemis"
source: "https://about.artemis.ai/resources/crypto-factor-model-analysis"
author:
published:
created: 2026-05-09
description:
tags:
  - "clippings"
---
## Executive Summary

Crypto exhibits persistent style premia, just like equities.

By constructing four systematic factors (Market Risk, Size, Value, Momentum) across eligible tokens, we find:

- **Market Risk (beta)** explains most returns and earns a **42% annualized premium**.
- **Size (small > large)** is the strongest factor, delivering **53% annualized performance** with low correlation to market beta.
- **Value (cheap > expensive)** is positive but weaker (**9.3% annualized**).
- **Momentum** generates high returns (**75% annualized**) but has low explanatory power — better as a trading strategy than a risk factor.

Together, these factors explain **~55% of individual token returns** and **~75% of diversified portfolio returns.**

## Goal:

The purpose of this study is to determine whether persistent style premia, such as those long observed in equities, also manifest in crypto markets. We test if systematic exposures such as market beta, size, valuation multiples, and trend persistence can explain cross-sectional variation in token returns.

To learn more about our methodology, request detailed testing results, or explore commercial opportunities, please reach out to the Artemis team.

## Process:

Constructed 4 time-series factors: Market Risk, Size, Value, and Momentum. Portfolios are rebalanced weekly using simple USD returns for factor construction and performance, with start date varying depending on threshold for minimum token inclusion. Correlation and regression utilize log returns.

Data is sourced from Artemis Analytics with the exception of equity index data which is sourced from Yahoo Finance.

Returns are gross of transaction costs; realized performance would depend on execution costs and liquidity at the time of trade.

Broad Eligibility Criteria:

All factor portfolio’s were constructed from eligible assets at each time period per the criteria below:

- ≥ $100M market cap at rebalancing periods
- ≥ $35M weekly volume at rebalancing periods
- minimum asset age of 30 days before eligible for inclusion

These thresholds balance breadth and data quality, excluding illiquid and microcap tokens whose volatility would distort factor returns.

## Market Risk Factor:

Captures broad crypto market exposure.

![](https://cdn.prod.website-files.com/6760e87b474d412dfa9a7a98/692ff3e2368bc7a247a55c65_https%253A%252F%252Fsubstack-post-media.s3.amazonaws.com%252Fpublic%252Fimages%252F2bb3be24-4d8c-429d-8e3f-99b8aad15683_1002x611.png)

Factor Model: market Number of Assets: 10 Weighting Method: market\_cap Annualized Return: 0.42 (42%) Cumulative Returns: 17.27 (1,727%) Years: 8.28

The Market Risk factor-mimicking portfolio is a long only portfolio constructed of the top 10 assets by market cap, and is market cap weighted. This factor behaves similarly to a crypto “market index,” and confirms the presence of a broad market risk premium that compensates investors for holding aggregate crypto exposure. Including the top 10 tokens is more reflective of broader crypto returns and is more inclusive, given Bitcoin and Ethereum dominance now stand at ~59% and ~13% respectively.

## Size Factor:

Tests whether small caps outperform large caps.

![](https://cdn.prod.website-files.com/6760e87b474d412dfa9a7a98/692ff40bc0e98e09dfedfe3b_https%253A%252F%252Fsubstack-post-media.s3.amazonaws.com%252Fpublic%252Fimages%252Fda4c95a6-18c6-42e1-ba4b-a1cb36cbf20d_1016x611.png)

Factor Model: smb Breakpoint: 0.5 Min Assets: 40 Weighting Method: equal Annualized Return: 0.536 (53.6%) Cumulative Returns: 7.23 (723%) Years: 4.90

The Size (SMB) factor-mimicking portfolio is an equal weighted long-short portfolio that longs the smallest 50% of eligible assets per period and shorts the largest 50% of eligible assets per period. The minimum number of assets must be ≥ 40 (20 per leg). Equal weighting ensures that small-cap tokens contribute meaningfully despite lower market caps. The SMB spread exhibits higher volatility but persistent positive drift, implying investors demand additional compensation for small-cap liquidity and risk.

## Value Factor:

Tests whether cheap tokens outperform expensive tokens (value measured by mc\_fees\_ratio)

![](https://cdn.prod.website-files.com/6760e87b474d412dfa9a7a98/692ff42334a57abbbce0115e_https%253A%252F%252Fsubstack-post-media.s3.amazonaws.com%252Fpublic%252Fimages%252F88f333eb-7a50-44da-9bd7-2aa13aff42c0_992x609.png)

Factor Model: value Breakpoint: 0.5 Min Assets: 30 Weighting Method: equal Annualized Return: 0.093 (9.3%) Cumulative Returns: 0.41 (41%) Years: 3.91

The Value factor-mimicking portfolio is an equal weighted long-short portfolio that longs the 50% of assets with the highest value (lowest mc\_fees\_ratio) and shorts the 50% of assets with the lowest value (highest mc\_fees\_ratio). Due to less fee metric coverage, the minimum number of assets required per period is 30 (15 per leg). Value is proxied by the inverse of the market-cap-to-fees ratio, analogous to a P/S multiple.

## Momentum Factor:

Tests whether winners keep winning and losers keep losing.

![](https://cdn.prod.website-files.com/6760e87b474d412dfa9a7a98/692ff430ff42e2f7c2f36277_https%253A%252F%252Fsubstack-post-media.s3.amazonaws.com%252Fpublic%252Fimages%252F1cb6e39e-56d6-4a4e-bedd-c510370892c3_1016x611.png)

Factor Model: momentum Breakpoint: 0.25 Min Assets: 30 Weighting Method: equal Annualized Return: 0.75 (75%) Cumulative Returns: 12.35 (1,235%) Years: 4.62

Momentum is calculated using a 3-week, volatility-adjusted framework designed to capture consistent price trends rather than short-term spikes. Our momentum score rewards smoother price appreciation and discounts volatile paths. At each rebalancing date, assets are ranked by their T-1 momentum score, and the factor portfolio is constructed by going long the top 25% and short the bottom 25% of assets. This allows us to capture persistent, low-volatility momentum while avoiding lookahead bias.

## Key Findings:

Traditional style factors apply to crypto and explain an average of 55% of individual asset returns and 74.8% of diversified portfolio returns.

**Market Factor:**

- Primary form of systematic risk; **Majority of returns are explained by market beta**
- 42% annualized return over 8.3 years demonstrates the substantial risk premium for bearing crypto market exposure

**Size Factor (SMB):**

- **Strongest standalone factor**: 53% annualized return over 4.9 years; the small-cap premium is real and economically meaningful
- **50% of assets show significant size loadings** (vs. 5% by chance), confirming size captures genuine cross-sectional risk
- **Low correlation with market** (0.29) means size provides independent diversification benefits beyond market exposure

**Value Factor:**

- **Less significant but still additive to the model**: Only 9.3% annualized return over 3.91 year testing period
- **35% of individual assets show significant value loadings** (vs. 5% by chance) and portfolio tests confirm value betas align with construction (high-value portfolios load positively, low-value negatively)

**Momentum Factor:**

- **Least significant** & explanatory factor; marginally additive to the model
- Only **25% of individual assets show significant momentum loadings** (vs. 5% by chance); of these all are negative loadings implying inverse relationship to momentum
- High economic significance (75% annualized returns) but low explanatory power imply this is **better used as a trading factor** and **less significant as a systemic risk factor**

## Testing & Analysis

**Factor Correlations:**

![](https://cdn.prod.website-files.com/6760e87b474d412dfa9a7a98/692ff463b8ffabbdfd54cd17_https%253A%252F%252Fsubstack-post-media.s3.amazonaws.com%252Fpublic%252Fimages%252F2dd2699a-5e6c-4efc-b597-d0c7a5fee7ac_584x164.png)

Low correlations between all factors, signifying they successfully capture different dimensions of risk and there is little cross-contamination between factors.

**Portfolio Sorts Analysis:**

I created 4 different portfolio’s sorting by size and value, to gauge whether our factors correctly model and explain the returns of each sort.

For each period, the portfolio’s are constructed as follows:

1. Sort eligible assets by size (top 50% and bottom 50%)
2. For each size group, rank eligible assets by mc\_fees\_ratio and form two portfolio’s using a 30% breakpoint (ie: lowest 30% by mc\_fees\_ratio and highest 30% by mc\_fees\_ratio)
3. each portfolio must have at minimum 15 assets to minimize idiosyncratic risk

This results in the following portfolios:

Large Cap High Value

Large Cap Low Value

Small Cap High Value

Small Cap Low Value

Given the distinct characteristics of each portfolio, we would expect to see high factor loadings for the SMB factor on the small cap portfolio’s, and high factor loadings for value on the high value portfolio’s. We would expect to see the inverse for the large cap portfolio’s and low value portfolio’s respectively.

**Results**

TLDR: The factor models largely work as intended and the factor loadings reflect what we would expect for each portfolio.

![](https://cdn.prod.website-files.com/6760e87b474d412dfa9a7a98/692ff463b8ffabbdfd54cd1d_https%253A%252F%252Fsubstack-post-media.s3.amazonaws.com%252Fpublic%252Fimages%252F869a88a8-5fd7-4bc4-8b71-c4bf3943bfcd_1015x116.png)

**Large Cap High Value:**

- high market risk exposure (beta\_mkt: 1.12)\*\*\*
- low size factor loading (beta\_smb:.106)correctly reflects our expectation given it’s large caps
- high value factor loading (beta\_value.609)\*\*\*correctly reflects our expectation given it is a high value structured portfolio
- Factor model explains 77.8% of returns (r^2:.778)\*\*\*

**Large Cap Low Value:**

- high market risk exposure (beta\_mkt: 1.13)\*\*\*
- low size factor loading (beta\_smb:.05)correctly reflects our expectation given it’s large caps
- negative value factor loading (beta\_value -0.22)\*correctly reflects our expectation given it is a low value structured portfolio
- Factor model explains 69.4% of returns (r^2:.694)\*\*\*

**Small Cap High Value:**

- high market risk exposure (beta\_mkt: 1.24)\*\*\*
- high size factor loading (beta\_smb: 1.10)\*\*\*correctly reflects our expectation given it’s small caps
- high value factor loading (beta\_value 0.66)\*\*\*correctly reflects our expectation given it is a high value structured portfolio
- Factor model explains 78% of returns (r^2: 0.78)\*\*\*

**Small Cap Low Value:**

- high market risk exposure (beta\_mkt: 1.13)\*\*\*
- high size factor loading (beta\_smb: 1.21)\*\*\*correctly reflects our expectation given it’s small caps
- negative value factor loading (beta\_value -0.32)\*\*\*correctly reflects our expectation given it is a low value structured portfolio
- Factor model explains 73% of returns (r^2: 0.73)\*\*\*

\*\*\* p\_value <.01

\*\* p\_value <.05

\*p\_value <.10

**Sequential Analysis:**

Market risk explains the majority of returns, then Size, and then Value. Each factor is valuable and explains an additional portion of return resulting in an overall better model.

![](https://cdn.prod.website-files.com/6760e87b474d412dfa9a7a98/692ff463b8ffabbdfd54cd1a_https%253A%252F%252Fsubstack-post-media.s3.amazonaws.com%252Fpublic%252Fimages%252Fddbdf656-0b5c-4644-8542-3ae62752c2c5_734x113.png)

**Individual Asset Factor Loadings:**

For each asset that satisfied the eligibility criteria in the most recent full rebalancing period and had mc\_fees\_ratio metric coverage, we regressed our factors onto that asset’s returns. There are 67 assets in total in this evaluation.

**Results:**

Number of assets: 67

Percent of assets where p-value for market is < 0.05: 100.0% Percent of assets where p-value for smb is < 0.05: 49.3% Percent of assets where p-value for value is < 0.05: 35.8% Percent of assets where p-value for momentum is < 0.05: 25.4%

**Key Takeaways:**

- Market risk factor is most pervading statistically significant for all assets
- SMB significantly captures size-related risk on individual assets. Larger caps generally have low or negative SMB factor loadings and small caps have large factor loadings
- Value factor captures value-related risk but is weaker than the size and market risk factors. Lower multiple tokens correctly have higher loadings (AAVE 0.91, CAKE 0.47, GMX 0.83, JTO 1.17) and higher multiple tokens correctly have lower loadings on average (XRP -0.34, FLOW -0.39, BTC -0.11)NOTE: I think there’s a possibility the value factor is actually also capturing an industry or sector characteristic as well. Most high value assets are Defi (Aave, GMX, etc.) and low value assets are L1 chains w/ high market caps relative to fees.
- Momentum factor is weakest in terms of explanatory power and statistical significance. All significant loadings are negative indicating an inverse relation to momentum.