# Data Compilation Tool

A Windows desktop application to automatically combine monthly Excel files with matching headers.

**Prepared by:** Hamza Yahya - Internal Audit

## Features

- Upload multiple Excel/CSV files at once
- Automatic header validation (152 columns)
- Fast data processing with pickle storage
- Dashboard with Top 10 statistics:
  - Top 10 Truck No. (Container ID)
  - Top 10 Transporter Name (Number of forwarding agent)
  - Top 10 Customer Name (Ship-to party)
- Date range filtering
- Native file save dialogs
- Professional desktop window with custom controls

## Requirements

- Windows 10/11 (64-bit)
- No additional software needed for end users

## Installation

1. Run `DataCompilationTool_Setup.exe`
2. Follow the installation wizard
3. Launch from desktop icon or Start Menu

**Installation Location:** `C:\Users\<user>\AppData\Local\DataCompilationTool\`

**Data Storage:** `...\DataCompilationTool\Consolidated Data\`

## Usage

### Upload Files
1. Click or drag Excel/CSV files to the upload area
2. Select multiple files at once (supported)
3. Click "Upload & Combine"

### View Dashboard
1. Click "View Dashboard" button
2. Select date range (auto-populated from data)
3. Click "Apply Filter" to view statistics

### Download Data
- **All Data:** Click "Download Data" on main page
- **Filtered Data:** Use dashboard's "Download Filtered Data"

### Reset Data
Click "Reset Data" to clear all consolidated data (cannot be undone!)

## For Developers

See `CLAUDE.md` for complete technical documentation.

### Quick Build

```batch
CLEAN_OLD_BUILD.bat
FIX_AND_BUILD.bat
```

### Manual Build

```batch
pip install flask pandas openpyxl werkzeug pywebview pyinstaller
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
```

## Project Structure

```
Data Compilation/
├── launcher.py              # Main application
├── templates/
│   ├── index.html           # Upload page
│   └── dashboard.html       # Dashboard page
├── data_compilation.spec    # PyInstaller config
├── installer_config.iss     # Inno Setup config
├── requirements.txt         # Python dependencies
├── CLAUDE.md                # Developer documentation
├── BUILD_INSTALLER.bat      # Build script
├── CLEAN_OLD_BUILD.bat      # Cleanup script
├── FIX_AND_BUILD.bat        # Quick build script
└── Consolidated Data/       # Data storage folder
```

## Troubleshooting

### Slow startup
The first launch may take a few seconds while loading. A splash screen will display.

### Download not working
The application uses native Windows save dialogs. Make sure to select a valid save location.

### Upload fails
- Verify file format is .xlsx, .xls, or .csv
- Check that column headers match exactly (152 columns)
- Ensure file size is under 50MB

## Support

For issues or feature requests, contact Internal Audit department.
