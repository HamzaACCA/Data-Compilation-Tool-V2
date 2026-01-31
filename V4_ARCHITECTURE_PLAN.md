# V4 Architecture Plan — Data Analytical and Compilation Tool

**Status:** Planning — Not yet implemented
**Date:** 31-Jan-2026
**Developer:** Hamza Yahya - Internal Audit

---

## Overview

Full rewrite from Flask + vanilla JS to **FastAPI + React** with SQLite database, multi-user auth, anomaly detection, and SAP S/4HANA integration readiness.

---

## Tech Stack

| Layer | V3 | V4 |
|-------|----|----|
| Backend | Flask 3.0 (sync) | **FastAPI** (async) |
| Frontend | Vanilla HTML/JS | **React 18** + Vite + TailwindCSS |
| Database | Pickle + JSON files | **SQLite** + SQLAlchemy |
| Auth | None | **JWT** (access + refresh tokens) |
| Charts | Chart.js (CDN) | **Recharts** (React-native) |
| Desktop | PyWebView + Flask | PyWebView + FastAPI |
| Excel Read | python-calamine | python-calamine (keep) |
| Excel Write | Raw XML writer | Raw XML writer (keep) |
| Data Processing | Pandas | Pandas (keep) |
| Task Queue | None | FastAPI **BackgroundTasks** |
| Real-time | XMLHttpRequest polling | **WebSocket** (upload progress) |
| SAP | None | **OData client** (Phase 2) |

---

## Project Structure

```
data-compilation-v4/
├── backend/
│   ├── main.py                    # FastAPI app entry point
│   ├── config.py                  # Settings, env vars
│   ├── database.py                # SQLAlchemy engine + session
│   ├── models/
│   │   ├── __init__.py
│   │   ├── user.py                # User, Role models
│   │   ├── project.py             # Project, ProjectMember models
│   │   ├── upload.py              # Upload, UploadRow models
│   │   ├── dataset.py             # Dataset metadata model
│   │   └── audit.py               # AuditLog model
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── user.py                # Pydantic request/response schemas
│   │   ├── project.py
│   │   ├── upload.py
│   │   ├── analytics.py
│   │   └── auth.py
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── auth.py                # POST /auth/login, /auth/register, /auth/refresh
│   │   ├── projects.py            # CRUD /projects
│   │   ├── uploads.py             # POST /uploads, DELETE /uploads/{id}
│   │   ├── data.py                # GET /data/stats, /data/columns, /data/summary
│   │   ├── downloads.py           # GET /downloads/consolidated, /filtered, /top10
│   │   ├── analytics.py           # GET /analytics/dashboard, /trend, /compare, /advanced
│   │   ├── anomalies.py           # GET /anomalies/scan, /anomalies/duplicates, /anomalies/gaps
│   │   ├── settings.py            # GET/POST /settings
│   │   └── sap.py                 # SAP integration (Phase 2)
│   ├── services/
│   │   ├── __init__.py
│   │   ├── auth_service.py        # JWT creation, password hashing
│   │   ├── file_service.py        # Read Excel/CSV, combine, optimize
│   │   ├── cache_service.py       # In-memory DataFrame cache
│   │   ├── export_service.py      # Raw XML xlsx writer, CSV export
│   │   ├── analytics_service.py   # Top 10, trend, compare, advanced
│   │   ├── anomaly_service.py     # Outlier, duplicate, gap detection
│   │   └── sap_service.py         # SAP OData client (Phase 2)
│   ├── middleware/
│   │   ├── __init__.py
│   │   └── auth.py                # JWT dependency injection
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── excel_reader.py        # calamine + openpyxl fallback
│   │   ├── excel_writer.py        # _write_xlsx_raw (carry from V3)
│   │   └── dataframe.py           # optimize_dataframe, prepare_export
│   ├── migrations/
│   │   └── init_db.py             # Create tables on first run
│   ├── tests/
│   │   ├── test_auth.py
│   │   ├── test_uploads.py
│   │   ├── test_analytics.py
│   │   └── test_anomalies.py
│   └── requirements.txt
├── frontend/
│   ├── package.json
│   ├── vite.config.ts
│   ├── tailwind.config.js
│   ├── index.html
│   ├── src/
│   │   ├── main.tsx               # React entry point
│   │   ├── App.tsx                # Router + layout
│   │   ├── api/
│   │   │   ├── client.ts          # Axios instance with JWT interceptor
│   │   │   ├── auth.ts            # Auth API calls
│   │   │   ├── projects.ts        # Project API calls
│   │   │   ├── uploads.ts         # Upload API calls
│   │   │   ├── analytics.ts       # Analytics API calls
│   │   │   └── anomalies.ts       # Anomaly API calls
│   │   ├── store/
│   │   │   ├── authStore.ts       # Zustand auth state
│   │   │   ├── projectStore.ts    # Current project state
│   │   │   └── themeStore.ts      # Dark mode state
│   │   ├── pages/
│   │   │   ├── LoginPage.tsx
│   │   │   ├── RegisterPage.tsx
│   │   │   ├── ProjectsPage.tsx   # Project list + create
│   │   │   ├── UploadPage.tsx     # File upload + history
│   │   │   ├── DashboardPage.tsx  # Analytics dashboard
│   │   │   ├── AnomaliesPage.tsx  # Anomaly detection results
│   │   │   └── SettingsPage.tsx   # Project + user settings
│   │   ├── components/
│   │   │   ├── layout/
│   │   │   │   ├── Sidebar.tsx    # Navigation sidebar
│   │   │   │   ├── Header.tsx     # Top bar with user menu
│   │   │   │   └── Layout.tsx     # Main layout wrapper
│   │   │   ├── upload/
│   │   │   │   ├── DropZone.tsx   # Drag-and-drop file area
│   │   │   │   ├── UploadProgress.tsx  # WebSocket progress bar
│   │   │   │   ├── UploadHistory.tsx   # Upload log table
│   │   │   │   └── ColumnMapper.tsx    # Column mapping UI
│   │   │   ├── dashboard/
│   │   │   │   ├── StatsCards.tsx      # Summary stat cards
│   │   │   │   ├── TopNChart.tsx       # Bar chart for Top N
│   │   │   │   ├── TrendChart.tsx      # Line chart for trends
│   │   │   │   ├── ComparePanel.tsx    # Period comparison
│   │   │   │   ├── AdvancedAnalysis.tsx # Group-by aggregation
│   │   │   │   ├── ColumnStats.tsx     # Column analysis table
│   │   │   │   └── DateFilter.tsx      # Date range picker
│   │   │   ├── anomalies/
│   │   │   │   ├── OutlierTable.tsx    # Statistical outlier results
│   │   │   │   ├── DuplicateTable.tsx  # Duplicate transaction results
│   │   │   │   ├── GapAnalysis.tsx     # Missing data analysis
│   │   │   │   └── AnomalySummary.tsx  # Overview cards
│   │   │   └── common/
│   │   │       ├── Modal.tsx
│   │   │       ├── Toast.tsx
│   │   │       ├── DataTable.tsx  # Reusable sortable table
│   │   │       └── Loading.tsx
│   │   ├── hooks/
│   │   │   ├── useAuth.ts
│   │   │   ├── useWebSocket.ts
│   │   │   └── useProject.ts
│   │   └── utils/
│   │       ├── formatters.ts      # Date, number formatting
│   │       └── constants.ts
│   └── public/
│       └── favicon.ico
├── desktop/
│   ├── desktop_app.py             # PyWebView wrapper
│   ├── data_compilation.spec      # PyInstaller config
│   └── installer_config.iss       # Inno Setup config
├── data/                          # SQLite DB + uploaded files
│   └── .gitkeep
├── .env.example
├── .gitignore
├── CLAUDE.md
├── README.md
└── docker-compose.yml             # Optional: for deployment
```

---

## Database Schema (SQLite)

### users
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | Auto-increment |
| username | TEXT UNIQUE | Login name |
| email | TEXT UNIQUE | Email address |
| password_hash | TEXT | bcrypt hashed |
| role | TEXT | 'admin' / 'editor' / 'viewer' |
| is_active | BOOLEAN | Default true |
| created_at | DATETIME | Auto |
| last_login | DATETIME | Nullable |

### projects
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | Auto-increment |
| name | TEXT UNIQUE | Project name |
| description | TEXT | Optional |
| created_by | INTEGER FK | -> users.id |
| created_at | DATETIME | Auto |
| updated_at | DATETIME | Auto |

### project_members
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | Auto-increment |
| project_id | INTEGER FK | -> projects.id |
| user_id | INTEGER FK | -> users.id |
| role | TEXT | 'owner' / 'editor' / 'viewer' |

### project_settings
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | Auto-increment |
| project_id | INTEGER FK | -> projects.id (UNIQUE) |
| date_column | TEXT | Selected date column |
| top_columns | TEXT | JSON array of {column, display_name} |

### uploads
| Column | Type | Notes |
|--------|------|-------|
| id | TEXT PK | Timestamp-based ID (keep V3 format) |
| project_id | INTEGER FK | -> projects.id |
| user_id | INTEGER FK | -> users.id (who uploaded) |
| original_name | TEXT | Original filename |
| file_path | TEXT | Path to stored file |
| rows_added | INTEGER | Number of rows |
| columns | INTEGER | Number of columns |
| file_size | INTEGER | Bytes |
| uploaded_at | DATETIME | Auto |

### datasets
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | Auto-increment |
| project_id | INTEGER FK | -> projects.id (UNIQUE) |
| pickle_path | TEXT | Path to .pkl file |
| total_rows | INTEGER | Current row count |
| total_columns | INTEGER | Current column count |
| file_size | INTEGER | Pickle file size |
| updated_at | DATETIME | Last modified |

### audit_log
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | Auto-increment |
| project_id | INTEGER FK | -> projects.id |
| user_id | INTEGER FK | -> users.id |
| action | TEXT | 'FILES_UPLOADED', 'UPLOAD_DELETED', etc. |
| details | TEXT | Description |
| created_at | DATETIME | Auto |

### anomaly_scans
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | Auto-increment |
| project_id | INTEGER FK | -> projects.id |
| user_id | INTEGER FK | -> users.id |
| scan_type | TEXT | 'outlier' / 'duplicate' / 'gap' |
| config | TEXT | JSON — columns, thresholds, params |
| results_count | INTEGER | Number of anomalies found |
| results | TEXT | JSON — anomaly details |
| created_at | DATETIME | Auto |

---

## API Design (FastAPI Routers)

### Auth Router — `/api/auth`
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/register` | Create account (first user = admin) |
| POST | `/login` | Get JWT access + refresh tokens |
| POST | `/refresh` | Refresh access token |
| GET | `/me` | Get current user profile |
| PUT | `/me` | Update profile/password |

### Projects Router — `/api/projects`
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | List user's projects |
| POST | `/` | Create project |
| GET | `/{id}` | Get project details |
| PUT | `/{id}` | Update project |
| DELETE | `/{id}` | Delete project + all data |
| POST | `/{id}/members` | Add member to project |
| DELETE | `/{id}/members/{user_id}` | Remove member |

### Uploads Router — `/api/projects/{id}/uploads`
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/` | Upload + combine files (WebSocket progress) |
| POST | `/mapped` | Upload with column mapping |
| GET | `/` | List uploads (paginated) |
| DELETE | `/{upload_id}` | Delete specific upload |

### Data Router — `/api/projects/{id}/data`
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/stats` | Row count, columns, size |
| GET | `/columns` | Column list + type detection |
| GET | `/summary` | Data quality summary |
| POST | `/reset` | Delete all consolidated data |

### Downloads Router — `/api/projects/{id}/downloads`
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/consolidated` | Download all data (csv/xlsx) |
| GET | `/filtered` | Download date-filtered data |
| GET | `/top10` | Download Top 10 data rows |
| GET | `/column-stats` | Download column analysis |
| GET | `/comparison` | Download period comparison |
| GET | `/advanced` | Download advanced analysis |

### Analytics Router — `/api/projects/{id}/analytics`
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/date-range` | Min/max dates |
| GET | `/dashboard` | Top N stats for configured columns |
| GET | `/trend` | Monthly trend data |
| GET | `/compare` | Compare column across 2 periods |
| GET | `/advanced` | Group-by aggregation |
| GET | `/column-stats` | Column type/quality analysis |

### Anomalies Router — `/api/projects/{id}/anomalies`
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/scan/outliers` | Run statistical outlier detection |
| POST | `/scan/duplicates` | Find duplicate/near-duplicate rows |
| POST | `/scan/gaps` | Find missing data and date gaps |
| GET | `/scans` | List previous scan results |
| GET | `/scans/{scan_id}` | Get specific scan results |
| GET | `/scans/{scan_id}/download` | Download anomaly report (xlsx) |

### Settings Router — `/api/projects/{id}/settings`
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Get project settings |
| PUT | `/` | Update project settings |

### SAP Router — `/api/sap` (Phase 2)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/connect` | Test SAP OData connection |
| GET | `/entities` | List available OData entities |
| POST | `/fetch` | Fetch data from SAP entity into project |
| GET | `/scheduled` | List scheduled SAP pulls |
| POST | `/scheduled` | Create scheduled pull |

---

## Anomaly Detection Design

### 1. Statistical Outliers (`anomaly_service.py`)
```
Algorithm: IQR method + Z-score
- For each numeric column selected by user:
  - IQR: Flag values < Q1 - 1.5*IQR or > Q3 + 1.5*IQR
  - Z-score: Flag values with |z| > 3
- User configurable: sensitivity threshold, columns to scan
- Output: row index, column, value, expected range, severity
```

### 2. Duplicate Detection
```
Algorithm: Exact match + fuzzy matching
- Exact duplicates: df.duplicated(subset=key_columns)
- Near-duplicates: Group by key columns, flag groups where
  non-key columns differ by < threshold (e.g., edit distance < 3)
- User configurable: key columns, similarity threshold
- Output: groups of duplicate rows, match type, similarity score
```

### 3. Gap / Missing Data Detection
```
Algorithm: Sequence analysis + completeness checks
- Date gaps: Find missing dates in expected sequence
  (e.g., daily shipments should have no gaps > 3 days)
- Value completeness: Flag columns with > X% null values
- Reference gaps: Flag values that appear in period 1 but not period 2
- User configurable: date column, expected frequency, null threshold
- Output: gap start/end, missing count, affected columns
```

---

## SAP S/4HANA Integration (Phase 2)

### Approach: OData V4 Client
```
1. User provides SAP Gateway URL + credentials (stored encrypted)
2. Backend discovers available OData entities (e.g., /sap/opu/odata4/...)
3. User selects entity + filters (date range, plant, etc.)
4. Backend fetches data via OData $filter, $select, $top
5. Data converted to DataFrame -> standard upload pipeline
6. Optional: scheduled recurring pull (cron-like)
```

### Libraries
- `requests` + `requests-oauthlib` for SAP OAuth
- Custom OData parser (SAP uses specific extensions)
- Store connection configs encrypted in SQLite

### Security
- SAP credentials encrypted with Fernet (per-user encryption key)
- Connection tested before saving
- Audit log for all SAP data pulls

---

## Authentication Flow

```
1. First user to register becomes admin
2. Admin can invite users (editor/viewer roles)
3. Login -> POST /auth/login -> returns {access_token, refresh_token}
4. Access token: JWT, 30 min expiry, stored in memory (React state)
5. Refresh token: JWT, 7 day expiry, stored in httpOnly cookie
6. Every API request includes Authorization: Bearer <access_token>
7. FastAPI Depends(get_current_user) validates token on protected routes
8. Role-based: viewer can view, editor can upload/delete, admin can manage users
```

---

## Frontend Pages + Components

### Page Flow
```
Login -> Projects List -> [Select Project] -> Upload Page
                                            -> Dashboard Page
                                            -> Anomalies Page
                                            -> Settings Page
```

### Key UI Improvements over V3
1. **Sidebar navigation** — always visible, shows all pages
2. **Real-time upload progress** — WebSocket, not polling
3. **Interactive data table** — sortable, filterable, paginated
4. **Anomaly dashboard** — dedicated page with scan history
5. **Responsive design** — TailwindCSS, works on tablets
6. **Toast notifications** — react-hot-toast
7. **Date picker** — react-datepicker (better than native input)
8. **Dark mode** — TailwindCSS dark: variants

---

## Desktop Mode (PyWebView)

```python
# desktop/desktop_app.py
import webview
import subprocess, threading

def start_backend():
    subprocess.Popen(["uvicorn", "backend.main:app", "--port", "8000"])

threading.Thread(target=start_backend, daemon=True).start()
webview.create_window("Data Compilation Tool V4", "http://localhost:8000")
webview.start()
```

- PyWebView loads the React build (served by FastAPI static files)
- No separate build needed — same codebase for web and desktop
- PyInstaller packages both backend + frontend build

---

## Migration from V3

### Data Migration Script
1. Read V3 `Data/config.json` -> create projects in SQLite
2. Read V3 `settings.json` per project -> create project_settings rows
3. Read V3 `upload_log.json` -> create upload rows
4. Read V3 `audit_log.json` -> create audit_log rows
5. Copy pickle files as-is (same pandas format)
6. Create default admin user

### Feature Parity Checklist
- [ ] Multi-project support
- [ ] File upload with progress
- [ ] Column mapping upload
- [ ] Upload history + delete
- [ ] Consolidated data stats
- [ ] CSV + Excel downloads (raw XML writer)
- [ ] Date range filtering
- [ ] Top N configurable dashboard
- [ ] Trend analysis chart
- [ ] Period comparison
- [ ] Advanced group-by aggregation
- [ ] Column analysis table
- [ ] Audit log
- [ ] Dark mode
- [ ] Keyboard shortcuts
- [ ] Performance monitor (cache stats)
- [ ] Desktop mode (PyWebView)

### New in V4
- [ ] User authentication (JWT)
- [ ] Role-based access control
- [ ] Anomaly detection: outliers
- [ ] Anomaly detection: duplicates
- [ ] Anomaly detection: gaps
- [ ] Anomaly scan history + download
- [ ] WebSocket upload progress
- [ ] SAP OData integration (Phase 2)
- [ ] Responsive sidebar navigation
- [ ] Interactive data tables

---

## Implementation Phases

### Phase 1: Foundation (Backend + Auth + DB)
- Set up FastAPI project structure
- SQLite + SQLAlchemy models
- Auth router (register, login, JWT)
- Project CRUD router
- Migration script from V3 data

### Phase 2: Core Features (Upload + Data + Downloads)
- File upload with combine logic (port from V3)
- calamine reader + DataFrame optimization (port from V3)
- Raw XML Excel writer (port from V3)
- Data stats, columns, summary endpoints
- Download endpoints (CSV + xlsx)
- Memory cache service

### Phase 3: React Frontend (Upload + Projects)
- Vite + React + TailwindCSS setup
- Login/Register pages
- Projects list page
- Upload page with drag-drop + WebSocket progress
- Upload history + delete
- Dark mode

### Phase 4: Dashboard
- Dashboard page with date filter
- Top N bar charts (Recharts)
- Trend line chart
- Period comparison panel
- Advanced group-by analysis
- Column stats table
- All download buttons

### Phase 5: Anomaly Detection
- Outlier detection service (IQR + Z-score)
- Duplicate detection service (exact + fuzzy)
- Gap detection service (date gaps + completeness)
- Anomalies page with scan UI
- Scan history + result download

### Phase 6: Desktop + Polish
- PyWebView integration
- PyInstaller build
- Inno Setup installer
- Keyboard shortcuts
- Performance optimization
- Testing

### Phase 7: SAP Integration (Future)
- SAP OData client
- Connection management UI
- Entity browser + data fetch
- Scheduled pulls

---

## V3 Code to Port (Key Functions)

These V3 functions should be extracted and refactored into V4 services:

| V3 Function | V4 Location | Notes |
|-------------|-------------|-------|
| `_read_excel_calamine()` | `utils/excel_reader.py` | Keep as-is |
| `_deduplicate_columns()` | `utils/excel_reader.py` | Keep as-is |
| `read_file()` | `services/file_service.py` | Keep as-is |
| `_write_xlsx_raw()` | `utils/excel_writer.py` | Keep as-is |
| `_write_excel_fast()` | `utils/excel_writer.py` | Keep as-is |
| `optimize_dataframe()` | `utils/dataframe.py` | Keep as-is |
| `get_cached_dataframe()` | `services/cache_service.py` | Refactor for async |
| `clear_cache()` | `services/cache_service.py` | Refactor for async |
| `combine_files()` | `services/file_service.py` | Refactor for project context |
| Dashboard stat logic | `services/analytics_service.py` | Extract from route handlers |
| Compare/advanced logic | `services/analytics_service.py` | Extract from route handlers |

---

## Verification Criteria

After each phase:
1. Run `pytest backend/tests/` for backend tests
2. Run `npm test` in frontend/ for component tests
3. Manual test: upload a V3 Excel file, verify stats, download, check dashboard
4. Compare V4 download speeds with V3 benchmarks
5. Test desktop mode via PyWebView
6. Test dark mode, responsive layout on different screen sizes

---

## Python Dependencies (backend/requirements.txt)

```
fastapi>=0.104.0
uvicorn[standard]>=0.24.0
sqlalchemy>=2.0.23
pydantic>=2.5.0
python-jose[cryptography]>=3.3.0
passlib[bcrypt]>=1.7.4
python-multipart>=0.0.6
pandas>=2.1.4
python-calamine>=0.2.0
openpyxl>=3.1.2
xlsxwriter>=3.1.9
aiofiles>=23.2.1
websockets>=12.0
pywebview>=4.4.1
cryptography>=41.0.0
```

## Node Dependencies (frontend/package.json)

```
react, react-dom, react-router-dom
@vitejs/plugin-react, vite, typescript
tailwindcss, postcss, autoprefixer
zustand (state management)
axios (HTTP client)
recharts (charts)
react-hot-toast (notifications)
react-datepicker (date picker)
react-dropzone (file upload)
lucide-react (icons)
```

---

**Version:** 4.0 (Planning)
**Last Updated:** 31-Jan-2026
**Developer:** Hamza Yahya - Internal Audit
