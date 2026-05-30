#!/usr/bin/env python3
"""
Plan A — Economic two-signal regime classifier
==============================================

Regime is identified from two endogenous cross-sectional signals (no external
macro data needed):

  1. Cross-Sectional Dispersion (CSD): std of weekly returns across the universe.
     High CSD => assets move independently => factor rankings are exploitable.
  2. BTC Dominance Momentum (dBtcDom): 4-week change in BTC's share of total
     market cap. Falling => capital rotating into alts (risk-on); rising =>
     flight to quality (risk-off).

Regime score   RS_t = 0.5 * CSD_z  -  0.5 * dBtcDom_z   (52w rolling z, lagged 1w)
Classification RS > +0.5 RiskOn | -0.5..+0.5 Neutral | RS < -0.5 RiskOff

Output: artifacts/data/a_regime_panel.parquet  [week, csd, btc_dom, dbtc_dom,
        csd_z, dbtc_z, rs, label, gross]
"""
from __future__ import annotations

import numpy as np
import pandas as pd

import _rcfp_common as C

RS_HI = 0.5
RS_LO = -0.5


def main() -> None:
    rets = C.load_returns()
    mcap = C.load_mcap()

    # cross-sectional dispersion of weekly returns
    csd = rets.groupby("week")["ret"].std().rename("csd")

    # BTC dominance = BTC mcap / total mcap each week
    tot = mcap.groupby("week")["mcap"].sum().rename("tot_mcap")
    btc = (mcap[mcap["symbol"] == "BTC"].set_index("week")["mcap"]
           .rename("btc_mcap"))
    dom = pd.concat([tot, btc], axis=1)
    dom["btc_dom"] = dom["btc_mcap"] / dom["tot_mcap"]
    dom["dbtc_dom"] = dom["btc_dom"] - dom["btc_dom"].shift(4)

    reg = pd.concat([csd, dom[["btc_dom", "dbtc_dom"]]], axis=1).sort_index()
    reg["csd_z"] = C.rolling_z(reg["csd"])
    reg["dbtc_z"] = C.rolling_z(reg["dbtc_dom"])

    # regime score, lagged one week (strictly OOS)
    reg["rs_raw"] = 0.5 * reg["csd_z"] - 0.5 * reg["dbtc_z"]
    reg["rs"] = reg["rs_raw"].shift(1)

    reg["label"] = "Neutral"
    reg.loc[reg["rs"] > RS_HI, "label"] = "RiskOn"
    reg.loc[reg["rs"] < RS_LO, "label"] = "RiskOff"
    # weeks before we have a score default to Neutral
    reg.loc[reg["rs"].isna(), "label"] = "Neutral"

    reg["gross"] = reg["label"].map(C.GROSS)

    out = reg.reset_index().rename(columns={"index": "week"})
    out = out[["week", "csd", "btc_dom", "dbtc_dom", "csd_z", "dbtc_z",
               "rs", "label", "gross"]]
    C.write_frame(out, "a_regime_panel")

    counts = out["label"].value_counts().to_dict()
    C.write_json({"regime_counts": counts,
                  "weeks": int(len(out)),
                  "rs_hi": RS_HI, "rs_lo": RS_LO,
                  "csd_mean": float(reg["csd"].mean()),
                  "btc_dom_mean": float(reg["btc_dom"].mean())},
                 "a_regime_manifest.json")

    print("Plan A regime panel written.")
    print("Regime counts:", counts)
    print(out.tail(8).to_string(index=False))


if __name__ == "__main__":
    main()
