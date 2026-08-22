ARTEMIS ANALYTICS
Quant Research / Trading Strategy Competition
Overview
Artemis Analytics is a leading crypto data and research firm. Through this competition, we aim to bridge
academic thinking with real-world market application. This competition challenges teams to apply
quantitative methods to real crypto markets and prediction markets — the same tools and frameworks
used by professional researchers and trading desks.
This competition is open to individual participants or teams of up to two people (no more than 2
per group).
Teams choose one of two tracks below. Each track results in a written research report and a final
pitch presentation to Artemis judges. There is no single right answer — we are looking for rigor,
creativity, and a clear-eyed understanding of the limitations of your approach.
Timeline
●​ April 2: Competition Launch
●​ June 1: Submission Deadline @ 11:59pm EST
●​ June 10: Finalists announced; top teams present virtually the following week
Registration & Access
To participate:
1.​ Complete the Registration Form
2.​ Create an Artemis account using the same email
Once registered:
●​ Your account will be upgraded to Artemis Enterprise
●​ You will receive an API key for data access
Competition Reward
●​ An internship opportunity with Artemis, with specific terms to be determined based on the
winner’s availability
●​ $500 prize (cash or USDC)
●​ Potential for strategy to be launched as a live vault by Artemis team (applicable to factor
strategies only)Track #1: Crypto Factor Rebalancing Strategy
Build a systematic, data-driven strategy for rotating across crypto assets
Background
In traditional equities, factor investing is the practice of systematically tilting a portfolio toward
characteristics — momentum, value, size, quality — that have historically been associated with excess
returns. The idea is that instead of picking individual stocks based on conviction, you define a set of
signals, rank assets by those signals, and rebalance periodically.
Crypto markets offer a rich and largely under-explored environment for this approach. Unlike equities,
crypto assets come with a wealth of on-chain data — wallet flows, protocol usage, DEX volumes,
stablecoin dynamics, funding rates — that can serve as unique factors with no equivalent in traditional
finance.
The Challenge
Design and backtest a systematic factor-based rebalancing strategy across a universe of crypto assets.
Your strategy should:
•​ Define a clear investment universe (e.g., top 50 assets by market cap, L1s only, DeFi tokens,
etc.)
•​ Identify one or more factors or signals used to rank or score assets — these can be price-based
(momentum, volatility, mean reversion) or on-chain (active addresses, DEX volume growth,
stablecoin inflows, funding rate divergence)
•​ Specify a rebalancing frequency and portfolio construction methodology (equal weight,
signal-weighted, long-only, long/short, etc.)
•​ Backtest the strategy across a meaningful historical window and report performance — returns,
Sharpe ratio, max drawdown, and turnover at minimum
•​ Critically evaluate your findings — does the signal hold up across regimes? What are the risks of
overfitting? What would break this strategy?
What We're Looking For
• Signal Quality: Is the factor economically motivated, or just pattern-matching?​
• Methodology: Is the backtest constructed properly? Are you leaking future information?​
• Honest Assessment: Do you understand where your strategy works and where it doesn't?​
• ​Presentation: Can you explain your approach clearly to someone who didn't build it?

Data Sources
Teams are free to use any publicly available data. Suggested sources include:
•​ Price and Market Data: CoinGecko, CoinMarketCap, Kaiko, Binance/OKX public APIs
•​ On-chain Data: Artemis Terminal and Data Share, Dune Analytics, Flipside Crypto, Nansen
•​ Derivatives Data: Coinglass (funding rates, open interest), Deribit (implied volatility)Track #2: Prediction Market Strategy on Kalshi
Design a systematic approach to trading event contracts
Background
Prediction markets are exchanges where participants trade contracts tied to the outcome of real-world
events — election results, economic data releases, Fed rate decisions, weather, sports, and more.
Unlike traditional financial markets, prices in prediction markets reflect the collective probability that a
given event occurs.
Kalshi is a CFTC-regulated prediction market exchange in the United States, offering contracts across
hundreds of event categories. The market is young, inefficient in places, and ripe for quantitative
approaches — but it also has quirks that make it genuinely hard: thin liquidity, wide spreads, discrete
outcomes, and the challenge of estimating true probabilities for complex events.
The Challenge
Design a systematic trading strategy for Kalshi prediction markets. Your strategy should:
•​ Select a specific market category or set of events to focus on (e.g., economic data releases, Fed
decisions, crypto price milestones, political outcomes)
•​ Define a clear edge hypothesis — why do you believe the market is mispriced relative to the true
probability?
•​ Describe how you would size and manage positions — what is your entry signal, exit signal, and
position sizing logic?
•​ Backtest or paper-trade your strategy where possible, or present a rigorous simulation if historical
market data is limited
•​ Address the practical constraints: bid-ask spreads, liquidity, position limits, and how your edge
degrades as markets become more efficient
•​ Note: We are not looking for arbitrage strategies - we only want long short adjacent strategies
that function solely on Kalshi
What We're Looking For
•​ Edge Thesis: Is there a clear, articulable reason why the market would be systematically wrong?
•​ Probability Calibration: How do you estimate fair value for an event contract? What reference
points or models do you use?
•​ Risk Management: How do you handle correlated events, binary outcomes, and tail risk?
•​ Practicality: Could this strategy actually be implemented? What are the real-world frictions?
Data Sources
Teams are free to use any publicly available data. Suggested sources include:
•​ Kalshi: Public market data via Kalshi API (kalshi.com/docs) — historical prices, volumes, open
interest
•​ Macro Data: Federal Reserve (FRED), BLS (CPI, jobs reports), CME FedWatch for rate
expectations
•​ Reference Probabilities: Polymarket, Metaculus, PredictIt for cross-market calibration
•​ News and Event Data: Public APIs, RSS feeds, or manual event taggingDeliverables: All teams — regardless of track — must submit the following:
Research Report: Written document covering your methodology, data, backtest results, and critical evaluation. No strict page limit, but quality over length.
Code / Analysis: All code or analysis used to produce results. Should be reproducible — include instructions for running it.
Pitch Deck: A presentation summarizing your strategy for a non-technical audience.
After submission, the Artemis team will review all entries. Selected participants will be invited to present their pitch deck in a live virtual session.
Live Virtual Presentation: You will present your pitch deck to Artemis judges followed by a short Q&A session. Judges will probe your assumptions, so know your work inside and out.
Judging Criteria
Submissions will be evaluated across four dimensions:
Criterion Description Weight
Research QualityIs the methodology sound? Are assumptions stated clearly? Is the analysis reproducible? 30%
Signal / Edge ValidityIs the core idea well-motivated? Does the evidence support the hypothesis? 30%
Critical EvaluationDoes the team understand the limitations of their approach? Are risks addressed honestly? 20%
Communication: Is the written report clear? Is the presentation compelling and well-structured? 20%
Submission Guidelines:
Once you are ready to submit your entry, please follow the instructions below and email your materials
to LINDSEY@ARTEMISANALYTICS.XYZ
You will receive a confirmation email within 24 hours of your submission.
Deadline: All submissions must be received by 11:59 PM on June 1.
Required Materials
To complete your submission, please include the following three items:
1.​ Research Report - Must be submitted in PDF format.​
2.​ Code / Analysis - Include a link to your GitHub repository containing all relevant code and
analysis.​
3.​ Pitch Deck - Provide a link to your Google Slides presentation.
a.​ Ensure the deck is shared with lindsey@artemisanalytics.xyz with viewer access.
Important:
●​ Submissions must be complete at the time of sending.
●​ If you forget to include any required component, you must resubmit all materials in a new email.
●​ Do not send partial follow-up emails (e.g., sending only the missing item).
○​ For example, if your initial submission includes only Items 1 and 2, you must resend
Items 1–3 together in a new email.
We are not looking for the most profitable strategy — we are looking for the best thinking. A
strategy with a negative Sharpe ratio that is correctly understood, honestly evaluated, and clearly
presented will score better than a strategy with impressive backtested returns and no critical analysis.
The researchers and analysts at Artemis work every day with the limits of historical data, noisy
signals, and uncertain markets. Showing that you understand those limits — and can think clearly about
them — is the most important thing you can demonstrate.
