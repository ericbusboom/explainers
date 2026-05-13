"""S&P 500 dollar-cost-averaging cohort analysis — model and plotting code.

Used by sp500_dca.ipynb. Loads historical annual S&P 500 total returns and
CPI inflation (Damodaran's "Historical Returns" dataset, FRED-sourced CPI),
runs a per-cohort DCA simulation, and plots final real net worth by
starting year.

Each cohort contributes $1,000 of real (constant) purchasing power per
year for N years, beginning at the start of their first career year.
Contributions earn the S&P 500 total return that year and every subsequent
career year. Final net worth is reported in real (constant-dollar) terms,
which is equivalent to compounding the real return r_real = (1+r_nom)/(1+infl)-1
on each contribution.
"""
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

DATA_PATH = Path(__file__).parent / 'historical_returns.csv'
INCOME_PATH = Path(__file__).parent / 'median_household_income.csv'
REAL_CONTRIBUTION = 1_000.0


def load_returns(path: Path = DATA_PATH) -> pd.DataFrame:
    df = pd.read_csv(path)
    return df.set_index('year')


def load_median_hh_income(path: Path = INCOME_PATH) -> pd.Series:
    """Real median household income, annual, in approximate 2025 dollars.

    Spliced series: FRED MEHOINUSA672N (real median household income, 2023
    CPI-U-RS dollars) for 1984+; FRED MEFAINUSA672N (real median family
    income) scaled by HH/Fam ratio at 1984 (~0.848) for 1953–1983; held
    flat at the 1953 value for 1950–1952. Inflated by ~5.7% to roll forward
    from 2023 CPI-U-RS to 2025 CPI dollars for headline consistency.
    """
    df = pd.read_csv(path)
    return df.set_index('year')['real_median_hh_income']


def final_real_net_worth(returns: pd.DataFrame, start_year: int, n_years: int,
                         contribution: float = REAL_CONTRIBUTION) -> float:
    """Final real net worth after `n_years` of $contribution real per year
    invested at the start of each career year.

    Contribution k (k=0..n_years-1) is made at start of year start_year+k and
    earns the real return for that year and every subsequent career year.
    """
    r = returns.loc[start_year:start_year + n_years - 1, 'real_return'].to_numpy()
    if len(r) != n_years:
        raise ValueError(f'Missing returns for {start_year}+{n_years}: have {len(r)}')
    total = 0.0
    for k in range(n_years):
        total += contribution * np.prod(1.0 + r[k:])
    return total


def final_real_net_worth_variable(returns: pd.DataFrame, contributions: pd.Series,
                                  start_year: int, n_years: int) -> float:
    """Like final_real_net_worth, but each year's real contribution comes from
    `contributions[start_year + k]` (k=0..n_years-1). `contributions` must
    cover all years in [start_year, start_year + n_years - 1]."""
    r = returns.loc[start_year:start_year + n_years - 1, 'real_return'].to_numpy()
    c = contributions.loc[start_year:start_year + n_years - 1].to_numpy()
    if len(r) != n_years or len(c) != n_years:
        raise ValueError(
            f'Missing data for {start_year}+{n_years}: '
            f'returns={len(r)}, contributions={len(c)}'
        )
    total = 0.0
    for k in range(n_years):
        total += c[k] * np.prod(1.0 + r[k:])
    return total


def cohort_table_variable(returns: pd.DataFrame, contributions: pd.Series,
                          start_years, n_years: int) -> pd.DataFrame:
    """Cohort table for a variable per-year real contribution stream."""
    rows = []
    for y in start_years:
        nw = final_real_net_worth_variable(returns, contributions, y, n_years)
        total_contrib = float(contributions.loc[y:y + n_years - 1].sum())
        r = returns.loc[y:y + n_years - 1, 'real_return'].to_numpy()
        cagr_real = float(np.prod(1.0 + r)) ** (1.0 / n_years) - 1.0
        rows.append({
            'start_year': y,
            'end_year': y + n_years - 1,
            'total_real_contributed': total_contrib,
            'final_real_net_worth': nw,
            'multiple_of_contributed': nw / total_contrib,
            'real_cagr': cagr_real,
        })
    return pd.DataFrame(rows)


def cohort_table(returns: pd.DataFrame, start_years, n_years: int,
                 contribution: float = REAL_CONTRIBUTION) -> pd.DataFrame:
    rows = []
    total_contributed = contribution * n_years
    for y in start_years:
        nw = final_real_net_worth(returns, y, n_years, contribution)
        # Geometric mean real return over the career
        r = returns.loc[y:y + n_years - 1, 'real_return'].to_numpy()
        cagr_real = float(np.prod(1.0 + r)) ** (1.0 / n_years) - 1.0
        rows.append({
            'start_year': y,
            'end_year': y + n_years - 1,
            'final_real_net_worth': nw,
            'multiple_of_contributed': nw / total_contributed,
            'real_cagr': cagr_real,
        })
    return pd.DataFrame(rows)


def plot_cohorts(table: pd.DataFrame, n_years: int, title: str = None, ax=None):
    if ax is None:
        fig, ax = plt.subplots(figsize=(11, 5))
    ax.bar(table['start_year'], table['final_real_net_worth'] / 1000, color='steelblue')
    ax.set_xlabel('Starting year of career')
    ax.set_ylabel(f'Final real net worth (2025 $, thousands)')
    if title is None:
        title = (f'{n_years}-year DCA into S&P 500: final real net worth by starting year '
                 f'(\\$1,000 real / year)')
    ax.set_title(title)
    contributed_k = REAL_CONTRIBUTION * n_years / 1000
    ax.axhline(contributed_k, color='black', linestyle='--', linewidth=1,
               label=f'Total contributed = \\${contributed_k:,.0f}k real')
    ax.legend(loc='upper left')
    ax.grid(axis='y', alpha=0.3)
    return ax


def plot_multiple(table: pd.DataFrame, n_years: int, ax=None):
    if ax is None:
        fig, ax = plt.subplots(figsize=(11, 4))
    ax.bar(table['start_year'], table['multiple_of_contributed'], color='darkorange')
    ax.axhline(1.0, color='black', linestyle='--', linewidth=1, label='Break-even (1.0x)')
    ax.set_xlabel('Starting year of career')
    ax.set_ylabel('Final real / total real contributed')
    ax.set_title(f'{n_years}-year DCA: real wealth multiple by starting year')
    ax.legend(loc='upper left')
    ax.grid(axis='y', alpha=0.3)
    return ax


def plot_cohorts_variable(table: pd.DataFrame, n_years: int, title: str, ax=None):
    """Bar plot of final real net worth with a second bar showing total real
    contributed (so the gap above contributions is the real investment gain)."""
    if ax is None:
        fig, ax = plt.subplots(figsize=(11, 5))
    ax.bar(table['start_year'], table['final_real_net_worth'] / 1000,
           color='steelblue', label='Final real net worth')
    ax.plot(table['start_year'], table['total_real_contributed'] / 1000,
            color='black', linewidth=1.5, linestyle='--',
            label='Total contributed (real, varies by cohort)')
    ax.set_xlabel('Starting year of career')
    ax.set_ylabel('Real $ (2025), thousands')
    ax.set_title(title)
    ax.legend(loc='upper left')
    ax.grid(axis='y', alpha=0.3)
    return ax


def plot_cagr(table: pd.DataFrame, n_years: int, ax=None):
    if ax is None:
        fig, ax = plt.subplots(figsize=(11, 4))
    colors = ['darkgreen' if x >= 0 else 'firebrick' for x in table['real_cagr']]
    ax.bar(table['start_year'], table['real_cagr'] * 100, color=colors)
    ax.axhline(0.0, color='black', linewidth=0.8)
    ax.set_xlabel('Starting year of career')
    ax.set_ylabel('Geometric mean real return (%/yr)')
    ax.set_title(f'{n_years}-year real CAGR of the S&P 500 by starting year')
    ax.grid(axis='y', alpha=0.3)
    return ax
