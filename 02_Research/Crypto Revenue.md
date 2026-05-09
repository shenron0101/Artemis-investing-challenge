---
title: "Artemis"
source: "https://about.artemis.ai/resources/crypto-revenue"
author:
published:
created: 2026-05-09
description:
tags:
  - "clippings"
---
How we measure crypto protocol revenue matters. Teams optimize for the metrics that become standard, making consistent definitions essential for healthy industry development. Historically there have been a very scattered set of definitions for what is protocol revenue leading to a lot of confusion. Here, we outline how Artemis and 10+ protocols and funds think about protocol businesses and propose a new standard for crypto value accrual metric: revenue.

## Understanding Protocol Businesses

Most protocol businesses operate as multi-sided marketplaces, a concept that is well understood in traditional business analysis. A multi-sided marketplace is a platform that connects supply and demand for a particular product or service. This means that the platform does not control the goods or services that are offered, rather it acts as a piece of infrastructure to connect users. Most crypto protocols function in a very similar way: permissionless platforms that facilitate the exchange of goods. Most DEXes operate this way (LPs and traders), as do lending protocols (borrowers and lenders), and liquid staking protocols (liquid stakers and validators). Crypto protocols have complex multi-party dynamics but we feel the lens of a multi-sided marketplace is the best to understand crypto economics and value accrual.

The analogies that make this most clear are Airbnb and Uber. Uber is a platform that helps meet demand for transportation/mobility by connecting drivers (supply) to riders (demand), taking a cut of the fee in exchange for providing this platform. The fee that users pay to access Uber’s service is what they call “Gross Bookings” in financial filings. The portion of these fees that accrue to Uber, the business, is what becomes its top line revenue. The same logic applies to Airbnb.

![](https://cdn.prod.website-files.com/6760e87b474d412dfa9a7a98/68c43669739057f8aab68ef8_504a60a4.png)

Above, Uber 10K

![](https://cdn.prod.website-files.com/6760e87b474d412dfa9a7a98/68c43669739057f8aab68efb_d62ac953.png)

Above, Airbnb 10K

**Fees**

What we measure with the \`fees\` metric is the value that users are willing to pay to access a product or service. Artemis defines fees as:

*Total value paid by users to use a platform or service.*

To extend the Uber analogy, what users pay to access Uber’s platform/service is the booking value (eg. you pay $30 for an Uber to Midtown). This is the equivalent to Uber’s Gross Bookings value, or what is typically called “fees” in crypto. The same logic applies to the AirBNB example.

**Revenue**

What we measure with the \`revenue\` metric is the value that the protocol is able to capture from its operations to the benefit of tokenholders. Artemis defines revenue as:

*Value accrued to tokenholders via fees accrued to a treasury, burns, buybacks and burns, or direct fee distributions to tokenholders (including active and passive tokenholders). These must be derived from the protocol’s core operations on a recurring basis. Revenue is considered prior to operating expense, token emissions, or other expenses.*

This is most clear with the example of a DAO. In the case of Lido, the DAO accrues ~5% of the yield generated through the protocol’s operations. This ~5% becomes the top line revenue for the DAO. Since tokenholders control the DAO, this is considered revenue for LDO. In cases where there is no DAO we consider a few mechanisms that “distribute” value to tokenholders: burns, buybacks, and direct fee distributions to tokenholders (inclusive of staked/actively participating tokenholders).

Note that here we do not include value captured by the team (Labs) or Foundations. We also do not include investment income generated through the DAO’s investment activities, as the focus is on quantifying operating activity. We also exclude value distributed via block rewards/token emissions.

**Why is this new definition of revenue important and better than Artemis’ old definition?**

In our previous definition of revenue we consistently and notably excluded the value accrued to “active” participants in a token economy. For instance, value accrued to staked ETH or staked SOL was excluded, as was value to vote-escrowed/locked assets like veAERO, veCRV, vePENDLE, and xSUSHI. *We believe the crypto industry is maturing towards valuing assets based on their “active” components as well*. These active and passive assets are analogous to different classes of shareholders in traditional equities. The most obvious example is the distinction between preferred and common shares, where preferred shareholders have a priority claim to the assets of the business and a fixed dividend yield but have a capped upside when compared to common shareholders. Either way, the revenue accrued to the business is the same for both. Unlike traditional businesses where employees provide services for wages, crypto validators/stakers must first own the underlying token to participate. Their rewards flow from their capital ownership as well as from providing an external service. With this new and expanded definition we believe we more accurately convey the value that a protocol is able to direct to tokenholders.

## What this means for Artemis users

**Updated Metric: REVENUE**

Value accrued to tokenholders via fees accrued to a treasury, burns, buybacks and burns, or direct fee distributions to tokenholders (including active and passive tokenholders). These must be derived from the protocol’s core operations on a recurring basis.

**New Metric: ACTIVE\_REVENUE**

The portion of revenue that you have a claim to as an active, participating holder of a token. For instance, as a staker of ETH or SOL you have claims on the economic benefits generated by burned base fees, as well as priority fees.

**New Metric: PASSIVE\_REVENUE**

We define this as the portion of revenue that you have a claim to as a passive, vanilla tokenholder. For instance, as a holder of unstaked ETH or SOL, you have claims on the economic benefits generated via token burns, but not priority fees.

**Timeline for changes**

- Fri, 9-12-25: publish article
- Week of Mon, 9-15-25: begin rolling out changes incrementally, starting with top protocols (AERO, PENDLE, CRV, and a few more)
- Week of Mon, 9-22-25: roll out changes to all protocols.

Once the changes are rolled out, the existing REVENUE metric will adopt the new methodologies and historical revenue data will be restated using the new methodology. Users can expect to see changes in historical revenue figures for protocols with significant staking/active participation components, particularly for assets like ETH, SOL, CRV, and AERO."

To maintain continuity for existing dashboards and analyses, the legacy revenue definition will remain available as PASSIVE\_REVENUE. Users who want to preserve their current metrics should update their queries to use PASSIVE\_REVENUE instead of REVENUE starting on 09-22-25.

You can follow along with our [progress in our dedicated docsite](https://app.artemisanalytics.com/docs/data-reference/revenue-migration-reference). Customer success will reach out proactively to Enterprise customers to discuss any dashboard updates needed.

**Conclusion**

In this piece we propose a clear and standard definition of revenue for crypto protocols, something currently missing in a rapidly maturing industry. We explain how protocol businesses often behave as multisided market places, and thus revenue should be accounted for using the agent framework. We also touch on the fact that crypto protocols often have multiple classes of tokens, where staking or otherwise actively participating in the protocol grants tokenholders greater economic benefits. With this in mind, we propose a new, consistent definition to an existing metric for value capture for crypto protocols. We then split this revenue into the portion captured by \`active\` vs \`passive\` tokenholders, introducing 2 new metrics: passive\_revenue and active\_revenue. This is only the first step in standardizing how crypto financial metrics are standardized and interpreted. The next step is understanding the cost structures of crypto protocols through token incentives, emissions, and other operating expenses, but we will leave that discussion for a later date.

**Shoutouts**

Thanks to everyone who took the time to give us feedback and think through these questions. In no particular order, we’d like to thank the Aerodrome team, Topher from Arca, Sunny from Syncracy, Austin from Relayer Capital, Bryan from Outerlands Capital, Paul at Franklin Templeton, Ken from Electric Capital, and many others! As always, grateful to the Artemis team for the countless hours spent debating and whiteboarding crypto and tokenomics.

## Appendix: Applications of this methodology to protocol tokenomics

![](https://cdn.prod.website-files.com/6760e87b474d412dfa9a7a98/68c43669739057f8aab68f0b_da585cbd.png)

![](https://cdn.prod.website-files.com/6760e87b474d412dfa9a7a98/68c43669739057f8aab68f0e_dea2366a.png)

![](https://cdn.prod.website-files.com/6760e87b474d412dfa9a7a98/68c43669739057f8aab68f11_424549d9.png)

![](https://cdn.prod.website-files.com/6760e87b474d412dfa9a7a98/68c43669739057f8aab68f17_b11dc5ab.png)

![](https://cdn.prod.website-files.com/6760e87b474d412dfa9a7a98/68c43669739057f8aab68f14_2cc61685.png)

![](https://cdn.prod.website-files.com/6760e87b474d412dfa9a7a98/68c43669739057f8aab68f1a_c4ccc966.png)

![](https://cdn.prod.website-files.com/6760e87b474d412dfa9a7a98/68c43669739057f8aab68f20_ce4d1c5d.png)

![](https://cdn.prod.website-files.com/6760e87b474d412dfa9a7a98/68c43669739057f8aab68f23_10d0c2ab.png)

![](https://cdn.prod.website-files.com/6760e87b474d412dfa9a7a98/68c43669739057f8aab68f1d_5152de56.png)