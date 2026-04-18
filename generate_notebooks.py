"""Generate notebooks 01-06 as runnable .ipynb files."""
import nbformat
from nbformat.v4 import new_notebook, new_code_cell, new_markdown_cell
import os

NB_DIR = "notebooks"
os.makedirs(NB_DIR, exist_ok=True)
os.makedirs("reports", exist_ok=True)


def make_nb(cells):
    nb = new_notebook()
    nb.metadata = {
        "kernelspec": {
            "display_name": "Python 3",
            "language": "python",
            "name": "python3",
        },
        "language_info": {"name": "python", "version": "3.12.0"},
    }
    nb.cells = cells
    return nb


# ---------------------------------------------------------------------------
# 01 -- Data Validation
# ---------------------------------------------------------------------------
NB01_SETUP = """\
import os, warnings
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
warnings.filterwarnings('ignore')
os.makedirs('../reports', exist_ok=True)

art = pd.read_parquet('../data/processed/panel_artemis_daily.parquet')
mkt = pd.read_parquet('../data/processed/panel_market_daily.parquet')
uni = pd.read_parquet('../data/processed/universe_monthly.parquet')

for df in [art, mkt, uni]:
    df['date'] = pd.to_datetime(df['date'])

art = art.sort_values(['symbol', 'date']).reset_index(drop=True)
mkt = mkt.sort_values(['symbol', 'date']).reset_index(drop=True)
uni = uni.sort_values(['date', 'symbol']).reset_index(drop=True)

print(f"Artemis daily : {art.shape}  |  {art['date'].min().date()} -> {art['date'].max().date()}")
print(f"Market daily  : {mkt.shape}  |  {mkt['date'].min().date()} -> {mkt['date'].max().date()}")
print(f"Universe      : {uni.shape}  |  {uni['date'].nunique()} rebalance dates, {uni['symbol'].nunique()} unique symbols")
print()
print("Artemis null rates:")
print(art.isnull().mean().drop('date').round(3).to_string())
"""

NB01_UNIVERSE = """\
## Section 1: Universe Coverage
rebalance_dates = sorted(uni['date'].unique())
cov_rows = []
for t in rebalance_dates:
    syms = uni[uni['date'] == t]['symbol'].tolist()
    art_t = art[(art['date'] == t) & art['symbol'].isin(syms)]
    n_price = art_t['price'].notna().sum()
    cov_rows.append({'date': t, 'n_universe': len(syms), 'n_with_price': n_price})

ucov = pd.DataFrame(cov_rows)
n_complete = (ucov['n_with_price'] >= 40).sum()
print(f"Months with >=40 coins having Artemis price: {n_complete} / {len(ucov)}")
print(ucov[['n_universe', 'n_with_price']].describe().round(1))
"""

NB01_HEATMAP = """\
## Section 2: Artemis Coverage Heatmap
metrics = ['fees', 'dau', 'tvl', 'txns', 'revenue']
all_uni_syms = sorted(uni['symbol'].unique())

coverage_records = []
for t in rebalance_dates:
    t_30 = t - pd.Timedelta(days=29)
    art_slice = art[(art['date'] >= t_30) & (art['date'] <= t)]
    for sym in uni[uni['date'] == t]['symbol'].tolist():
        sym_data = art_slice[art_slice['symbol'] == sym]
        row = {'symbol': sym, 'date': t}
        for m in metrics:
            row[m] = int(sym_data[m].notna().sum())
        coverage_records.append(row)

cov_df = pd.DataFrame(coverage_records)

print("Coverage (non-null days in trailing 30d window) -- % of (symbol,month) pairs with >15 obs:")
for m in metrics:
    pct = (cov_df[m] > 15).mean() * 100
    print(f"  {m:12s}: {pct:5.1f}%")

# Heatmap: months with >15 valid obs per symbol
heatmap = cov_df.groupby('symbol')[metrics].apply(lambda x: (x > 15).sum())
heatmap = heatmap.reindex(index=[s for s in all_uni_syms if s in heatmap.index])
heatmap['total'] = heatmap.sum(axis=1)
heatmap = heatmap.sort_values('total', ascending=False).drop('total', axis=1)

fig, ax = plt.subplots(figsize=(7, max(8, len(heatmap) * 0.18)))
im = ax.imshow(heatmap.values, aspect='auto', cmap='YlOrRd', vmin=0, vmax=48)
ax.set_xticks(range(len(metrics))); ax.set_xticklabels(metrics)
ax.set_yticks(range(len(heatmap))); ax.set_yticklabels(heatmap.index, fontsize=5)
ax.set_title('Months with >15 non-null days per metric per symbol')
plt.colorbar(im, ax=ax, label='Months (max 48)')
plt.tight_layout()
plt.savefig('../reports/coverage_heatmap.png', dpi=100, bbox_inches='tight')
plt.show()
print("Coverage heatmap saved to reports/coverage_heatmap.png")
"""

NB01_RETURNS = """\
## Section 3: Return Sanity
price_df = art[['symbol', 'date', 'price']].dropna(subset=['price']).copy()
price_df = price_df.sort_values(['symbol', 'date'])
price_df['daily_ret'] = price_df.groupby('symbol')['price'].pct_change()

extreme = price_df[price_df['daily_ret'].abs() > 1.0]
print(f"Extreme daily returns (|ret| > 100%): {len(extreme)} instances")
if len(extreme):
    print(extreme.nlargest(10, 'daily_ret')[['symbol', 'date', 'daily_ret']].to_string(index=False))

print()
desc = price_df['daily_ret'].describe(percentiles=[0.01, 0.05, 0.25, 0.5, 0.75, 0.95, 0.99])
print("Daily return distribution:")
print(desc.round(4).to_string())
"""

NB01_SURV = """\
## Section 4: Survivorship Check
early = set(uni[uni['date'].isin(rebalance_dates[:6])]['symbol'])
late  = set(uni[uni['date'].isin(rebalance_dates[-6:])]['symbol'])
print(f"Symbols in first 6 months : {len(early)}")
print(f"Symbols in last  6 months : {len(late)}")
print(f"Survived (in both)        : {len(early & late)}")
print(f"Dropped out               : {len(early - late)}")
print(f"New entrants              : {len(late - early)}")

print()
print("Per-factor coverage summary (months with >15 non-null obs):")
rows = []
for m in metrics:
    valid = (cov_df[m] > 15).sum()
    total = len(cov_df)
    per_sym = cov_df.groupby('symbol')[m].apply(lambda x: (x > 15).sum())
    rows.append({
        'Metric': m,
        'Valid (sym x month)': valid,
        'Coverage %': f"{valid/total*100:.1f}%",
        'Median months/sym': f"{per_sym.median():.0f}",
        'Max months/sym': f"{per_sym.max():.0f}",
    })
print(pd.DataFrame(rows).to_string(index=False))
print("\\n>> Data validation complete.")
"""

nb01_cells = [
    new_markdown_cell("# 01 -- Data Validation\nCoverage heatmap, return sanity, universe completeness."),
    new_code_cell(NB01_SETUP),
    new_code_cell(NB01_UNIVERSE),
    new_code_cell(NB01_HEATMAP),
    new_code_cell(NB01_RETURNS),
    new_code_cell(NB01_SURV),
]
nb01 = make_nb(nb01_cells)
with open(f"{NB_DIR}/01_data_validation.ipynb", "w") as f:
    nbformat.write(nb01, f)
print("Written 01_data_validation.ipynb")


# ---------------------------------------------------------------------------
# 02 -- Factor Engineering
# ---------------------------------------------------------------------------
NB02_SETUP = """\
import warnings, os
import pandas as pd
import numpy as np
warnings.filterwarnings('ignore')

art = pd.read_parquet('../data/processed/panel_artemis_daily.parquet')
uni = pd.read_parquet('../data/processed/universe_monthly.parquet')

art['date'] = pd.to_datetime(art['date'])
uni['date'] = pd.to_datetime(uni['date'])
art = art.sort_values(['symbol', 'date'])

rebalance_dates = sorted(uni['date'].unique())
print(f"Artemis: {art.shape} | Universe: {uni.shape}")
print(f"Rebalance dates: {len(rebalance_dates)}  ({rebalance_dates[0].date()} -> {rebalance_dates[-1].date()})")

def make_wide(df, col):
    return df.pivot_table(index='date', columns='symbol', values=col, aggfunc='last')

price_w = make_wide(art, 'price')
fees_w  = make_wide(art, 'fees')
rev_w   = make_wide(art, 'revenue')
tvl_w   = make_wide(art, 'tvl')
dau_w   = make_wide(art, 'dau')
txns_w  = make_wide(art, 'txns')
mc_w    = make_wide(art, 'mc')
print("Wide tables built.")
"""

NB02_HELPERS = """\
## Helper functions (no lookahead: all slices end at or before rebalance date t)

def last_val(wide, t, cols):
    # Last non-null value on or before date t for each column.
    sub = wide.reindex(columns=cols).loc[:t]
    if len(sub) == 0:
        return pd.Series(np.nan, index=cols)
    return sub.ffill().iloc[-1]


def window_mean(wide, t_end, n_days, cols, min_obs=15):
    # Mean over n_days ending at t_end; NaN if fewer than min_obs non-null.
    t_start = t_end - pd.Timedelta(days=n_days - 1)
    sub = wide.reindex(columns=cols).loc[t_start:t_end]
    cnt = sub.notna().sum()
    m = sub.mean()
    m[cnt < min_obs] = np.nan
    return m


def window_std(wide, t_end, n_days, cols, min_obs=15):
    t_start = t_end - pd.Timedelta(days=n_days - 1)
    sub = wide.reindex(columns=cols).loc[t_start:t_end]
    cnt = sub.notna().sum()
    s = sub.std()
    s[cnt < min_obs] = np.nan
    return s


def realized_vol(pw, t_end, n_days, cols, min_obs=10):
    # Annualised realised vol from log daily returns.
    t_start = t_end - pd.Timedelta(days=n_days - 1)
    sub = pw.reindex(columns=cols).loc[t_start:t_end]
    log_ret = np.log(sub).diff()
    cnt = log_ret.notna().sum()
    s = log_ret.std() * np.sqrt(252)
    s[cnt < min_obs] = np.nan
    return s


def safe_ratio(num, denom):
    d = denom.copy().astype(float)
    d[d == 0] = np.nan
    return num / d
"""

NB02_COMPUTE = """\
## Factor computation loop -- no future data used (all windows end at t)
FACTOR_COLS = [
    'mom_1m', 'mom_3m', 'mom_6m', 'vol_30d',
    'fees_mc', 'rev_mc', 'fees_growth_30d', 'rev_growth_30d',
    'dau_growth_30d', 'txns_growth_30d', 'dau_zscore',
    'tvl_mc', 'tvl_growth_30d',
]

all_records = []

for t in rebalance_dates:
    uni_syms = uni[uni['date'] == t]['symbol'].tolist()
    uni_syms = [s for s in uni_syms if s in price_w.columns]

    # Group A: Momentum
    p_now = last_val(price_w, t, uni_syms)
    p_30  = last_val(price_w, t - pd.Timedelta(30),  uni_syms)
    p_90  = last_val(price_w, t - pd.Timedelta(90),  uni_syms)
    p_180 = last_val(price_w, t - pd.Timedelta(180), uni_syms)

    mom_1m = safe_ratio(p_now, p_30)  - 1
    mom_3m = safe_ratio(p_now, p_90)  - 1
    mom_6m = safe_ratio(p_now, p_180) - 1
    vol_30 = realized_vol(price_w, t, 31, uni_syms, min_obs=10)

    # Group B: Fundamentals
    mc_now = last_val(mc_w, t, uni_syms)

    f_30    = window_mean(fees_w, t,                        30, uni_syms)
    f_lag30 = window_mean(fees_w, t - pd.Timedelta(30),    30, uni_syms)
    fees_mc        = safe_ratio(f_30, mc_now)
    fees_growth_30 = safe_ratio(f_30, f_lag30) - 1

    r_30    = window_mean(rev_w, t,                      30, uni_syms)
    r_lag30 = window_mean(rev_w, t - pd.Timedelta(30),  30, uni_syms)
    rev_mc        = safe_ratio(r_30, mc_now)
    rev_growth_30 = safe_ratio(r_30, r_lag30) - 1

    # Group C: Usage
    d_30    = window_mean(dau_w, t,                      30, uni_syms)
    d_lag30 = window_mean(dau_w, t - pd.Timedelta(30),  30, uni_syms)
    dau_growth_30 = safe_ratio(d_30, d_lag30) - 1

    d_90_mean = window_mean(dau_w, t, 90, uni_syms, min_obs=20)
    d_90_std  = window_std(dau_w,  t, 90, uni_syms, min_obs=20)
    dau_zscore = safe_ratio(d_30 - d_90_mean, d_90_std)

    x_30    = window_mean(txns_w, t,                     30, uni_syms)
    x_lag30 = window_mean(txns_w, t - pd.Timedelta(30), 30, uni_syms)
    txns_growth_30 = safe_ratio(x_30, x_lag30) - 1

    # Group D: TVL
    tv_30    = window_mean(tvl_w, t,                     30, uni_syms)
    tv_lag30 = window_mean(tvl_w, t - pd.Timedelta(30), 30, uni_syms)
    tvl_mc        = safe_ratio(tv_30, mc_now)
    tvl_growth_30 = safe_ratio(tv_30, tv_lag30) - 1

    df_t = pd.DataFrame({
        'symbol': uni_syms, 'date': t,
        'mom_1m':          mom_1m.reindex(uni_syms).values,
        'mom_3m':          mom_3m.reindex(uni_syms).values,
        'mom_6m':          mom_6m.reindex(uni_syms).values,
        'vol_30d':         vol_30.reindex(uni_syms).values,
        'fees_mc':         fees_mc.reindex(uni_syms).values,
        'rev_mc':          rev_mc.reindex(uni_syms).values,
        'fees_growth_30d': fees_growth_30.reindex(uni_syms).values,
        'rev_growth_30d':  rev_growth_30.reindex(uni_syms).values,
        'dau_growth_30d':  dau_growth_30.reindex(uni_syms).values,
        'txns_growth_30d': txns_growth_30.reindex(uni_syms).values,
        'dau_zscore':      dau_zscore.reindex(uni_syms).values,
        'tvl_mc':          tvl_mc.reindex(uni_syms).values,
        'tvl_growth_30d':  tvl_growth_30.reindex(uni_syms).values,
    })
    all_records.append(df_t)

factors_raw = pd.concat(all_records, ignore_index=True)
print(f"Raw factors: {factors_raw.shape}")
print("Null rates (raw):")
print(factors_raw[FACTOR_COLS].isnull().mean().round(3).to_string())
"""

NB02_STD = """\
## Standardization: winsorize at 1/99% -> z-score -> fill NaN = 0

factors_std = factors_raw.copy()

for col in FACTOR_COLS:
    for t, idx in factors_raw.groupby('date').groups.items():
        s = factors_raw.loc[idx, col].astype(float)
        if s.notna().sum() < 3:
            factors_std.loc[idx, col] = 0.0
            continue
        q01, q99 = s.quantile(0.01), s.quantile(0.99)
        s = s.clip(q01, q99)
        mu, sigma = s.mean(), s.std()
        if sigma > 1e-10:
            s = (s - mu) / sigma
        else:
            s = pd.Series(0.0, index=s.index)
        factors_std.loc[idx, col] = s.fillna(0.0).values

print("Standardized factors -- mean / std check (should be ~0 / 1 per date):")
for col in FACTOR_COLS:
    mu  = factors_std.groupby('date')[col].mean().mean()
    sig = factors_std.groupby('date')[col].std().mean()
    print(f"  {col:20s}  mean={mu:+.3f}  std={sig:.3f}")
"""

NB02_SAVE = """\
out_path = '../data/processed/factors_monthly.parquet'
factors_std.to_parquet(out_path, index=False)
print(f"Saved: {out_path}  shape={factors_std.shape}")
print("\\nSample (first rebalance date):")
first_t = factors_std['date'].min()
print(factors_std[factors_std['date'] == first_t][['symbol'] + FACTOR_COLS[:4]].head())
print("\\n>> Factor engineering complete.")
"""

nb02_cells = [
    new_markdown_cell("# 02 -- Factor Engineering\nProduce `factors_monthly.parquet` with standardized cross-sectional factors."),
    new_code_cell(NB02_SETUP),
    new_code_cell(NB02_HELPERS),
    new_code_cell(NB02_COMPUTE),
    new_code_cell(NB02_STD),
    new_code_cell(NB02_SAVE),
]
nb02 = make_nb(nb02_cells)
with open(f"{NB_DIR}/02_factors.ipynb", "w") as f:
    nbformat.write(nb02, f)
print("Written 02_factors.ipynb")


# ---------------------------------------------------------------------------
# 03 -- IC Tests
# ---------------------------------------------------------------------------
NB03_SETUP = """\
import warnings
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy import stats
warnings.filterwarnings('ignore')

factors = pd.read_parquet('../data/processed/factors_monthly.parquet')
art     = pd.read_parquet('../data/processed/panel_artemis_daily.parquet')

factors['date'] = pd.to_datetime(factors['date'])
art['date']     = pd.to_datetime(art['date'])
art = art.sort_values(['symbol', 'date'])

FACTOR_COLS = [
    'mom_1m', 'mom_3m', 'mom_6m', 'vol_30d',
    'fees_mc', 'rev_mc', 'fees_growth_30d', 'rev_growth_30d',
    'dau_growth_30d', 'txns_growth_30d', 'dau_zscore',
    'tvl_mc', 'tvl_growth_30d',
]

price_w = art.pivot_table(index='date', columns='symbol', values='price', aggfunc='last')
rebalance_dates = sorted(factors['date'].unique())
print(f"Factors: {factors.shape}  |  Rebalance dates: {len(rebalance_dates)}")
"""

NB03_FWD = """\
## Compute forward returns (price at t+1 / price at t - 1)
# No lookahead: we use the rebalance date price, which is already in the past
# when the next period starts.

def last_val(wide, t, cols):
    sub = wide.reindex(columns=cols).loc[:t]
    if len(sub) == 0:
        return pd.Series(np.nan, index=cols)
    return sub.ffill().iloc[-1]

fwd_rows = []
for i, t in enumerate(rebalance_dates[:-1]):
    t_next = rebalance_dates[i + 1]
    syms = factors[factors['date'] == t]['symbol'].tolist()
    syms_in = [s for s in syms if s in price_w.columns]
    p_t  = last_val(price_w, t,      syms_in)
    p_t1 = last_val(price_w, t_next, syms_in)
    fwd  = (p_t1 / p_t.replace(0, np.nan)) - 1
    for sym, r in fwd.items():
        fwd_rows.append({'symbol': sym, 'date': t, 'fwd_ret': r})

fwd_df = pd.DataFrame(fwd_rows)
print(f"Forward returns: {fwd_df.shape}  |  NaN rate: {fwd_df['fwd_ret'].isna().mean():.2%}")
print(fwd_df['fwd_ret'].describe().round(3).to_string())
"""

NB03_IC = """\
## Spearman IC per factor
merged = factors.merge(fwd_df, on=['symbol', 'date'], how='inner')

ic_records = []

for factor in FACTOR_COLS:
    ics = []
    for t, grp in merged.groupby('date'):
        valid = grp[[factor, 'fwd_ret']].dropna()
        if len(valid) < 5:
            continue
        ic, _ = stats.spearmanr(valid[factor], valid['fwd_ret'])
        ics.append(ic)

    ics = np.array(ics)
    n = len(ics)
    if n < 2:
        ic_records.append({'Factor': factor, 'Mean IC': np.nan, 'IC Std': np.nan,
                           't-stat': np.nan, 'Hit Rate': np.nan, 'Q5-Q1 Spread': np.nan, 'N': n})
        continue

    mean_ic  = ics.mean()
    std_ic   = ics.std(ddof=1)
    t_stat   = mean_ic / std_ic * np.sqrt(n) if std_ic > 1e-10 else 0.0
    hit_rate = (ics > 0).mean()

    spreads = []
    for t, grp in merged.groupby('date'):
        valid = grp[[factor, 'fwd_ret']].dropna()
        if len(valid) < 10:
            continue
        valid = valid.copy()
        valid['q'] = pd.qcut(valid[factor], 5, labels=False, duplicates='drop')
        q5 = valid[valid['q'] == valid['q'].max()]['fwd_ret'].mean()
        q1 = valid[valid['q'] == valid['q'].min()]['fwd_ret'].mean()
        spreads.append(q5 - q1)
    q5q1 = float(np.mean(spreads)) if spreads else np.nan

    ic_records.append({
        'Factor':       factor,
        'Mean IC':      round(mean_ic, 4),
        'IC Std':       round(std_ic,  4),
        't-stat':       round(t_stat,  2),
        'Hit Rate':     round(hit_rate, 3),
        'Q5-Q1 Spread': round(q5q1, 4) if not np.isnan(q5q1) else np.nan,
        'N':            n,
    })

ic_df = pd.DataFrame(ic_records).sort_values('t-stat', ascending=False)
print("Factor IC Summary:")
print(ic_df.to_string(index=False))
print()
sig = ic_df[ic_df['t-stat'].abs() > 1.0]['Factor'].tolist()
print(f"Factors with |t-stat| > 1.0: {sig}")
"""

NB03_CHART = """\
## IC bar chart for top 4 factors by |t-stat|
top_factors = ic_df.head(4)['Factor'].tolist()

fig, axes = plt.subplots(2, 2, figsize=(12, 7), sharey=True)
axes = axes.flatten()

for ax, factor in zip(axes, top_factors):
    ics, dates = [], []
    for t, grp in merged.groupby('date'):
        valid = grp[[factor, 'fwd_ret']].dropna()
        if len(valid) < 5:
            continue
        ic, _ = stats.spearmanr(valid[factor], valid['fwd_ret'])
        ics.append(ic); dates.append(t)
    ax.bar(dates, ics, color=['steelblue' if ic > 0 else 'tomato' for ic in ics], width=20)
    ax.axhline(0, color='k', lw=0.8)
    ax.set_title(f'{factor}  (mean={float(np.mean(ics)):.3f})')
    ax.set_ylabel('Spearman IC')

plt.suptitle('IC by period -- top 4 factors', fontsize=13)
plt.tight_layout()
plt.savefig('../reports/ic_by_period.png', dpi=100, bbox_inches='tight')
plt.show()
"""

NB03_SAVE = """\
out_path = '../data/processed/factor_ic_results.csv'
ic_df.to_csv(out_path, index=False)
print(f"Saved: {out_path}")
print("\\n>> IC tests complete.")
"""

nb03_cells = [
    new_markdown_cell("# 03 -- IC Tests\nSpearman IC per factor; saves `factor_ic_results.csv`."),
    new_code_cell(NB03_SETUP),
    new_code_cell(NB03_FWD),
    new_code_cell(NB03_IC),
    new_code_cell(NB03_CHART),
    new_code_cell(NB03_SAVE),
]
nb03 = make_nb(nb03_cells)
with open(f"{NB_DIR}/03_ic_tests.ipynb", "w") as f:
    nbformat.write(nb03, f)
print("Written 03_ic_tests.ipynb")


# ---------------------------------------------------------------------------
# 04 -- Network Clusters
# ---------------------------------------------------------------------------
NB04_SETUP = """\
import warnings
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.cluster.hierarchy import linkage, fcluster
from scipy.spatial.distance import squareform
warnings.filterwarnings('ignore')

art = pd.read_parquet('../data/processed/panel_artemis_daily.parquet')
uni = pd.read_parquet('../data/processed/universe_monthly.parquet')

art['date'] = pd.to_datetime(art['date'])
uni['date'] = pd.to_datetime(uni['date'])
art = art.sort_values(['symbol', 'date'])

rebalance_dates = sorted(uni['date'].unique())
price_w = art.pivot_table(index='date', columns='symbol', values='price', aggfunc='last')

def last_val(wide, t, cols):
    sub = wide.reindex(columns=cols).loc[:t]
    if len(sub) == 0:
        return pd.Series(np.nan, index=cols)
    return sub.ffill().iloc[-1]

print(f"Rebalance dates: {len(rebalance_dates)}")
print(f"Price wide shape: {price_w.shape}")
"""

NB04_CLUSTER = """\
## Clustering loop
# At each rebalance date t:
#   1. 60-day return correlation matrix (data up to and including t -- no lookahead)
#   2. Ward hierarchical clustering -> cluster labels
#   3. Within-cluster rank by 30d momentum

MIN_OBS_FRAC = 0.50   # symbol must have >50% non-NaN return obs in 60d window
N_CLUSTERS   = 5

records = []

for t in rebalance_dates:
    uni_syms = uni[uni['date'] == t]['symbol'].tolist()
    uni_syms = [s for s in uni_syms if s in price_w.columns]

    # 60-day return window ending at t
    t_60 = t - pd.Timedelta(days=60)
    price_60 = price_w.reindex(columns=uni_syms).loc[t_60:t]
    ret_60   = price_60.pct_change().iloc[1:]

    valid_cols = ret_60.columns[ret_60.notna().mean() > MIN_OBS_FRAC].tolist()

    # 30d momentum for within-cluster rank
    t_30  = t - pd.Timedelta(days=30)
    p_now = last_val(price_w, t,    uni_syms)
    p_30  = last_val(price_w, t_30, uni_syms)
    mom_30 = (p_now / p_30.replace(0, np.nan) - 1)

    if len(valid_cols) < 4:
        for sym in uni_syms:
            records.append({'symbol': sym, 'date': t,
                            'cluster_id': 0, 'cluster_size': len(uni_syms),
                            'within_cluster_rank': 0.5})
        continue

    # Correlation -> distance -> Ward linkage
    ret_filled = ret_60[valid_cols].fillna(0)
    corr       = ret_filled.corr().clip(-1, 1)
    dist_mat   = np.sqrt(0.5 * (1.0 - corr.values))
    np.fill_diagonal(dist_mat, 0.0)
    dist_cond  = squareform(dist_mat, checks=False)

    Z      = linkage(dist_cond, method='ward')
    k      = min(N_CLUSTERS, len(valid_cols) - 1)
    labels = fcluster(Z, k, criterion='maxclust')
    cmap   = dict(zip(valid_cols, labels.tolist()))

    for sym in uni_syms:
        cid = cmap.get(sym, -1)
        if cid == -1:
            records.append({'symbol': sym, 'date': t,
                            'cluster_id': 0, 'cluster_size': 1,
                            'within_cluster_rank': 0.5})
            continue
        cluster_syms = [s for s, c in cmap.items() if c == cid]
        cluster_rets = mom_30.reindex(cluster_syms).dropna()
        sym_ret = mom_30.get(sym, np.nan)
        if pd.isna(sym_ret) or len(cluster_rets) == 0:
            rank = 0.5
        else:
            rank = float((cluster_rets < sym_ret).sum()) / len(cluster_rets)
        records.append({
            'symbol': sym, 'date': t,
            'cluster_id': int(cid), 'cluster_size': len(cluster_syms),
            'within_cluster_rank': rank,
        })

clusters_df = pd.DataFrame(records)
print(f"Clusters output: {clusters_df.shape}")
print("\\nCluster size distribution:")
print(clusters_df['cluster_size'].value_counts().sort_index().to_string())
print("\\nWithin-cluster rank distribution:")
print(clusters_df['within_cluster_rank'].describe().round(3).to_string())
"""

NB04_CHART = """\
## Plot cluster counts over time
cluster_counts = clusters_df.groupby('date')['cluster_id'].nunique()
fig, ax = plt.subplots(figsize=(10, 3))
ax.bar(cluster_counts.index, cluster_counts.values, width=20, color='steelblue')
ax.set_title('Number of clusters per rebalance date')
ax.set_ylabel('Clusters'); ax.set_xlabel('Date')
plt.tight_layout(); plt.show()
"""

NB04_SAVE = """\
out_path = '../data/processed/network_clusters_monthly.parquet'
clusters_df.to_parquet(out_path, index=False)
print(f"Saved: {out_path}  shape={clusters_df.shape}")
print("\\n>> Network clusters complete.")
"""

nb04_cells = [
    new_markdown_cell("# 04 -- Network Clusters\n60-day rolling correlation -> hierarchical clustering -> within-cluster rank.\nSaves `network_clusters_monthly.parquet`."),
    new_code_cell(NB04_SETUP),
    new_code_cell(NB04_CLUSTER),
    new_code_cell(NB04_CHART),
    new_code_cell(NB04_SAVE),
]
nb04 = make_nb(nb04_cells)
with open(f"{NB_DIR}/04_network_clusters.ipynb", "w") as f:
    nbformat.write(nb04, f)
print("Written 04_network_clusters.ipynb")


# ---------------------------------------------------------------------------
# 05 -- Portfolio Construction
# ---------------------------------------------------------------------------
NB05_SETUP = """\
import warnings
import pandas as pd
import numpy as np
warnings.filterwarnings('ignore')

factors  = pd.read_parquet('../data/processed/factors_monthly.parquet')
ic_df    = pd.read_csv('../data/processed/factor_ic_results.csv')
clusters = pd.read_parquet('../data/processed/network_clusters_monthly.parquet')

factors['date']  = pd.to_datetime(factors['date'])
clusters['date'] = pd.to_datetime(clusters['date'])

FACTOR_COLS  = [
    'mom_1m', 'mom_3m', 'mom_6m', 'vol_30d',
    'fees_mc', 'rev_mc', 'fees_growth_30d', 'rev_growth_30d',
    'dau_growth_30d', 'txns_growth_30d', 'dau_zscore',
    'tvl_mc', 'tvl_growth_30d',
]
MOM_FACTORS  = ['mom_1m', 'mom_3m', 'mom_6m', 'vol_30d']
FUND_FACTORS = [f for f in FACTOR_COLS if f not in MOM_FACTORS]

# Significant factors from NB03: t-stat > 1.0 (positive IC, significant)
# Factors with negative t-stat are excluded from the positive-IC composite;
# they are predictive but their z-score would need to be sign-flipped, which
# we handle instead via explicit vol_30d inversion below.
sig_pos  = ic_df[ic_df['t-stat'] > 1.0]['Factor'].tolist()
sig_mom  = [f for f in MOM_FACTORS  if f in sig_pos]
sig_fund = [f for f in FUND_FACTORS if f in sig_pos]

# For factors with strongly negative IC (|t| > 1.0, mean IC < 0), flip their
# sign so "higher score = better expected return" for the composite.
neg_sig  = ic_df[(ic_df['t-stat'] < -1.0)]['Factor'].tolist()
print(f"Positive-IC significant factors (t>1) : {sig_pos}")
print(f"  Momentum subset                     : {sig_mom}")
print(f"  Fund/usage subset                   : {sig_fund}")
print(f"Negative-IC significant factors (t<-1): {neg_sig}  [sign will be flipped]")
"""

NB05_MERGE = """\
## Merge cluster rank and standardise it cross-sectionally

factors_full = factors.merge(
    clusters[['symbol', 'date', 'within_cluster_rank']],
    on=['symbol', 'date'], how='left'
)
factors_full['within_cluster_rank'] = factors_full['within_cluster_rank'].fillna(0.5)

# Cross-sectional standardize within_cluster_rank (same procedure as factors)
col = 'within_cluster_rank'
for t, idx in factors_full.groupby('date').groups.items():
    s = factors_full.loc[idx, col].astype(float)
    if s.notna().sum() < 3:
        factors_full.loc[idx, col] = 0.0
        continue
    q01, q99 = s.quantile(0.01), s.quantile(0.99)
    s = s.clip(q01, q99)
    mu, sigma = s.mean(), s.std()
    if sigma > 1e-10:
        s = (s - mu) / sigma
    else:
        s = pd.Series(0.0, index=s.index)
    factors_full.loc[idx, col] = s.fillna(0.0).values

print(f"factors_full shape: {factors_full.shape}")
print(f"Columns: {list(factors_full.columns)}")
"""

NB05_WEIGHTS = """\
## Build long/short weights for four variants

N_LONG  = 10   # top quintile of 50-coin universe
N_SHORT = 10   # bottom quintile

# Flip sign of strongly-negative-IC factors so higher score = better return
factors_cs = factors_full.copy()
for f in neg_sig:
    if f in factors_cs.columns:
        factors_cs[f] = -factors_cs[f]

# Fallback to full set (sign-adjusted) when no factor passes the positive-IC threshold
all_sig = sig_pos + neg_sig   # include sign-flipped negatives too
v1_factors = sig_mom  if sig_mom  else MOM_FACTORS
v2_factors = sig_fund if sig_fund else FUND_FACTORS
v3_factors = all_sig  if all_sig  else FACTOR_COLS
v4_factors = v3_factors + ['within_cluster_rank']

VARIANTS = {
    'v1_momentum':     v1_factors,
    'v2_fund_usage':   v2_factors,
    'v3_full':         v3_factors,
    'v4_full_cluster': v4_factors,
}

print("Variant factor sets (negative-IC factors sign-flipped):")
for k, v in VARIANTS.items():
    print(f"  {k:20s}: {v}")

all_weights = []

for variant, sel_factors in VARIANTS.items():
    for t, grp in factors_cs.groupby('date'):
        grp = grp.reset_index(drop=True)
        available = [f for f in sel_factors if f in grp.columns]
        composite = grp[available].mean(axis=1) if available else pd.Series(0.0, index=grp.index)
        composite.index = grp['symbol'].values

        long_syms  = composite.nlargest(N_LONG).index.tolist()
        short_syms = composite.nsmallest(N_SHORT).index.tolist()

        for sym in grp['symbol']:
            if sym in long_syms:
                w = 1.0 / N_LONG
            elif sym in short_syms:
                w = -1.0 / N_SHORT
            else:
                w = 0.0
            all_weights.append({'symbol': sym, 'date': t, 'weight': w, 'variant': variant})

weights_df = pd.DataFrame(all_weights)
print(f"\\nWeights shape: {weights_df.shape}")

# Turnover estimate
print("\\nAverage monthly turnover per variant (fraction of portfolio that changes):")
for variant in VARIANTS:
    v_df = weights_df[weights_df['variant'] == variant].pivot_table(
        index='date', columns='symbol', values='weight', fill_value=0)
    turnovers = v_df.diff().abs().sum(axis=1) / 2
    print(f"  {variant:22s}: {turnovers.mean():.2f}")
"""

NB05_SAVE = """\
out_path = '../data/processed/portfolio_weights_monthly.parquet'
weights_df.to_parquet(out_path, index=False)
print(f"Saved: {out_path}  shape={weights_df.shape}")
print("\\n>> Portfolio construction complete.")
"""

nb05_cells = [
    new_markdown_cell("# 05 -- Portfolio Construction\nComposite alpha from IC-significant factors -> four long/short variants.\nSaves `portfolio_weights_monthly.parquet`."),
    new_code_cell(NB05_SETUP),
    new_code_cell(NB05_MERGE),
    new_code_cell(NB05_WEIGHTS),
    new_code_cell(NB05_SAVE),
]
nb05 = make_nb(nb05_cells)
with open(f"{NB_DIR}/05_portfolio.ipynb", "w") as f:
    nbformat.write(nb05, f)
print("Written 05_portfolio.ipynb")


# ---------------------------------------------------------------------------
# 06 -- Backtest
# ---------------------------------------------------------------------------
NB06_SETUP = """\
import warnings
import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
warnings.filterwarnings('ignore')
os.makedirs('../reports', exist_ok=True)

weights = pd.read_parquet('../data/processed/portfolio_weights_monthly.parquet')
art     = pd.read_parquet('../data/processed/panel_artemis_daily.parquet')
uni     = pd.read_parquet('../data/processed/universe_monthly.parquet')

for df in [weights, art, uni]:
    df['date'] = pd.to_datetime(df['date'])

art = art.sort_values(['symbol', 'date'])
price_w = art.pivot_table(index='date', columns='symbol', values='price', aggfunc='last')
mc_w    = art.pivot_table(index='date', columns='symbol', values='mc',    aggfunc='last')

rebalance_dates = sorted(uni['date'].unique())
variants        = sorted(weights['variant'].unique().tolist())
print(f"Variants: {variants}")
print(f"Rebalance dates: {len(rebalance_dates)}")

def last_val(wide, t, cols):
    sub = wide.reindex(columns=cols).loc[:t]
    if len(sub) == 0:
        return pd.Series(np.nan, index=cols)
    return sub.ffill().iloc[-1]
"""

NB06_FWD = """\
## Forward returns for all symbols and benchmarks

all_syms = sorted(weights['symbol'].unique())
fwd_map  = {}   # t -> Series(symbol -> fwd_ret)

for i, t in enumerate(rebalance_dates[:-1]):
    t_next = rebalance_dates[i + 1]
    syms   = [s for s in all_syms if s in price_w.columns]
    p_t    = last_val(price_w, t,      syms)
    p_t1   = last_val(price_w, t_next, syms)
    fwd_map[t] = (p_t1 / p_t.replace(0, np.nan)) - 1

# BTC benchmark
btc_rets = {}
for i, t in enumerate(rebalance_dates[:-1]):
    t_next = rebalance_dates[i + 1]
    if 'BTC' in price_w.columns:
        p_t  = last_val(price_w, t,      ['BTC']).iloc[0]
        p_t1 = last_val(price_w, t_next, ['BTC']).iloc[0]
        btc_rets[t] = float((p_t1 / p_t) - 1) if (pd.notna(p_t) and p_t > 0) else np.nan
    else:
        btc_rets[t] = np.nan

# Equal-weight top-50 benchmark
ew_rets = {}
for i, t in enumerate(rebalance_dates[:-1]):
    t_next   = rebalance_dates[i + 1]
    uni_syms = [s for s in uni[uni['date'] == t]['symbol'].tolist() if s in price_w.columns]
    p_t  = last_val(price_w, t,      uni_syms)
    p_t1 = last_val(price_w, t_next, uni_syms)
    ret  = (p_t1 / p_t.replace(0, np.nan)) - 1
    ew_rets[t] = float(ret.mean())

print("BTC sample:", {str(k.date()): round(v, 3) for k, v in list(btc_rets.items())[:4]})
print("EW  sample:", {str(k.date()): round(v, 3) for k, v in list(ew_rets.items())[:4]})
"""

NB06_COMPUTE = """\
## Portfolio return computation

def compute_returns(weights_df, fwd_map, cost_bps=0, lag_periods=0,
                    exclude_top_n_mcap=0):
    port_rets = {}
    # Sorted weight dates for lag lookup
    all_dates = sorted(weights_df['date'].unique().tolist())
    date_to_idx = {d: i for i, d in enumerate(all_dates)}

    for variant in weights_df['variant'].unique():
        v_df = weights_df[weights_df['variant'] == variant].copy()
        monthly_rets = []
        prev_weights = None

        for i, t in enumerate(rebalance_dates[:-1]):
            fwd = fwd_map.get(t)
            if fwd is None:
                continue

            # For lag stress test: use weights from lag_periods earlier rebalance
            # (simulates data delay -- avoids any look-ahead)
            if lag_periods > 0 and t in date_to_idx:
                w_idx  = max(0, date_to_idx[t] - lag_periods)
                w_date = all_dates[w_idx]
            else:
                w_date = t

            w_t = v_df[v_df['date'] == w_date].set_index('symbol')['weight'].copy()

            if exclude_top_n_mcap > 0:
                mc_t     = last_val(mc_w, t, w_t.index.tolist())
                top_syms = mc_t.nlargest(exclude_top_n_mcap).index.tolist()
                w_t      = w_t.drop(labels=top_syms, errors='ignore')
                longs    = w_t[w_t > 0]
                shorts   = w_t[w_t < 0]
                if len(longs):  w_t[longs.index]  = longs  / longs.sum()
                if len(shorts): w_t[shorts.index]  = shorts / shorts.abs().sum() * -1

            if len(w_t) == 0:
                monthly_rets.append(0.0)
                continue

            # Transaction cost: one-way cost on turnover
            cost = 0.0
            if cost_bps > 0 and prev_weights is not None:
                prev     = prev_weights.reindex(w_t.index).fillna(0)
                turnover = (w_t - prev).abs().sum() / 2
                cost     = turnover * cost_bps / 10_000

            fwd_a = fwd.reindex(w_t.index).fillna(0)
            ret   = float((w_t * fwd_a).sum()) - cost
            monthly_rets.append(ret)
            prev_weights = w_t

        n = len(monthly_rets)
        port_rets[variant] = pd.Series(
            monthly_rets, index=rebalance_dates[:n])

    return port_rets

base_rets = compute_returns(weights, fwd_map)
print("Base portfolio returns computed:")
for v, r in sorted(base_rets.items()):
    print(f"  {v}: n={len(r)}, mean={r.mean():.4f}, std={r.std():.4f}")
"""

NB06_METRICS = """\
## Performance metrics

def metrics(rets_series, periods_per_year=12):
    r = rets_series.dropna()
    if len(r) < 2:
        return {k: np.nan for k in ['CAGR', 'Ann Vol', 'Sharpe', 'Max DD', 'Hit Rate', 'N']}
    cagr  = (1 + r).prod() ** (periods_per_year / len(r)) - 1
    vol   = r.std() * np.sqrt(periods_per_year)
    sr    = cagr / vol if vol > 1e-10 else np.nan
    cum   = (1 + r).cumprod()
    maxdd = (cum / cum.cummax() - 1).min()
    hit   = (r > 0).mean()
    return {'CAGR': cagr, 'Ann Vol': vol, 'Sharpe': sr,
            'Max DD': maxdd, 'Hit Rate': hit, 'N': len(r)}

btc_s = pd.Series(btc_rets).dropna()
ew_s  = pd.Series(ew_rets).dropna()

rows = []
for v, r in sorted(base_rets.items()):
    m = metrics(r); m['Strategy'] = v; rows.append(m)
for name, s in [('BTC buy-hold', btc_s), ('EW top-50', ew_s)]:
    m = metrics(s); m['Strategy'] = name; rows.append(m)

perf = pd.DataFrame(rows).set_index('Strategy')

def fmt(df):
    d = df.copy()
    for col in ['CAGR', 'Ann Vol', 'Max DD']:
        d[col] = d[col].map(lambda x: f"{x:.1%}" if pd.notna(x) else 'n/a')
    d['Sharpe']   = d['Sharpe'].map(lambda x: f"{x:.2f}" if pd.notna(x) else 'n/a')
    d['Hit Rate'] = d['Hit Rate'].map(lambda x: f"{x:.1%}" if pd.notna(x) else 'n/a')
    d['N']        = d['N'].astype(int)
    return d

print("\\n=== Base Performance Metrics ===")
print(fmt(perf)[['CAGR', 'Ann Vol', 'Sharpe', 'Max DD', 'Hit Rate', 'N']].to_string())
"""

NB06_CHART = """\
## Cumulative return chart
colors = plt.cm.tab10.colors

# Align all series to the same date index
date_idx = list(base_rets.values())[0].index

fig, ax = plt.subplots(figsize=(12, 6))
for (v, r), col in zip(sorted(base_rets.items()), colors[:4]):
    cum = (1 + r).cumprod()
    ax.plot(cum.index, cum.values, label=v, lw=1.8, color=col)

cum_btc = (1 + btc_s.reindex(date_idx).fillna(0)).cumprod()
cum_ew  = (1 + ew_s.reindex(date_idx).fillna(0)).cumprod()
ax.plot(cum_btc.index, cum_btc.values, label='BTC buy-hold', lw=1.5, ls='--', color='orange')
ax.plot(cum_ew.index,  cum_ew.values,  label='EW top-50',    lw=1.5, ls='--', color='grey')

ax.set_title('Cumulative Returns -- Strategy Variants vs Benchmarks', fontsize=13)
ax.set_ylabel('Cumulative return (1 = start)')
ax.legend(fontsize=9); ax.grid(alpha=0.3)
ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
plt.tight_layout()
plt.savefig('../reports/cumulative_returns.png', dpi=120, bbox_inches='tight')
plt.show()
print("Saved: reports/cumulative_returns.png")
"""

NB06_ROLL = """\
## Rolling 12-month Sharpe
fig, ax = plt.subplots(figsize=(12, 4))
for (v, r), col in zip(sorted(base_rets.items()), colors[:4]):
    roll_sr = r.rolling(12).apply(
        lambda x: x.mean() / x.std() * np.sqrt(12) if x.std() > 1e-10 else 0.0)
    ax.plot(roll_sr.index, roll_sr.values, label=v, lw=1.5, color=col)
ax.axhline(0, color='k', lw=0.8)
ax.set_title('Rolling 12-month Sharpe ratio'); ax.set_ylabel('Sharpe')
ax.legend(fontsize=9); ax.grid(alpha=0.3)
plt.tight_layout(); plt.show()

## Annual return table
print("\\n=== Annual Returns ===")
ann_rows = {}
for v, r in sorted(base_rets.items()):
    ann_rows[v] = r.groupby(r.index.year).apply(lambda x: (1 + x).prod() - 1)
for name, s in [('BTC', btc_s), ('EW top-50', ew_s)]:
    ann_rows[name] = s.groupby(s.index.year).apply(lambda x: (1 + x).prod() - 1)
annual_df = pd.DataFrame(ann_rows).T
print(annual_df.map(lambda x: f"{x:.1%}" if pd.notna(x) else 'n/a').to_string())
"""

NB06_STRESS = """\
## Stress tests

# (a) Lag signals by 1 period (~1 month) to simulate 3-day fundamental data delay
lag_rets  = compute_returns(weights, fwd_map, lag_periods=1)

# (b) 10 bps one-way transaction cost
cost_rets = compute_returns(weights, fwd_map, cost_bps=10)

# (c) Exclude top-5 coins by market cap
excl_rets = compute_returns(weights, fwd_map, exclude_top_n_mcap=5)

scenarios = {
    'Base':            base_rets,
    'Lag signals 1m':  lag_rets,
    '+10bps cost':     cost_rets,
    'Excl top-5 mc':   excl_rets,
}

print("\\n=== Stress Tests -- v3_full composite ===")
stress_rows = []
for scenario, rd in scenarios.items():
    r = rd.get('v3_full', pd.Series(dtype=float))
    m = metrics(r); m['Scenario'] = scenario; stress_rows.append(m)

stress_df = pd.DataFrame(stress_rows).set_index('Scenario')
print(fmt(stress_df)[['CAGR', 'Ann Vol', 'Sharpe', 'Max DD', 'Hit Rate']].to_string())
"""

NB06_REGIME = """\
## BTC regime analysis (loose = BTC 90d return > 0, tight = <=0)
print("\\n=== BTC Regime Analysis -- v3_full ===")
v3 = base_rets.get('v3_full', pd.Series(dtype=float))

btc_price_s = None
if 'BTC' in art['symbol'].values:
    btc_price_s = art[art['symbol'] == 'BTC'].set_index('date')['price']

regime = {'Loose (BTC 90d>0)': [], 'Tight (BTC 90d<=0)': []}
for t, r in v3.items():
    key = 'Loose (BTC 90d>0)'
    if btc_price_s is not None:
        t_90     = t - pd.Timedelta(days=90)
        btc_now  = btc_price_s.loc[:t].iloc[-1]  if len(btc_price_s.loc[:t])  else np.nan
        btc_90   = btc_price_s.loc[:t_90].iloc[-1] if len(btc_price_s.loc[:t_90]) else np.nan
        if pd.notna(btc_now) and pd.notna(btc_90) and btc_90 > 0:
            key = 'Loose (BTC 90d>0)' if (btc_now / btc_90 - 1) > 0 else 'Tight (BTC 90d<=0)'
    regime[key].append(r)

for key, rets in regime.items():
    if rets:
        s  = pd.Series(rets)
        sr = s.mean() / s.std() * np.sqrt(12) if s.std() > 0 else np.nan
        print(f"  {key}: n={len(s)}, mean ret={s.mean():.2%}, Sharpe={sr:.2f}")
"""

NB06_FINAL = """\
## Final summary
print("\\n" + "="*70)
print("FINAL PERFORMANCE SUMMARY")
print("="*70)
print(fmt(perf)[['CAGR', 'Ann Vol', 'Sharpe', 'Max DD', 'Hit Rate']].to_string())
print("\\n>> Backtest complete.")
"""

nb06_cells = [
    new_markdown_cell("# 06 -- Backtest\nCAGR / Sharpe / drawdown per variant; benchmark comparison; stress tests."),
    new_code_cell(NB06_SETUP),
    new_code_cell(NB06_FWD),
    new_code_cell(NB06_COMPUTE),
    new_code_cell(NB06_METRICS),
    new_code_cell(NB06_CHART),
    new_code_cell(NB06_ROLL),
    new_code_cell(NB06_STRESS),
    new_code_cell(NB06_REGIME),
    new_code_cell(NB06_FINAL),
]
nb06 = make_nb(nb06_cells)
with open(f"{NB_DIR}/06_backtest.ipynb", "w") as f:
    nbformat.write(nb06, f)
print("Written 06_backtest.ipynb")

print("\nAll six notebooks generated successfully.")
