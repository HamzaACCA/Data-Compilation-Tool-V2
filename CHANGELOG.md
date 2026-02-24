# Changelog

## V3.5 — 24-Feb-2026 (Dual Trend Charts + Performance Optimization)

**New Features:**
- **Dual Trend Charts** — single trend card replaced with a `trendSection` containing shared controls, a COUNT card, and a SUM card; both charts always visible
- **Multi-select legend isolation** — click legend items to select/deselect groups for isolation, ESC clears all selections
- **Dashboard state persistence** — `saveUiState()` writes filter dates, trend settings, ECG toggles, baseline month to `localStorage` per project; restored on page load

**Performance Optimization:**
- **Pre-convert date column in cache** — `get_cached_dataframe()` now calls `pd.to_datetime()` once on load (guarded by `is_datetime64_any_dtype`); eliminates redundant conversion across all endpoints
- **Removed 11 redundant `pd.to_datetime()` calls** — from `get_date_range`, `get_dashboard_stats`, `compare_column`, `download_filtered`, `download_comparison`, `advanced_analysis`, `get_trend_line_data`, `download_trend_line`, `download_column_stats`, `download_advanced_analysis`, `data_summary`
- **Fixed latent mutation bug** — several endpoints were modifying the cached DataFrame directly without `.copy()`, silently converting the date column in-place on the shared cache object
- **Slim column copy in trend endpoints** — `get_trend_line_data()` and `download_trend_line()` now do `df[cols_needed].copy()` (2-3 cols) instead of `df.copy()` (all 153 cols)
- **Benchmarks (37,740 rows × 153 cols):** `pd.to_datetime()` per endpoint 5-9ms → 0ms; `df.copy()` 54ms → ~5ms; single trend call ~180ms → ~80ms; dual-fetch ~400ms → ~170ms

**Frontend:**
- `onTrendControlChange()` fires `Promise.all` with two `/api/trend-line-data` calls (agg_method=count, agg_method=sum)
- Shared rendering functions: `renderRawChart()`, `renderMovementChart()`, `attachChartHover()`, `toggleIsolate()`, `applyIsolation()`, `renderLegend()`, `buildLabelHtml()`
- ECG theme scoped to `.ecg-theme-wrap` class on `wrapCount`/`wrapSum` divs
- Removed: `currentAggMethod`, `lastTrendLineData`, `ecgThemeActive`, `currentChartMode`, `setAggMethod()`, `renderLineChart()`, `renderEcgChart()`, `renderLineLegend()`, `renderLineSummary()`, `toggleEcgTheme()`, `.agg-toggle` CSS

---

## V3.4 — 21-Feb-2026 (Structured Logging)

**New:**
- `utils/logging.py` — logging utility with colored console output (ANSI level tags), rotating file handler (`app.log`, 2 MB / 3 backups) written to `Data/`, and `get_logger()` helper; noisy third-party loggers (`werkzeug`, `urllib3`, `PIL`) silenced at WARNING

**Integration (`launcher.py`):**
- `setup_logging(APP_DIR)` called at startup (after `APP_DIR` is resolved) so logs are co-located with project data
- Module-level `log = get_logger(__name__)` replaces all `print()` calls
- Startup banner and shutdown message converted to `log.info()`
- `Api.minimize_window`, `maximize_window`, `close_window` error handlers converted to `log.error()`
- `log_audit()` bare `except: pass` replaced with `except Exception as e: log.warning(...)` so silent failures are now visible in the log file

---

## V3.3 — 08-Feb-2026 (Monthly Trend Line Chart + ECG Sequential Pulse)

**Replaced Features:**
- Removed Aggregated Trend bar chart (Box 1) and Trend Breakdown stacked bar chart (Box 2)
- Removed anomaly detection, concentration warnings, new/disappeared values, YoY comparison, and MoM % change sub-features
- Replaced with a single **Monthly Trend Line Chart** card

**New Feature — Monthly Trend Line Chart:**
- Multi-line chart showing monthly values per group with CSS-drawn lines and dots
- Group-by column selector (any column) with auto-select first column on load
- SUM/COUNT toggle with value column dropdown (numeric columns, visible in SUM mode)
- Top N selector (Top 5/10/15/20/25) for quick analysis
- "Specific..." mode with searchable chip input for selecting individual groups
- Y-axis with smart scaling (nice round numbers) and horizontal grid lines
- Hover tooltips showing group name, value, and month
- Color legend with group totals
- Summary line showing group count, month count, and grand total
- Excel download (2-sheet: Summary + Trend Data)
- Full dark mode support

**New Feature — ECG/Medical Monitor Theme:**
- **Movement mode:** Shows deviation from a user-selected baseline month as a bipolar chart (positive = above center, negative = below)
- **Trend-specific date range:** Independent start/end dates for the trend chart (clamped within main filter)
- **Baseline month picker:** Dropdown populated from available months, selects reference point for movement calculation
- **RAW/MOVEMENT toggle:** Switch between standard values and deviation-from-baseline view
- **ECG theme toggle:** Dark neon medical monitor styling (black background, neon green text, monospace font, glow effects)
- **Neon color palette:** Cyan, Magenta, Lime, Yellow, Red for ECG mode line groups
- **Zero baseline line:** Dashed white line at chart center labeled with baseline month name
- **Baseline highlight:** Selected baseline month underlined in X-axis labels
- **3-sheet Excel download:** When baseline is selected — Summary (with baseline month), Raw Data, Movement Data
- Full dark mode + ECG theme compatibility (no style conflicts)

**Backend:**
- Removed `/api/trend-analysis` endpoint
- Removed `/api/download-trend-analysis` endpoint
- Removed `/api/trend-breakdown` endpoint
- Removed `/api/download-trend-breakdown` endpoint
- New endpoint `/api/trend-line-data` — group-by trend with `top_n`, `specific_groups` (via getlist), `agg_method` (sum/count), `value_column` params; returns `available_groups` list when `top_n=0` with no specific groups
- `/api/trend-line-data` — added `baseline_month`, `trend_start_date`, `trend_end_date` params; returns `movement_series`, `baseline_month`, `baseline_values` when baseline is valid
- New endpoint `/api/download-trend-line` — 2-sheet Excel (without baseline) or 3-sheet Excel (with baseline: Summary + Raw Data + Movement Data) via `_write_xlsx_raw` + `BytesIO`
- Added `columns_cache` for `/api/columns` endpoint (677ms → 12ms cached)
- Added cache for `/api/column-stats` endpoint (1051ms → 10ms cached)

**Frontend:**
- New CSS for line chart (`.line-chart-container`, `.line-dot`, `.line-segment`, `.line-chart-grid-line`, `.line-chart-y-labels`, `.line-chart-x-labels`), agg toggle (`.agg-toggle`), chip input (`.chip-input-wrapper`, `.chip`, `.chip-search`, `.chip-dropdown`, `.chip-option`), and legend (`.line-chart-legend`, `.legend-line`, `.legend-dot`)
- New CSS for ECG theme (`#trendLineCard.ecg-theme` scoped selectors), mode toggle (`.mode-toggle`), baseline line (`.ecg-baseline-line`), ECG toggle button (`.ecg-toggle-btn`)
- Removed CSS for old trend bars, stacked breakdown, audit alerts, YoY chart, MoM table
- Single card `#trendLineCard` replaces two old cards (`#trendCard`, `#breakdownTrendCard`)
- Removed dead code: `showTrendAnalysis()`, `displayTrendModal()`, `closeTrendModal()` modal functions
- New JS functions: `setChartMode()`, `onTrendDateChange()`, `populateBaselineMonths()`, `toggleEcgTheme()`, `formatMovementNumber()`, `getNiceMaxBipolar()`, `renderEcgChart()`
- Modified: `onTrendControlChange()` (trend dates, baseline, renderer selection), `updateDashboard()` (trend date init), `downloadTrendLineExcel()` (new params), `loadUniqueGroups()` (trend dates), `renderLineChart()` + `renderLineLegend()` (ECG color palette swap)
- `populateColumnSelectors()` populates `trendGroupSelect` and `trendValueSelect` with auto-select first column
- `updateDashboard()` calls `onTrendControlChange()` instead of `loadInlineTrend()` + `loadBreakdownTrend()`
- Parallelized init API calls with `Promise.all([loadProjectInfo(), loadColumns(), loadSettings(), loadDateRange()])`
- Parallelized post-load calls with `Promise.all([onTrendControlChange(), loadColumnStats()])`

**ECG Chart Redesign — Sequential Pulse:**
- Rewrote `renderEcgChart()` as a sequential pulse chart: months shown once on X-axis, all groups plotted side by side within each month, connected by ONE continuous line
- Color-coded dots per group with compact value labels on every dot: `+74 (Baba: 1.7K)`
- Pixel-accurate line segment math (accounts for container aspect ratio) — lines connect properly across months
- Month separator vertical lines, baseline month highlighted as "(BASELINE)"
- Chart overflow clipped, compact K/M number formatting on labels
- New CSS: `.ecg-month-sep`, `.ecg-dot-label`, `.ecg-x-label`, `.ecg-mode`

**Bug Fixes:**
- Fixed line segment angle/length math in both `renderLineChart` and `renderEcgChart` — uses pixel-accurate calculations accounting for container aspect ratio
- Added `overflow: hidden` to `.line-chart-container` CSS to prevent lines/dots overflowing chart bounds
- `renderLineChart` uses `requestAnimationFrame` two-pass rendering so lines connect properly after layout
- Fixed orphan `}` syntax error left behind when old trend modal code was removed
- Fixed trend chart not showing on load — added auto-select of first column in `populateColumnSelectors()`
- Added favicon.ico to prevent 404 errors

---

## V3.2 — 31-Jan-2026 (Enhanced Monthly Trend Analysis)

**New Features:**
- **Aggregated Trend Analysis (Box 1):** Column + aggregation selector (COUNT/SUM/AVERAGE/MIN/MAX) on the monthly trend chart; numeric-only column filtering for SUM/AVG/MIN/MAX; smart number formatting; Excel download button
- **Trend Breakdown by Group (Box 2):** Group-by column selector with stacked bar chart (Top 10 groups + Others), color legend with percentages, Excel download (3-sheet: Summary + Breakdown + Audit)
- **Anomaly Detection:** Months where a group's value exceeds 2x its average are flagged with pulsing red borders on chart segments
- **Concentration Warnings:** Alert badges when any group accounts for >50% of total records
- **New/Disappeared Value Detection:** Identifies values present in last month but not first (and vice versa)
- **Year-over-Year Comparison:** Overlaid dot-and-line chart comparing monthly totals across years (visible when data spans 2+ years)
- **Month-over-Month % Change:** Color-coded table showing consecutive month percentage changes for top 5 groups

**Backend:**
- Modified `/api/trend-analysis` — added `column` and `agg_method` parameters (backwards compatible; default is COUNT)
- New endpoint `/api/trend-breakdown` — group-by breakdown with 5 audit features (anomalies, new/disappeared, concentration, YoY, MoM)
- New endpoint `/api/download-trend-breakdown` — 3-sheet Excel download via `_write_xlsx_raw` + `BytesIO`

**Frontend:**
- Enhanced trend card (Box 1) with column and aggregation dropdowns
- New breakdown card (Box 2) with group selector, stacked bar chart, legend, audit alerts, YoY overlay, MoM table
- Full dark mode support for all new elements (`.breakdown-section-heading` CSS class, dark mode variants for alerts, charts, tables)
- 10-color palette for groups + gray for "Others"
- `populateColumnSelectors()` extended to populate both new dropdowns
- `updateDashboard()` calls `loadBreakdownTrend()` after `loadInlineTrend()`

---

## V3.1 — 30-Jan-2026 (Bug Fixes + Download Speed)

**Bug Fixes:**
- Fixed `delete_upload` unbound `rows_removed` variable when pickle file doesn't exist
- Fixed `delete_upload` not clearing cache or removing stale Excel after row removal
- Fixed `upload_mapped_file` not clearing cache after saving pickle
- Fixed `upload_mapped_file` not running `optimize_dataframe()` on uploaded data
- Fixed `reset_consolidated` not clearing cache after deleting data files
- Fixed `reset_consolidated` not logging to audit log
- Fixed `_write_excel_fast` crashing on NaN/Inf values — enabled `nan_inf_to_errors` on all 6 `xlsxwriter.Workbook` instances
- Fixed `_write_excel_fast` writing raw datetime objects — now converts to `dd-MMM-YYYY` formatted strings
- Fixed `get_memory_stats` returning wrong cache size — uses `memory_usage(deep=True).sum()` for DataFrames instead of `sys.getsizeof()`
- Fixed `combine_files` optimization condition `% 10000 == 0` (almost never triggers) — changed to `> 10000`
- Fixed Escape key not closing Summary and Audit Log modals in `index.html`
- Fixed dark mode not applying to summary modal "Column Types" header — replaced hardcoded `color:#2c3e50` with `.summary-heading` CSS class

**Enhancements:**
- Raw XML Excel writer (`_write_xlsx_raw`) — generates xlsx via direct XML + zipfile, ~3x faster than xlsxwriter (14s vs 42s for 18K rows × 152 cols)
- All Excel download endpoints (filtered, top10, comparison, advanced analysis) now use raw XML writer
- Streaming CSV downloads — `/download?format=csv` uses `BytesIO` instead of writing temp files to disk
- In-memory filtered downloads — `/api/download-filtered` uses `BytesIO` for both CSV and Excel (no temp files)
- All read-only endpoints now use `get_cached_dataframe()` instead of direct `pd.read_pickle()`/`pd.read_excel()` (15+ endpoints)
- PyWebView save dialogs now use `get_cached_dataframe()` and `_write_excel_fast()` instead of `pd.read_pickle()` and `df.to_excel()`
- `Content-Length` headers added to all `BytesIO` responses for accurate download progress
- Removed duplicate `import os`; moved `import io` and `import xlsxwriter` to top-level imports
