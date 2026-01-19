# Data Compilation Tool V2 - Developer Reference

## Project Overview

A Windows desktop application that automatically combines monthly Excel files with matching headers into a single consolidated file. **Version 2** adds multi-project support, dynamic dashboard column selection, and comprehensive data management features.

**Developer:** Hamza Yahya - Internal Audit

## What's New in V2

### Core Features
1. **Multi-Project Support** - Create and manage multiple consolidation projects
2. **Dynamic Column Selection** - Choose which columns to display as Top 10 in dashboard
3. **Per-Project Settings** - Each project has its own date column and dashboard columns
4. **Project Switching** - Quick switch between projects with all projects displayed
5. **Upload Tracking** - Track all uploads with ability to delete specific uploads

### Upload Enhancements
6. **Progress Bar** - Real-time upload progress with percentage and file size
7. **Upload Confirmation** - Popup modal showing filename, count, and size before upload
8. **Undo Last Upload** - Popup modal confirmation for undo with file details
9. **Column Mapping** - Map columns from files with different header names

### User Experience
10. **Dark Mode** - Toggle between light and dark themes (persists to localStorage)
11. **Keyboard Shortcuts** - Ctrl+O (open), Ctrl+D (download), Ctrl+Z (undo), Ctrl+N (new), Ctrl+B (dashboard), F1 (help), Esc (close modals)
12. **Search/Filter** - Search uploads by filename or date in upload history
13. **Toast Notifications** - Modern notification popups for actions
14. **All Projects Quick Switch** - Shows all projects with active project highlighted in blue
15. **Date Format** - All dates display as DD-MMM-YYYY (e.g., 15-Jan-2026)
16. **Text Selection** - Content is fully selectable and copyable

### Data Management
17. **Audit Log** - Track all actions (uploads, deletes, restores)
18. **Data Summary** - View detailed statistics about project data

### Dashboard Features
19. **Visual Bar Charts** - Color-coded gradient bar charts for Top 10 data
20. **Inline Trend Analysis** - Monthly trend chart displayed below stats cards
21. **Compare Periods** - Side-by-side comparison with date picker limited to available data
22. **Column Analysis** - Detailed stats per column (type, fill %, unique count, duplicates Yes/No)
23. **Export PDF** - Generate printable PDF report (button above Top 10 charts)
24. **Top 10 Analysis** - Configure which columns to display in dashboard
25. **Top 10 Excel Download** - Download button on each chart exports actual data rows

### Performance Enhancements
26. **Memory Caching** - Dataframes cached in memory with 5-minute TTL
27. **DataFrame Optimization** - Automatic memory optimization (categories, downcasting)
28. **Chunked File Reading** - Large CSV files (>50MB) read in chunks
29. **Lazy Loading** - Upload log loads in pages with "Load More"
30. **Background Task Tracking** - Visual indicator for long-running operations
31. **Performance Monitor** - Bottom-left indicator showing cache size and status

### Window Controls
32. **Standard Maximize/Restore** - Works like normal Windows applications
33. **Double-Click Title Bar** - Double-click to maximize/restore window
34. **Draggable Title Bar** - Title bar is draggable only when not maximized

## Tech Stack

- **Backend:** Python 3.13, Flask 3.0.0
- **Data Processing:** Pandas 2.1.4, openpyxl 3.1.2, xlsxwriter
- **Desktop Window:** PyWebView 4.4.1
- **Packaging:** PyInstaller 6.x
- **Installer:** Inno Setup 6.x

## Project Structure

```
Data Compilation V2/
├── launcher.py              # Main application (Flask + PyWebView)
├── templates/
│   ├── index.html           # Upload page with all features
│   └── dashboard.html       # Dashboard with charts and analytics
├── data_compilation.spec    # PyInstaller build config
├── installer_config.iss     # Inno Setup installer config
├── requirements.txt         # Python dependencies
├── BUILD_INSTALLER.bat      # Main build script
├── CLEAN_OLD_BUILD.bat      # Cleanup script
├── FIX_AND_BUILD.bat        # Quick build script
├── README.md                # User documentation
├── USER_GUIDE.txt           # End-user guide
└── Data/                    # Data storage folder
    ├── config.json          # Global configuration
    └── Projects/            # Project folders
        └── <project_name>/
            ├── uploads/              # Uploaded files
            ├── consolidated_data.pkl # Pickle data file (fast)
            ├── consolidated_data.xlsx # Excel export (cached)
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
| `/download` | GET | Download consolidated file |
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
| `/api/columns` | GET | Get available columns |
| `/api/settings` | GET | Get project settings |
| `/api/settings` | POST | Save project settings |
| `/api/date-range` | GET | Get min/max dates |
| `/api/dashboard-stats` | GET | Get dashboard statistics |
| `/api/download-filtered` | GET | Download filtered data |
| `/api/download-top10` | GET | Download Top 10 actual data rows as Excel |
| `/api/column-stats` | GET | Get column analysis (includes duplicates) |
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
    # Converts low-cardinality text to categories
    # Downcasts integers and floats
    # Reduces memory usage significantly
```

### Background Task Tracking
```python
def create_background_task(task_id, task_type, description)
def update_task_progress(task_id, progress, status=None)
def complete_task(task_id, result=None, error=None)
```

### Window Maximize State (Python)
```python
is_maximized = False

def maximize_window(self):
    global is_maximized
    if is_maximized:
        webview_window.restore()
    else:
        webview_window.maximize()
    is_maximized = not is_maximized
```

### Date Formatting (JavaScript)
```javascript
// DD-MMM-YYYY format
function formatDate(dateStr) {
    const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                    'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    const date = new Date(dateStr);
    return `${day}-${months[date.getMonth()]}-${year}`;
}

// DD-MMM-YYYY HH:MM format
function formatDateTime(dateStr) {
    // Returns "15-Jan-2026 10:30"
}
```

### Title Bar Drag Control (JavaScript)
```javascript
let isMaximized = false;

function updateTitleBarDrag() {
    const titleBar = document.getElementById('titleBar');
    if (isMaximized) {
        titleBar.classList.remove('draggable');
    } else {
        titleBar.classList.add('draggable');
    }
}

// Double-click to maximize/restore
titleBar.addEventListener('dblclick', (e) => {
    if (e.target.closest('.window-controls')) return;
    maximizeWindow();
});
```

### JavaScript API for PyWebView
- `minimize_window()` - Minimize window
- `maximize_window()` - Toggle maximize/restore
- `close_window()` - Close application
- `save_consolidated_file()` - Native save dialog for consolidated data
- `save_filtered_file(start_date, end_date)` - Save filtered data

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
   pip install flask pandas openpyxl werkzeug pywebview pyinstaller xlsxwriter
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
   - Installer: `installer_output\DataCompilationTool_V2_Setup.exe`

## Installation Paths

- **Application:** `C:\Users\<user>\AppData\Local\DataCompilationTool\`
- **Data Storage:** `...\DataCompilationTool\Data\`
- **Projects:** `...\Data\Projects\<project_name>\`
- **Config:** `...\Data\config.json`

## Frontend Design

### Color Scheme
- **Title Bar:** Dark blue (#2c3e50)
- **Background:** Light gray (#f5f7fa)
- **Primary:** Blue (#3498db)
- **Success:** Green (#27ae60)
- **Warning:** Orange (#f39c12)
- **Danger:** Red (#e74c3c)
- **Settings:** Purple (#9b59b6)
- **Info:** Teal (#1abc9c)

### Dark Mode Colors
- **Background:** #1a1a2e
- **Cards:** #16213e
- **Borders:** #0f3460
- **Text:** #e0e0e0

### Date Picker Styling
- Blue calendar icon for better visibility
- Focus state with blue glow/shadow
- Dates limited to available data range in Compare Periods

### Quick Switch Buttons
- All projects displayed (not just recent)
- Active project highlighted with blue background
- Instant color update on project switch

## User Workflow

1. **Create a Project** - Click "New Project" and enter a name
2. **Upload Files** - Drag & drop or select Excel/CSV files
3. **Confirm Upload** - Review filename and size in popup modal
4. **Configure Dashboard** - Click "Top 10 Analysis" to select display columns
5. **View Statistics** - Apply date filter to see Top 10 charts and Trend Analysis
6. **Download Top 10 Data** - Click Excel button on each chart to download actual rows
7. **Analyze Data** - Use Column Analysis and Compare Periods
8. **Download Data** - Download full or filtered data (CSV recommended for speed)
9. **Export Reports** - Use Export PDF for printable reports

## Top 10 Excel Download

Each Top 10 chart has a download button that exports an Excel file with **two sheets**:

| Sheet | Contents |
|-------|----------|
| **Summary** | Rank, Name, Count (overview of Top 10) |
| **Data** | All actual rows from consolidated data for Top 10 values |

The Data sheet includes a `Top10_Rank` column for easy filtering by rank.

## Performance Tips

1. **Use CSV for exports** - 20x faster than Excel
2. **Enable caching** - Data loads instantly on repeated access
3. **Use pagination** - Upload log loads in chunks for large histories
4. **Monitor cache** - Click performance indicator to view/clear cache
5. **Optimize large files** - Files >50MB are read in chunks automatically

## Common Issues & Solutions

### Download button not working
**Cause:** PyWebView doesn't handle `window.location.href` downloads like a browser.
**Solution:** Use `window.pywebview.api.save_consolidated_file()` with native file dialog.

### Slow startup
**Cause:** PyInstaller one-file mode extracts files to temp on each launch.
**Solution:** Added splash screen for better UX. Disabled UPX compression.

### Column mismatch error
**Cause:** New file has different columns than existing data.
**Solution:** Use Column Mapping feature to map columns or start fresh project.

### High memory usage
**Cause:** Large datasets cached in memory.
**Solution:** Click performance monitor and clear cache, or reduce cache TTL.

### Slow Excel export
**Cause:** Excel generation is slower than CSV.
**Solution:** Use CSV format for large datasets (default option).

### Window moving when maximized
**Cause:** Title bar drag region active in maximized state.
**Solution:** Fixed - title bar drag disabled when maximized.

### Cannot copy text from app
**Cause:** Entire window had drag region enabled.
**Solution:** Fixed - only title bar is draggable, content is selectable.

## V2 Final Changes Summary

### Removed Features (Simplified for V2)
- Data Preview (replaced with simple upload confirmation modal)
- Data Validation Rules
- Backup & Restore
- Export/Import Settings

### UI Improvements
- All dates formatted as DD-MMM-YYYY
- Undo confirmation as popup modal (not browser alert)
- Trend Analysis displayed inline below stats
- Column Analysis shows Duplicates (Yes/No) column
- Export PDF button moved above Top 10 charts
- Date picker with improved visibility styling
- Compare Periods calendar limited to available data dates
- Quick Switch shows ALL projects with active highlighted
- Download button on each Top 10 chart (exports actual data rows)
- Standard window maximize/restore behavior
- Double-click title bar to maximize/restore
- Content area fully selectable (can copy text)

### Renamed Elements
- "Column Settings" → "Top 10 Analysis"
- "Column Stats" → "Column Analysis"

---

**Version:** 2.0 Final
**Last Updated:** 19-Jan-2026
**Developer:** Hamza Yahya - Internal Audit
