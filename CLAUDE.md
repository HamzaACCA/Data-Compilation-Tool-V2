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
24. **Inline Trend Analysis** - Monthly trend chart displayed below stats cards
25. **Inline Column Analysis** - Always-visible column stats table on dashboard (type, fill %, unique count, duplicates Yes/No) with Excel download
26. **Compare Periods** - Side-by-side comparison with column-level breakdown (toggle modal), 3-sheet Excel download (Summary + Comparison + Data)
27. **Date Column Auto-Detection** - Date column dropdown only shows columns containing date values
28. **Date Column in Filter Card** - Date column selector moved from settings modal to main filter area with auto-save
29. **Export PDF** - Generate printable PDF report (button above Top 10 charts)
30. **Top 10 Analysis** - Configure which columns to display in dashboard
31. **Top 10 Excel Download** - Download button on each chart exports actual data rows (2-sheet workbook: Summary + Data)
32. **Column Analysis Excel Download** - Download button exports all column stats (2-sheet workbook: Column Analysis + Summary)
33. **Auto Date Range** - Filter dates auto-populate with earliest and latest dates from data

### Performance
34. **Fast Excel Reader** - python-calamine (Rust-based) replaces openpyxl for ~10x faster uploads
35. **Fast Excel Writer** - Direct xlsxwriter API bypasses pandas overhead for ~2x faster Excel generation
36. **Lazy Excel Cache** - Excel file generated on download only, not on every upload
37. **CSV Download Option** - `/download?format=csv` for near-instant downloads
38. **Memory Caching** - Dataframes cached in memory with 5-minute TTL
39. **DataFrame Optimization** - Automatic memory optimization (categories, downcasting, ~79% reduction)
40. **Chunked File Reading** - Large CSV files (>50MB) read in chunks
41. **Lazy Loading** - Upload log loads in pages with "Load More"
42. **Performance Monitor** - Bottom-left indicator showing cache size and status

### Window Controls
43. **Standard Maximize/Restore** - Works like normal Windows applications
44. **Double-Click Title Bar** - Double-click to maximize/restore window
45. **Draggable Title Bar** - Title bar is draggable only when not maximized

## Tech Stack

- **Backend:** Python 3.13, Flask 3.0.0
- **Data Processing:** Pandas 2.1.4, python-calamine (fast read), openpyxl 3.1.2 (fallback), xlsxwriter (fast write)
- **Desktop Window:** PyWebView 4.4.1
- **Packaging:** PyInstaller 6.x
- **Installer:** Inno Setup 6.x

## Project Structure

```
Data Compilation V3/
├── launcher.py              # Main application (Flask + PyWebView)
├── templates/
│   ├── index.html           # Upload page with all features
│   └── dashboard.html       # Dashboard with charts and analytics
├── data_compilation.spec    # PyInstaller build config
├── installer_config.iss     # Inno Setup installer config
├── requirements.txt         # Python dependencies
├── Procfile                 # Web deployment (Gunicorn)
├── render.yaml              # Render deployment config
├── BUILD_INSTALLER.bat      # Main build script
├── CLEAN_OLD_BUILD.bat      # Cleanup script
├── FIX_AND_BUILD.bat        # Quick build script
├── CLAUDE.md                # Developer documentation (this file)
├── README.md                # User documentation
├── USER_GUIDE.txt           # End-user guide
└── Data/                    # Data storage folder
    ├── config.json          # Global configuration
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
| `/api/columns` | GET | Get available columns (includes `date_columns` for auto-detected date fields) |
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
| `/api/trend-analysis` | GET | Get monthly trend data |

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

### Fast Excel Writer
```python
def _write_excel_fast(df, filepath):
    # Writes Excel using xlsxwriter directly (bypasses pandas overhead, ~2x faster)
    # Uses constant_memory mode + write_row for speed
    # Used by: generate_excel_cache(), download_consolidated(), download_filtered()
```

### Lazy Excel Cache
```python
# Excel cache is NOT generated on upload — stale .xlsx is deleted on upload
# Excel is generated on-demand via _write_excel_fast() when user downloads
# /download supports ?format=csv for near-instant CSV downloads
```

### Memory Caching System
```python
data_cache = {}
cache_timestamps = {}
CACHE_TTL = 300  # 5 minutes

def get_cached_dataframe(project_name, force_reload=False):
    # Returns cached dataframe or loads from disk

def clear_cache(project_name=None):
    # Clears memory cache
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

1. **Use CSV for downloads** — `/download?format=csv` is ~6x faster than Excel
2. **Second Excel download is instant** — first download generates and caches the `.xlsx`; subsequent downloads serve the cached file (~1s)
3. **Enable caching** — data loads instantly on repeated access (5-min TTL)
4. **Use pagination** — upload log loads in chunks for large histories
5. **Monitor cache** — click performance indicator to view/clear cache
6. **Large CSV files** — files >50MB are read in chunks automatically

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

## Performance Learnings (V3 Optimization Log)

### Upload Speed: 143s → 15s (10x faster)

**Root cause:** `pd.read_excel(engine='openpyxl')` is pure Python XML parsing — ~30s per file for 10K rows × 152 cols.

**Fix:** Replaced with `python-calamine` (Rust-based Excel reader). ~3-5s per file.

**Key insight:** calamine doesn't auto-rename duplicate columns like openpyxl does. `_deduplicate_columns()` was added to match openpyxl's `.1`, `.2` suffix behavior.

### Download Speed: 103s → 54s (Excel) / 9s (CSV)

**Root cause:** `df.to_excel()` via pandas has heavy per-cell type-checking overhead.

**Fix:** `_write_excel_fast()` writes directly via xlsxwriter API using `write_row()` + `constant_memory` mode — bypasses pandas overhead, ~2x faster.

**Key insight:** CSV is 40x faster than any Excel approach for the same data. Added `?format=csv` to `/download` endpoint.

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
| xlsxwriter direct `write_row()` | 35s |
| CSV `df.to_csv()` | 2s |

**Other approaches tested (not adopted):**
| Method | Time | Why not adopted |
|--------|------|-----------------|
| pyexcelerate | 35-77s | No speed gain over direct xlsxwriter; extra dependency; type conversion issues |
| openpyxl write_only | 107s | Slower than xlsxwriter |
| xlsxwriter constant_memory via pandas | 48s | Produced corrupted files through pandas interface |

**DataFrame Optimization:**
| Metric | Before | After |
|--------|--------|-------|
| Memory per file | 36-46 MB | 8-10 MB |
| Reduction | — | ~79% |
| Time cost | — | ~300ms |

---

**Version:** 3.0 (In Development)
**Last Updated:** 30-Jan-2026
**Developer:** Hamza Yahya - Internal Audit
