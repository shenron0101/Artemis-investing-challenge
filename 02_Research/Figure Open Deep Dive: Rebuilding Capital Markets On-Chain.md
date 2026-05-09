---
title: "Artemis"
source: "https://about.artemis.ai/resources/figure-open-deep-dive-rebuilding-capital-markets-on-chain"
author:
published:
created: 2026-05-09
description:
tags:
  - "clippings"
---
**Executive Summary**

The tokenization of real-world assets (RWAs) stands at an inflection point. The market has grown to approximately $20 billion in tokenized assets today (excluding stablecoins), with projections ranging from $2 trillion (McKinsey, conservative) to $4–5 trillion (Citi, moderate) to $18.9 trillion by 2033 (BCG/Ripple, 53% CAGR). What was theoretical in 2023 is now operational infrastructure, and one company has built the dominant full-stack platform to capture this transition.

Figure Technology Solutions (NYSE: FIGR) completed its IPO in September 2025 at $25 per share, raising $787.5 million. The company now trades at approximately $40–41 per share, representing an ~$8.8 billion market cap and a ~66% appreciation from IPO. Figure reached an all-time high of $78 in January 2026 following the announcement of the On-Chain Public Equity Network (OPEN). Nine sell-side analysts cover the stock with an average price target of $56.89 and a consensus “Buy” rating.

The numbers underpin the thesis. Figure has processed over $50 billion in blockchain transactions, originated $22 billion or more in home equity products, and tokenized over $15.3 billion in assets on Provenance Blockchain. Revenue reached $341 million in 2024, up 62% year-over-year from $210 million in 2023, and the company was profitable. Figure commands an estimated ~75% share of the RWA tokenization market and approximately 70% of the on-chain private credit market.

![Image](https://cdn.prod.website-files.com/6760e87b474d412dfa9a7a98/699833d0c3fc22febbacd2fd_HBDjcf4akAE5EKv.jpeg)

Source: Artemis Analytics, Yahoo Finance

Two product lines illustrate the retail opportunity that the full-stack model uniquely enables. YLDS, the only SEC-registered yield-bearing stablecoin, has grown to $376 million in circulation with month-over-month growth of 15%. Democratized Prime, a transparent securities-lending marketplace, has matched $253 million in offers, growing 23% month-over-month, delivering approximately 9% APY to participants in a $15.3 billion annual-revenue market where retail investors historically receive just 15–50% of the economics.

Figure is not a wrapper, a bridge, or a receipt layer. It is the only platform that owns the entire vertical: blockchain (Provenance), regulated exchange (ATS), yield-bearing stablecoin (YLDS), securities lending (Democratized Prime), AAA-rated securitization (S&P), and institutional distribution (Goldman Sachs, JPMorgan, Jefferies, Deutsche Bank). This report examines why that distinction matters and what it means for the capital markets infrastructure of the next decade.

**What Is Figure Open?**

**The Company**

Figure Technology Solutions was founded by Mike Cagney, co-founder and former CEO of SoFi, with the thesis that blockchain technology could fundamentally restructure capital markets — not by building speculative tokens, but by replacing legacy financial infrastructure with programmable, transparent, on-chain systems.

The company completed its IPO on the New York Stock Exchange in September 2025 at $25 per share under the ticker FIGR, raising $787.5 million. The listing followed the July 2025 merger of Figure Technology Solutions and Figure Markets, consolidating the origination, blockchain infrastructure, and marketplace functions under a single public entity. The combined organization employs several hundred people across operations spanning lending, blockchain development, exchange infrastructure, and regulatory compliance.

**The OPEN Network**

On January 14, 2026, Figure announced the On-Chain Public Equity Network — the platform’s most ambitious initiative to date. OPEN enables native equity issuance directly on Provenance Blockchain, meaning the blockchain itself serves as the registry and settlement layer for public equities. This is not a tokenization overlay atop existing infrastructure; it is a wholesale replacement of the Depository Trust & Clearing Corporation (DTCC) for participating securities. The first equity to be natively issued on-chain is Figure’s own stock, with additional listings expected throughout 2026.

**Why is OPEN Different?**

Figure Open is fundamentally different from every other tokenized equity project because the blockchain is the book of record — not a wrapper, not a receipt, not a copy of something that lives off-chain. When a security is issued through OPEN, Provenance Blockchain serves as the official registry and settlement layer, replacing the DTCC entirely for participating securities. That single architectural decision is what enables everything else: T+0 settlement instead of T+1, 24/7 trading through a regulated ATS, self-custody without a required intermediary, and programmable compliance baked into the protocol. Competitors like Ondo, Securitize, and Dinari take the existing off-chain system and put a token on top of it — preserving the same custodial risk, the same intermediary fees, and the same settlement delays they claim to be disrupting. Figure is the only platform that owns the full stack needed to actually replace that system: its own blockchain, its own SEC-registered ATS, the only SEC-registered yield-bearing stablecoin (YLDS), a transparent securities-lending marketplace (Democratized Prime), AAA-rated securitization capability, and institutional distribution.

**The Technology Stack**

Figure’s competitive differentiation lies in its vertically integrated four-layer architecture:

**Layer 1 — Provenance Blockchain.** Built on Cosmos SDK, Provenance is an application-specific Layer 1 blockchain purpose-built for financial services. It operates with 64 or more validators and has processed over $50 billion in transactions. Provenance is second only to Ethereum in total value locked across RWA protocols, distinguishing it from general-purpose chains that bolt on financial functionality as an afterthought.

**Layer 2 — Figure ATS.** Figure operates an SEC-registered Alternative Trading System, is a FINRA member, and provides SIPC protection for customer accounts. The ATS enables 24/7 trading of tokenized securities under full regulatory compliance — a critical distinction from offshore or unregulated token exchanges.

**Layer 3 — Products.** Three core offerings sit atop the infrastructure: YLDS (yield-bearing stablecoin, $376M in circulation), Democratized Prime (securities-lending marketplace, $253M matched), and the Consumer Loan Marketplace ($816M volume, +115% year-over-year).

**Layer 4 — Distribution.** Institutional and retail distribution via Goldman Sachs, JPMorgan, Jefferies, Deutsche Bank, BitGo (custody), Jump Trading (market making), moomoo (retail brokerage access), and Keplr (wallet integration). Over 175 partners participate in the ecosystem.

![Image](https://cdn.prod.website-files.com/6760e87b474d412dfa9a7a98/699833d1c3fc22febbacd307_HBDkLkQWEAA9tYn.png)

**Native On-Chain Issuance vs. Wrapped/Synthetic Models**

The distinction between native on-chain issuance and wrapped or synthetic tokenization is the single most important architectural decision in the RWA space — and the one most frequently misunderstood by market participants.

**The Wrapped Model**

The vast majority of tokenized asset projects employ what we term the “wrapped” model. The underlying asset (a Treasury bill, an equity share, a bond) exists off-chain, held by a custodian or transfer agent. A token is issued on a blockchain as a digital receipt or claim on that off-chain asset. The token is a representation, not the asset itself.

This model introduces several structural limitations. Counterparty risk concentrates in the custodian. Settlement requires coordination between the on-chain token layer and the off-chain asset layer, often preserving the T+1 or T+2 delays of the traditional system. Fees accrue at every intermediary hop. Transparency is limited to what the custodian elects to disclose. This is the approach employed by Ondo Finance, Backed Finance, Dinari, and most tokenized Treasury products.

**The Native Model**

Figure’s OPEN network takes a fundamentally different approach: the blockchain is the book of record. When a home equity line of credit (HELOC) is originated on Provenance, the loan is written directly to the blockchain. When that loan is packaged into a securitization and rated AAA by S&P, the securitization structure exists on-chain. When Goldman Sachs or JPMorgan purchases that tranche, settlement occurs on-chain. There is no off-chain “real” version and on-chain “copy.” The on-chain representation is the authoritative record.

This architecture enables T+0 (near-instant) settlement, self-custody without a required intermediary, programmable compliance embedded at the protocol level, and 24/7 trading through the ATS. The practical impact is the elimination of the five or more intermediaries typically required in traditional securitization — originators, warehouse lenders, servicers, trustees, custodians, transfer agents, and clearing corporations — replacing them with smart contracts and validator consensus.

![Image](https://cdn.prod.website-files.com/6760e87b474d412dfa9a7a98/699833d1c3fc22febbacd304_HBDkkaJWMAAE1Hg.jpeg)

**Competitive Landscape**

The RWA tokenization market has attracted significant capital and attention, but the competitive field is highly fragmented, and no other participant has assembled the full vertical stack that Figure operates. Below, we analyze the key competitors and Figure’s structural advantages.

![Image](https://cdn.prod.website-files.com/6760e87b474d412dfa9a7a98/699833d1c3fc22febbacd313_HBDm0YsWwAAOMC9.png)

**Competitor Profiles**

**Ondo Finance** has emerged as the most visible tokenized Treasury protocol, reaching approximately $2.5 billion in total value locked across its OUSG and USDY products. However, Ondo operates as a wrapper: it purchases Treasury ETFs off-chain, issues tokens as claims, and relies on third-party custodians. U.S. retail investors are largely excluded from its core products due to regulatory structuring. Ondo has no proprietary blockchain, no ATS, no securities-lending capability, and no securitization infrastructure. It is a single-product DeFi protocol, not an integrated capital markets platform.

**Securitize and BlackRock’s BUIDL** represent the institutional tokenization play, with over $4 billion in AUM across tokenized money market and Treasury products. Securitize holds SEC transfer agent and broker-dealer registrations, giving it meaningful regulatory credibility. However, the platform’s minimum investment thresholds ($5 million for BUIDL) exclude retail participation entirely. Securitize does not operate its own blockchain or ATS, and its model is primarily focused on issuance and transfer agency rather than end-to-end market infrastructure.

**tZERO** was arguably the original vision for regulated on-chain securities trading, operating an SEC-registered ATS since 2019. However, the platform has struggled with adoption, liquidity, and commercial traction. It lacks an origination engine, stablecoin, securities-lending product, or proprietary blockchain. tZERO demonstrated that an ATS alone is insufficient without the vertical integration to drive asset supply and trading demand.

**Superstate** operates as an SEC-registered transfer agent offering tokenized Treasury and money market products, with approximately $650 million in AUM. The platform is institutional-focused with limited retail distribution and does not offer lending, exchange, or blockchain infrastructure beyond token issuance.

**Market Share Analysis**

Figure commands an estimated ~75% of the RWA tokenization market by value and approximately 70% of the on-chain private credit market. This dominance is analogous to Coinbase’s position in U.S. regulated crypto exchange volume — a function of being the first compliant, full-stack operator at scale. The $15.3 billion in assets tokenized on Provenance dwarfs the next largest competitor by a factor of nearly four.

![Image](https://cdn.prod.website-files.com/6760e87b474d412dfa9a7a98/699833d0c3fc22febbacd2fa_HBDnDSsaoAAEtkx.jpeg)

**The Securities Lending Opportunity: Democratized Prime**

**The Market**

Securities lending generated record revenue in 2025, part of a broader $37 billion prime brokerage financing revenue pool. The global lendable asset base exceeds $40 trillion, with approximately $4 trillion on loan at any given time. The market is dominated by three prime brokerages — Goldman Sachs, Morgan Stanley, and JPMorgan Chase — which collectively control approximately 60% of market share. It is, by design, one of the most opaque and intermediated markets in finance.

**The Retail Problem**

Retail investors are structurally disadvantaged in securities lending to a degree that most do not fully appreciate.

When a retail investor enables share lending through a brokerage, the economics are heavily skewed toward the intermediary. Robinhood’s Fully Paid Securities Lending program keeps approximately 85% of the lending revenue, passing only ~15% to the investor whose shares are being lent. Interactive Brokers offers the best widely available retail split at 50/50. By contrast, institutional lending programs typically return 85–90% of the revenue to the asset owner.

The asymmetry extends beyond revenue sharing. Retail margin borrowing rates range from 5.5% to 10.5%, compared to 5–6% for institutional borrowers accessing the same capital. Cross-margining — the ability to offset long and short positions across asset classes to reduce margin requirements — saves institutional market participants an estimated $8 billion per day. This capability is entirely unavailable to retail investors. Additionally, when shares are lent, retail investors lose voting rights and may face unfavorable tax treatment as “payments in lieu of dividends” are taxed as ordinary income rather than at qualified dividend rates.

**A concrete example illustrates the disparity.** Consider an investor holding 5,000 shares of a stock trading at $75 (portfolio value: $375,000) with a 9% annualized lending rate, generating $33,750 in annual lending revenue. An institutional investor through a prime broker would retain approximately $30,375 (90%). An Interactive Brokers retail client would receive $16,875 (50%). A Robinhood client would receive approximately $5,063 (15%). The same shares, the same borrower demand, the same lending rate — yet the retail investor on Robinhood captures one-sixth of what the institution earns.

**Figure’s Solution: Democratized Prime**

Democratized Prime is Figure’s answer to this structural inequity: a transparent, on-chain limit order book for securities lending. Rather than accepting whatever split a brokerage dictates, lenders set their own rates. A Dutch auction mechanism matches borrowers and lenders based on price discovery, with hourly liquidity windows allowing participants to enter and exit positions.

As of January 2026, Democratized Prime has matched $253 million in offers, growing 23% month-over-month. Funded positions are delivering approximately 9% APY to lenders — a rate that, under the traditional model, would be split predominantly in favor of the intermediary.

**Why Only Figure Can Do This**

Building a transparent securities-lending marketplace is not simply a software problem. It requires the full stack: Provenance Blockchain for atomic settlement and immutable record-keeping, the ATS for regulated trading and transfer of loaned securities, SEC and FINRA registrations for compliance across the lending lifecycle, and the securitization infrastructure to manage credit risk. No other platform has assembled all four components. This is why Democratized Prime has no direct competitor — the barrier to entry is not technology alone but the intersection of technology, regulation, and financial infrastructure that took Figure nearly a decade to construct.

**Cross-Collateralization: The Unified Balance Sheet**

**Traditional Fragmentation**

Today, a typical investor’s financial life is fragmented across disconnected silos. Stocks sit at a brokerage. Cash resides at a bank. Crypto is held at an exchange. Real estate equity is locked in a property with no liquid mechanism for extraction short of a refinance or sale. Each silo operates under its own margin rules, its own collateral framework, and its own risk engine. There is no netting across these positions, meaning an investor with $500,000 in equities, $200,000 in crypto, and $300,000 in home equity cannot borrow against the aggregate $1 million portfolio at a single blended rate.

**The Institutional Advantage**

Institutional investors and market professionals operate in a fundamentally different paradigm. Cross-margining programs allow them to offset risk across asset classes, saving an estimated $8 billion per day in margin requirements. Portfolio margin accounts — available only to investors meeting $125,000 to $175,000 minimums — enable risk-based margining that can reduce capital requirements by 50–70% compared to retail Reg-T margin. Cross-clearinghouse margining is restricted entirely to clearing members and market professionals.

**Figure’s Unified Model**

Figure’s architecture places all asset classes on a single ledger. Stocks issued through OPEN, bonds, cryptocurrency, YLDS stablecoin holdings, and real estate equity (via tokenized HELOCs) all exist on Provenance Blockchain. This enables a single cross-collateral margin engine that calculates risk across the entire portfolio simultaneously. An investor can borrow against their combined holdings — equities plus crypto plus stablecoin plus real estate — at institutional-grade rates, with collateral automatically managed by smart contracts.

The implication is profound: every retail investor using the Figure platform effectively becomes their own mini-prime-brokerage client, accessing the margin efficiency, cross-asset netting, and capital optimization that has historically been reserved for hedge funds and proprietary trading desks.

**YLDS: The Settlement Layer**

YLDS occupies a unique position in the stablecoin landscape as the only asset that is both SEC-registered and yield-bearing. Launched as a digital asset under SEC oversight, YLDS has grown to $376 million in circulation as of January 2026, with 15% month-over-month growth.

The yield mechanism is straightforward: YLDS pays the overnight secured financing rate minus 35 basis points, translating to approximately 3.82–3.84% APY at current rates. This yield accrues daily to holders, making YLDS a productive cash-equivalent rather than a dormant dollar peg.

Within Figure’s ecosystem, YLDS serves three critical functions. First, it acts as the settlement currency for the ATS, enabling instantaneous T+0 settlement of securities transactions. Second, it serves as eligible collateral within Democratized Prime, allowing lenders to post yield-bearing collateral rather than idle cash. Third, it functions as a cash management tool, providing competitive money market returns without requiring investors to move funds off-platform.

The competitive positioning is instructive. USDC, with over $30 billion in circulation, is the leading regulated stablecoin — but pays no yield. USDT, with over $100 billion in circulation, faces persistent regulatory questions and also pays no yield. Algorithmic or DeFi yield-bearing stablecoins offer returns but lack SEC registration and the corresponding regulatory protections. YLDS stands alone in the upper-right quadrant of the two dimensions that matter most: regulatory standing and economic return.

![Image](https://cdn.prod.website-files.com/6760e87b474d412dfa9a7a98/699833d1c3fc22febbacd301_HBDnzoEakAA2KyU.png)

**Growth Metrics & Financial Performance**

**Revenue Trajectory**

Figure generated $341 million in revenue in 2024, a 62% increase from $210 million in 2023. The company achieved profitability in 2024, a notable distinction in an industry where most competitors remain pre-revenue or cash-flow negative. The revenue base spans origination fees, securitization economics, ATS transaction revenue, and platform fees across the Figure ecosystem.

![Image](https://cdn.prod.website-files.com/6760e87b474d412dfa9a7a98/699833d1c3fc22febbacd310_HBDoEqLakAA5J36.jpeg)

The January 2026 data reveals accelerating momentum across all product lines. The Consumer Loan Marketplace’s 115% year-over-year growth reflects expanding origination capacity and borrower demand. YLDS and Democratized Prime, both relatively early-stage products, are compounding at double-digit monthly rates — trajectories that, if sustained, would place both products in the multi-billion-dollar range within 12–18 months.

**The RWA Market Opportunity**

**Current State**

The tokenized RWA market stands at approximately $20 billion today, excluding stablecoins. Tokenized U.S. Treasuries alone account for roughly $8.7 billion of this total, reflecting the initial “low-hanging fruit” of bringing the safest, most liquid assets on-chain. The market has grown from under $2 billion in early 2023 to its current level in under three years — a trajectory that, while impressive, represents a fraction of the addressable opportunity.

**Forward Projections**

Multiple institutional research teams have published projections for the RWA tokenization market, and while the estimates vary widely, the direction is unanimous:

![Image](https://cdn.prod.website-files.com/6760e87b474d412dfa9a7a98/699833d1c3fc22febbacd30d_HBDoUgqWQAAVnv_.jpeg)

Even the most conservative estimate (McKinsey’s $2 trillion) implies approximately 100x growth from today’s base. At the midpoint (Citi’s $4–5 trillion), the market would grow 200–250x. The BCG/Ripple projection of $18.9 trillion by 2033 would make tokenized RWAs roughly equivalent to the current U.S. mutual fund industry.

**What This Means for Figure**

Figure’s estimated ~75% market share of the current $15.3 billion in tokenized assets positions it as the dominant incumbent entering a market that is projected to grow by two to three orders of magnitude. Market share will inevitably compress as the opportunity expands and new entrants arrive, but even a decline to 20–30% market share of a $4 trillion market would imply $800 billion to $1.2 trillion in tokenized assets on Provenance — a transformative outcome.

Provenance Blockchain’s position as second only to Ethereum in RWA total value locked, with 64 or more validators and over $50 billion in processed transactions, provides the infrastructure credibility to absorb this growth. The chain was purpose-built for financial services, not retrofitted from a general-purpose smart contract platform, which translates to performance, compliance, and governance characteristics aligned with institutional requirements.

![Image](https://cdn.prod.website-files.com/6760e87b474d412dfa9a7a98/699833d1c3fc22febbacd30a_HBDocMFWkAEtBj4.png)

**Investment Thesis: Why OPEN Is Positioned to Win**

**Five Bull Case Arguments**

**1\. Dominant market share in a 100–1,000x growth market.** Figure’s ~75% share of RWA tokenization is the starting position, not the ceiling. The company has spent nearly a decade building the infrastructure — blockchain, ATS, regulatory registrations, securitization capability, institutional relationships — that cannot be replicated in 12–18 months. First-mover advantage in regulated financial infrastructure is qualitatively different from first-mover advantage in consumer software; the switching costs, compliance costs, and integration complexity create durable barriers.

**2\. Only full-stack platform in the market.** No competitor owns a blockchain, operates an ATS, issues an SEC-registered stablecoin, runs a securities-lending marketplace, and has AAA-rated securitization capability. Competitors have one or two of these components; Figure has all six. This vertical integration eliminates the interoperability challenges, fee leakage, and counterparty risks that fragment every other approach.

**3\. Retail unlock in securities lending and prime brokerage.** The $15.3 billion securities-lending revenue pool and $37 billion prime brokerage financing market are addressable through Democratized Prime and cross-collateralization. If Figure captures even 5–10% of securities-lending revenue by delivering institutional economics to retail, the incremental revenue opportunity exceeds $750 million to $1.5 billion annually — multiples of the current revenue base.

**4\. Profitable at scale with accelerating growth.** $341 million in revenue, profitability in 2024, and 62% year-over-year growth is a financial profile that supports continued reinvestment without dilutive capital raises. The combination of profitability and high growth in a nascent market is exceedingly rare and provides the balance sheet to fund the multi-year build-out that full-stack financial infrastructure requires.

**5\. Multi-year regulatory moat.** SEC registrations for the equity network, ATS, stablecoin (YLDS), and securitization programs represent years of legal, compliance, and regulatory work. Each registration is a separate barrier to entry. The compound effect of holding registrations across the entire stack — while competitors hold one or none — creates a moat that is measured not in technology cycles but in regulatory approval cycles.

**Key Risks**

**1\. Regulatory change.** SEC or FINRA rule changes could alter the framework under which Figure operates. The current regulatory posture is constructive (GENIUS Act, Clarity Act discussions), but administrations and Commission compositions change. A hostile regulatory shift could slow adoption or require structural changes to products.

**2\. Revenue concentration.** Figure’s revenue base is heavily weighted toward home equity origination and securitization. While the product portfolio is diversifying, a downturn in the housing market or rising interest rates compressing origination volumes would disproportionately impact near-term financials.

**3\. Incumbent competition.** BlackRock (through its Securitize/BUIDL partnership), Fidelity, and other asset management giants have the resources and distribution to build or acquire competing infrastructure. If a $10 trillion asset manager commits to vertical integration in tokenization, it would represent the most credible competitive threat to Figure’s dominance.

**4\. Execution risk in new products.** Democratized Prime and YLDS are growing rapidly but remain early-stage relative to the addressable opportunity. Scaling a securities-lending marketplace requires liquidity, which requires participants, which requires liquidity — the classic cold-start problem. The +23% and +15% monthly growth rates are encouraging but must be sustained through market cycles.

**5\. RWA timing risk.** The $2–18.9 trillion projections for tokenized RWAs assume adoption curves that may prove optimistic. Institutional migration from legacy infrastructure is constrained by vendor contracts, internal technology roadmaps, regulatory comfort, and organizational inertia. The market could take longer to materialize than projections suggest, compressing near-term multiples.

**Sources**

1. Figure Technology Solutions IPO Prospectus, SEC Filing, September 2025. [SEC EDGAR](https://www.sec.gov/)
2. Figure Technology Solutions, [“January 2026 Operating Data Release,”](https://www.globenewswire.com/news-release/2026/02/05/3232600/0/en/Figure-Technology-Solutions-Reports-January-Operating-Data.html) GlobeNewsWire, February 5, 2026.
3. Figure Technology Solutions, [“Q4 2025 / December Operating Data,”](https://www.globenewswire.com/news-release/2026/01/12/3216769/0/en/Figure-Technology-Solutions-Reports-Preliminary-Q4-2025-December-Operating-Data.html) GlobeNewsWire, January 12, 2026.
4. Figure Technology Solutions, [“Figure Announces On-Chain Public Equity Network (OPEN),”](https://investors.figure.com/news-releases/news-release-details/figure-announces-chain-public-equity-network-open-running) January 14, 2026.
5. CoinDesk, [“Figure Joins Stock Tokenization Race with New Trading Platform Backed by BitGo, Jump,”](https://www.coindesk.com/business/2026/01/14/figure-joins-stock-tokenization-race-with-new-trading-platform-backed-by-bitgo-jump) January 14, 2026.
6. Citi Global Perspectives & Solutions, “Money, Tokens, and Games: Blockchain’s Next Billion Users,” March 2023.
7. BCG and Ripple, “Relevance of On-Chain Asset Tokenization in Crypto Winter,” 2023; Updated Projection, 2024.
8. McKinsey & Company, “What Is Tokenization?” August 2024.
9. [Figure Technology Solutions Investor Relations.](https://investors.figure.com/)
10. [StockAnalysis, FIGR Overview and Analyst Estimates.](https://stockanalysis.com/stocks/figr/)
11. BusinessWire, [“Figure Technology Solutions to Merge with Figure Markets,”](https://www.businesswire.com/news/home/20250715274148/en/) July 15, 2025.
12. Pantera Capital, [“Figure IPO: Where Capital Markets Meet Blockchain.”](https://panteracapital.com/blockchain-letter/figure-ipo-where-capital-markets-meet-blockchain/)
13. S&P Global / DBRS Morningstar, Provenance Blockchain HELOC Securitization Ratings (FIGRE 2023-HE1), Various 2023–2025.
14. PRNewsWire, [“Figure Markets Launches Industry-First Yield-Bearing Stablecoin as SEC-Registered Public Security,”](https://www.prnewswire.com/news-releases/figure-markets-launched-industry-first-yield-bearing-stablecoin-as-an-sec-registered-public-security-302381466.html) February 2025.
15. [YLDS Official Site.](https://www.ylds.com/)
16. [Figure, “How Democratized Prime Gives You Access to Lend at the Prime Rate.”](https://www.figure.com/blog/how-democratized-prime-gives-you-access-to-lend-at-the-prime-rate/)
17. HedgeWeek, [“Global Securities Lending Revenue Hits Record $15.3bn in 2025.”](https://www.hedgeweek.com/global-securities-lending-revenue-hits-record-15-3bn-in-2025/)
18. Hedge Fund Alpha, [“Global Securities Lending Revenue Hits $15B, 2025.”](https://hedgefundalpha.com/news/global-securities-lending-revenue-hits-15b-2025/)
19. [Interactive Brokers, Stock Yield Enhancement Program.](https://www.interactivebrokers.com/en/pricing/stock-yield-enhancement-program.php)
20. [Schwab, “Earning Extra Income with Securities Lending.”](https://www.schwab.com/learn/story/earning-extra-income-with-securities-lending)
21. [Fidelity, Fully Paid Lending Program.](https://www.fidelity.com/trading/fully-paid-lending)
22. ShareGain, [“How Much Online Brokers Made from Securities Lending.”](https://sharegain.com/how-much-online-brokers-made-from-securities-lending/)
23. Finadium, [“Prime Brokerage Equity Finance Revenues in 2025.”](https://finadium.com/prime-brokerage-equity-finance-revenues-in-2025/)
24. [Provenance Blockchain Foundation.](https://provenance.io/)
25. Coinbase Developer Platform, [“Guide to Provenance Blockchain.”](https://www.coinbase.com/developer-platform/discover/protocol-guides/guide-to-provenance-blockchain)
26. AInvest, [“Ondo Finance Expands Tokenized RWA Market Share, $2.5B TVL Growth.”](https://www.ainvest.com/news/ondo-finance-ondo-expands-tokenized-rwa-market-share-2-5-billion-tvl-growth-2602/)
27. [Securitize / BlackRock BUIDL.](https://securitize.io/blackrock/buidl)
28. PRNewsWire, [“Securitize to Become a Public Company at $1.25B Valuation.”](https://www.prnewswire.com/news-releases/securitize-the-leading-tokenization-platform-to-become-a-public-company-at-1-25b-valuation-302596208.html)
29. CoinDesk, [“Why Tokenized Stocks, Funds, and Gold Will Have a Breakout Year in 2026.”](https://www.coindesk.com/news-analysis/2026/01/17/why-tokenized-stocks-funds-and-gold-will-have-a-breakout-year-in-2026)
30. BDO, [“Trends in Tokenization: Reimagining Real-World Assets.”](https://www.bdo.com/insights/industries/fintech/trends-in-tokenization-reimagining-real-world-assets)
31. World Economic Forum, [“Tokenization of Assets: Transforming the Future of Finance.”](https://www.weforum.org/stories/2025/08/tokenization-assets-transform-future-of-finance/)
32. CoinDesk, [“This Blockchain Lender’s Stock Named 2026 Top Pick by Wall Street Analyst.”](https://www.coindesk.com/markets/2026/01/14/this-blockchain-lender-s-stock-named-2026-top-pick-by-wall-street-analyst)
33. [FINRA BrokerCheck, Figure Securities Registration Records.](https://files.brokercheck.finra.org/crs_307093.pdf)
34. Architect Partners, [“Figure Technology Solutions to Merge with Figure Markets.”](https://architectpartners.com/figure-technology-solutions-to-merge-with-figure-markets/)

Allied Market Research, [“Securities Lending Market Report.”](https://www.alliedmarketresearch.com/securities-lending-market-A325782)