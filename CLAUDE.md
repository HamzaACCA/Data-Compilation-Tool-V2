# Data Analytical and Compilation Tool - Developer Reference

## Project Overview

A smart analytical tool with multi-project support that automatically consolidates different file types with matching headers into a single file, with a full analytics dashboard.

**Developer:** Hamza Yahya - Internal Audit

### V2 Reference (Historical)
- **Live App:** https://HamzaACCAAI.pythonanywhere.com
- **GitHub:** https://github.com/HamzaACCA/Data-Compilation-Tool-V2 (Private)

## Features

### Core
1. **Multi-Project Support** - Create and manage multiple consolidation projects
2. **Delete Project** - Delete projects via trash icon on quick-switch buttons or dedicated delete button
3. **Project Description** - Optional description shown in active project info area
4. **Dynamic Column Selection** - Choose which columns to display as Top 10 in dashboard
5. **Per-Project Settings** - Each project has its own date column and dashboard columns
6. **Project Switching** - Quick switch between projects with all projects displayed
7. **Upload Tracking** - Track all uploads with ability to delete specific uploads

### Upload
8. **Progress Bar** - Real-time upload progress with percentage and file size
9. **Upload Confirmation** - Popup modal showing filename, count, and size before upload
10. **Undo Last Upload** - Popup modal confirmation for undo with file details
11. **Column Mapping** - Map columns from files with different header names
12. **Collapsible Upload History** - Upload history panel hidden by default, toggle via side tab

### User Experience
13. **Dark Mode** - Toggle between light and dark themes (persists to localStorage)
14. **Keyboard Shortcuts** - Ctrl+O (open), Ctrl+D (download), Ctrl+Z (undo), Ctrl+N (new), Ctrl+B (dashboard), F1 (help), Esc (close modals)
15. **Search/Filter** - Search uploads by filename or date in upload history
16. **Toast Notifications** - Modern notification popups for actions
17. **All Projects Quick Switch** - Shows all projects with active project highlighted in blue
18. **Date Format** - All dates display as DD-MMM-YYYY (e.g., 15-Jan-2026)
19. **Text Selection** - Content is fully selectable and copyable
20. **Date Picker Toggle** - Click date input to open calendar, click again to close

### Data Management
21. **Audit Log** - Track all actions (uploads, deletes, restores)
22. **Data Summary** - View detailed statistics about project data

### Dashboard
23. **Visual Bar Charts** - Color-coded gradient bar charts for Top 10 data
24. **Monthly Trend Line Chart** - Multi-line chart with group-by column, SUM/COUNT toggle, Top N selector (5/10/15/20/25), specific group search with chip input, Y-axis scaling, hover tooltips, color legend, and Excel download (2-sheet: Summary + Trend Data)
25. **ECG/Medical Monitor Theme** - Toggle neon green-on-black medical monitor styling on trend chart (heart icon button), with glow effects on dots and lines
26. **Movement Mode** - RAW/MOVEMENT toggle shows deviation from user-selected baseline month as a bipolar chart (zero line at center, positive above, negative below)
27. **Trend-Specific Date Range** - Independent start/end date inputs for the trend chart, clamped within main filter range, auto-reset on Apply Filter
28. **Baseline Month Picker** - Dropdown populated from available months; 3-sheet Excel download when baseline selected (Summary + Raw Data + Movement Data)
25. **Inline Column Analysis** - Always-visible column stats table on dashboard (type, fill %, unique count, duplicates Yes/No) with Excel download
26. **Compare Periods** - Side-by-side comparison with column-level breakdown (toggle modal), 3-sheet Excel download (Summary + Comparison + Data)
27. **Advanced Comparative Analysis** - Group-by aggregation (SUM/COUNT/AVERAGE/MIN/MAX) across two periods with numeric value columns, inline results section with Excel download (3-sheet: Summary + Comparison + Data)
28. **Date Column Auto-Detection** - Date column dropdown only shows columns containing date values
29. **Date Column in Filter Card** - Date column selector moved from settings modal to main filter area with auto-save
30. **Export PDF** - Generate printable PDF report (button above Top 10 charts)
31. **Top 10 Analysis** - Configure which columns to display in dashboard
32. **Top 10 Excel Download** - Download button on each chart exports actual data rows (2-sheet workbook: Summary + Data)
33. **Column Analysis Excel Download** - Download button exports all column stats (2-sheet workbook: Column Analysis + Summary)
34. **Auto Date Range** - Filter dates auto-populate with earliest and latest dates from data

### Audit Bot (AI-Powered)
41. **Chat Panel** - Slide-out chat panel on dashboard with natural language command parser (39 dashboard actions)
42. **9 Audit Checks** - Duplicates, outliers, concentration, trend anomalies, missing data, round numbers, weekend activity, Benford's Law, split transactions — all run locally via pandas (FREE)
43. **AI Interpreter** - GPT-5.2 via OpenAI API for interpreting findings, answering questions, and proposing dashboard actions (PAID per query)
44. **Risk Report Generator** - AI-generated structured risk assessment report with PDF/text download
45. **Smart Hybrid Commands** - Multi-step commands ("filter jan 2025 to jun 2025, then risk scan"), smart column name matching (display names + partial match)
46. **Chat Persistence** - SQLite database stores chat history, risk scans, findings, and token usage per project
47. **Confirm Before Execute** - Bot proposes actions, user clicks [Apply] to execute

### Performance
48. **Fast Excel Reader** - python-calamine (Rust-based) replaces openpyxl for ~10x faster uploads
42. **Fast Excel Writer** - Raw XML generation bypasses xlsxwriter overhead for ~3x faster Excel generation, with datetime formatting (dd-MMM-YYYY) and multi-sheet support
43. **Lazy Excel Cache** - Excel file generated on download only, not on every upload
44. **Streaming CSV Downloads** - CSV downloads use in-memory `BytesIO` streaming (no temp files on disk)
45. **In-Memory Excel Downloads** - Filtered and comparison Excel downloads use `BytesIO` with `Content-Length` headers (no temp files)
46. **Memory Caching** - Dataframes cached in memory with 5-minute TTL; all read-only endpoints use `get_cached_dataframe()`
47. **Cache Invalidation** - Cache is cleared on upload, delete upload, mapped upload, and data reset
48. **DataFrame Optimization** - Automatic memory optimization (categories, downcasting, ~79% reduction); triggers on datasets >10K rows and on mapped uploads
49. **Chunked File Reading** - Large CSV files (>50MB) read in chunks
50. **Lazy Loading** - Upload log loads in pages with "Load More"
51. **Performance Monitor** - Bottom-left indicator showing accurate cache size (uses `memory_usage(deep=True)` for DataFrames)

### Window Controls
52. **Standard Maximize/Restore** - Works like normal Windows applications
53. **Double-Click Title Bar** - Double-click to maximize/restore window
54. **Draggable Title Bar** - Title bar is draggable only when not maximized

## Tech Stack

- **Backend:** Python 3.13, Flask 3.0.0
- **Data Processing:** Pandas 2.1.4, python-calamine (fast read), openpyxl 3.1.2 (fallback), xlsxwriter (fast write)
- **AI:** OpenAI GPT-5.2 (optional, per-query pricing)
- **Database:** SQLite (audit bot chat history, risk scans)
- **Desktop Window:** PyWebView 4.4.1
- **Packaging:** PyInstaller 6.x
- **Installer:** Inno Setup 6.x

## Project Structure

```
Data Compilation V3/
├── launcher.py              # Main application (Flask + PyWebView)
├── utils/
│   ├── __init__.py          # Package init
│   ├── logging.py           # Logging utility (colored console + rotating file)
│   ├── audit_checks.py      # 9 pandas-based audit checks (100% data scan)
│   ├── ai_chat.py           # OpenAI GPT-5.2 client, prompt builder, report generator
│   └── db.py                # SQLite connection helper, CRUD for chat/scans
├── templates/
│   ├── index.html           # Upload page with all features
│   └── dashboard.html       # Dashboard with charts, analytics, and chat panel
├── data_compilation.spec    # PyInstaller build config
├── installer_config.iss     # Inno Setup installer config
├── requirements.txt         # Python dependencies
├── RAG_AUDIT_BOT_PLAN.md    # Audit Bot implementation plan
├── Procfile                 # Web deployment (Gunicorn)
├── render.yaml              # Render deployment config
├── BUILD_INSTALLER.bat      # Main build script
├── CLEAN_OLD_BUILD.bat      # Cleanup script
├── FIX_AND_BUILD.bat        # Quick build script
├── .env                     # Environment variables (GITHUB_TOKEN, OPENAI_API_KEY) - git-ignored
├── .gitignore               # Git ignore rules
├── CLAUDE.md                # Developer documentation (this file)
├── README.md                # User documentation
├── USER_GUIDE.txt           # End-user guide
└── Data/                    # Data storage folder
    ├── config.json          # Global configuration
    ├── audit_bot.db         # SQLite database (chat history, risk scans)
    └── Projects/            # Project folders
        └── <project_name>/
            ├── uploads/              # Uploaded files
            ├── consolidated_data.pkl # Pickle data file (fast)
            ├── consolidated_data.xlsx # Excel export (generated on download)
            ├── settings.json         # Project settings
            ├── upload_log.json       # Upload history
            └── audit_log.json        # Activity log
```

## API Endpoints

### Project Management
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/projects` | GET | List all projects |
| `/api/projects` | POST | Create new project |
| `/api/projects/<name>` | DELETE | Delete project |
| `/api/projects/<name>/select` | POST | Switch to project |

### Data Operations
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Main upload page |
| `/upload` | POST | Upload and combine files |
| `/upload-mapped` | POST | Upload with column mapping |
| `/stats` | GET | Get consolidated file stats |
| `/download` | GET | Download consolidated file (`?format=csv` or `xlsx`) |
| `/reset` | POST | Delete consolidated file |

### Upload Management
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/uploads` | GET | List uploads (paginated) |
| `/api/uploads/<id>` | DELETE | Delete specific upload |

### Dashboard & Settings
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/dashboard` | GET | Dashboard page |
| `/api/columns` | GET | Get available columns (includes `date_columns` and `numeric_columns`) |
| `/api/settings` | GET | Get project settings |
| `/api/settings` | POST | Save project settings |
| `/api/date-range` | GET | Get min/max dates |
| `/api/dashboard-stats` | GET | Get dashboard statistics |
| `/api/download-filtered` | GET | Download filtered data (`?format=csv` or `xlsx`) |
| `/api/download-top10` | GET | Download Top 10 actual data rows as Excel |
| `/api/column-stats` | GET | Get column analysis |
| `/api/download-column-stats` | GET | Download column analysis as Excel (2-sheet: Column Analysis + Summary) |
| `/api/compare-column` | GET | Compare a column across two periods (top 25 values with counts and change %) |
| `/api/download-comparison` | GET | Download full comparison as Excel (3-sheet: Summary + Comparison + Data) |
| `/api/advanced-analysis` | GET | Advanced group-by aggregation comparison across two periods (top 50 results) |
| `/api/download-advanced-analysis` | GET | Download advanced analysis as Excel (3-sheet: Summary + Comparison + Data) |
| `/api/trend-line-data` | GET | Get monthly trend line data (supports `group_column`, `value_column`, `agg_method`, `top_n`, `specific_groups`, `baseline_month`, `trend_start_date`, `trend_end_date` params; returns `movement_series` when baseline valid) |
| `/api/download-trend-line` | GET | Download trend line data as Excel (2-sheet without baseline; 3-sheet with baseline: Summary + Raw Data + Movement Data) |

### Audit Bot
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/chat` | POST | Send message — local save (`source=local`) or route to GPT-5.2 (`source=ai`) |
| `/api/chat/history` | GET | Load chat history for current project from SQLite |
| `/api/chat/history` | DELETE | Clear chat history for current project |
| `/api/risk-scan` | GET | Run all 9 audit checks on 100% data, store results in SQLite |
| `/api/generate-report` | POST | Generate AI risk assessment report from latest scan results |

### Data Management
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/data-summary` | GET | Get data summary statistics |
| `/api/audit-log` | GET | Get activity log |

### Performance
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/memory-stats` | GET | Get cache size and status |
| `/api/clear-cache` | POST | Clear memory cache |
| `/api/background-tasks` | GET | List background tasks |
| `/api/background-tasks/<id>` | GET | Get task status |

## Data Storage Structure

### Global Config (config.json)
```json
{
  "current_project": "Project Name",
  "projects": {
    "Project Name": {
      "created": "2024-01-15 10:30:00",
      "description": "Project description"
    }
  }
}
```

### Project Settings (settings.json)
```json
{
  "date_column": "ActShpmtCmpletDate",
  "top_columns": [
    {"column": "Container ID", "display_name": "Truck No."},
    {"column": "Number of forwarding agent", "display_name": "Transporter Name"},
    {"column": "Ship-to party", "display_name": "Customer Name"}
  ]
}
```

### Upload Log (upload_log.json)
```json
[
  {
    "id": "20240115_103000_filename.xlsx",
    "original_name": "filename.xlsx",
    "upload_date": "2024-01-15 10:30:00",
    "rows": 1500,
    "file_path": "/path/to/uploads/..."
  }
]
```

## Key Code Components

### Fast Excel Reader (calamine)
```python
# Rust-based Excel reader (~10x faster than openpyxl)
from python_calamine import CalamineWorkbook
# Fallback to openpyxl if calamine is not installed

def _deduplicate_columns(columns):
    # Renames duplicate columns with .1, .2 suffix (matches openpyxl behavior)

def _read_excel_calamine(filepath_or_obj):
    # Reads Excel via CalamineWorkbook.from_path() or .from_filelike()

def read_file(filepath_or_obj):
    # Uses calamine for .xlsx/.xls, pandas for .csv
    # Accepts both string paths and file-like objects (FileStorage)
```

### Fast Excel Writer (Raw XML)
```python
def _write_xlsx_raw(sheets_data, output):
    # Generates xlsx via raw XML + zipfile (~3x faster than xlsxwriter)
    # Builds shared string table, worksheet XML, and packages as ZIP
    # Supports multiple sheets, numeric values, and string data
    # Used by: _write_excel_fast(), download_filtered(), download_top10(),
    #          download_comparison(), download_advanced_analysis()

def _write_excel_fast(df, filepath):
    # Convenience wrapper: calls _write_xlsx_raw() with a single sheet
    # Converts datetime columns to dd-MMM-YYYY, category columns to strings
```

### Lazy Excel Cache
```python
# Excel cache is NOT generated on upload — stale .xlsx is deleted on upload
# Excel is generated on-demand via _write_excel_fast() when user downloads
# /download supports ?format=csv for near-instant streaming CSV downloads (no temp file)
```

### Memory Caching System
```python
data_cache = {}
cache_timestamps = {}
CACHE_TTL = 300  # 5 minutes

def get_cached_dataframe(project_name, force_reload=False):
    # Returns cached dataframe or loads from disk
    # Pre-converts configured date column to datetime on load (guarded by is_datetime64_any_dtype)
    # Used by ALL read-only endpoints (stats, columns, dashboard, downloads, comparisons, etc.)
    # Endpoints NO LONGER call pd.to_datetime() on the date column — it's already datetime in cache

def clear_cache(project_name=None):
    # Clears memory cache
    # Called after: upload, delete_upload, upload_mapped, reset_consolidated
```

### DataFrame Optimization
```python
def optimize_dataframe(df):
    # Converts low-cardinality text (<50% unique) to categories
    # Downcasts integers and floats
    # Reduces memory usage ~79%
```

### Window Controls (PyWebView API)
- `minimize_window()` - Minimize window
- `maximize_window()` - Toggle maximize/restore
- `close_window()` - Close application
- `save_consolidated_file()` - Native save dialog for consolidated data
- `save_filtered_file(start_date, end_date)` - Save filtered data

### Date Formatting (JavaScript)
```javascript
// DD-MMM-YYYY format
function formatDate(dateStr) {
    const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
    const date = new Date(dateStr);
    return `${day}-${months[date.getMonth()]}-${year}`;
}
```

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| Ctrl+O | Open file dialog |
| Ctrl+D | Download data |
| Ctrl+Z | Undo last upload |
| Ctrl+N | New project |
| Ctrl+B | Go to Dashboard |
| Escape | Close modals |
| F1 | Show shortcuts help |

## Build Instructions

### Prerequisites
1. Python 3.12+ installed
2. Inno Setup 6 installed at `C:\Program Files (x86)\Inno Setup 6\`

### Build Steps

1. **Install dependencies:**
   ```batch
   pip install flask pandas openpyxl werkzeug pywebview pyinstaller xlsxwriter python-calamine
   ```

2. **Clean old builds:**
   ```batch
   CLEAN_OLD_BUILD.bat
   ```

3. **Build executable and installer:**
   ```batch
   FIX_AND_BUILD.bat
   ```

4. **Output:**
   - Executable: `dist\DataCompilationTool.exe`
   - Installer: `installer_output\DataCompilationTool_V3_Setup.exe`

## Installation Paths

- **Application:** `C:\Users\<user>\AppData\Local\DataCompilationTool\`
- **Data Storage:** `...\DataCompilationTool\Data\`
- **Projects:** `...\Data\Projects\<project_name>\`
- **Config:** `...\Data\config.json`

## Frontend Design

### Color Scheme
| Element | Color |
|---------|-------|
| Title Bar | #2c3e50 (Dark blue) |
| Background | #f5f7fa (Light gray) |
| Primary | #3498db (Blue) |
| Success | #27ae60 (Green) |
| Warning | #f39c12 (Orange) |
| Danger | #e74c3c (Red) |
| Settings | #9b59b6 (Purple) |
| Info | #1abc9c (Teal) |

### Dark Mode Colors
| Element | Color |
|---------|-------|
| Background | #1a1a2e |
| Cards | #16213e |
| Borders | #0f3460 |
| Text | #e0e0e0 |

## Web Deployment (PythonAnywhere)

### File Locations
- **App Code:** `/home/HamzaACCAAI/mysite/`
- **WSGI Config:** `/var/www/hamzaaccaai_pythonanywhere_com_wsgi.py`
- **Data Storage:** `/home/HamzaACCAAI/mysite/Data/`

### WSGI Configuration
```python
import sys, os
project_home = '/home/HamzaACCAAI/mysite'
if project_home not in sys.path:
    sys.path.insert(0, project_home)
os.environ['WEB_MODE'] = 'true'
from launcher import app as application
```

### Updating the Web App
1. Push changes to GitHub
2. SSH to PythonAnywhere or use Files tab
3. `cd ~/mysite && git pull`
4. Reload web app from Web tab

## Performance Tips

1. **Use CSV for downloads** — `/download?format=csv` streams directly from memory (~6x faster than Excel, no temp files)
2. **Second Excel download is instant** — first download generates and caches the `.xlsx`; subsequent downloads serve the cached file (~1s)
3. **All endpoints use cache** — every read-only endpoint uses `get_cached_dataframe()`, data loads instantly on repeated access (5-min TTL)
4. **Use pagination** — upload log loads in chunks for large histories
5. **Monitor cache** — click performance indicator to view/clear cache; shows accurate DataFrame memory usage
6. **Large CSV files** — files >50MB are read in chunks automatically
7. **Filtered downloads are in-memory** — `/api/download-filtered` uses `BytesIO`, no temp files left on disk

## Common Issues & Solutions

| Issue | Cause | Solution |
|-------|-------|----------|
| Download button not working (desktop) | PyWebView doesn't handle `window.location.href` | Use `window.pywebview.api.save_consolidated_file()` |
| Slow startup (desktop) | PyInstaller one-file mode extracts to temp | Splash screen added; UPX compression disabled |
| Column mismatch error | New file has different columns | Use Column Mapping or start a fresh project |
| High memory usage | Large datasets cached in memory | Click performance monitor → clear cache |
| Slow first Excel download | Excel cache is lazy (generated on-demand) | Use CSV download; second Excel download is cached |
| Window moves when maximized | Title bar drag region active | Fixed — drag disabled when maximized |
| Cannot copy text from app | Window-wide drag region | Fixed — only title bar is draggable |
| NaN/Inf crash on Excel download | xlsxwriter can't write NaN/Inf values | Fixed — `nan_inf_to_errors` enabled on all Workbook instances |
| Stale data after delete upload | Cache not invalidated after removing rows | Fixed — `clear_cache()` called after all data mutations |
| Dark mode summary header wrong color | Hardcoded `color:#2c3e50` on `<h4>` | Fixed — uses `.summary-heading` CSS class with dark mode variant |

## Performance Learnings (V3 Optimization Log)

### Upload Speed: 143s → 15s (10x faster)

**Root cause:** `pd.read_excel(engine='openpyxl')` is pure Python XML parsing — ~30s per file for 10K rows × 152 cols.

**Fix:** Replaced with `python-calamine` (Rust-based Excel reader). ~3-5s per file.

**Key insight:** calamine doesn't auto-rename duplicate columns like openpyxl does. `_deduplicate_columns()` was added to match openpyxl's `.1`, `.2` suffix behavior.

### Download Speed: 103s → 14s (Excel) / 3s (CSV)

**Root cause:** `df.to_excel()` via pandas has heavy per-cell type-checking overhead. xlsxwriter's `write_row()` is ~2x faster but still bottlenecked by per-cell XML generation (~72K cells/sec).

**Fix:** `_write_xlsx_raw()` generates xlsx XML directly via string concatenation + `zipfile`, bypassing xlsxwriter entirely — ~3x faster than xlsxwriter for large datasets.

**Key insight:** An xlsx file is a ZIP of XML files. By generating the XML directly with Python string operations and a shared string table, we skip xlsxwriter's per-cell type checking, format management, and XML builder overhead. CSV remains fastest for non-Excel formats.

### Excel Cache: Removed Background Thread

**Root cause:** V2 ran `generate_excel_cache()` in a background thread after every upload. While it didn't block the HTTP response, the GIL contention slowed subsequent uploads from ~6s to ~14s.

**Fix:** Removed background thread. Stale `.xlsx` is deleted on upload; Excel is generated on-demand at download time.

**Key insight:** Python threading doesn't provide true parallelism for CPU-bound work due to the GIL. Background threads that do heavy CPU work (like Excel generation) will slow down the main thread.

### Benchmark Reference (18,870 rows × 152 cols)

**Excel Reading:**
| Engine | Time |
|--------|------|
| openpyxl (pure Python) | 28-35s |
| python-calamine (Rust) | 3-9s |

**Excel Writing:**
| Method | Time |
|--------|------|
| `df.to_excel()` via pandas | 70-80s |
| xlsxwriter `write_row()` + constant_memory | 42s |
| xlsxwriter `write_row()` + in_memory | 35s |
| **Raw XML + zipfile (`_write_xlsx_raw`)** | **14s** |
| CSV `df.to_csv()` | 3s |

**Other approaches tested (not adopted):**
| Method | Time | Why not adopted |
|--------|------|-----------------|
| polars write_excel (Rust xlsxwriter) | 53s | Slower than Python xlsxwriter (no constant_memory), duplicate column issues |
| pyexcelerate | 35-77s | No speed gain over direct xlsxwriter; extra dependency; type conversion issues |
| openpyxl write_only | 107s | Slower than xlsxwriter |
| xlsxwriter constant_memory via pandas | 48s | Produced corrupted files through pandas interface |

**DataFrame Optimization:**
| Metric | Before | After |
|--------|--------|-------|
| Memory per file | 36-46 MB | 8-10 MB |
| Reduction | — | ~79% |
| Time cost | — | ~300ms |

**Trend Endpoint Optimization (37,740 rows × 153 cols):**
| Step | Before | After |
|------|--------|-------|
| `pd.to_datetime()` per endpoint | 5-9ms | 0ms (pre-converted in cache) |
| `df.copy()` (all cols) | 54ms | ~5ms (slim 2-3 col copy) |
| Single trend call | ~180ms | ~80ms |
| Dual-fetch (COUNT+SUM) | ~400ms | ~170ms |

## Environment Variables

Store secrets in `.env` (git-ignored):

```
GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

The `.env` file is listed in `.gitignore` and will never be committed.
`OPENAI_API_KEY` is optional — if not set, AI chat/reports are disabled but all local features (39 commands, 9 audit checks) still work.

## Changelog

See **[CHANGELOG.md](CHANGELOG.md)** for version history (V3.1, V3.2, V3.3).

---

## Development Notes & Learnings

### Dashboard Performance Optimization

**Problem:** Dashboard was loading slowly (3-5 seconds).

**Root Causes & Fixes:**
1. **Sequential API calls** — Changed to `Promise.all()` for parallel loading
   - Init phase: `Promise.all([loadProjectInfo(), loadColumns(), loadSettings(), loadDateRange()])`
   - Post-load: `Promise.all([onTrendControlChange(), loadColumnStats()])`

2. **Slow `/api/columns` endpoint** — Added `columns_cache` dictionary
   - Before: 677ms (runs `pd.to_datetime()` on 152 columns to detect date columns)
   - After: 12ms (cached)

3. **Slow `/api/column-stats` endpoint** — Added cache with `colstats_` prefix
   - Before: 1051ms (runs `nunique()` on all 152 columns)
   - After: 10ms (cached)

4. **Redundant `pd.to_datetime()` in 11 endpoints** — Date column now pre-converted once in `get_cached_dataframe()` on load
   - Before: 5-9ms wasted per endpoint call (×11 endpoints)
   - After: 0ms (already datetime in cache)
   - Also fixed latent mutation bug: several endpoints modified the cached df without `.copy()`

5. **Full `df.copy()` in trend endpoints** — Slim column copy (`df[cols_needed].copy()`) in `get_trend_line_data()` and `download_trend_line()`
   - Before: 54ms (copies all 153 columns)
   - After: ~5ms (copies 2-3 columns)
   - Single trend call: ~180ms → ~80ms; dual-fetch: ~400ms → ~170ms

**Final Performance:** ~590ms total dashboard load (with cache warm); ~170ms dual trend fetch

### Common Code Issues to Check

1. **Orphan braces** — When removing code blocks, check for leftover `}` that causes syntax errors
2. **Hidden elements** — Cards with `display:none` need a trigger to show; verify default selection
3. **Missing HTML elements** — Verify all `getElementById()` references have matching HTML `id=` attributes
4. **Cache invalidation** — Always call `clear_cache()` after data mutations (upload, delete, reset)

### Testing Checklist

```bash
# 1. JavaScript syntax validation
node --check /tmp/extracted_js.js

# 2. Brace/paren/bracket balance
grep -o '{' file.html | wc -l  # should match } count

# 3. API endpoint test
curl -s "http://127.0.0.1:5000/api/endpoint" | python3 -c "import sys,json; print(json.load(sys.stdin))"

# 4. Full dashboard flow test
curl -s -w "HTTP: %{http_code}\n" "http://127.0.0.1:5000/dashboard"
```

### CSS Line Chart Technique

The line chart uses pure CSS (no canvas/SVG libraries):
- **Dots:** Positioned `div` elements with `border-radius: 50%`
- **Lines:** Rotated `div` elements using `transform: rotate(Xdeg)` calculated from `Math.atan2(dy, dx)`
- **Grid:** Absolute-positioned horizontal `div` lines at percentage heights
- **Tooltips:** CSS `::after` pseudo-element with `data-tooltip` attribute

### ECG/Movement Chart — Sequential Pulse Design

- **Sequential pulse:** Months shown once on X-axis, all groups plotted side by side within each month, ONE continuous line connects all points left-to-right
- **Bipolar Y-axis:** Maps `[-niceMax, +niceMax]` to `[0%, 100%]`, zero baseline at 50% center
- **Pixel-accurate lines:** Line segment angle/length calculated using actual container pixel dimensions (aspect ratio correction) so lines connect properly across months
- **Dot labels:** Every dot labeled with compact values: `+74 (Baba: 1.7K)` — movement value + short group name + raw value in K/M format
- **Month separators:** Vertical dashed lines between month groups, baseline month marked "(BASELINE)"
- **ECG theme:** Scoped CSS via `#trendLineCard.ecg-theme` — black bg, neon green line, monospace font
- **Neon colors:** `ecgColors` array (cyan, magenta, lime, yellow, red) replaces `lineColors` when theme active
- **CSS classes:** `.ecg-month-sep`, `.ecg-dot-label`, `.ecg-x-label`, `.ecg-mode` (x-labels override)
- **State variables:** `currentChartMode` ('raw'/'movement'), `ecgThemeActive` (boolean)

---

## V4 Roadmap

A full architectural rewrite is planned. See **[V4_ARCHITECTURE_PLAN.md](V4_ARCHITECTURE_PLAN.md)** for the complete design document.

### V4 Key Changes
- **Backend:** Flask → FastAPI (async)
- **Frontend:** Vanilla HTML/JS → React 18 + Vite + TailwindCSS
- **Database:** Pickle + JSON files → SQLite + SQLAlchemy
- **Auth:** None → JWT (access + refresh tokens) with role-based access
- **Charts:** Chart.js (CDN) → Recharts (React-native)
- **New Features:** Anomaly detection (outliers, duplicates, gaps), WebSocket upload progress, SAP S/4HANA integration (Phase 2)

**Status:** Planning — Not yet implemented

---

**Version:** 3.6
**Last Updated:** 25-Feb-2026
**Developer:** Hamza Yahya - Internal Audit
