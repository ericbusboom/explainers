"""Buy, borrow, die — model and plotting code.

Used by buy_borrow_die.ipynb. All inputs are bundled into a Scenario dataclass;
all results are returned as plain dicts so the notebook can format them itself.

Three financing paths for the same target consumption (a "$expenditure"
spend today, lump sum):
- Scenario A: sell stock upfront, pay capital-gains tax now, hold residual
  until death `years_to_death` years later.
- Scenario B: borrow `expenditure` and amortize the loan over `loan_term`
  years by selling small chunks of stock each year. Hold any residual stock
  until death.
- Scenario C: borrow `expenditure` interest-only; sell stock annually only
  to fund the interest. Die at `years_to_death` with the loan outstanding;
  the estate sells stock at stepped-up basis to repay the loan, then pays
  estate tax on the remainder.

Defaults match 2026 federal numbers:
- LTCG: 20% + 3.8% NIIT = 23.8% for high earners.
- Estate tax: 40% above $15M individual / $30M MFJ (OBBBA-permanent).
- SBLOC rate: ~5.5% (SOFR ~4.5% + ~100 bps).
- Lender ordinary income on interest: 30% blended.
"""
from dataclasses import dataclass
from typing import Dict

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


# --- Defaults (2026) -----------------------------------------------------
LTCG_RATE          = 0.238
LENDER_INCOME_RATE = 0.30
ESTATE_TAX_RATE    = 0.40
ESTATE_EXEMPTION   = 30_000_000   # MFJ with portability
SBLOC_RATE         = 0.055
STOCK_GROWTH       = 0.07
RETIREMENT_AGE     = 65


@dataclass
class Scenario:
    expenditure:        float           # dollars spent today
    starting_stock:     float           # total stock position today
    starting_basis:     float           # cost basis of that position
    years_to_death:     int   = 25      # age 65 -> 90 by default
    loan_term:          int   = 10      # Scenario B amortization horizon

    sbloc_rate:         float = SBLOC_RATE
    stock_growth:       float = STOCK_GROWTH
    ltcg_rate:          float = LTCG_RATE
    lender_income_rate: float = LENDER_INCOME_RATE
    estate_tax_rate:    float = ESTATE_TAX_RATE
    estate_exemption:   float = ESTATE_EXEMPTION

    @property
    def basis_ratio_0(self) -> float:
        return self.starting_basis / self.starting_stock


# --- Helpers -------------------------------------------------------------
def amortizing_payment(principal: float, rate: float, n: int) -> float:
    return principal * rate / (1 - (1 + rate) ** -n)


def estate_tax(gross_estate: float, outstanding_loan: float,
               exemption: float, rate: float) -> float:
    return rate * max(0.0, gross_estate - outstanding_loan - exemption)


# --- Scenarios -----------------------------------------------------------
def run_A(s: Scenario) -> Dict:
    """Sell upfront, hold residual until death."""
    br0 = s.basis_ratio_0
    sale = s.expenditure / (1 - s.ltcg_rate * (1 - br0))
    gain = sale * (1 - br0)
    cgt  = s.ltcg_rate * gain
    stock_after_sale = s.starting_stock - sale
    stock_at_death   = stock_after_sale * (1 + s.stock_growth) ** s.years_to_death
    et = estate_tax(stock_at_death, 0.0, s.estate_exemption, s.estate_tax_rate)

    traj = np.array(
        [stock_after_sale * (1 + s.stock_growth) ** y for y in range(s.years_to_death + 1)]
    )

    return {
        'label':         'A. Sell upfront, die',
        'borrower_cgt':  cgt,
        'lender_tax':    0.0,
        'estate_tax':    et,
        'interest_paid': 0.0,
        'total_fed':     cgt + et,
        'heirs':         stock_at_death - et,
        'stock_sold':    sale,
        'stock_at_death': stock_at_death,
        'trajectory':    traj,
    }


def run_B(s: Scenario) -> Dict:
    """Borrow + amortize over `loan_term` years, then hold residual to death."""
    payment      = amortizing_payment(s.expenditure, s.sbloc_rate, s.loan_term)
    loan_balance = s.expenditure
    stock_value  = s.starting_stock
    stock_basis  = s.starting_basis

    rows = []
    # Phase 1: amortize. Sell stock each year to net `payment` after CGT.
    for year in range(1, s.loan_term + 1):
        stock_value *= (1 + s.stock_growth)
        basis_ratio = stock_basis / stock_value
        interest = loan_balance * s.sbloc_rate
        principal_paid = payment - interest

        sale = payment / (1 - s.ltcg_rate * (1 - basis_ratio))
        gain = sale * (1 - basis_ratio)
        bcgt = s.ltcg_rate * gain

        fraction = sale / stock_value
        stock_value -= sale
        stock_basis *= (1 - fraction)

        lender_tax = s.lender_income_rate * interest
        loan_balance -= principal_paid

        rows.append(dict(
            year=year, phase='amortize',
            stock=stock_value, loan_balance=loan_balance,
            interest=interest, principal_paid=principal_paid, payment=payment,
            stock_sold=sale, gain=gain, basis_ratio=basis_ratio,
            borrower_tax=bcgt, lender_tax=lender_tax,
        ))

    # Phase 2: hold. No more sales; stock just appreciates until death.
    for year in range(s.loan_term + 1, s.years_to_death + 1):
        stock_value *= (1 + s.stock_growth)
        rows.append(dict(
            year=year, phase='hold',
            stock=stock_value, loan_balance=0.0,
            interest=0.0, principal_paid=0.0, payment=0.0,
            stock_sold=0.0, gain=0.0, basis_ratio=stock_basis / stock_value,
            borrower_tax=0.0, lender_tax=0.0,
        ))

    df = pd.DataFrame(rows)
    stock_at_death = float(df['stock'].iloc[-1])
    et = estate_tax(stock_at_death, 0.0, s.estate_exemption, s.estate_tax_rate)

    return {
        'label':         'B. Borrow & amortize, die',
        'borrower_cgt':  float(df['borrower_tax'].sum()),
        'lender_tax':    float(df['lender_tax'].sum()),
        'estate_tax':    et,
        'interest_paid': float(df['interest'].sum()),
        'total_fed':     float(df['borrower_tax'].sum() + df['lender_tax'].sum()) + et,
        'heirs':         stock_at_death - et,
        'annual_payment': payment,
        'stock_at_death': stock_at_death,
        'df':            df,
        'trajectory':    np.concatenate([[s.starting_stock], df['stock'].values]),
    }


def run_C(s: Scenario) -> Dict:
    """Borrow interest-only, fund interest with annual stock sales, die at horizon."""
    stock_value = s.starting_stock
    stock_basis = s.starting_basis

    rows = []
    for year in range(1, s.years_to_death + 1):
        stock_value *= (1 + s.stock_growth)
        basis_ratio = stock_basis / stock_value
        interest = s.expenditure * s.sbloc_rate          # balance stays flat
        sale = interest / (1 - s.ltcg_rate * (1 - basis_ratio))
        gain = sale * (1 - basis_ratio)
        bcgt = s.ltcg_rate * gain

        fraction = sale / stock_value
        stock_value -= sale
        stock_basis *= (1 - fraction)
        lender_tax = s.lender_income_rate * interest

        rows.append(dict(
            year=year, stock=stock_value, basis_ratio=basis_ratio,
            interest=interest, stock_sold=sale, gain=gain,
            borrower_tax=bcgt, lender_tax=lender_tax,
        ))

    df = pd.DataFrame(rows)
    stock_at_death = float(df['stock'].iloc[-1])
    # Outstanding loan is deductible from the gross estate before estate tax.
    et = estate_tax(stock_at_death, s.expenditure, s.estate_exemption, s.estate_tax_rate)
    # Estate then sells `expenditure` of stock at stepped-up basis (zero CGT) to repay loan.
    heirs = stock_at_death - s.expenditure - et

    return {
        'label':         'C. Borrow, die at horizon',
        'borrower_cgt':  float(df['borrower_tax'].sum()),
        'lender_tax':    float(df['lender_tax'].sum()),
        'estate_tax':    et,
        'interest_paid': float(df['interest'].sum()),
        'total_fed':     float(df['borrower_tax'].sum() + df['lender_tax'].sum()) + et,
        'heirs':         heirs,
        'stock_at_death': stock_at_death,
        'df':            df,
        'trajectory':    np.concatenate([[s.starting_stock], df['stock'].values]),
    }


def run_all(s: Scenario) -> Dict[str, Dict]:
    return {'A': run_A(s), 'B': run_B(s), 'C': run_C(s)}


# --- Tables --------------------------------------------------------------
def comparison_table(results: Dict[str, Dict]) -> pd.DataFrame:
    """Build a string-formatted DataFrame summarizing the three scenarios."""
    rows = []
    for k in ('A', 'B', 'C'):
        r = results[k]
        rows.append({
            'Scenario':           r['label'],
            'Borrower CGT':       r['borrower_cgt'],
            'Lender income tax':  r['lender_tax'],
            'Estate tax':         r['estate_tax'],
            'Total fed revenue':  r['total_fed'],
            'Interest paid':      r['interest_paid'],
            'Net to heirs':       r['heirs'],
        })
    df = pd.DataFrame(rows)
    for c in df.columns:
        if c != 'Scenario':
            df[c] = df[c].map(lambda x: f'${x:>14,.0f}')
    return df


# --- Plots ---------------------------------------------------------------
_SCENARIO_LABELS = ['A. Sell upfront', 'B. Borrow & amortize', 'C. Borrow & die']


def plot_revenue_stack(results: Dict[str, Dict], s: Scenario, title_suffix: str = ''):
    """Stacked bar of federal revenue components per scenario."""
    cgt    = np.array([results[k]['borrower_cgt'] for k in 'ABC']) / 1e6
    lender = np.array([results[k]['lender_tax']   for k in 'ABC']) / 1e6
    estate = np.array([results[k]['estate_tax']   for k in 'ABC']) / 1e6
    totals = cgt + lender + estate

    fig, ax = plt.subplots(figsize=(10, 6))
    x = np.arange(3)
    ax.bar(x, cgt,    color='#185FA5', label='Borrower capital-gains tax',
           edgecolor='black', linewidth=0.5)
    ax.bar(x, lender, bottom=cgt, color='#ff7f0e',
           label='Lender tax on interest', edgecolor='black', linewidth=0.5)
    ax.bar(x, estate, bottom=cgt + lender, color='#993C1D',
           label=f'Federal estate tax (40% above ${s.estate_exemption/1e6:.0f}M)',
           edgecolor='black', linewidth=0.5)

    for i, t in enumerate(totals):
        ax.text(i, t + max(totals)*0.02, f'${t:,.1f}M',
                ha='center', va='bottom', fontsize=11, fontweight='bold')

    ax.set_xticks(x)
    ax.set_xticklabels(_SCENARIO_LABELS)
    ax.set_ylabel('$M')
    title = (f'Federal tax revenue over {s.years_to_death} years '
             f'(\\${s.expenditure/1e6:.0f}M expenditure, \\${s.starting_stock/1e6:.0f}M start)')
    if title_suffix:
        title += f' — {title_suffix}'
    ax.set_title(title)
    ax.set_ylim(0, max(totals) * 1.25)
    ax.legend(loc='upper left', framealpha=0.95)
    plt.tight_layout()
    return fig


def plot_heirs(results: Dict[str, Dict], s: Scenario, title_suffix: str = ''):
    heirs = np.array([results[k]['heirs'] for k in 'ABC']) / 1e6
    fig, ax = plt.subplots()
    colors = ['#185FA5', '#ff7f0e', '#2ca02c']
    bars = ax.bar(_SCENARIO_LABELS, heirs, color=colors,
                  edgecolor='black', linewidth=0.5)
    for b, v in zip(bars, heirs):
        ax.text(b.get_x() + b.get_width()/2, v + max(heirs)*0.02,
                f'${v:,.1f}M', ha='center', fontsize=11, fontweight='bold')
    ax.set_ylabel('Net to heirs ($M)')
    title = 'Inheritance after all taxes'
    if title_suffix:
        title += f' — {title_suffix}'
    ax.set_title(title)
    ax.set_ylim(0, max(heirs) * 1.15)
    plt.tight_layout()
    return fig


def plot_trajectories(results: Dict[str, Dict], s: Scenario, title_suffix: str = ''):
    years = np.arange(0, s.years_to_death + 1)
    fig, ax = plt.subplots()
    for k, color, marker, label in [
        ('A', '#185FA5', 'o', 'A. Sell upfront (no further sales)'),
        ('B', '#ff7f0e', 's', 'B. Borrow & amortize'),
        ('C', '#2ca02c', '^', 'C. Borrow, interest-only'),
    ]:
        ax.plot(years, results[k]['trajectory']/1e6,
                marker=marker, markersize=4, linewidth=2,
                color=color, label=label)
    ax.axvline(s.loan_term, color='gray', linestyle=':', linewidth=1, alpha=0.6)
    ax.text(s.loan_term, ax.get_ylim()[1]*0.04, 'loan paid off (B)',
            rotation=90, fontsize=9, alpha=0.7, va='bottom')
    ax.set_xlabel(f'Year (age {RETIREMENT_AGE} → {RETIREMENT_AGE + s.years_to_death})')
    ax.set_ylabel('Stock value ($M)')
    title = 'Stock value over time'
    if title_suffix:
        title += f' — {title_suffix}'
    ax.set_title(title)
    ax.legend()
    plt.tight_layout()
    return fig


def plot_side_by_side(results_a: Dict, label_a: str, scenario_a: Scenario,
                       results_b: Dict, label_b: str, scenario_b: Scenario):
    """Two scenarios on one figure (e.g., moderate-vs-large), showing total federal
    revenue per scenario, normalized as a multiple of the expenditure."""
    fig, ax = plt.subplots(figsize=(10, 6))
    x = np.arange(3)
    w = 0.35

    a_totals = np.array([results_a[k]['total_fed'] for k in 'ABC']) / scenario_a.expenditure
    b_totals = np.array([results_b[k]['total_fed'] for k in 'ABC']) / scenario_b.expenditure

    ax.bar(x - w/2, a_totals * 100, w, color='#185FA5', label=label_a,
           edgecolor='black', linewidth=0.5)
    ax.bar(x + w/2, b_totals * 100, w, color='#993C1D', label=label_b,
           edgecolor='black', linewidth=0.5)

    for i, v in enumerate(a_totals * 100):
        ax.text(i - w/2, v + max(np.concatenate([a_totals, b_totals]))*100*0.02,
                f'{v:,.0f}%', ha='center', fontsize=9)
    for i, v in enumerate(b_totals * 100):
        ax.text(i + w/2, v + max(np.concatenate([a_totals, b_totals]))*100*0.02,
                f'{v:,.0f}%', ha='center', fontsize=9)

    ax.set_xticks(x)
    ax.set_xticklabels(_SCENARIO_LABELS)
    ax.set_ylabel('Total federal revenue ÷ expenditure (%)')
    ax.set_title('Federal revenue collected per dollar of consumption financed')
    ax.legend(loc='upper left')
    ax.set_ylim(0, max(np.concatenate([a_totals, b_totals]))*100 * 1.20)
    plt.tight_layout()
    return fig
