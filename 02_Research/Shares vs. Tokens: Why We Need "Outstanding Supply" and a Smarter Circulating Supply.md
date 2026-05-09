---
title: "Artemis"
source: "https://about.artemis.ai/resources/outstanding-supply"
author:
published:
created: 2026-05-09
description:
tags:
  - "clippings"
---
**Summary**: Currently, crypto data providers show wildly different supply metrics for the same token which drastically affects market cap or valuation multiples (e.g Market Cap/Revenue). Artemis and Pantera Capital propose a simple framework called **Outstanding Supply** which is Total Supply - Total Protocol Holdings that is similar to Outstanding Shares which is Total Issued Shares - Total Treasury Shares in the equities market. Our aim is to give investors a clearer apples-to-apples comparison between tokens and stocks when it comes to valuation.

### Intro

When you buy a stock, there are a few numbers every investor looks at to understand how many shares exist:

- **Authorized Shares** - How many shares a company is legally allowed to create
- **Issued Shares** - How many shares the company has ever created
- **Outstanding Shares** - How many shares currently owned by all investors excluding any treasury shares held by the company
- **Floating Shares** - How many shares are actually available for public trading

### Why does this matter?

These numbers matter because they help investors figure out:

- **Ownership** - How much economic interest in the company investors are buying
- **Supply Risk** - How much more shares could hit the market later
- **Liquidity** - How easily the stock can be traded without moving the price
![](https://cdn.prod.website-files.com/6760e87b474d412dfa9a7a98/68ae2d32d13662a089f9c969_AD_4nXdDKWbGCb5l7T0EoNlnwLwxecmXE_WimnnWMp7aGvO3TUhxQzNBCW8Muq_Axyom8OpQZ9ipLx0eQ9nOqr8U1vHFKdaBHbh65QEupQkKblqgwCsoZtAAX3LUDvYsuifcW-qy7HPO.png)

Source: Artemis

Let’s look at Uber.

- **Authorized Shares**: 5 billion shares → the maximum number of shares Uber is legally allowed to create. ***Public market investors almost never reference authorized shares.***
- **Issued Shares**: ~2.1 billion shares → the number of shares Uber has actually created
- **Outstanding Shares**: ~2.09 billion shares → the number of shares currently held by Uber investors. ***This is the share count that public market investors actually care about.***
- **Floating Shares**: ~2.07 billion shares → the number of shares that are actually tradable in the market

Now, imagine if Uber was valued on its Authorized Shares, that would make Uber look like a $469 billion company trading at 70x forward P/E, which seems unreasonable. Authorized Shares is not a number any investor uses to model a company’s valuation, because Authorized Shares \* price is not economically relevant.

However, in reality, investors value Uber on Outstanding Shares (~2.09 billion), which puts Uber’s market cap closer to $195.9 billion (as of August 17th, 2025) and a 30x forward P/E. Outstanding Shares represent the economic reality of who owns a piece of the value of the company.

### The Problem with token supply metrics right now

In crypto, most investors only refer to a token’s **Circulating Supply**.

> `Circulating Supply = Tokens available for public trading`

However, **Circulating Supply** definitions vary wildly:

- Some count locked tokens, some don’t
- Some include treasury wallets, some exclude them
- Some ignore burns
- Some projects quietly release tokens with no clear disclosure

On the other hand, investors will often see **FDV (Fully Diluted Valuation)**

> `FDV = Token Price x Total Supply `

That’s like valuing Uber as if every single share that exists was tradable tomorrow, or the $469B market cap as described above, which is also not economically correct.

So investors are left choosing between: **FDV** (everything that exists), or **Circulating Supply** (messy, inconsistent definitions that, critically, often exclude outstanding and unvested tokens).

### Why Outstanding Supply is the Practical Middle

Here is how Outstanding Supply comes in. Outstanding Supply counts all tokens that have already been created and it excludes protocol-owned balances like foundations, treasuries or labs that aren’t really in circulation.

Think of it as crypto’s version of **Outstanding Shares**.

Outstanding Supply is more relevant than FDV.

Outstanding Supply is cleaner and more standardized than Circulating Supply.

Outstanding Supply is a middle ground grounded in economic reality that investors can actually **trust**.

### Real Token Example - Hyperliquid

![](https://cdn.prod.website-files.com/6760e87b474d412dfa9a7a98/68ae2dcd3788cb8dfcd5a777_AD_4nXeqa9t40YRwrAo7FLeYraWN4ndvjVw6YfjhPlVIt8HY8flgjwd2PM-dIxN1P0Rxz4V7rQ41tiQ6Hm0dURpLxhwW5M-fwQCQ_TlnXTJVybECdppRamKjdsUHW8AoRhnjRrmpZuujAA.png)

Source: Artemis

![](https://cdn.prod.website-files.com/6760e87b474d412dfa9a7a98/68ae2e452d21ac72bea6525a_Screenshot%202025-08-26%20at%205.58.31%E2%80%AFPM.png)

Source: Artemis

### Why does Outstanding Supply matter?

For years, crypto defaulted to valuing tokens as **FDV = Max Supply \* Price**. That’s like valuing Uber as if all 5 billion Authorized Shares were already issued. This make Uber valuation come up to ~$469 billion, instead of ~$196 billion market cap you’d normally see on Google Finance.

The industry then shifted to using **Total Supply**, but this still overstates valuations because Total Supply includes total protocol holdings. For instance, 6% of Hyperliquid’s 1B HYPE tokens (60M tokens) sit with the Hyper Foundation. These tokens belong to the protocol and can be deployed for operations, grants, or team compensation. They aren’t economically equivalent to tokens owned by investors.

![](https://cdn.prod.website-files.com/6760e87b474d412dfa9a7a98/68ae3283a6917b81b1b355dc_Screenshot%202025-08-26%20at%206.16.50%E2%80%AFPM.png)

Source: Mint Ventures

That’s why, Hyperliquid’s Outstanding Supply (~$20.8 billion) provides the closest **“true”** view of market cap. It mirrors Outstanding Shares in equities - all tokens held by investors, excluding treasury shares.

By contrast, Hyperliquid’s Circulating Supply valuation (~$10.5 billion) is closer to how much HYPE tokens are actually liquid and tradeable, similar to Floating Shares for stocks.

These supply metrics matter because valuation multiples like P/E or P/S become artificially inflated when calculated on FDV - effectively penalizing businesses with large amounts of supply that have not yet been released into circulation, like Hyperliquid, compared to peers.

**<sub>Footnote:</sub>***<sub>Our definition of</sub>* ***<sub>Total Supply</sub>*** *<sub>differs from CoinGecko. While CoinGecko includes all tokens regardless of ownership, we net out tokens permanently burned and uncreated, ensuring Total Supply reflects the true amount of tokens that exist and can impact valuation.</sub>*

### Why existing numbers don’t add up

At the moment, most investors looking at $HYPE will see two very different numbers depending on the data provider:

1. DefiLlama’s Outstanding FDV puts Hyperliquid at $27.8 billion. Assuming the token price is $43, this means they’re assuming ~647 million tokens are already outstanding. That’s actually more than the 577 million tokens minted so far.
2. CoinGecko’s Circulating Supply valuation comes in at $14.5 billion. This implies they’re counting ~337 million tokens as circulating**.**

However that figure is likely overstated, because CoinGecko doesn’t exclude all protocol-owned wallets (like Hyper Foundation, Community Grants and the Assistance Fund). In practice, many of those tokens aren’t actually in the market yet, so the “true” circulating number should be lower.

The challenge is that these differences can swing valuations by billions of dollars. Without clear standards, two people can look at the same token and come away with very different impressions of its size.

This is exactly why we need **Outstanding Supply and a Smarter Circulating Supply**. Outstanding Supply for tokens gives us a standard that’s both transparent and comparable to stocks.

### Artemis Fix: Outstanding Supply and a smarter Circulating Supply

### Total Supply

Definition: All tokens that have been created (minted), subtracting burns. You can simply think of it like **Issued Shares in stocks**.

> `Total Supply = Max Supply - Uncreated Tokens - Burns`

### Outstanding Supply (New Metric)

Definition: All tokens that exist today, except the ones the protocol itself is still holding (foundation, DAO, Labs, or locked distribution contracts). We exclude tokens held by the protocol holdings because they are like treasury shares in stocks. They exist but are not owned by outside investors. Only tokens in external hands reflect true ownership, liquidity, and market value. You can simply think of it like **Outstanding Shares in stocks**.

![](https://cdn.prod.website-files.com/6760e87b474d412dfa9a7a98/68ae2ef410eed096d6077fa0_AD_4nXeV9Aoy8jCgeWRTHio7cUop2kPdx_Qh0019ZnGMcJ73ElXbph_b5Nj4kRPIgc6EBtJk3xR7irCJglbInKA8Egx9LlNVdDoRy4yy2Koc-ZND9NI2uC7KcS_cW1OtEZqN854ljnwM.png)

Source: Artemis

> `Outstanding Supply = Total Supply - Total Protocol Holdings`

Where:

- Total Protocol Holdings = Tokens held by the primary steward of the protocol (DAO, Foundation, Labs)
	1. DAO/Foundation Owned - Tokens held by the entity responsible for governance or growth
		2. Labs - Tokens held by a Labs entity that is effectively acting as the protocol’s steward (e.g., ecosystem fund, distribution manager) in cases where no independent Foundation exists
		3. Programmatic Distribution Contract - Smart contracts that automatically release tokens to the ecosystem over time
		4. Idle Fund - Tokens held in an on-chain fund managed by validator governance, where deployment is controlled through decentralized voting and remains under protocol custody until released
		5. Buyback Reserves (Unburned) - Tokens repurchased by the protocol but not yet burned

### A smarter Circulating Supply (Revised Metric)

Definition: Tokens that are available to trade now. This excludes locked tokens, insider/team holdings under vesting and illiquid treasury wallets. You can simply think of it like **Floating Shares in stocks**.

![](https://cdn.prod.website-files.com/6760e87b474d412dfa9a7a98/68ae2f19d0987798bd163fb7_AD_4nXdxQq-J_4QsixYYHeBfx5oKCMk1XZvGi6f3VLVNIvbzPsKDfiVjeTacPUkjd37Y3CnNtjwN4H2k2nl-8tdyEkRzrjOgIvEbrISUOMrW1cU17koHfuFfldFFUJnSZpcsps9CZUPU.png)

Source: Artemis

> `Circulating Supply = Outstanding Supply - Locked Tokens`

### Why do we need both of these metrics?

- Transparency - Clear view of what’s been created vs what’s actually tradeable
- Better Risk Assessment - See the overhang of supply that could enter circulation later
- Standardization - Removes ambiguity across projects
- True Market Cap - A refined Circulating Supply means more accurate valuation
- Comparability - Projects can finally be compared apples-to-apples across the industry

### Wrapping it Up

In stocks, no one has to guess how many shares exist or how much supply could hit the market. That clarity builds trust.

Crypto needs to be the same. If the industry wants institutional trust, it needs institutional-grade transparency. With Outstanding Supply and a smarter Circulating Supply, investors finally get the same transparency.

### Shoutouts

**Big thanks** to the folks who gave feedback and sharpened this piece:

[Cosmo Jiang](https://www.linkedin.com/in/cosmojiang/) at Pantera for helping refine the “Outstanding Supply” definition

[Eric Wallach](https://www.linkedin.com/in/eric-wallach-149044100/) at Panterafor pressing on “why does this matter” framing and making sure the valuation implications came through

[Katie Talati](https://www.linkedin.com/in/katie-talati/) at Arca for pointing out edge cases like buybacks and grants that needed to be explicitly addressed

And of course, the [Artemis team](https://www.artemisanalytics.com/about-us).

[Jon Ma](https://www.linkedin.com/in/jonbma/) for helping frame Outstanding Supply in plain economic terms and tying it back to equity comparisons

[Alex Weseley](https://www.linkedin.com/in/alex-weseley/) for pushing the team to make Supply metrics consistent across all projects and keeping the methodology transparent.

**BDR Team** - [Ben Stamm](https://www.linkedin.com/in/ben-stamm/), [Akhil Vajjhala](https://www.linkedin.com/in/akhilvajjhala/) and [Kaviish Sethi](https://www.linkedin.com/in/kaviish-sethi-272b7a1ab/)