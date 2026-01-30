"""
Data Analytical and Compilation Tool - Multi-Project Support
Supports multiple consolidation projects with dynamic dashboard columns
"""
import os
import sys
import threading
import time
import json
from flask import Flask, request, render_template, jsonify, send_file
import pandas as pd
import numpy as np
from datetime import datetime
from werkzeug.utils import secure_filename
from functools import lru_cache

# Fast Excel reader (Rust-based, ~9x faster than openpyxl)
try:
    from python_calamine import CalamineWorkbook
    HAS_CALAMINE = True
except ImportError:
    HAS_CALAMINE = False

# Memory cache for frequently accessed data
data_cache = {}
cache_timestamps = {}
CACHE_TTL = 300  # 5 minutes cache

# Background tasks tracking
background_tasks = {}
task_lock = threading.Lock()

# Import webview for native window (optional - not used in web deployment)
import os
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
    except:
        pass  # Silently fail - audit log is not critical


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
    global data_cache, cache_timestamps
    if project_name:
        cache_key = f"df_{project_name}"
        data_cache.pop(cache_key, None)
        cache_timestamps.pop(cache_key, None)
        cache_timestamps.pop(f"{cache_key}_mtime", None)
    else:
        data_cache.clear()
        cache_timestamps.clear()


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
    """Write DataFrame to Excel using xlsxwriter directly (bypasses pandas overhead, ~2.3x faster)"""
    import xlsxwriter
    wb = xlsxwriter.Workbook(filepath, {'constant_memory': True})
    ws = wb.add_worksheet()
    headers = list(df.columns)
    for col_idx, h in enumerate(headers):
        ws.write(0, col_idx, h)
    for row_idx, row in enumerate(df.values.tolist(), start=1):
        ws.write_row(row_idx, 0, row)
    wb.close()


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

        # Optimize combined dataframe periodically
        if len(combined_df) % 10000 == 0:
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
                if os.path.exists(project_files['excel']):
                    os.remove(project_files['excel'])

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

        if os.path.exists(files['pickle']):
            df = pd.read_pickle(files['pickle'])
            file_to_check = files['pickle']
        elif os.path.exists(files['excel']):
            df = pd.read_excel(files['excel'])
            file_to_check = files['excel']
        else:
            return jsonify({'exists': False, 'project': project_name})

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

        files = get_project_files(project_name)

        if os.path.exists(files['pickle']):
            df = pd.read_pickle(files['pickle'])
        elif os.path.exists(files['excel']):
            df = pd.read_excel(files['excel'])
        else:
            return jsonify({'success': False, 'error': 'No data in project', 'columns': []})

        # Return simple list of column names for dashboard (exclude internal _upload_id)
        columns = [c for c in df.columns if c != '_upload_id']

        # Detect date columns: already datetime, or parseable as dates
        date_columns = []
        for c in columns:
            if pd.api.types.is_datetime64_any_dtype(df[c]):
                date_columns.append(c)
            elif df[c].dtype == 'object':
                sample = df[c].dropna().head(20)
                if len(sample) > 0:
                    parsed = pd.to_datetime(sample, errors='coerce')
                    if parsed.notna().sum() >= len(sample) * 0.8:
                        date_columns.append(c)

        return jsonify({
            'success': True,
            'columns': columns,
            'date_columns': date_columns
        })
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

        # CSV download (fast - ~2s)
        if file_format == 'csv':
            if os.path.exists(files['pickle']):
                df = pd.read_pickle(files['pickle'])
            else:
                df = pd.read_excel(files['excel'])
            export_df = df[[c for c in df.columns if c != '_upload_id']]
            csv_path = files['excel'].replace('.xlsx', '.csv')
            export_df.to_csv(csv_path, index=False)
            return send_file(csv_path, as_attachment=True, download_name=f'{project_name}_consolidated.csv')

        # Excel download - check if cached Excel exists and is up-to-date
        if os.path.exists(files['excel']) and os.path.exists(files['pickle']):
            excel_time = os.path.getmtime(files['excel'])
            pickle_time = os.path.getmtime(files['pickle'])
            if excel_time >= pickle_time:
                return send_file(files['excel'], as_attachment=True, download_name=f'{project_name}_consolidated.xlsx')

        # Generate Excel if no cache or cache is stale
        if os.path.exists(files['pickle']):
            df = pd.read_pickle(files['pickle'])
            export_df = df[[c for c in df.columns if c != '_upload_id']]
            _write_excel_fast(export_df, files['excel'])
            return send_file(files['excel'], as_attachment=True, download_name=f'{project_name}_consolidated.xlsx')
        elif os.path.exists(files['excel']):
            return send_file(files['excel'], as_attachment=True, download_name=f'{project_name}_consolidated.xlsx')
        else:
            return jsonify({'success': False, 'error': 'No consolidated file exists yet'}), 404
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

        if os.path.exists(files['pickle']):
            df = pd.read_pickle(files['pickle'])
            file_size = os.path.getsize(files['pickle'])
        elif os.path.exists(files['excel']):
            df = pd.read_excel(files['excel'])
            file_size = os.path.getsize(files['excel'])
        else:
            return jsonify({'success': False, 'error': 'No data available'})

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

        df['_upload_id'] = upload_id

        # Combine with existing data
        if os.path.exists(project_files['pickle']):
            existing_df = pd.read_pickle(project_files['pickle'])
            combined_df = pd.concat([existing_df, df], ignore_index=True)
        else:
            combined_df = df

        combined_df.to_pickle(project_files['pickle'])

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
        import sys

        cache_size = sum(sys.getsizeof(v) for v in data_cache.values())
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

        if deleted:
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

        files = get_project_files(project_name)
        settings = load_project_settings(project_name)
        date_column = settings.get('date_column', '')

        if os.path.exists(files['pickle']):
            df = pd.read_pickle(files['pickle'])
        elif os.path.exists(files['excel']):
            df = pd.read_excel(files['excel'])
        else:
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

        files = get_project_files(project_name)
        settings = load_project_settings(project_name)

        if os.path.exists(files['pickle']):
            df = pd.read_pickle(files['pickle'])
        elif os.path.exists(files['excel']):
            df = pd.read_excel(files['excel'])
        else:
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

        files = get_project_files(project_name)
        settings = load_project_settings(project_name)

        if os.path.exists(files['pickle']):
            df = pd.read_pickle(files['pickle'])
        elif os.path.exists(files['excel']):
            df = pd.read_excel(files['excel'])
        else:
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
            change_pct = ((c2 - c1) / c1 * 100) if c1 > 0 else (100.0 if c2 > 0 else 0.0)
            comparison.append({
                'value': str(val) if val is not None else '',
                'count1': c1,
                'count2': c2,
                'change_pct': round(change_pct, 1)
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

        files = get_project_files(project_name)
        settings = load_project_settings(project_name)

        if os.path.exists(files['pickle']):
            df = pd.read_pickle(files['pickle'])
        elif os.path.exists(files['excel']):
            df = pd.read_excel(files['excel'])
        else:
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
            change_pct = ((c2 - c1) / c1 * 100) if c1 > 0 else (100.0 if c2 > 0 else 0.0)
            rows.append({
                'Value': str(val) if val is not None else '',
                p1_label: c1,
                p2_label: c2,
                'Change %': round(change_pct, 1)
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

        import io
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            summary_df = pd.DataFrame({
                'Metric': ['Period 1 Total Records', 'Period 2 Total Records', 'Column Compared'],
                'Value': [len(df1), len(df2), column]
            })
            summary_df.to_excel(writer, index=False, sheet_name='Summary')

            comparison_df = pd.DataFrame(rows)
            comparison_df.to_excel(writer, index=False, sheet_name='Comparison')

            data_df.to_excel(writer, index=False, sheet_name='Data')

            workbook = writer.book
            for sheet_name in ['Summary', 'Comparison', 'Data']:
                worksheet = writer.sheets[sheet_name]
                if sheet_name == 'Summary':
                    sheet_df = summary_df
                elif sheet_name == 'Comparison':
                    sheet_df = comparison_df
                else:
                    sheet_df = data_df
                for i, col_name in enumerate(sheet_df.columns):
                    max_len = max(sheet_df[col_name].astype(str).map(len).max(), len(str(col_name))) + 2
                    worksheet.set_column(i, i, min(max_len, 50))

        output.seek(0)
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=f'Comparison_{column}_{start1}_to_{end2}.xlsx'
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

        files = get_project_files(project_name)

        if os.path.exists(files['pickle']):
            df = pd.read_pickle(files['pickle'])
        elif os.path.exists(files['excel']):
            df = pd.read_excel(files['excel'])
        else:
            return jsonify({'success': False, 'error': 'No data available'})

        columns_stats = []
        for col in df.columns:
            if col == '_upload_id':
                continue

            fill_pct = round((df[col].notna().sum() / len(df)) * 100, 1)
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

        return jsonify({
            'success': True,
            'columns': columns_stats,
            'total_rows': len(df)
        })
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

        files = get_project_files(project_name)

        if os.path.exists(files['pickle']):
            df = pd.read_pickle(files['pickle'])
        elif os.path.exists(files['excel']):
            df = pd.read_excel(files['excel'])
        else:
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

        import io
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            stats_df.to_excel(writer, sheet_name='Column Analysis', index=False)
            workbook = writer.book
            worksheet = writer.sheets['Column Analysis']

            header_fmt = workbook.add_format({'bold': True, 'bg_color': '#34495e', 'font_color': 'white', 'border': 1})
            for col_idx, col_name in enumerate(stats_df.columns):
                worksheet.write(0, col_idx, col_name, header_fmt)

            worksheet.set_column('A:A', 30)
            worksheet.set_column('B:B', 12)
            worksheet.set_column('C:C', 12)
            worksheet.set_column('D:D', 15)
            worksheet.set_column('E:E', 12)
            worksheet.set_column('F:F', 40)

            # Summary row
            summary_sheet = workbook.add_worksheet('Summary')
            bold = workbook.add_format({'bold': True})
            summary_sheet.write('A1', 'Project', bold)
            summary_sheet.write('B1', project_name)
            summary_sheet.write('A2', 'Total Rows', bold)
            summary_sheet.write('B2', len(df))
            summary_sheet.write('A3', 'Total Columns', bold)
            summary_sheet.write('B3', len(rows))
            summary_sheet.set_column('A:A', 20)
            summary_sheet.set_column('B:B', 30)

        output.seek(0)
        safe_name = "".join(c for c in project_name if c.isalnum() or c in (' ', '-', '_')).strip()
        filename = f"{safe_name}_Column_Analysis.xlsx"

        return send_file(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                         as_attachment=True, download_name=filename)
    except Exception as e:
        return str(e), 500


@app.route('/api/trend-analysis')
def get_trend_analysis():
    """Get monthly trend data for the date range"""
    try:
        config = load_config()
        project_name = config.get('current_project')

        if not project_name:
            return jsonify({'success': False, 'error': 'No project selected'})

        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')

        files = get_project_files(project_name)
        settings = load_project_settings(project_name)

        if os.path.exists(files['pickle']):
            df = pd.read_pickle(files['pickle'])
        elif os.path.exists(files['excel']):
            df = pd.read_excel(files['excel'])
        else:
            return jsonify({'success': False, 'error': 'No data available'})

        date_column = settings.get('date_column', '')

        if not date_column or date_column not in df.columns:
            return jsonify({'success': False, 'error': 'No date column configured'})

        df[date_column] = pd.to_datetime(df[date_column], errors='coerce')

        if start_date and end_date:
            start = pd.to_datetime(start_date)
            end = pd.to_datetime(end_date)
            df = df[(df[date_column] >= start) & (df[date_column] <= end)]

        # Group by month
        df['_month'] = df[date_column].dt.to_period('M')
        monthly_counts = df.groupby('_month').size().reset_index(name='count')
        monthly_counts['_month'] = monthly_counts['_month'].astype(str)

        monthly_data = [{'month': row['_month'], 'count': int(row['count'])} for _, row in monthly_counts.iterrows()]

        return jsonify({
            'success': True,
            'monthly_counts': monthly_data,
            'total': int(df.shape[0]),
            'average': float(df.shape[0] / len(monthly_data)) if monthly_data else 0
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


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

        files = get_project_files(project_name)
        settings = load_project_settings(project_name)

        if os.path.exists(files['pickle']):
            df = pd.read_pickle(files['pickle'])
        elif os.path.exists(files['excel']):
            df = pd.read_excel(files['excel'])
        else:
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
            temp_file = os.path.join(files['path'], f'filtered_{start_date}_to_{end_date}.xlsx')
            _write_excel_fast(export_df, temp_file)
            return send_file(temp_file, as_attachment=True, download_name=f'{project_name}_{start_date}_to_{end_date}.xlsx')
        else:
            temp_file = os.path.join(files['path'], f'filtered_{start_date}_to_{end_date}.csv')
            export_df.to_csv(temp_file, index=False)
            return send_file(temp_file, as_attachment=True, download_name=f'{project_name}_{start_date}_to_{end_date}.csv')

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

        files = get_project_files(project_name)
        settings = load_project_settings(project_name)

        if os.path.exists(files['pickle']):
            df = pd.read_pickle(files['pickle'])
        elif os.path.exists(files['excel']):
            df = pd.read_excel(files['excel'])
        else:
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
        import io
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            # Summary sheet
            summary_df = pd.DataFrame({
                'Rank': range(1, len(top10_values) + 1),
                display_name: top10_values,
                'Count': [len(top10_data[top10_data[column] == val]) for val in top10_values]
            })
            summary_df.to_excel(writer, index=False, sheet_name='Summary')

            # Data sheet with all rows
            top10_data.to_excel(writer, index=False, sheet_name='Data')

            # Format summary sheet
            workbook = writer.book
            worksheet = writer.sheets['Summary']
            for i, col in enumerate(summary_df.columns):
                max_len = max(summary_df[col].astype(str).map(len).max(), len(col)) + 2
                worksheet.set_column(i, i, min(max_len, 50))

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
            print(f"Minimize error: {e}")
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
            print(f"Maximize error: {e}")
            return {'success': False, 'error': str(e)}

    def close_window(self):
        global webview_window
        try:
            webview_window.destroy()
            return {'success': True}
        except Exception as e:
            print(f"Close error: {e}")
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
            files = get_project_files(project_name)

            # Load data
            if os.path.exists(files['pickle']):
                df = pd.read_pickle(files['pickle'])
            elif os.path.exists(files['excel']):
                df = pd.read_excel(files['excel'])
            else:
                return {'success': False, 'error': 'No data to export'}

            export_df = df[[c for c in df.columns if c != '_upload_id']]

            # Save based on file extension
            if save_path.lower().endswith('.csv'):
                export_df.to_csv(save_path, index=False)
                return {'success': True, 'message': f'CSV saved! ({len(export_df)} records)'}
            else:
                if not save_path.lower().endswith('.xlsx'):
                    save_path += '.xlsx'
                export_df.to_excel(save_path, index=False, engine='xlsxwriter')
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
            files = get_project_files(project_name)
            settings = load_project_settings(project_name)

            if os.path.exists(files['pickle']):
                df = pd.read_pickle(files['pickle'])
            elif os.path.exists(files['excel']):
                df = pd.read_excel(files['excel'])
            else:
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
                export_df.to_excel(save_path, index=False, engine='xlsxwriter')
                return {'success': True, 'message': f'Excel saved! ({len(export_df)} records)'}
        except Exception as e:
            return {'success': False, 'error': str(e)}


def start_server():
    app.run(host='127.0.0.1', port=5000, debug=False, use_reloader=False, threaded=True)


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
    print("=" * 60)
    print("  Data Analytical and Compilation Tool")
    print("  Multi-Project Support")
    print("=" * 60)
    print(f"  Data Directory: {APP_DIR}")
    print(f"  Projects Directory: {PROJECTS_DIR}")
    print("=" * 60)

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

    print("\nApplication closed.")
