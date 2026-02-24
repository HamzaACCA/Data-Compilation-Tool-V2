"""
Audit Checks Engine — 9 pandas-based checks that run on 100% of data locally.
Zero token cost. Each check returns a list of finding dicts.
"""
import pandas as pd
import numpy as np
from collections import Counter


def check_duplicates(df, key_cols=None):
    """Check for exact duplicate rows across key columns (or all columns)."""
    findings = []
    cols = key_cols if key_cols else list(df.columns)
    cols = [c for c in cols if c in df.columns and c != '_upload_id']
    if not cols:
        return findings

    dupes = df[df.duplicated(subset=cols, keep=False)]
    if len(dupes) == 0:
        return findings

    n_groups = dupes.groupby(cols, observed=True).ngroups if len(cols) <= 10 else len(dupes) // 2
    n_rows = len(dupes)

    # Sample evidence (max 50 rows)
    sample = dupes.head(50)
    evidence = sample.to_dict(orient='records')
    for row in evidence:
        for k, v in row.items():
            if pd.isna(v):
                row[k] = None
            elif isinstance(v, (np.integer,)):
                row[k] = int(v)
            elif isinstance(v, (np.floating,)):
                row[k] = float(v)
            elif hasattr(v, 'isoformat'):
                row[k] = v.isoformat()

    level = 'high' if n_rows > 100 else ('medium' if n_rows > 10 else 'low')
    findings.append({
        'check_type': 'duplicate',
        'level': level,
        'title': f'{n_rows} duplicate rows found',
        'detail': f'{n_groups} groups of duplicate records detected across {len(cols)} columns.',
        'evidence': evidence[:20],
        'stats': {'total_duplicates': n_rows, 'groups': n_groups, 'columns_checked': cols}
    })
    return findings


def check_outliers(df, numeric_cols=None):
    """Detect outliers using IQR method per numeric column."""
    findings = []
    if numeric_cols is None:
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    numeric_cols = [c for c in numeric_cols if c in df.columns]

    for col in numeric_cols[:20]:  # cap at 20 columns
        series = df[col].dropna()
        if len(series) < 10:
            continue

        q1 = series.quantile(0.25)
        q3 = series.quantile(0.75)
        iqr = q3 - q1
        if iqr == 0:
            continue

        lower = q1 - 1.5 * iqr
        upper = q3 + 1.5 * iqr
        outliers = df[(df[col] < lower) | (df[col] > upper)]

        if len(outliers) == 0:
            continue

        pct = round(len(outliers) / len(df) * 100, 1)
        level = 'high' if pct > 10 else ('medium' if pct > 3 else 'low')

        sample = outliers.head(10)
        evidence = []
        for _, row in sample.iterrows():
            evidence.append({
                'value': float(row[col]) if pd.notna(row[col]) else None,
                'expected_range': f'{lower:.2f} - {upper:.2f}'
            })

        findings.append({
            'check_type': 'outlier',
            'level': level,
            'title': f'{len(outliers)} outliers in "{col}" ({pct}%)',
            'detail': f'Values outside IQR range [{lower:.2f}, {upper:.2f}]. Q1={q1:.2f}, Q3={q3:.2f}.',
            'evidence': evidence,
            'stats': {'column': col, 'outlier_count': len(outliers), 'pct': pct,
                      'lower_bound': float(lower), 'upper_bound': float(upper)}
        })
    return findings


def check_concentration(df, cat_cols=None):
    """Check for high concentration in categorical columns (single value dominates)."""
    findings = []
    if cat_cols is None:
        cat_cols = df.select_dtypes(include=['object', 'category']).columns.tolist()
    cat_cols = [c for c in cat_cols if c in df.columns and c != '_upload_id']

    for col in cat_cols[:15]:
        vc = df[col].value_counts(normalize=True)
        if len(vc) == 0:
            continue

        top_pct = round(vc.iloc[0] * 100, 1)
        if top_pct < 25:
            continue

        top_5 = vc.head(5)
        evidence = [{'value': str(k), 'percentage': round(v * 100, 1),
                      'count': int(df[col].value_counts()[k])}
                     for k, v in top_5.items()]

        level = 'high' if top_pct > 60 else ('medium' if top_pct > 40 else 'low')
        findings.append({
            'check_type': 'concentration',
            'level': level,
            'title': f'"{col}": top value is {top_pct}% of all records',
            'detail': f'"{vc.index[0]}" accounts for {top_pct}% ({int(vc.iloc[0] * len(df))} rows).',
            'evidence': evidence,
            'stats': {'column': col, 'top_value': str(vc.index[0]), 'top_pct': top_pct,
                      'unique_count': len(vc)}
        })
    return findings


def check_trend_anomalies(df, date_col, group_col=None):
    """Detect month-over-month spikes/drops >2x the average change."""
    findings = []
    if not date_col or date_col not in df.columns:
        return findings

    try:
        dates = pd.to_datetime(df[date_col], errors='coerce')
    except Exception:
        return findings

    monthly = dates.dt.to_period('M').value_counts().sort_index()
    if len(monthly) < 3:
        return findings

    counts = monthly.values.astype(float)
    changes = np.abs(np.diff(counts))
    avg_change = changes.mean() if len(changes) > 0 else 0

    if avg_change == 0:
        return findings

    evidence = []
    for i in range(1, len(counts)):
        change = counts[i] - counts[i - 1]
        if abs(change) > 2 * avg_change:
            pct_change = round(change / counts[i - 1] * 100, 1) if counts[i - 1] != 0 else 0
            evidence.append({
                'month': str(monthly.index[i]),
                'count': int(counts[i]),
                'prev_count': int(counts[i - 1]),
                'change': int(change),
                'pct_change': pct_change
            })

    if evidence:
        level = 'high' if len(evidence) > 3 else ('medium' if len(evidence) > 1 else 'low')
        findings.append({
            'check_type': 'trend_anomaly',
            'level': level,
            'title': f'{len(evidence)} monthly trend anomalies detected',
            'detail': f'Months with volume changes exceeding 2x the average monthly variation ({avg_change:.0f}).',
            'evidence': evidence[:10],
            'stats': {'anomaly_count': len(evidence), 'avg_monthly_change': round(avg_change, 1)}
        })
    return findings


def check_missing_data(df):
    """Check for columns with significant missing data (>5%)."""
    findings = []
    total = len(df)
    if total == 0:
        return findings

    for col in df.columns:
        if col == '_upload_id':
            continue
        null_count = int(df[col].isnull().sum())
        pct = round(null_count / total * 100, 1)
        if pct < 5:
            continue

        level = 'high' if pct > 50 else ('medium' if pct > 20 else 'low')
        findings.append({
            'check_type': 'missing_data',
            'level': level,
            'title': f'"{col}": {pct}% missing ({null_count} rows)',
            'detail': f'Column has {null_count} null/empty values out of {total} total rows.',
            'evidence': [],
            'stats': {'column': col, 'null_count': null_count, 'pct': pct}
        })
    return findings


def check_round_numbers(df, numeric_cols=None):
    """Check for suspicious rounding patterns in numeric columns."""
    findings = []
    if numeric_cols is None:
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    numeric_cols = [c for c in numeric_cols if c in df.columns]

    for col in numeric_cols[:15]:
        series = df[col].dropna()
        if len(series) < 20:
            continue

        # Check for round numbers (divisible by 100, 1000, etc.)
        round_1000 = (series % 1000 == 0).sum()
        round_100 = (series % 100 == 0).sum()

        pct_1000 = round(round_1000 / len(series) * 100, 1)
        pct_100 = round(round_100 / len(series) * 100, 1)

        if pct_1000 > 30:
            level = 'medium' if pct_1000 > 50 else 'low'
            findings.append({
                'check_type': 'round_numbers',
                'level': level,
                'title': f'"{col}": {pct_1000}% are round thousands',
                'detail': f'{round_1000} values are exact multiples of 1,000 — may indicate estimation or rounding.',
                'evidence': [],
                'stats': {'column': col, 'round_1000_count': int(round_1000),
                          'round_1000_pct': pct_1000, 'round_100_pct': pct_100}
            })
        elif pct_100 > 40:
            findings.append({
                'check_type': 'round_numbers',
                'level': 'low',
                'title': f'"{col}": {pct_100}% are round hundreds',
                'detail': f'{round_100} values are exact multiples of 100.',
                'evidence': [],
                'stats': {'column': col, 'round_100_count': int(round_100), 'round_100_pct': pct_100}
            })
    return findings


def check_weekend_activity(df, date_col):
    """Check for unusual weekend/holiday transaction patterns."""
    findings = []
    if not date_col or date_col not in df.columns:
        return findings

    try:
        dates = pd.to_datetime(df[date_col], errors='coerce')
    except Exception:
        return findings

    valid = dates.dropna()
    if len(valid) < 10:
        return findings

    weekend_mask = valid.dt.dayofweek >= 5  # Saturday=5, Sunday=6
    weekend_count = int(weekend_mask.sum())
    total = len(valid)
    pct = round(weekend_count / total * 100, 1)

    if weekend_count == 0:
        return findings

    # Break down by day of week
    dow_counts = valid.dt.day_name().value_counts().to_dict()
    evidence = [{'day': day, 'count': int(cnt)} for day, cnt in dow_counts.items()]

    level = 'medium' if pct > 15 else 'low'
    findings.append({
        'check_type': 'weekend_activity',
        'level': level,
        'title': f'{weekend_count} weekend transactions ({pct}%)',
        'detail': f'{weekend_count} records dated on Saturday/Sunday out of {total} total.',
        'evidence': evidence,
        'stats': {'weekend_count': weekend_count, 'total': total, 'pct': pct}
    })
    return findings


def check_benfords_law(df, numeric_cols=None):
    """Check if first-digit distribution follows Benford's Law (chi-squared test)."""
    findings = []
    if numeric_cols is None:
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    numeric_cols = [c for c in numeric_cols if c in df.columns]

    # Benford's expected distribution
    benford = {d: np.log10(1 + 1 / d) for d in range(1, 10)}

    for col in numeric_cols[:10]:
        series = df[col].dropna().abs()
        series = series[series > 0]
        if len(series) < 100:
            continue

        # Extract first digit
        first_digits = series.apply(lambda x: int(str(x).lstrip('0').lstrip('.').lstrip('0')[0])
                                    if str(x).lstrip('0').lstrip('.').lstrip('0') else 0)
        first_digits = first_digits[first_digits.between(1, 9)]

        if len(first_digits) < 50:
            continue

        observed = first_digits.value_counts(normalize=True).sort_index()

        # Chi-squared test
        chi2 = 0
        n = len(first_digits)
        evidence = []
        for d in range(1, 10):
            obs_pct = observed.get(d, 0)
            exp_pct = benford[d]
            chi2 += (obs_pct - exp_pct) ** 2 / exp_pct * n
            evidence.append({
                'digit': d,
                'observed_pct': round(obs_pct * 100, 1),
                'expected_pct': round(exp_pct * 100, 1),
                'deviation': round((obs_pct - exp_pct) * 100, 1)
            })

        # Critical value for 8 df at 0.05 significance = 15.51
        if chi2 > 15.51:
            level = 'high' if chi2 > 30 else 'medium'
            findings.append({
                'check_type': 'benfords_law',
                'level': level,
                'title': f'"{col}" deviates from Benford\'s Law (chi2={chi2:.1f})',
                'detail': f'First-digit distribution significantly deviates from expected pattern. High chi-squared ({chi2:.1f} > 15.51) may indicate data manipulation.',
                'evidence': evidence,
                'stats': {'column': col, 'chi_squared': round(chi2, 2), 'sample_size': int(n)}
            })
    return findings


def check_split_transactions(df, date_col, vendor_col=None, amount_col=None):
    """Detect potential transaction splitting (multiple same-day entries near round thresholds)."""
    findings = []
    if not date_col or date_col not in df.columns:
        return findings
    if not amount_col or amount_col not in df.columns:
        return findings

    group_col = vendor_col if vendor_col and vendor_col in df.columns else None

    try:
        df_work = df[[c for c in [date_col, group_col, amount_col] if c]].copy()
        df_work['_date'] = pd.to_datetime(df_work[date_col], errors='coerce').dt.date
    except Exception:
        return findings

    df_work = df_work.dropna(subset=['_date', amount_col])
    if len(df_work) < 10:
        return findings

    # Common approval thresholds
    thresholds = [1000, 5000, 10000, 25000, 50000, 100000]

    group_cols = ['_date']
    if group_col:
        group_cols.append(group_col)

    groups = df_work.groupby(group_cols, observed=True)
    evidence = []

    for name, group in groups:
        if len(group) < 2:
            continue

        total = group[amount_col].sum()
        max_val = group[amount_col].max()

        for threshold in thresholds:
            # All individual amounts below threshold but total exceeds it
            if (group[amount_col] < threshold).all() and total >= threshold:
                # Check if amounts are suspiciously close to threshold
                near_threshold = (group[amount_col] > threshold * 0.5).sum()
                if near_threshold >= 2:
                    date_str = str(name[0]) if isinstance(name, tuple) else str(name)
                    vendor_str = str(name[1]) if isinstance(name, tuple) and len(name) > 1 else 'N/A'
                    evidence.append({
                        'date': date_str,
                        'vendor': vendor_str,
                        'transaction_count': len(group),
                        'individual_amounts': [float(v) for v in group[amount_col].tolist()[:5]],
                        'total': float(total),
                        'threshold': threshold
                    })
                    break  # only flag first matching threshold

        if len(evidence) >= 20:
            break

    if evidence:
        level = 'high' if len(evidence) > 5 else ('medium' if len(evidence) > 2 else 'low')
        findings.append({
            'check_type': 'split_transaction',
            'level': level,
            'title': f'{len(evidence)} potential split transactions detected',
            'detail': f'Same-day transactions by the same party with individual amounts below approval thresholds but combined total exceeding them.',
            'evidence': evidence[:15],
            'stats': {'groups_flagged': len(evidence)}
        })
    return findings


def run_all_checks(df, settings=None):
    """Run all 9 audit checks and return consolidated results."""
    settings = settings or {}
    date_col = settings.get('date_column', '')
    top_columns = settings.get('top_columns', [])

    # Determine key columns for duplicate check
    key_cols = [tc.get('column') for tc in top_columns if tc.get('column')]

    # Determine numeric columns
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    numeric_cols = [c for c in numeric_cols if c != '_upload_id']

    # Determine categorical columns
    cat_cols = df.select_dtypes(include=['object', 'category']).columns.tolist()
    cat_cols = [c for c in cat_cols if c != '_upload_id']

    # Determine vendor/amount columns (best guess from settings)
    vendor_col = None
    amount_col = None
    for tc in top_columns:
        col_name = tc.get('column', '')
        display = tc.get('display_name', '').lower()
        if any(w in display for w in ['vendor', 'supplier', 'transporter', 'agent', 'party']):
            vendor_col = col_name
        if any(w in display for w in ['amount', 'value', 'cost', 'price', 'total']):
            amount_col = col_name

    # If no amount column from settings, try to find one
    if not amount_col and numeric_cols:
        for col in numeric_cols:
            cl = col.lower()
            if any(w in cl for w in ['amount', 'value', 'cost', 'price', 'total', 'sum']):
                amount_col = col
                break

    # Group column for trend anomalies
    group_col = None
    if top_columns:
        group_col = top_columns[0].get('column')

    all_findings = []
    all_findings.extend(check_duplicates(df, key_cols or None))
    all_findings.extend(check_outliers(df, numeric_cols))
    all_findings.extend(check_concentration(df, cat_cols))
    all_findings.extend(check_trend_anomalies(df, date_col, group_col))
    all_findings.extend(check_missing_data(df))
    all_findings.extend(check_round_numbers(df, numeric_cols))
    all_findings.extend(check_weekend_activity(df, date_col))
    all_findings.extend(check_benfords_law(df, numeric_cols))
    all_findings.extend(check_split_transactions(df, date_col, vendor_col, amount_col))

    # Sort by severity
    level_order = {'high': 0, 'medium': 1, 'low': 2}
    all_findings.sort(key=lambda f: level_order.get(f.get('level', 'low'), 3))

    summary = {
        'total_rows': len(df),
        'total_findings': len(all_findings),
        'high': sum(1 for f in all_findings if f['level'] == 'high'),
        'medium': sum(1 for f in all_findings if f['level'] == 'medium'),
        'low': sum(1 for f in all_findings if f['level'] == 'low'),
    }

    return {'summary': summary, 'findings': all_findings}
