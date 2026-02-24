# Data Analytical and Compilation Tool

A desktop + web application to automatically combine monthly Excel files with matching headers into a single consolidated file, with analytics dashboard.

**Prepared by:** Hamza Yahya - Internal Audit
**Version:** 3.5

## Features

- Multi-project support with per-project settings
- Upload multiple Excel/CSV files at once with column mapping
- Fast data processing with pickle storage and calamine Excel reader
- Dashboard with configurable Top 10 charts, Dual Trend Charts (COUNT + SUM), and PDF export
- Dual Monthly Trend Charts with group-by column, always-visible COUNT and SUM, Top N selector, multi-select legend isolation
- ECG/Medical Monitor theme with movement mode (deviation from baseline), neon styling, and trend-specific date range
- Date range filtering and period comparison
- Dark mode, keyboard shortcuts, audit log
- Streaming CSV and in-memory Excel downloads (no temp files)
- Memory-cached data access across all endpoints with automatic invalidation

## Requirements

- Windows 10/11 (64-bit)
- No additional software needed for end users

## Installation

1. Run `DataCompilationTool_V3_Setup.exe`
2. Follow the installation wizard
3. Launch from desktop icon or Start Menu

**Installation Location:** `C:\Users\<user>\AppData\Local\DataCompilationTool\`

**Data Storage:** `...\DataCompilationTool\Data\Projects\`

## Usage

### Upload Files
1. Create or select a project
2. Click or drag Excel/CSV files to the upload area
3. Confirm upload in the popup modal

### View Dashboard
1. Click "View Dashboard" or press Ctrl+B
2. Configure Top 10 columns via "Top 10 Analysis"
3. Select date range and click "Apply Filter"

### Download Data
- **All Data:** Click "Download Data" (CSV recommended for speed)
- **Filtered Data:** Use dashboard's "Download Filtered Data"

### Keyboard Shortcuts
| Shortcut | Action |
|----------|--------|
| Ctrl+O | Open file dialog |
| Ctrl+D | Download data |
| Ctrl+Z | Undo last upload |
| Ctrl+N | New project |
| Ctrl+B | Go to Dashboard |
| F1 | Show shortcuts help |

## For Developers

See `CLAUDE.md` for complete technical documentation.

### Quick Build

```batch
CLEAN_OLD_BUILD.bat
FIX_AND_BUILD.bat
```

### Manual Build

```batch
pip install flask pandas openpyxl werkzeug pywebview pyinstaller xlsxwriter python-calamine
python -m PyInstaller --clean data_compilation.spec
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer_config.iss
```

### Dependencies

```
Flask==3.0.0
pandas==2.1.4
openpyxl==3.1.2
werkzeug==3.0.1
pywebview==4.4.1
xlsxwriter
python-calamine
```

## Environment Setup

Create a `.env` file in the project root (already git-ignored):

```
GITHUB_TOKEN=your_github_token_here
```

## Project Structure

```
Data Compilation V3/
├── launcher.py              # Main application (Flask + PyWebView)
├── utils/
│   └── logging.py           # Logging utility (colored console + rotating file)
├── templates/
│   ├── index.html           # Upload page
│   └── dashboard.html       # Dashboard page
├── data_compilation.spec    # PyInstaller config
├── installer_config.iss     # Inno Setup config
├── requirements.txt         # Python dependencies
├── .env                     # Environment variables (git-ignored)
├── .gitignore               # Git ignore rules
├── CLAUDE.md                # Developer documentation
├── README.md                # This file
├── USER_GUIDE.txt           # End-user guide
└── Data/Projects/           # Project data storage
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Slow startup | Normal on first launch — splash screen displays while loading |
| Download not working | Use native save dialog (desktop) or CSV format (web) |
| Upload fails | Check file is .xlsx/.xls/.csv, headers match, file < 50MB |
| Slow Excel download | Use CSV format — much faster for large datasets |
| Stale data after deleting upload | Refresh the page — cache is auto-cleared on mutations |

## Changelog

### V3.5 (24-Feb-2026)
- **Dual Trend Charts** — COUNT and SUM charts always visible side by side with shared controls
- **Multi-select legend isolation** — click legend items to isolate specific groups, ESC clears
- **Dashboard state persistence** — filter dates, trend settings, ECG toggles saved to localStorage
- **Performance optimization** — date column pre-converted in cache (eliminates 11 redundant `pd.to_datetime()` calls), slim column copy in trend endpoints (~50% faster dual-fetch)

### V3.4 (21-Feb-2026)
- Structured logging via `utils/logging.py` — colored console output and rotating log file (`Data/app.log`)
- All internal `print()` calls replaced with proper log levels (info / warning / error)

### V3.3 (08-Feb-2026)
- **Monthly Trend Line Chart** — replaced old trend boxes with single multi-line chart
- Group-by column selector with auto-select first column
- SUM/COUNT toggle with value column dropdown (numeric columns)
- Top N selector (Top 5/10/15/20/25) and "Specific..." mode with searchable chip input
- Y-axis with smart scaling, hover tooltips, color legend with totals
- Excel download (2-sheet: Summary + Trend Data)
- **ECG/Medical Monitor Theme** — toggle neon green-on-black styling on the trend chart
- **Movement mode** — RAW/MOVEMENT toggle shows deviation from user-selected baseline month as a sequential pulse chart (one continuous line, groups side by side per month, compact K/M labels on every dot)
- **Trend-specific date range** — independent start/end dates for the trend chart (clamped within main filter)
- **Baseline month picker** — dropdown to select reference month; 3-sheet Excel download (Summary + Raw Data + Movement Data)
- Parallelized dashboard API calls for faster loading (~590ms with cache)
- Added caching for `/api/columns` and `/api/column-stats` endpoints

### V3.2 (31-Jan-2026)
- Enhanced Monthly Trend Analysis with column + aggregation selector (COUNT/SUM/AVG/MIN/MAX)
- Trend Breakdown by Group — stacked bar chart with Top 10 groups, color legend, Excel download
- Audit insights: anomaly detection (>2x average), concentration warnings (>50%), new/disappeared values
- Year-over-Year comparison chart (when data spans 2+ years)
- Month-over-Month % change table with color-coded percentages
- Full dark mode support for all new dashboard elements

### V3.1 (30-Jan-2026)
- Raw XML Excel writer — 3x faster Excel downloads (14s vs 42s for large datasets)
- Fixed multiple cache invalidation bugs (delete upload, mapped upload, reset)
- Fixed Excel download crashes on NaN/Inf values
- Fixed datetime columns displaying as raw objects in Excel exports
- Fixed Escape key not closing all modals
- Fixed dark mode styling on summary modal
- Streaming CSV downloads (no temp files)
- In-memory filtered Excel downloads
- All endpoints now use memory cache for faster responses
- Accurate cache size reporting in performance monitor

### V3.0
- Initial release with multi-project support, dashboard, and analytics

## V4 Roadmap

A full rewrite to **FastAPI + React** is planned, including:
- SQLite database replacing pickle/JSON file storage
- JWT authentication with role-based access control
- Anomaly detection (outliers, duplicates, gap analysis)
- React dashboard with Recharts
- WebSocket real-time upload progress
- SAP S/4HANA OData integration (Phase 2)

See **[V4_ARCHITECTURE_PLAN.md](V4_ARCHITECTURE_PLAN.md)** for the full architecture plan.

## Support

For issues or feature requests, contact Internal Audit department.
