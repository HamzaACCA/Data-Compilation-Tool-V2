"""
Data Analytical and Compilation Tool - Multi-Project Support
Supports multiple consolidation projects with dynamic dashboard columns
"""
import os
import sys
import io
import threading
import time
import json
from flask import Flask, request, render_template, jsonify, send_file
import pandas as pd
import numpy as np
from datetime import datetime
from werkzeug.utils import secure_filename
from functools import lru_cache
import xlsxwriter
import zipfile
from xml.sax.saxutils import escape as _xml_escape
from utils.logging import setup_logging, get_logger

# Fast Excel reader (Rust-based, ~9x faster than openpyxl)
try:
    from python_calamine import CalamineWorkbook
    HAS_CALAMINE = True
except ImportError:
    HAS_CALAMINE = False

# Memory cache for frequently accessed data
data_cache = {}
cache_timestamps = {}
columns_cache = {}  # Cache for column metadata (date_columns, numeric_columns)
CACHE_TTL = 300  # 5 minutes cache

# Background tasks tracking
background_tasks = {}
task_lock = threading.Lock()

# Import webview for native window (optional - not used in web deployment)
WEB_MODE = os.environ.get('RENDER') or os.environ.get('WEB_MODE')
HAS_WEBVIEW = False
if not WEB_MODE:
    try:
        import webview
        HAS_WEBVIEW = True
    except ImportError:
        pass

# Global reference to webview window
webview_window = None
is_maximized = False

# Determine the base path
if os.environ.get('RENDER'):
    # Running on Render - use persistent disk
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    APP_DIR = '/var/data'
elif getattr(sys, 'frozen', False):
    BASE_DIR = sys._MEIPASS
    EXE_DIR = os.path.dirname(sys.executable)
    APP_DIR = os.path.join(EXE_DIR, 'Data')
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    APP_DIR = os.path.join(BASE_DIR, 'Data')

os.makedirs(APP_DIR, exist_ok=True)
setup_logging(APP_DIR)
log = get_logger(__name__)

PROJECTS_DIR = os.path.join(APP_DIR, 'Projects')
os.makedirs(PROJECTS_DIR, exist_ok=True)

CONFIG_FILE = os.path.join(APP_DIR, 'config.json')

app = Flask(__name__,
            template_folder=os.path.join(BASE_DIR, 'templates'),
            static_folder=os.path.join(BASE_DIR, 'static'))

app.config['TEMPLATES_AUTO_RELOAD'] = True
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024

ALLOWED_EXTENSIONS = {'xlsx', 'xls', 'csv'}


def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    return {'current_project': None, 'projects': {}}


def save_config(config):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)


def get_project_path(project_name):
    return os.path.join(PROJECTS_DIR, secure_filename(project_name))


def get_project_files(project_name):
    project_path = get_project_path(project_name)
    return {
        'path': project_path,
        'uploads': os.path.join(project_path, 'uploads'),
        'pickle': os.path.join(project_path, 'consolidated_data.pkl'),
        'excel': os.path.join(project_path, 'consolidated_data.xlsx'),
        'settings': os.path.join(project_path, 'settings.json'),
        'upload_log': os.path.join(project_path, 'upload_log.json'),
        'audit_log': os.path.join(project_path, 'audit_log.json')
    }


def log_audit(project_name, action, details=''):
    """Add entry to audit log"""
    try:
        files = get_project_files(project_name)
        audit_log = []
        if os.path.exists(files['audit_log']):
            with open(files['audit_log'], 'r') as f:
                audit_log = json.load(f)

        audit_log.append({
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'action': action,
            'details': details
        })

        # Keep last 500 entries
        if len(audit_log) > 500:
            audit_log = audit_log[-500:]

        with open(files['audit_log'], 'w') as f:
            json.dump(audit_log, f, indent=2)
    except Exception as e:
        log.warning("audit log write failed: %s", e)


def load_upload_log(project_name):
    files = get_project_files(project_name)
    if os.path.exists(files['upload_log']):
        with open(files['upload_log'], 'r') as f:
            return json.load(f)
    return []


def save_upload_log(project_name, log):
    files = get_project_files(project_name)
    with open(files['upload_log'], 'w') as f:
        json.dump(log, f, indent=2)


def load_project_settings(project_name):
    files = get_project_files(project_name)
    if os.path.exists(files['settings']):
        with open(files['settings'], 'r') as f:
            return json.load(f)
    return {'top_columns': [], 'date_column': ''}


def save_project_settings(project_name, settings):
    files = get_project_files(project_name)
    with open(files['settings'], 'w') as f:
        json.dump(settings, f, indent=2)


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def get_cached_dataframe(project_name, force_reload=False):
    """Get dataframe from memory cache or load from disk"""
    global data_cache, cache_timestamps

    cache_key = f"df_{project_name}"
    files = get_project_files(project_name)

    # Check if cache is valid
    if not force_reload and cache_key in data_cache:
        if time.time() - cache_timestamps.get(cache_key, 0) < CACHE_TTL:
            # Check if file hasn't changed
            if os.path.exists(files['pickle']):
                file_mtime = os.path.getmtime(files['pickle'])
                if file_mtime <= cache_timestamps.get(f"{cache_key}_mtime", 0):
                    return data_cache[cache_key]

    # Load from disk
    if os.path.exists(files['pickle']):
        df = pd.read_pickle(files['pickle'])
        data_cache[cache_key] = df
        cache_timestamps[cache_key] = time.time()
        cache_timestamps[f"{cache_key}_mtime"] = os.path.getmtime(files['pickle'])
        return df
    elif os.path.exists(files['excel']):
        df = pd.read_excel(files['excel'])
        return df

    return None


def clear_cache(project_name=None):
    """Clear memory cache"""
    global data_cache, cache_timestamps, columns_cache
    if project_name:
        cache_key = f"df_{project_name}"
        data_cache.pop(cache_key, None)
        data_cache.pop(f"colstats_{project_name}", None)
        cache_timestamps.pop(cache_key, None)
        cache_timestamps.pop(f"{cache_key}_mtime", None)
        columns_cache.pop(project_name, None)
    else:
        data_cache.clear()
        cache_timestamps.clear()
        columns_cache.clear()


def optimize_dataframe(df):
    """Optimize dataframe memory usage"""
    for col in df.columns:
        col_type = df[col].dtype

        if col_type == 'object':
            # Convert to category if low cardinality
            num_unique = df[col].nunique()
            num_total = len(df[col])
            if num_unique / num_total < 0.5:  # Less than 50% unique
                df[col] = df[col].astype('category')

        elif col_type == 'int64':
            # Downcast integers
            df[col] = pd.to_numeric(df[col], downcast='integer')

        elif col_type == 'float64':
            # Downcast floats
            df[col] = pd.to_numeric(df[col], downcast='float')

    return df


def create_background_task(task_id, task_type, description):
    """Create a new background task"""
    with task_lock:
        background_tasks[task_id] = {
            'id': task_id,
            'type': task_type,
            'description': description,
            'status': 'running',
            'progress': 0,
            'started_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'completed_at': None,
            'result': None,
            'error': None
        }
    return task_id


def update_task_progress(task_id, progress, status=None):
    """Update task progress"""
    with task_lock:
        if task_id in background_tasks:
            background_tasks[task_id]['progress'] = progress
            if status:
                background_tasks[task_id]['status'] = status


def complete_task(task_id, result=None, error=None):
    """Mark task as complete"""
    with task_lock:
        if task_id in background_tasks:
            background_tasks[task_id]['status'] = 'error' if error else 'completed'
            background_tasks[task_id]['progress'] = 100
            background_tasks[task_id]['completed_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            background_tasks[task_id]['result'] = result
            background_tasks[task_id]['error'] = error


def _deduplicate_columns(columns):
    """Rename duplicate columns with .1, .2 suffix (matches pandas/openpyxl behavior)"""
    seen = {}
    result = []
    for col in columns:
        col_str = str(col) if col is not None else ''
        if col_str in seen:
            seen[col_str] += 1
            result.append(f"{col_str}.{seen[col_str]}")
        else:
            seen[col_str] = 0
            result.append(col_str)
    return result


def _read_excel_calamine(filepath_or_obj):
    """Read Excel file using calamine (Rust-based, ~9x faster than openpyxl)"""
    if isinstance(filepath_or_obj, str):
        wb = CalamineWorkbook.from_path(filepath_or_obj)
    else:
        wb = CalamineWorkbook.from_filelike(filepath_or_obj)
    sheet_name = wb.sheet_names[0]
    data = wb.get_sheet_by_name(sheet_name).to_python()
    if len(data) < 2:
        return pd.DataFrame()
    headers = _deduplicate_columns(data[0])
    rows = data[1:]
    return pd.DataFrame(rows, columns=headers)


def read_file_chunked(filepath, chunk_size=10000):
    """Read large files in chunks for memory efficiency"""
    ext = filepath.rsplit('.', 1)[1].lower()
    if ext == 'csv':
        chunks = pd.read_csv(filepath, chunksize=chunk_size)
        return pd.concat(chunks, ignore_index=True)
    else:
        if HAS_CALAMINE:
            return _read_excel_calamine(filepath)
        return pd.read_excel(filepath, engine='openpyxl')


def read_file(filepath_or_obj):
    # Determine extension from string path or file-like object
    if isinstance(filepath_or_obj, str):
        ext = filepath_or_obj.rsplit('.', 1)[1].lower()
        file_size = os.path.getsize(filepath_or_obj) if os.path.exists(filepath_or_obj) else 0
    else:
        ext = getattr(filepath_or_obj, 'filename', '').rsplit('.', 1)[-1].lower()
        file_size = 0

    if ext == 'csv':
        large_file = file_size > 50 * 1024 * 1024  # > 50MB
        if large_file:
            return read_file_chunked(filepath_or_obj)
        return pd.read_csv(filepath_or_obj)
    else:
        if HAS_CALAMINE:
            return _read_excel_calamine(filepath_or_obj)
        return pd.read_excel(filepath_or_obj, engine='openpyxl')


def _write_excel_fast(df, filepath):
    """Write DataFrame to Excel using raw XML generation (~3x faster than xlsxwriter)"""
    export_df = _prepare_export_df(df)
    _write_xlsx_raw([('Sheet1', export_df)], filepath)


# ── Raw XML Excel writer (~3x faster than xlsxwriter for large datasets) ──────

def _col_letter(idx):
    """Convert 0-based column index to Excel column letter (A, B, ... Z, AA, AB, ...)."""
    result = ''
    while True:
        result = chr(65 + idx % 26) + result
        idx = idx // 26 - 1
        if idx < 0:
            break
    return result

_COL_LETTERS = [_col_letter(i) for i in range(300)]


def _collect_strings(df):
    """Collect all unique string values from a DataFrame for shared string table."""
    strings = set(str(h) for h in df.columns)
    for c in range(df.shape[1]):
        if df.iloc[:, c].dtype.kind not in ('i', 'u', 'f'):
            arr = df.iloc[:, c].astype(str).replace(
                {'nan': '', 'None': '', '<NA>': '', 'NaT': ''}
            ).values
            strings.update(arr)
    strings.add('')
    return strings


def _df_to_sheet_xml(df, sst_index):
    """Convert a DataFrame to xlsx worksheet XML using a shared string index."""
    rows, cols = df.shape
    if cols == 0:
        return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                '<sheetData/></worksheet>')

    while len(_COL_LETTERS) < cols:
        _COL_LETTERS.append(_col_letter(len(_COL_LETTERS)))

    headers = [str(h) for h in df.columns]
    is_numeric = [df.iloc[:, c].dtype.kind in ('i', 'u', 'f') for c in range(cols)]

    col_data = []
    for c in range(cols):
        if is_numeric[c]:
            col_data.append(df.iloc[:, c].values)
        else:
            col_data.append(
                df.iloc[:, c].astype(str).replace(
                    {'nan': '', 'None': '', '<NA>': '', 'NaT': ''}
                ).values
            )

    parts = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<sheetData><row r="1">'
    ]
    for c in range(cols):
        parts.append(f'<c r="{_COL_LETTERS[c]}1" t="s"><v>{sst_index[headers[c]]}</v></c>')
    parts.append('</row>')

    for r in range(rows):
        r_num = r + 2
        parts.append(f'<row r="{r_num}">')
        for c in range(cols):
            cl = _COL_LETTERS[c]
            if is_numeric[c]:
                val = col_data[c][r]
                if pd.isna(val) or np.isinf(val):
                    parts.append(f'<c r="{cl}{r_num}" t="s"><v>{sst_index[""]}</v></c>')
                else:
                    parts.append(f'<c r="{cl}{r_num}"><v>{val}</v></c>')
            else:
                parts.append(f'<c r="{cl}{r_num}" t="s"><v>{sst_index[col_data[c][r]]}</v></c>')
        parts.append('</row>')

    parts.append('</sheetData></worksheet>')
    return ''.join(parts)


def _write_xlsx_raw(sheets_data, output):
    """Write multi-sheet xlsx using raw XML generation (~3x faster than xlsxwriter).

    Args:
        sheets_data: list of (sheet_name, DataFrame) tuples
        output: file path string or BytesIO object
    """
    all_strings = set()
    for _, df in sheets_data:
        all_strings.update(_collect_strings(df))

    sst = sorted(all_strings)
    sst_index = {s: i for i, s in enumerate(sst)}

    sst_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        f'count="0" uniqueCount="{len(sst)}">'
        + ''.join(f'<si><t>{_xml_escape(s)}</t></si>' for s in sst)
        + '</sst>'
    )

    ws_xmls = [_df_to_sheet_xml(df, sst_index) for _, df in sheets_data]

    n = len(sheets_data)
    ct_sheets = ''.join(
        f'<Override PartName="/xl/worksheets/sheet{i+1}.xml" '
        f'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        for i in range(n)
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        + ct_sheets +
        '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
        '<Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>'
        '</Types>'
    )
    wb_rels_sheets = ''.join(
        f'<Relationship Id="rId{i+1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i+1}.xml"/>'
        for i in range(n)
    )
    wb_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        + wb_rels_sheets +
        f'<Relationship Id="rId{n+1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
        f'<Relationship Id="rId{n+2}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings" Target="sharedStrings.xml"/>'
        '</Relationships>'
    )
    sheet_entries = ''.join(
        f'<sheet name="{_xml_escape(sheets_data[i][0])}" sheetId="{i+1}" r:id="rId{i+1}"/>'
        for i in range(n)
    )
    workbook_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f'<sheets>{sheet_entries}</sheets></workbook>'
    )
    rels_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
        '</Relationships>'
    )
    styles_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<fonts count="1"><font><sz val="11"/><name val="Calibri"/></font></fonts>'
        '<fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill></fills>'
        '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'
        '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
        '<cellXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/></cellXfs>'
        '</styleSheet>'
    )

    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('[Content_Types].xml', content_types)
        zf.writestr('_rels/.rels', rels_xml)
        zf.writestr('xl/_rels/workbook.xml.rels', wb_rels)
        zf.writestr('xl/workbook.xml', workbook_xml)
        zf.writestr('xl/styles.xml', styles_xml)
        zf.writestr('xl/sharedStrings.xml', sst_xml)
        for i, ws_xml in enumerate(ws_xmls):
            zf.writestr(f'xl/worksheets/sheet{i+1}.xml', ws_xml)


def _prepare_export_df(df):
    """Prepare a DataFrame for Excel export: format datetimes, convert categories."""
    export_df = df.copy()
    for col in export_df.columns:
        if pd.api.types.is_datetime64_any_dtype(export_df[col]):
            export_df[col] = export_df[col].dt.strftime('%d-%b-%Y').fillna('')
        elif export_df[col].dtype.name == 'category':
            export_df[col] = export_df[col].astype(str)
    return export_df


def generate_excel_cache(project_name):
    """Pre-generate Excel file in background for fast downloads"""
    try:
        files = get_project_files(project_name)
        if os.path.exists(files['pickle']):
            df = pd.read_pickle(files['pickle'])
            export_df = df[[c for c in df.columns if c != '_upload_id']]
            _write_excel_fast(export_df, files['excel'])
    except:
        pass  # Silently fail - Excel will be generated on demand if needed


def combine_files(project_name, new_file_path, upload_id):
    try:
        files = get_project_files(project_name)
        new_df = read_file(new_file_path)
        new_rows = len(new_df)

        # Optimize new dataframe
        new_df = optimize_dataframe(new_df)

        # Add upload_id to track which rows came from which upload
        new_df['_upload_id'] = upload_id

        if os.path.exists(files['pickle']):
            consolidated_df = pd.read_pickle(files['pickle'])
            # Check columns match (excluding _upload_id)
            new_cols = [c for c in new_df.columns if c != '_upload_id']
            existing_cols = [c for c in consolidated_df.columns if c != '_upload_id']
            if new_cols != existing_cols:
                return {'success': False, 'error': 'Column headers do not match!'}
            combined_df = pd.concat([consolidated_df, new_df], ignore_index=True, copy=False)
        elif os.path.exists(files['excel']):
            consolidated_df = pd.read_excel(files['excel'], engine='openpyxl')
            new_cols = [c for c in new_df.columns if c != '_upload_id']
            existing_cols = [c for c in consolidated_df.columns if c != '_upload_id']
            if new_cols != existing_cols:
                return {'success': False, 'error': 'Column headers do not match!'}
            if '_upload_id' not in consolidated_df.columns:
                consolidated_df['_upload_id'] = 'legacy'
            combined_df = pd.concat([consolidated_df, new_df], ignore_index=True, copy=False)
        else:
            combined_df = new_df

        # Optimize combined dataframe for large datasets
        if len(combined_df) > 10000:
            combined_df = optimize_dataframe(combined_df)

        combined_df.to_pickle(files['pickle'])

        # Clear cache so next read gets fresh data
        clear_cache(project_name)

        # Remove stale Excel cache (will be regenerated on download via fast writer)
        if os.path.exists(files['excel']):
            try:
                os.remove(files['excel'])
            except OSError:
                pass

        return {
            'success': True,
            'rows_added': new_rows,
            'total_rows': len(combined_df),
            'columns': len(combined_df.columns) - 1  # Exclude _upload_id from count
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/projects', methods=['GET'])
def get_projects():
    config = load_config()
    projects = []
    for name, info in config.get('projects', {}).items():
        projects.append({
            'name': name,
            'created': info.get('created', ''),
            'description': info.get('description', '')
        })
    return jsonify({
        'success': True,
        'projects': projects,
        'current_project': config.get('current_project')
    })


@app.route('/api/projects', methods=['POST'])
def create_project():
    data = request.json
    name = data.get('name', '').strip()
    description = data.get('description', '').strip()

    if not name:
        return jsonify({'success': False, 'error': 'Project name is required'}), 400

    config = load_config()
    if name in config.get('projects', {}):
        return jsonify({'success': False, 'error': 'Project already exists'}), 400

    project_path = get_project_path(name)
    os.makedirs(project_path, exist_ok=True)
    os.makedirs(os.path.join(project_path, 'uploads'), exist_ok=True)

    if 'projects' not in config:
        config['projects'] = {}
    config['projects'][name] = {
        'created': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'description': description
    }
    config['current_project'] = name
    save_config(config)

    save_project_settings(name, {'top_columns': [], 'date_column': ''})
    log_audit(name, 'PROJECT_CREATED', f'Project "{name}" created')

    return jsonify({'success': True, 'message': f'Project "{name}" created'})


@app.route('/api/projects/<name>', methods=['DELETE'])
def delete_project(name):
    config = load_config()
    if name not in config.get('projects', {}):
        return jsonify({'success': False, 'error': 'Project not found'}), 404

    import shutil
    project_path = get_project_path(name)
    if os.path.exists(project_path):
        shutil.rmtree(project_path)

    del config['projects'][name]
    if config.get('current_project') == name:
        config['current_project'] = list(config['projects'].keys())[0] if config['projects'] else None
    save_config(config)

    return jsonify({'success': True, 'message': f'Project "{name}" deleted'})


@app.route('/api/projects/<name>/select', methods=['POST'])
def select_project(name):
    config = load_config()
    if name not in config.get('projects', {}):
        return jsonify({'success': False, 'error': 'Project not found'}), 404

    config['current_project'] = name
    save_config(config)
    return jsonify({'success': True, 'message': f'Switched to project "{name}"'})


@app.route('/upload', methods=['POST'])
def upload_file():
    config = load_config()
    project_name = config.get('current_project')

    if not project_name:
        return jsonify({'success': False, 'error': 'No project selected. Create or select a project first.'}), 400

    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'No file provided'}), 400

    files = request.files.getlist('file')
    if not files or all(f.filename == '' for f in files):
        return jsonify({'success': False, 'error': 'No file selected'}), 400

    project_files = get_project_files(project_name)
    total_rows_added = 0
    files_processed = 0
    failed_files = []
    upload_log = load_upload_log(project_name)

    try:
        for file in files:
            if file.filename == '':
                continue

            if not allowed_file(file.filename):
                failed_files.append(f"{file.filename} (invalid type)")
                continue

            filename = secure_filename(file.filename)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
            upload_id = f"{timestamp}_{filename}"
            filepath = os.path.join(project_files['uploads'], upload_id)
            file.save(filepath)

            result = combine_files(project_name, filepath, upload_id)

            if result['success']:
                total_rows_added += result['rows_added']
                files_processed += 1
                # Add to upload log
                upload_log.append({
                    'id': upload_id,
                    'original_name': file.filename,
                    'upload_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'rows': result['rows_added'],
                    'file_path': filepath
                })
            else:
                failed_files.append(f"{file.filename} ({result['error']})")
                # Remove the saved file if combine failed
                if os.path.exists(filepath):
                    os.remove(filepath)

        # Save upload log
        save_upload_log(project_name, upload_log)

        # Log audit
        if files_processed > 0:
            log_audit(project_name, 'FILES_UPLOADED', f'{files_processed} file(s), {total_rows_added} rows added')

        if files_processed > 0:
            response = {
                'success': True,
                'files_processed': files_processed,
                'rows_added': total_rows_added,
                'total_rows': result.get('total_rows', 0),
                'columns': result.get('columns', 0)
            }
            if failed_files:
                response['failed_files'] = failed_files
            return jsonify(response), 200
        else:
            return jsonify({
                'success': False,
                'error': 'No files were processed',
                'failed_files': failed_files
            }), 400

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/uploads', methods=['GET'])
def get_uploads():
    try:
        config = load_config()
        project_name = config.get('current_project')

        if not project_name:
            return jsonify({'success': False, 'error': 'No project selected'})

        # Pagination parameters
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        per_page = min(per_page, 100)  # Max 100 per page

        upload_log = load_upload_log(project_name)
        reversed_log = list(reversed(upload_log))

        # Calculate pagination
        total = len(reversed_log)
        start = (page - 1) * per_page
        end = start + per_page
        paginated = reversed_log[start:end]

        return jsonify({
            'success': True,
            'uploads': paginated,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total,
                'pages': (total + per_page - 1) // per_page
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/uploads/<upload_id>', methods=['DELETE'])
def delete_upload(upload_id):
    try:
        config = load_config()
        project_name = config.get('current_project')

        if not project_name:
            return jsonify({'success': False, 'error': 'No project selected'}), 400

        project_files = get_project_files(project_name)
        upload_log = load_upload_log(project_name)

        # Find the upload in log
        upload_entry = None
        for entry in upload_log:
            if entry['id'] == upload_id:
                upload_entry = entry
                break

        if not upload_entry:
            return jsonify({'success': False, 'error': 'Upload not found'}), 404

        # Remove rows from consolidated data
        rows_removed = 0
        if os.path.exists(project_files['pickle']):
            df = pd.read_pickle(project_files['pickle'])
            rows_before = len(df)
            df = df[df['_upload_id'] != upload_id]
            rows_after = len(df)
            rows_removed = rows_before - rows_after

            if len(df) > 0:
                df.to_pickle(project_files['pickle'])
            else:
                # If no rows left, delete the pickle file
                os.remove(project_files['pickle'])

            # Clear cache so next read gets fresh data
            clear_cache(project_name)

            # Remove stale Excel cache
            if os.path.exists(project_files['excel']):
                try:
                    os.remove(project_files['excel'])
                except OSError:
                    pass

        # Delete the uploaded file
        if os.path.exists(upload_entry['file_path']):
            os.remove(upload_entry['file_path'])

        # Remove from upload log
        upload_log = [e for e in upload_log if e['id'] != upload_id]
        save_upload_log(project_name, upload_log)

        log_audit(project_name, 'UPLOAD_DELETED', f'Deleted "{upload_entry["original_name"]}", {rows_removed} rows removed')

        return jsonify({
            'success': True,
            'message': f'Upload deleted. {rows_removed} rows removed from consolidated data.',
            'rows_removed': rows_removed
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/stats')
def get_stats():
    try:
        config = load_config()
        project_name = config.get('current_project')

        if not project_name:
            return jsonify({'exists': False, 'no_project': True})

        files = get_project_files(project_name)
        df = get_cached_dataframe(project_name)
        if df is None:
            return jsonify({'exists': False, 'project': project_name})

        # Determine file for size/mtime
        file_to_check = files['pickle'] if os.path.exists(files['pickle']) else files['excel']

        # Exclude _upload_id from columns list
        visible_columns = [c for c in df.columns if c != '_upload_id']
        return jsonify({
            'exists': True,
            'project': project_name,
            'total_rows': len(df),
            'total_columns': len(visible_columns),
            'columns': visible_columns,
            'file_size': os.path.getsize(file_to_check),
            'last_modified': datetime.fromtimestamp(os.path.getmtime(file_to_check)).strftime('%Y-%m-%d %H:%M:%S')
        })
    except Exception as e:
        return jsonify({'exists': False, 'error': str(e)})


@app.route('/api/columns')
def get_columns():
    try:
        config = load_config()
        project_name = config.get('current_project')

        if not project_name:
            return jsonify({'success': False, 'error': 'No project selected'})

        # Check columns cache first
        if project_name in columns_cache:
            return jsonify(columns_cache[project_name])

        df = get_cached_dataframe(project_name)
        if df is None:
            return jsonify({'success': False, 'error': 'No data in project', 'columns': []})

        # Return simple list of column names for dashboard (exclude internal _upload_id)
        columns = [c for c in df.columns if c != '_upload_id']

        # Detect date columns: already datetime, datetime.date objects, or parseable as dates
        import datetime as _dt
        import warnings
        date_columns = []
        for c in columns:
            if pd.api.types.is_datetime64_any_dtype(df[c]):
                date_columns.append(c)
            elif df[c].dtype == 'object' or df[c].dtype.name == 'category':
                sample = df[c].dropna().head(10)  # Reduced from 20 to 10
                if len(sample) > 0:
                    first_val = sample.iloc[0]
                    # Check if values are datetime.date/datetime objects (not time-only)
                    if isinstance(first_val, _dt.date) and not isinstance(first_val, _dt.time):
                        date_columns.append(c)
                    elif isinstance(first_val, str):
                        # Skip bare numbers that falsely parse as years (e.g. "2034")
                        if not all(s.strip().isdigit() and len(s.strip()) <= 4 for s in sample.astype(str)):
                            with warnings.catch_warnings():
                                warnings.simplefilter("ignore")
                                parsed = pd.to_datetime(sample.astype(str), errors='coerce')
                            if parsed.notna().sum() >= len(sample) * 0.8:
                                date_columns.append(c)

        # Detect numeric columns
        numeric_columns = [c for c in columns if pd.api.types.is_numeric_dtype(df[c])]

        result = {
            'success': True,
            'columns': columns,
            'date_columns': date_columns,
            'numeric_columns': numeric_columns
        }
        # Cache the result
        columns_cache[project_name] = result
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e), 'columns': []})


@app.route('/api/settings', methods=['GET'])
def get_settings():
    try:
        config = load_config()
        project_name = config.get('current_project')

        if not project_name:
            return jsonify({'success': False, 'error': 'No project selected'})

        settings = load_project_settings(project_name)
        return jsonify({
            'success': True,
            'settings': {
                'date_column': settings.get('date_column', ''),
                'top_columns': settings.get('top_columns', [])
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/settings', methods=['POST'])
def save_settings():
    try:
        config = load_config()
        project_name = config.get('current_project')

        if not project_name:
            return jsonify({'success': False, 'error': 'No project selected'})

        data = request.json
        settings = load_project_settings(project_name)
        settings['top_columns'] = data.get('top_columns', [])
        settings['date_column'] = data.get('date_column', '')
        save_project_settings(project_name, settings)

        return jsonify({'success': True, 'message': 'Settings saved'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/download')
def download_consolidated():
    try:
        config = load_config()
        project_name = config.get('current_project')

        if not project_name:
            return jsonify({'success': False, 'error': 'No project selected'}), 400

        file_format = request.args.get('format', 'xlsx')
        files = get_project_files(project_name)

        if not os.path.exists(files['pickle']) and not os.path.exists(files['excel']):
            return jsonify({'success': False, 'error': 'No consolidated file exists yet'}), 404

        df = get_cached_dataframe(project_name)
        if df is None:
            return jsonify({'success': False, 'error': 'No consolidated file exists yet'}), 404

        export_df = df[[c for c in df.columns if c != '_upload_id']]

        # CSV download (fast - streaming, no temp file)
        if file_format == 'csv':
            csv_buffer = io.BytesIO()
            export_df.to_csv(csv_buffer, index=False)
            csv_buffer.seek(0)
            response = send_file(csv_buffer, mimetype='text/csv', as_attachment=True,
                                 download_name=f'{project_name}_consolidated.csv')
            response.headers['Content-Length'] = csv_buffer.getbuffer().nbytes
            return response

        # Excel download - check if cached Excel exists and is up-to-date
        if os.path.exists(files['excel']) and os.path.exists(files['pickle']):
            excel_time = os.path.getmtime(files['excel'])
            pickle_time = os.path.getmtime(files['pickle'])
            if excel_time >= pickle_time:
                return send_file(files['excel'], as_attachment=True, download_name=f'{project_name}_consolidated.xlsx')

        # Generate Excel cache on disk (for future fast re-downloads)
        _write_excel_fast(export_df, files['excel'])
        return send_file(files['excel'], as_attachment=True, download_name=f'{project_name}_consolidated.xlsx')
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500




@app.route('/api/data-summary')
def get_data_summary():
    """Get summary statistics for current project data"""
    try:
        config = load_config()
        project_name = config.get('current_project')

        if not project_name:
            return jsonify({'success': False, 'error': 'No project selected'})

        files = get_project_files(project_name)
        df = get_cached_dataframe(project_name)
        if df is None:
            return jsonify({'success': False, 'error': 'No data available'})

        # Determine file size from disk
        if os.path.exists(files['pickle']):
            file_size = os.path.getsize(files['pickle'])
        elif os.path.exists(files['excel']):
            file_size = os.path.getsize(files['excel'])
        else:
            file_size = 0

        # Exclude internal columns
        visible_cols = [c for c in df.columns if c != '_upload_id']

        # Get column info
        column_info = []
        for col in visible_cols:
            non_null_pct = round((df[col].notna().sum() / len(df)) * 100, 1)
            dtype = str(df[col].dtype)
            if dtype == 'object':
                dtype = 'Text'
            elif 'int' in dtype:
                dtype = 'Integer'
            elif 'float' in dtype:
                dtype = 'Decimal'
            elif 'datetime' in dtype:
                dtype = 'Date'
            column_info.append({
                'name': col,
                'dtype': dtype,
                'non_null': non_null_pct
            })

        # Get file count from upload log
        upload_log = load_upload_log(project_name)

        # Format file size
        if file_size > 1024 * 1024:
            size_str = f"{file_size / (1024*1024):.1f} MB"
        elif file_size > 1024:
            size_str = f"{file_size / 1024:.1f} KB"
        else:
            size_str = f"{file_size} B"

        return jsonify({
            'success': True,
            'total_rows': len(df),
            'total_columns': len(visible_cols),
            'file_count': len(upload_log),
            'file_size': size_str,
            'column_info': column_info
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/upload-mapped', methods=['POST'])
def upload_mapped_file():
    """Upload file with column mapping"""
    try:
        config = load_config()
        project_name = config.get('current_project')

        if not project_name:
            return jsonify({'success': False, 'error': 'No project selected'}), 400

        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'No file provided'}), 400

        file = request.files['file']
        mapping_json = request.form.get('mapping', '{}')
        mapping = json.loads(mapping_json)

        if not mapping:
            return jsonify({'success': False, 'error': 'No column mapping provided'}), 400

        # Read and map columns
        df = read_file(file)
        df = df.rename(columns=mapping)

        # Keep only mapped columns
        mapped_cols = list(mapping.values())
        df = df[mapped_cols]

        project_files = get_project_files(project_name)
        upload_log = load_upload_log(project_name)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        upload_id = f"{timestamp}_{secure_filename(file.filename)}"

        # Optimize dataframe memory usage
        df = optimize_dataframe(df)

        df['_upload_id'] = upload_id

        # Combine with existing data
        if os.path.exists(project_files['pickle']):
            existing_df = pd.read_pickle(project_files['pickle'])
            combined_df = pd.concat([existing_df, df], ignore_index=True)
        else:
            combined_df = df

        combined_df.to_pickle(project_files['pickle'])

        # Clear cache so next read gets fresh data
        clear_cache(project_name)

        # Remove stale Excel cache (will be regenerated on download via fast writer)
        if os.path.exists(project_files['excel']):
            try:
                os.remove(project_files['excel'])
            except OSError:
                pass

        # Update upload log
        upload_log.append({
            'id': upload_id,
            'original_name': file.filename,
            'upload_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'rows': len(df),
            'file_path': '',
            'mapped': True
        })
        save_upload_log(project_name, upload_log)

        log_audit(project_name, 'FILES_UPLOADED', f'Mapped upload: {file.filename}, {len(df)} rows')

        return jsonify({
            'success': True,
            'rows_added': len(df),
            'total_rows': len(combined_df)
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/audit-log')
def get_audit_log():
    """Get audit log for current project"""
    try:
        config = load_config()
        project_name = config.get('current_project')

        if not project_name:
            return jsonify({'success': False, 'error': 'No project selected'})

        files = get_project_files(project_name)

        if os.path.exists(files['audit_log']):
            with open(files['audit_log'], 'r') as f:
                audit_log = json.load(f)
            return jsonify({
                'success': True,
                'audit_log': list(reversed(audit_log))  # Newest first
            })
        else:
            return jsonify({
                'success': True,
                'audit_log': []
            })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/background-tasks')
def get_background_tasks():
    """Get status of background tasks"""
    with task_lock:
        # Return only recent tasks (last 10)
        tasks = list(background_tasks.values())[-10:]
        return jsonify({
            'success': True,
            'tasks': tasks
        })


@app.route('/api/background-tasks/<task_id>')
def get_task_status(task_id):
    """Get status of specific background task"""
    with task_lock:
        if task_id in background_tasks:
            return jsonify({
                'success': True,
                'task': background_tasks[task_id]
            })
        return jsonify({'success': False, 'error': 'Task not found'}), 404


@app.route('/api/clear-cache', methods=['POST'])
def api_clear_cache():
    """Clear memory cache"""
    try:
        config = load_config()
        project_name = config.get('current_project')
        clear_cache(project_name)
        return jsonify({'success': True, 'message': 'Cache cleared'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/memory-stats')
def get_memory_stats():
    """Get memory usage statistics"""
    try:
        cache_size = sum(
            v.memory_usage(deep=True).sum() if isinstance(v, pd.DataFrame) else sys.getsizeof(v)
            for v in data_cache.values()
        )
        cache_items = len(data_cache)

        return jsonify({
            'success': True,
            'cache_items': cache_items,
            'cache_size_mb': round(cache_size / (1024 * 1024), 2),
            'active_tasks': sum(1 for t in background_tasks.values() if t['status'] == 'running')
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})






@app.route('/reset', methods=['POST'])
def reset_consolidated():
    try:
        config = load_config()
        project_name = config.get('current_project')

        if not project_name:
            return jsonify({'success': False, 'error': 'No project selected'}), 400

        files = get_project_files(project_name)
        deleted = False

        if os.path.exists(files['excel']):
            os.remove(files['excel'])
            deleted = True
        if os.path.exists(files['pickle']):
            os.remove(files['pickle'])
            deleted = True

        # Clear upload log
        if os.path.exists(files['upload_log']):
            os.remove(files['upload_log'])

        # Clear uploaded files
        if os.path.exists(files['uploads']):
            import shutil
            shutil.rmtree(files['uploads'])
            os.makedirs(files['uploads'], exist_ok=True)

        # Clear cache so next read doesn't return stale data
        clear_cache(project_name)

        if deleted:
            log_audit(project_name, 'DATA_RESET', 'All data reset')
            return jsonify({'success': True, 'message': 'All data has been reset'})
        else:
            return jsonify({'success': False, 'error': 'No consolidated file exists'}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')


@app.route('/api/date-range')
def get_date_range():
    try:
        config = load_config()
        project_name = config.get('current_project')

        if not project_name:
            return jsonify({'success': False, 'error': 'No project selected'})

        settings = load_project_settings(project_name)
        date_column = settings.get('date_column', '')

        df = get_cached_dataframe(project_name)
        if df is None:
            return jsonify({'success': False, 'error': 'No consolidated file exists', 'needs_setup': True})

        if date_column and date_column in df.columns:
            df[date_column] = pd.to_datetime(df[date_column], errors='coerce')
            min_date = df[date_column].min()
            max_date = df[date_column].max()

            return jsonify({
                'success': True,
                'date_column': date_column,
                'min_date': min_date.strftime('%Y-%m-%d') if pd.notna(min_date) else None,
                'max_date': max_date.strftime('%Y-%m-%d') if pd.notna(max_date) else None
            })
        else:
            # No date column configured, return without dates
            return jsonify({'success': False, 'error': 'No date column configured', 'needs_setup': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/dashboard-stats')
def get_dashboard_stats():
    try:
        config = load_config()
        project_name = config.get('current_project')

        if not project_name:
            return jsonify({'success': False, 'error': 'No project selected'})

        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')

        settings = load_project_settings(project_name)

        df = get_cached_dataframe(project_name)
        if df is None:
            return jsonify({'success': False, 'error': 'No consolidated file exists'}), 404

        date_column = settings.get('date_column', '')
        if date_column and date_column in df.columns and start_date and end_date:
            df[date_column] = pd.to_datetime(df[date_column], errors='coerce')
            start = pd.to_datetime(start_date)
            end = pd.to_datetime(end_date)
            filtered_df = df[(df[date_column] >= start) & (df[date_column] <= end)]
        else:
            filtered_df = df

        top_data = {}
        top_columns = settings.get('top_columns', [])

        for col_config in top_columns:
            col_name = col_config.get('column') if isinstance(col_config, dict) else col_config
            if col_name and col_name in filtered_df.columns:
                top_data[col_name] = filtered_df[col_name].value_counts().head(10).to_dict()

        stats = {
            'success': True,
            'project': project_name,
            'total_records': len(filtered_df),
            'date_range': {'start': start_date, 'end': end_date},
            'date_column': date_column,
            'top_data': top_data
        }

        return jsonify(stats)

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/compare-column')
def compare_column():
    """Compare a column's value counts between two periods"""
    try:
        config = load_config()
        project_name = config.get('current_project')

        if not project_name:
            return jsonify({'success': False, 'error': 'No project selected'})

        column = request.args.get('column')
        start1 = request.args.get('start1')
        end1 = request.args.get('end1')
        start2 = request.args.get('start2')
        end2 = request.args.get('end2')

        if not column or not start1 or not end1 or not start2 or not end2:
            return jsonify({'success': False, 'error': 'Missing parameters'}), 400

        settings = load_project_settings(project_name)

        df = get_cached_dataframe(project_name)
        if df is None:
            return jsonify({'success': False, 'error': 'No data available'}), 404

        if column not in df.columns:
            return jsonify({'success': False, 'error': f'Column "{column}" not found'}), 404

        date_column = settings.get('date_column', '')

        if date_column and date_column in df.columns:
            df[date_column] = pd.to_datetime(df[date_column], errors='coerce')
            df1 = df[(df[date_column] >= pd.to_datetime(start1)) & (df[date_column] <= pd.to_datetime(end1))]
            df2 = df[(df[date_column] >= pd.to_datetime(start2)) & (df[date_column] <= pd.to_datetime(end2))]
        else:
            df1 = df
            df2 = df

        counts1 = df1[column].value_counts()
        counts2 = df2[column].value_counts()

        all_values = set(counts1.index.tolist()) | set(counts2.index.tolist())

        comparison = []
        for val in all_values:
            c1 = int(counts1.get(val, 0))
            c2 = int(counts2.get(val, 0))
            change_pct = round(((c2 - c1) / c1 * 100), 1) if c1 > 0 else round(c2 * 100.0, 1)
            comparison.append({
                'value': str(val) if val is not None else '',
                'count1': c1,
                'count2': c2,
                'change_pct': change_pct
            })

        comparison.sort(key=lambda x: x['count1'] + x['count2'], reverse=True)

        return jsonify({
            'success': True,
            'column': column,
            'period1': {'total': len(df1)},
            'period2': {'total': len(df2)},
            'comparison': comparison[:25]
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/download-comparison')
def download_comparison():
    """Download full comparison data as Excel"""
    try:
        config = load_config()
        project_name = config.get('current_project')

        if not project_name:
            return jsonify({'success': False, 'error': 'No project selected'}), 400

        column = request.args.get('column')
        start1 = request.args.get('start1')
        end1 = request.args.get('end1')
        start2 = request.args.get('start2')
        end2 = request.args.get('end2')

        if not column or not start1 or not end1 or not start2 or not end2:
            return jsonify({'success': False, 'error': 'Missing parameters'}), 400

        settings = load_project_settings(project_name)

        df = get_cached_dataframe(project_name)
        if df is None:
            return jsonify({'success': False, 'error': 'No data available'}), 404

        if column not in df.columns:
            return jsonify({'success': False, 'error': f'Column "{column}" not found'}), 404

        date_column = settings.get('date_column', '')

        if date_column and date_column in df.columns:
            df[date_column] = pd.to_datetime(df[date_column], errors='coerce')
            df1 = df[(df[date_column] >= pd.to_datetime(start1)) & (df[date_column] <= pd.to_datetime(end1))]
            df2 = df[(df[date_column] >= pd.to_datetime(start2)) & (df[date_column] <= pd.to_datetime(end2))]
        else:
            df1 = df
            df2 = df

        counts1 = df1[column].value_counts()
        counts2 = df2[column].value_counts()

        all_values = set(counts1.index.tolist()) | set(counts2.index.tolist())

        def _fmt_date(d):
            """Format YYYY-MM-DD to DD-MMM-YYYY"""
            try:
                return pd.to_datetime(d).strftime('%d-%b-%Y')
            except:
                return d

        p1_label = f'Period 1 ({_fmt_date(start1)} to {_fmt_date(end1)})'
        p2_label = f'Period 2 ({_fmt_date(start2)} to {_fmt_date(end2)})'

        rows = []
        for val in all_values:
            c1 = int(counts1.get(val, 0))
            c2 = int(counts2.get(val, 0))
            change_pct = round(((c2 - c1) / c1 * 100), 1) if c1 > 0 else round(c2 * 100.0, 1)
            rows.append({
                'Value': str(val) if val is not None else '',
                p1_label: c1,
                p2_label: c2,
                'Change %': change_pct
            })

        rows.sort(key=lambda x: x[p1_label] + x[p2_label], reverse=True)

        # Build the Data sheet: all transaction rows from both periods
        export_cols = [c for c in df.columns if c != '_upload_id']
        data_df1 = df1[export_cols].copy()
        data_df1.insert(0, 'Period', p1_label)
        data_df2 = df2[export_cols].copy()
        data_df2.insert(0, 'Period', p2_label)
        data_df = pd.concat([data_df1, data_df2], ignore_index=True)
        data_df = data_df.sort_values(by=[column, 'Period'], ignore_index=True)

        summary_df = pd.DataFrame({
            'Metric': ['Period 1 Total Records', 'Period 2 Total Records', 'Column Compared'],
            'Value': [str(len(df1)), str(len(df2)), column]
        })
        comparison_df = pd.DataFrame(rows)

        output = io.BytesIO()
        _write_xlsx_raw([
            ('Summary', summary_df),
            ('Comparison', _prepare_export_df(comparison_df)),
            ('Data', _prepare_export_df(data_df))
        ], output)
        output.seek(0)
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=f'Comparison_{column}_{start1}_to_{end2}.xlsx'
        )

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/advanced-analysis')
def advanced_analysis():
    """Advanced comparative analysis with group-by aggregation across two periods"""
    try:
        config = load_config()
        project_name = config.get('current_project')

        if not project_name:
            return jsonify({'success': False, 'error': 'No project selected'})

        date_column = request.args.get('date_column')
        group_column = request.args.get('group_column')
        value_column = request.args.get('value_column')
        agg_method = request.args.get('agg_method', 'sum')
        start1 = request.args.get('start1')
        end1 = request.args.get('end1')
        start2 = request.args.get('start2')
        end2 = request.args.get('end2')

        if not all([date_column, group_column, value_column, start1, end1, start2, end2]):
            return jsonify({'success': False, 'error': 'Missing required parameters'}), 400

        df = get_cached_dataframe(project_name)
        if df is None:
            return jsonify({'success': False, 'error': 'No data available'}), 404

        for col in [date_column, group_column, value_column]:
            if col not in df.columns:
                return jsonify({'success': False, 'error': f'Column "{col}" not found'}), 404

        df[date_column] = pd.to_datetime(df[date_column], errors='coerce')
        df[value_column] = pd.to_numeric(df[value_column], errors='coerce')

        df1 = df[(df[date_column] >= pd.to_datetime(start1)) & (df[date_column] <= pd.to_datetime(end1))]
        df2 = df[(df[date_column] >= pd.to_datetime(start2)) & (df[date_column] <= pd.to_datetime(end2))]

        agg_map = {'sum': 'sum', 'count': 'count', 'average': 'mean', 'min': 'min', 'max': 'max'}
        agg_func = agg_map.get(agg_method.lower(), 'sum')

        if len(df1) == 0 and len(df2) == 0:
            return jsonify({'success': False, 'error': 'No data found for either period'})

        agg1 = df1.groupby(group_column)[value_column].agg(agg_func) if len(df1) > 0 else pd.Series(dtype=float)
        agg2 = df2.groupby(group_column)[value_column].agg(agg_func) if len(df2) > 0 else pd.Series(dtype=float)

        all_groups = set(agg1.index.tolist()) | set(agg2.index.tolist())

        comparison = []
        for group in all_groups:
            v1 = float(agg1.get(group, 0)) if group in agg1.index else 0
            v2 = float(agg2.get(group, 0)) if group in agg2.index else 0
            if pd.isna(v1):
                v1 = 0
            if pd.isna(v2):
                v2 = 0
            change_pct = round(((v2 - v1) / v1 * 100), 1) if v1 != 0 else round(v2 * 100.0, 1)
            comparison.append({
                'group': str(group) if group is not None else '',
                'value1': round(v1, 2),
                'value2': round(v2, 2),
                'change_pct': change_pct
            })

        comparison.sort(key=lambda x: x['value1'] + x['value2'], reverse=True)

        return jsonify({
            'success': True,
            'group_column': group_column,
            'value_column': value_column,
            'agg_method': agg_method,
            'period1': {'start': start1, 'end': end1, 'rows': len(df1)},
            'period2': {'start': start2, 'end': end2, 'rows': len(df2)},
            'comparison': comparison[:50]
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/download-advanced-analysis')
def download_advanced_analysis():
    """Download advanced analysis as Excel (3 sheets: Summary, Comparison, Data)"""
    try:
        config = load_config()
        project_name = config.get('current_project')

        if not project_name:
            return jsonify({'success': False, 'error': 'No project selected'}), 400

        date_column = request.args.get('date_column')
        group_column = request.args.get('group_column')
        value_column = request.args.get('value_column')
        agg_method = request.args.get('agg_method', 'sum')
        start1 = request.args.get('start1')
        end1 = request.args.get('end1')
        start2 = request.args.get('start2')
        end2 = request.args.get('end2')

        if not all([date_column, group_column, value_column, start1, end1, start2, end2]):
            return jsonify({'success': False, 'error': 'Missing required parameters'}), 400

        df = get_cached_dataframe(project_name)
        if df is None:
            return jsonify({'success': False, 'error': 'No data available'}), 404

        df[date_column] = pd.to_datetime(df[date_column], errors='coerce')
        df[value_column] = pd.to_numeric(df[value_column], errors='coerce')

        df1 = df[(df[date_column] >= pd.to_datetime(start1)) & (df[date_column] <= pd.to_datetime(end1))]
        df2 = df[(df[date_column] >= pd.to_datetime(start2)) & (df[date_column] <= pd.to_datetime(end2))]

        agg_map = {'sum': 'sum', 'count': 'count', 'average': 'mean', 'min': 'min', 'max': 'max'}
        agg_func = agg_map.get(agg_method.lower(), 'sum')

        agg1 = df1.groupby(group_column)[value_column].agg(agg_func) if len(df1) > 0 else pd.Series(dtype=float)
        agg2 = df2.groupby(group_column)[value_column].agg(agg_func) if len(df2) > 0 else pd.Series(dtype=float)

        all_groups = set(agg1.index.tolist()) | set(agg2.index.tolist())

        def _fmt_date(d):
            try:
                return pd.to_datetime(d).strftime('%d-%b-%Y')
            except:
                return d

        p1_label = f'Period 1 ({_fmt_date(start1)} to {_fmt_date(end1)})'
        p2_label = f'Period 2 ({_fmt_date(start2)} to {_fmt_date(end2)})'

        rows = []
        for group in all_groups:
            v1 = float(agg1.get(group, 0)) if group in agg1.index else 0
            v2 = float(agg2.get(group, 0)) if group in agg2.index else 0
            if pd.isna(v1):
                v1 = 0
            if pd.isna(v2):
                v2 = 0
            change_pct = round(((v2 - v1) / v1 * 100), 1) if v1 != 0 else round(v2 * 100.0, 1)
            rows.append({
                group_column: str(group) if group is not None else '',
                p1_label: round(v1, 2),
                p2_label: round(v2, 2),
                'Change %': change_pct
            })

        rows.sort(key=lambda x: x[p1_label] + x[p2_label], reverse=True)

        # Build Data sheet: raw transaction rows from both periods
        export_cols = [c for c in df.columns if c != '_upload_id']
        data_df1 = df1[export_cols].copy()
        data_df1.insert(0, 'Period', p1_label)
        data_df2 = df2[export_cols].copy()
        data_df2.insert(0, 'Period', p2_label)
        data_df = pd.concat([data_df1, data_df2], ignore_index=True)
        data_df = data_df.sort_values(by=[group_column, 'Period'], ignore_index=True)

        summary_df = pd.DataFrame({
            'Metric': ['Group Column', 'Value Column', 'Aggregation Method',
                        'Period 1', 'Period 1 Rows', 'Period 2', 'Period 2 Rows'],
            'Value': [group_column, value_column, agg_method.upper(),
                      f'{_fmt_date(start1)} to {_fmt_date(end1)}', str(len(df1)),
                      f'{_fmt_date(start2)} to {_fmt_date(end2)}', str(len(df2))]
        })
        comparison_df = pd.DataFrame(rows)

        output = io.BytesIO()
        _write_xlsx_raw([
            ('Summary', summary_df),
            ('Comparison', _prepare_export_df(comparison_df)),
            ('Data', _prepare_export_df(data_df))
        ], output)
        output.seek(0)
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=f'Advanced_Analysis_{group_column}_{agg_method}_{start1}_to_{end2}.xlsx'
        )

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/column-stats')
def get_column_stats():
    """Get detailed statistics for each column"""
    try:
        config = load_config()
        project_name = config.get('current_project')

        if not project_name:
            return jsonify({'success': False, 'error': 'No project selected'})

        # Check cache
        cache_key = f"colstats_{project_name}"
        if cache_key in data_cache:
            return jsonify(data_cache[cache_key])

        df = get_cached_dataframe(project_name)
        if df is None:
            return jsonify({'success': False, 'error': 'No data available'})

        total_rows = len(df)
        columns_stats = []

        # Pre-compute notna counts for all columns at once (vectorized)
        notna_counts = df.notna().sum()

        for col in df.columns:
            if col == '_upload_id':
                continue

            fill_pct = round((notna_counts[col] / total_rows) * 100, 1)
            unique_count = df[col].nunique()

            # Get sample values
            sample = df[col].dropna().head(3).astype(str).tolist()
            sample_str = ', '.join(sample[:3])
            if len(sample_str) > 50:
                sample_str = sample_str[:50] + '...'

            # Determine type
            dtype = str(df[col].dtype)
            if dtype == 'object':
                dtype_display = 'Text'
            elif 'int' in dtype:
                dtype_display = 'Integer'
            elif 'float' in dtype:
                dtype_display = 'Decimal'
            elif 'datetime' in dtype:
                dtype_display = 'Date'
            elif 'bool' in dtype:
                dtype_display = 'Boolean'
            else:
                dtype_display = dtype

            columns_stats.append({
                'name': col,
                'dtype': dtype_display,
                'fill_pct': fill_pct,
                'unique_count': unique_count,
                'sample_values': sample_str
            })

        result = {
            'success': True,
            'columns': columns_stats,
            'total_rows': total_rows
        }
        # Cache the result
        data_cache[cache_key] = result
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/download-column-stats')
def download_column_stats():
    """Download column analysis as Excel"""
    try:
        config = load_config()
        project_name = config.get('current_project')

        if not project_name:
            return "No project selected", 404

        df = get_cached_dataframe(project_name)
        if df is None:
            return "No data available", 404

        rows = []
        for col in df.columns:
            if col == '_upload_id':
                continue
            fill_pct = round((df[col].notna().sum() / len(df)) * 100, 1)
            unique_count = df[col].nunique()
            has_duplicates = 'Yes' if unique_count < len(df) else 'No'

            dtype = str(df[col].dtype)
            if dtype == 'object':
                dtype_display = 'Text'
            elif 'int' in dtype:
                dtype_display = 'Integer'
            elif 'float' in dtype:
                dtype_display = 'Decimal'
            elif 'datetime' in dtype:
                dtype_display = 'Date'
            elif 'bool' in dtype:
                dtype_display = 'Boolean'
            else:
                dtype_display = dtype

            sample = df[col].dropna().head(3).astype(str).tolist()
            sample_str = ', '.join(sample[:3])

            rows.append({
                'Column': col,
                'Type': dtype_display,
                'Filled %': fill_pct,
                'Unique Values': unique_count,
                'Duplicates': has_duplicates,
                'Sample Values': sample_str
            })

        stats_df = pd.DataFrame(rows)

        output = io.BytesIO()
        wb = xlsxwriter.Workbook(output, {'nan_inf_to_errors': True})

        # Column Analysis sheet
        ws_stats = wb.add_worksheet('Column Analysis')
        header_fmt = wb.add_format({'bold': True, 'bg_color': '#34495e', 'font_color': 'white', 'border': 1})
        stat_headers = list(stats_df.columns)
        for col_idx, col_name in enumerate(stat_headers):
            ws_stats.write(0, col_idx, col_name, header_fmt)
        for r_idx, row_data in enumerate(stats_df.values.tolist(), start=1):
            ws_stats.write_row(r_idx, 0, row_data)
        ws_stats.set_column(0, 0, 30)
        ws_stats.set_column(1, 1, 12)
        ws_stats.set_column(2, 2, 12)
        ws_stats.set_column(3, 3, 15)
        ws_stats.set_column(4, 4, 12)
        ws_stats.set_column(5, 5, 40)

        # Summary sheet
        ws_summary = wb.add_worksheet('Summary')
        bold = wb.add_format({'bold': True})
        ws_summary.write(0, 0, 'Project', bold)
        ws_summary.write(0, 1, project_name)
        ws_summary.write(1, 0, 'Total Rows', bold)
        ws_summary.write(1, 1, len(df))
        ws_summary.write(2, 0, 'Total Columns', bold)
        ws_summary.write(2, 1, len(rows))
        ws_summary.set_column(0, 0, 20)
        ws_summary.set_column(1, 1, 30)

        wb.close()

        output.seek(0)
        safe_name = "".join(c for c in project_name if c.isalnum() or c in (' ', '-', '_')).strip()
        filename = f"{safe_name}_Column_Analysis.xlsx"

        return send_file(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                         as_attachment=True, download_name=filename)
    except Exception as e:
        return str(e), 500


@app.route('/api/trend-line-data')
def get_trend_line_data():
    """Get monthly trend line data grouped by a column"""
    try:
        config = load_config()
        project_name = config.get('current_project')

        if not project_name:
            return jsonify({'success': False, 'error': 'No project selected'})

        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        group_column = request.args.get('group_column', '')
        value_column = request.args.get('value_column', '')
        agg_method = request.args.get('agg_method', 'count').lower()
        top_n = int(request.args.get('top_n', '10'))
        specific_groups = request.args.getlist('specific_groups')
        baseline_month = request.args.get('baseline_month', '')
        trend_start_date = request.args.get('trend_start_date', '')
        trend_end_date = request.args.get('trend_end_date', '')

        if not group_column:
            return jsonify({'success': False, 'error': 'No group column specified'})

        settings = load_project_settings(project_name)
        df = get_cached_dataframe(project_name)
        if df is None:
            return jsonify({'success': False, 'error': 'No data available'})

        date_column = settings.get('date_column', '')
        if not date_column or date_column not in df.columns:
            return jsonify({'success': False, 'error': 'No date column configured'})

        if group_column not in df.columns:
            return jsonify({'success': False, 'error': f'Column "{group_column}" not found'})

        df = df.copy()
        df[date_column] = pd.to_datetime(df[date_column], errors='coerce')

        # Use trend-specific dates if provided, else fall back to main filter dates
        eff_start = trend_start_date if trend_start_date else start_date
        eff_end = trend_end_date if trend_end_date else end_date

        if eff_start and eff_end:
            s = pd.to_datetime(eff_start)
            e = pd.to_datetime(eff_end)
            df = df[(df[date_column] >= s) & (df[date_column] <= e)]

        if len(df) == 0:
            return jsonify({'success': False, 'error': 'No data in selected range'})

        # Convert group column safely (handles categorical)
        df[group_column] = df[group_column].astype(str).fillna('(blank)').replace('nan', '(blank)')

        # Mode: return available groups list for searchable dropdown
        if top_n == 0 and not specific_groups:
            freq = df[group_column].value_counts()
            available = freq.index.tolist()[:500]
            return jsonify({'success': True, 'available_groups': available})

        # Determine which groups to include
        if top_n == 0 and specific_groups:
            selected_groups = specific_groups
        else:
            # Top N by total
            if agg_method == 'sum' and value_column and value_column in df.columns:
                df['_val'] = pd.to_numeric(df[value_column], errors='coerce').fillna(0)
                group_ranks = df.groupby(group_column)['_val'].sum().sort_values(ascending=False)
            else:
                group_ranks = df[group_column].value_counts()
            selected_groups = group_ranks.head(top_n).index.tolist()

        # Build month column
        df['_month'] = df[date_column].dt.to_period('M').astype(str)

        # Aggregate
        if agg_method == 'sum' and value_column and value_column in df.columns:
            df['_val'] = pd.to_numeric(df[value_column], errors='coerce').fillna(0)
            filtered = df[df[group_column].isin(selected_groups)]
            pivot = filtered.groupby(['_month', group_column])['_val'].sum().unstack(fill_value=0)
        else:
            filtered = df[df[group_column].isin(selected_groups)]
            pivot = filtered.groupby(['_month', group_column]).size().unstack(fill_value=0)

        months = sorted(pivot.index.tolist())

        # Build series and totals
        series = {}
        group_totals = {}
        for g in selected_groups:
            if g in pivot.columns:
                vals = [round(float(pivot.loc[m, g]), 2) if m in pivot.index else 0 for m in months]
            else:
                vals = [0] * len(months)
            series[g] = vals
            group_totals[g] = round(sum(vals), 2)

        # Sort groups by total descending
        groups_sorted = sorted(selected_groups, key=lambda g: group_totals.get(g, 0), reverse=True)

        result = {
            'success': True,
            'months': months,
            'groups': groups_sorted,
            'series': series,
            'group_totals': group_totals
        }

        # Compute movement series if baseline_month is provided and valid
        if baseline_month and baseline_month in months:
            movement_series = {}
            baseline_values = {}
            for g in groups_sorted:
                vals = series[g]
                bi = months.index(baseline_month)
                base_val = vals[bi]
                baseline_values[g] = base_val
                movement_series[g] = [round(v - base_val, 2) for v in vals]
            result['movement_series'] = movement_series
            result['baseline_month'] = baseline_month
            result['baseline_values'] = baseline_values

        return jsonify(result)

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/download-trend-line')
def download_trend_line():
    """Download trend line data as Excel (2-3 sheets: Summary, Trend Data, Movement Data)"""
    try:
        config = load_config()
        project_name = config.get('current_project')

        if not project_name:
            return jsonify({'success': False, 'error': 'No project selected'}), 400

        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        group_column = request.args.get('group_column', '')
        value_column = request.args.get('value_column', '')
        agg_method = request.args.get('agg_method', 'count').lower()
        top_n = int(request.args.get('top_n', '10'))
        specific_groups = request.args.getlist('specific_groups')
        baseline_month = request.args.get('baseline_month', '')
        trend_start_date = request.args.get('trend_start_date', '')
        trend_end_date = request.args.get('trend_end_date', '')

        if not group_column:
            return jsonify({'success': False, 'error': 'No group column specified'}), 400

        settings = load_project_settings(project_name)
        df = get_cached_dataframe(project_name)
        if df is None:
            return jsonify({'success': False, 'error': 'No data available'}), 404

        date_column = settings.get('date_column', '')
        if not date_column or date_column not in df.columns:
            return jsonify({'success': False, 'error': 'No date column configured'}), 400

        if group_column not in df.columns:
            return jsonify({'success': False, 'error': f'Column "{group_column}" not found'}), 400

        df = df.copy()
        df[date_column] = pd.to_datetime(df[date_column], errors='coerce')

        # Use trend-specific dates if provided, else fall back to main filter dates
        eff_start = trend_start_date if trend_start_date else start_date
        eff_end = trend_end_date if trend_end_date else end_date

        if eff_start and eff_end:
            s = pd.to_datetime(eff_start)
            e = pd.to_datetime(eff_end)
            df = df[(df[date_column] >= s) & (df[date_column] <= e)]

        if len(df) == 0:
            return jsonify({'success': False, 'error': 'No data in selected range'}), 400

        df[group_column] = df[group_column].astype(str).fillna('(blank)').replace('nan', '(blank)')

        # Determine groups
        if top_n == 0 and specific_groups:
            selected_groups = specific_groups
        else:
            if agg_method == 'sum' and value_column and value_column in df.columns:
                df['_val'] = pd.to_numeric(df[value_column], errors='coerce').fillna(0)
                group_ranks = df.groupby(group_column)['_val'].sum().sort_values(ascending=False)
            else:
                group_ranks = df[group_column].value_counts()
            n = top_n if top_n > 0 else 10
            selected_groups = group_ranks.head(n).index.tolist()

        df['_month'] = df[date_column].dt.to_period('M').astype(str)

        if agg_method == 'sum' and value_column and value_column in df.columns:
            df['_val'] = pd.to_numeric(df[value_column], errors='coerce').fillna(0)
            filtered = df[df[group_column].isin(selected_groups)]
            pivot = filtered.groupby(['_month', group_column])['_val'].sum().unstack(fill_value=0)
        else:
            filtered = df[df[group_column].isin(selected_groups)]
            pivot = filtered.groupby(['_month', group_column]).size().unstack(fill_value=0)

        months = sorted(pivot.index.tolist())
        groups_in_pivot = [g for g in selected_groups if g in pivot.columns]

        # Sheet 1: Summary
        agg_label = agg_method.upper()
        val_label = value_column if value_column and agg_method == 'sum' else '(Row Count)'
        summary_rows = [
            {'Field': 'Project', 'Value': project_name},
            {'Field': 'Date Range', 'Value': f'{eff_start} to {eff_end}'},
            {'Field': 'Group Column', 'Value': group_column},
            {'Field': 'Value Column', 'Value': val_label},
            {'Field': 'Aggregation', 'Value': agg_label},
            {'Field': 'Groups', 'Value': len(groups_in_pivot)},
            {'Field': 'Months', 'Value': len(months)},
        ]
        if baseline_month and baseline_month in months:
            summary_rows.append({'Field': 'Baseline Month', 'Value': baseline_month})
        summary_data = pd.DataFrame(summary_rows)

        # Sheet 2: Trend Data (months as rows, groups as columns)
        trend_rows = []
        for m in months:
            row = {'Month': m}
            for g in groups_in_pivot:
                row[g] = round(float(pivot.loc[m, g]), 2) if m in pivot.index and g in pivot.columns else 0
            trend_rows.append(row)
        trend_df = pd.DataFrame(trend_rows)

        sheets = [
            ('Summary', summary_data),
            ('Raw Data', trend_df)
        ]

        # Sheet 3: Movement Data (if baseline_month provided)
        if baseline_month and baseline_month in months:
            movement_rows = []
            for m in months:
                row = {'Month': m}
                for g in groups_in_pivot:
                    raw_val = round(float(pivot.loc[m, g]), 2) if m in pivot.index and g in pivot.columns else 0
                    base_val = round(float(pivot.loc[baseline_month, g]), 2) if baseline_month in pivot.index and g in pivot.columns else 0
                    row[g] = round(raw_val - base_val, 2)
                movement_rows.append(row)
            movement_df = pd.DataFrame(movement_rows)
            sheets.append(('Movement Data', movement_df))

        output = io.BytesIO()
        _write_xlsx_raw(sheets, output)
        output.seek(0)

        def _fmt(d):
            try:
                return pd.to_datetime(d).strftime('%d%b%Y')
            except:
                return d

        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=f'Trend_Line_{agg_label}_{_fmt(eff_start)}_to_{_fmt(eff_end)}.xlsx'
        )

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/download-filtered')
def download_filtered():
    try:
        config = load_config()
        project_name = config.get('current_project')

        if not project_name:
            return jsonify({'success': False, 'error': 'No project selected'}), 400

        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        file_format = request.args.get('format', 'csv')  # Default to CSV for speed

        settings = load_project_settings(project_name)

        df = get_cached_dataframe(project_name)
        if df is None:
            return jsonify({'success': False, 'error': 'No consolidated file exists'}), 404

        date_column = settings.get('date_column', '')

        if date_column and date_column in df.columns and start_date and end_date:
            df[date_column] = pd.to_datetime(df[date_column], errors='coerce')
            start = pd.to_datetime(start_date)
            end = pd.to_datetime(end_date)
            filtered_df = df[(df[date_column] >= start) & (df[date_column] <= end)]
        else:
            filtered_df = df

        # Exclude _upload_id from export
        export_df = filtered_df[[c for c in filtered_df.columns if c != '_upload_id']]

        if file_format == 'xlsx':
            output = io.BytesIO()
            _write_xlsx_raw([('Data', _prepare_export_df(export_df))], output)
            output.seek(0)
            response = send_file(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                                 as_attachment=True, download_name=f'{project_name}_{start_date}_to_{end_date}.xlsx')
            response.headers['Content-Length'] = output.getbuffer().nbytes
            return response
        else:
            csv_buffer = io.BytesIO()
            export_df.to_csv(csv_buffer, index=False)
            csv_buffer.seek(0)
            response = send_file(csv_buffer, mimetype='text/csv', as_attachment=True,
                                 download_name=f'{project_name}_{start_date}_to_{end_date}.csv')
            response.headers['Content-Length'] = csv_buffer.getbuffer().nbytes
            return response

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/download-top10')
def download_top10():
    """Download actual data rows for Top 10 values of a specific column as Excel"""
    try:
        config = load_config()
        project_name = config.get('current_project')

        if not project_name:
            return jsonify({'success': False, 'error': 'No project selected'}), 400

        column = request.args.get('column')
        display_name = request.args.get('display_name', column)
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')

        if not column:
            return jsonify({'success': False, 'error': 'No column specified'}), 400

        settings = load_project_settings(project_name)

        df = get_cached_dataframe(project_name)
        if df is None:
            return jsonify({'success': False, 'error': 'No consolidated file exists'}), 404

        date_column = settings.get('date_column', '')

        # Filter by date range
        if date_column and date_column in df.columns and start_date and end_date:
            df[date_column] = pd.to_datetime(df[date_column], errors='coerce')
            start = pd.to_datetime(start_date)
            end = pd.to_datetime(end_date)
            filtered_df = df[(df[date_column] >= start) & (df[date_column] <= end)]
        else:
            filtered_df = df

        # Get Top 10 values for the column
        if column not in filtered_df.columns:
            return jsonify({'success': False, 'error': f'Column {column} not found'}), 404

        top10_values = filtered_df[column].value_counts().head(10).index.tolist()

        # Get all rows where column value is in Top 10
        top10_data = filtered_df[filtered_df[column].isin(top10_values)].copy()

        # Exclude _upload_id from export
        export_columns = [c for c in top10_data.columns if c != '_upload_id']
        top10_data = top10_data[export_columns]

        # Add a rank column based on the Top 10 order
        rank_map = {val: idx + 1 for idx, val in enumerate(top10_values)}
        top10_data['Top10_Rank'] = top10_data[column].map(rank_map)

        # Sort by rank
        top10_data = top10_data.sort_values('Top10_Rank')

        # Move rank column to first position
        cols = ['Top10_Rank'] + [c for c in top10_data.columns if c != 'Top10_Rank']
        top10_data = top10_data[cols]

        # Save to Excel with summary sheet
        summary_df = pd.DataFrame({
            'Rank': range(1, len(top10_values) + 1),
            display_name: top10_values,
            'Count': [len(top10_data[top10_data[column] == val]) for val in top10_values]
        })

        output = io.BytesIO()
        _write_xlsx_raw([
            ('Summary', _prepare_export_df(summary_df)),
            ('Data', _prepare_export_df(top10_data))
        ], output)
        output.seek(0)
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=f'Top10_{display_name}_{start_date}_to_{end_date}.xlsx'
        )

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# PyWebView API Class
class Api:
    def minimize_window(self):
        global webview_window
        try:
            webview_window.minimize()
            return {'success': True}
        except Exception as e:
            log.error("Minimize error: %s", e)
            return {'success': False, 'error': str(e)}

    def maximize_window(self):
        global webview_window, is_maximized
        try:
            if is_maximized:
                webview_window.restore()
                is_maximized = False
            else:
                webview_window.maximize()
                is_maximized = True
            return {'success': True, 'maximized': is_maximized}
        except Exception as e:
            log.error("Maximize error: %s", e)
            return {'success': False, 'error': str(e)}

    def close_window(self):
        global webview_window
        try:
            webview_window.destroy()
            return {'success': True}
        except Exception as e:
            log.error("Close error: %s", e)
            return {'success': False, 'error': str(e)}

    def get_data_path(self):
        """Return the data directory path for user reference"""
        try:
            config = load_config()
            project_name = config.get('current_project', '')
            project_path = get_project_path(project_name) if project_name else ''
            return {
                'success': True,
                'app_dir': APP_DIR,
                'projects_dir': PROJECTS_DIR,
                'current_project_path': project_path
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def save_consolidated_file(self):
        global webview_window
        try:
            project_name = load_config().get('current_project', 'consolidated')

            # Show dialog immediately - offer both CSV and Excel
            result = webview_window.create_file_dialog(
                webview.SAVE_DIALOG,
                save_filename=f'{project_name}_data.csv',
                file_types=('CSV Files (*.csv)', 'Excel Files (*.xlsx)', 'All Files (*.*)')
            )

            if not result:
                return {'success': False, 'error': 'Save cancelled'}

            save_path = result[0] if isinstance(result, (tuple, list)) else result

            # Load data from cache
            df = get_cached_dataframe(project_name)
            if df is None:
                return {'success': False, 'error': 'No data to export'}

            export_df = df[[c for c in df.columns if c != '_upload_id']]

            # Save based on file extension
            if save_path.lower().endswith('.csv'):
                export_df.to_csv(save_path, index=False)
                return {'success': True, 'message': f'CSV saved! ({len(export_df)} records)'}
            else:
                if not save_path.lower().endswith('.xlsx'):
                    save_path += '.xlsx'
                _write_excel_fast(export_df, save_path)
                return {'success': True, 'message': f'Excel saved! ({len(export_df)} records)'}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def save_filtered_file(self, start_date, end_date):
        global webview_window
        try:
            project_name = load_config().get('current_project', 'filtered')

            # Show dialog immediately - offer both CSV and Excel
            result = webview_window.create_file_dialog(
                webview.SAVE_DIALOG,
                save_filename=f'{project_name}_{start_date}_to_{end_date}.csv',
                file_types=('CSV Files (*.csv)', 'Excel Files (*.xlsx)', 'All Files (*.*)')
            )

            if not result:
                return {'success': False, 'error': 'Save cancelled'}

            save_path = result[0] if isinstance(result, (tuple, list)) else result
            settings = load_project_settings(project_name)

            df = get_cached_dataframe(project_name)
            if df is None:
                return {'success': False, 'error': 'No data to export'}

            date_column = settings.get('date_column', '')

            if date_column and date_column in df.columns:
                df[date_column] = pd.to_datetime(df[date_column], errors='coerce')
                start = pd.to_datetime(start_date)
                end = pd.to_datetime(end_date)
                filtered_df = df[(df[date_column] >= start) & (df[date_column] <= end)]
            else:
                filtered_df = df

            if len(filtered_df) == 0:
                return {'success': False, 'error': 'No data found for selected date range'}

            export_df = filtered_df[[c for c in filtered_df.columns if c != '_upload_id']]

            # Save based on file extension
            if save_path.lower().endswith('.csv'):
                export_df.to_csv(save_path, index=False)
                return {'success': True, 'message': f'CSV saved! ({len(export_df)} records)'}
            else:
                if not save_path.lower().endswith('.xlsx'):
                    save_path += '.xlsx'
                _write_excel_fast(export_df, save_path)
                return {'success': True, 'message': f'Excel saved! ({len(export_df)} records)'}
        except Exception as e:
            return {'success': False, 'error': str(e)}


def start_server():
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False, threaded=True)


def show_splash_screen():
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {
                margin: 0; padding: 0;
                display: flex; justify-content: center; align-items: center;
                height: 100vh; background: #2c3e50;
                font-family: 'Segoe UI', Tahoma, sans-serif;
            }
            .splash { text-align: center; color: white; }
            .title { font-size: 2em; margin-bottom: 10px; font-weight: bold; }
            .subtitle { font-size: 1em; opacity: 0.8; margin-bottom: 30px; }
            .spinner {
                border: 4px solid rgba(255,255,255,0.3);
                border-top: 4px solid white;
                border-radius: 50%; width: 40px; height: 40px;
                animation: spin 1s linear infinite; margin: 0 auto 20px;
            }
            @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
            .loading-text { font-size: 0.9em; opacity: 0.7; }
        </style>
    </head>
    <body>
        <div class="splash">
            <div class="title">Data Analytical and Compilation Tool</div>
            <div class="subtitle">Multi-Project Support</div>
            <div class="spinner"></div>
            <div class="loading-text">Loading...</div>
        </div>
    </body>
    </html>
    '''


def wait_for_server(timeout=30):
    import urllib.request
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            urllib.request.urlopen('http://127.0.0.1:5000/stats', timeout=1)
            return True
        except:
            time.sleep(0.2)
    return False


if __name__ == '__main__':
    log.info("Data Analytical and Compilation Tool — Multi-Project Support")
    log.info("Data Directory: %s", APP_DIR)
    log.info("Projects Directory: %s", PROJECTS_DIR)

    if HAS_WEBVIEW:
        api = Api()

        # Create window with resizable=True from the start (required for maximize to work)
        webview_window = webview.create_window(
            'Data Analytical and Compilation Tool',
            html=show_splash_screen(),
            width=500, height=300,
            resizable=True, frameless=True,
            min_size=(500, 300),
            js_api=api
        )

        def load_main_app():
            global webview_window
            server_thread = threading.Thread(target=start_server, daemon=True)
            server_thread.start()

            if wait_for_server():
                webview_window.load_url('http://127.0.0.1:5000')
                # Resize to main app size
                webview_window.resize(1200, 800)
                # Move window to center of screen
                try:
                    webview_window.move(100, 50)
                except:
                    pass
            else:
                webview_window.load_html('<h1>Error: Failed to start server</h1>')

        webview.start(load_main_app)
    else:
        server_thread = threading.Thread(target=start_server, daemon=True)
        server_thread.start()
        time.sleep(2)
        import webbrowser
        webbrowser.open('http://127.0.0.1:5000')
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass

    log.info("Application closed.")
