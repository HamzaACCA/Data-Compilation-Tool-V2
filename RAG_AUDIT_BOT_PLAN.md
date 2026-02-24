# RAG Audit Bot — Implementation Plan

## Context
Adding an AI-powered audit assistant to the V3 dashboard. The bot has 3 roles:
1. **Dashboard Controller** — operates all 39 dashboard actions via natural language (FREE, local parser)
2. **Audit Analyst** — scans 100% of data with 9 checks, identifies red flags (FREE, local pandas)
3. **AI Interpreter** — uses OpenAI GPT-5.2 Pro to interpret findings, answer questions, write reports (PAID, per-query)

**Key design decisions:**
- **Two-tier system:** Simple commands handled locally (zero tokens), complex analysis via GPT-5.2 Pro
- **Model:** OpenAI GPT-5.2 Pro (`gpt-5.2-pro`) — $1.75/M input, $14/M output, $0.175/M cached input (90% off), 400K context window, 128K max output
- **100% data coverage:** All audit checks run on full dataset locally via pandas
- **Hybrid AI:** Flagged rows (suspicious subsets) sent to GPT-5.2 Pro for interpretation
- **Confirm before execute:** Bot proposes actions, user clicks [Apply] to execute
- **Persistence:** SQLite database for chat history, risk scans, token tracking
- **Scope:** V3 (current Flask app)

## Files to Create/Modify

### New Files
| File | Purpose |
|------|---------|
| `utils/audit_checks.py` | 9 pandas-based audit checks (100% data scan) |
| `utils/ai_chat.py` | OpenAI GPT-5.2 Pro client, prompt builder, context assembler |
| `utils/db.py` | SQLite connection helper, CRUD functions |

### Modified Files
| File | Changes |
|------|---------|
| `launcher.py` | 4 new API endpoints (`/api/chat`, `/api/risk-scan`, `/api/chat/history`, `/api/chat/history` DELETE) |
| `templates/dashboard.html` | Chat panel UI, local command parser (39 actions), action executor, confirm dialog |
| `requirements.txt` | Add `openai>=1.0.0` |
| `.env` | Add `OPENAI_API_KEY=sk-...` |

---

## SQLite Schema

**File:** `Data/audit_bot.db` (auto-created on first use)

```sql
CREATE TABLE chat_messages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    project     TEXT NOT NULL,
    role        TEXT NOT NULL,              -- 'user' or 'assistant'
    content     TEXT NOT NULL,
    actions     TEXT,                       -- JSON array of proposed actions
    risks       TEXT,                       -- JSON array of risk findings
    source      TEXT DEFAULT 'local',       -- 'local' or 'ai'
    tokens_used INTEGER DEFAULT 0,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE risk_scans (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    project     TEXT NOT NULL,
    total_rows  INTEGER,
    findings    INTEGER,
    high_risk   INTEGER DEFAULT 0,
    medium_risk INTEGER DEFAULT 0,
    low_risk    INTEGER DEFAULT 0,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE risk_findings (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_id     INTEGER REFERENCES risk_scans(id),
    check_type  TEXT NOT NULL,              -- 'duplicate', 'outlier', etc.
    level       TEXT NOT NULL,              -- 'high', 'medium', 'low'
    title       TEXT NOT NULL,
    detail      TEXT,
    evidence    TEXT,                       -- JSON: flagged rows, values
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_chat_project ON chat_messages(project, created_at);
CREATE INDEX idx_scans_project ON risk_scans(project, created_at);
CREATE INDEX idx_findings_scan ON risk_findings(scan_id);
```

---

## API Endpoints (New)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/chat` | POST | Send message -> local parse or GPT-5.2 Pro -> return response + actions |
| `/api/chat/history` | GET | Load chat history for current project from SQLite |
| `/api/chat/history` | DELETE | Clear chat history for current project |
| `/api/risk-scan` | GET | Run all 9 audit checks on 100% data, store results in SQLite |

---

## Complete Action Catalog (39 Actions — All FREE via Local Parser)

### Filtering & Date Range (6)
| Action | Parameters | Maps To |
|--------|-----------|---------|
| `setDateFilter` | `{start, end}` | `#startDate` + `#endDate` inputs |
| `applyFilter` | `{}` | `loadDashboard()` |
| `setDateColumn` | `{column}` | `#dateColumnSelect` + `saveDateColumn()` |
| `setTrendDates` | `{start, end}` | `#trendStartDate` + `#trendEndDate` + `onTrendDateChange()` |
| `clearTrendDates` | `{}` | Clear trend date inputs |
| `clearDateFilter` | `{}` | Reset to full range via `loadDateRange()` |

### Trend Chart Controls (8)
| Action | Parameters | Maps To |
|--------|-----------|---------|
| `setTrendGroup` | `{column}` | `#trendGroupSelect` + `onTrendControlChange()` |
| `setTrendValue` | `{column}` | `#trendValueSelect` + `onTrendControlChange()` |
| `setTopN` | `{n}` | `#trendShowSelect` + `onShowChange()` |
| `setSpecificGroups` | `{groups:[...]}` | Switch to Specific mode, add chips |
| `addSpecificGroup` | `{group}` | `addChip(name)` |
| `removeSpecificGroup` | `{group}` | `removeChip(name)` |
| `clearSpecificGroups` | `{}` | Clear all chips |
| `setBaseline` | `{month}` | `#baselineMonthSelect` + `onTrendControlChange()` |

### Chart Mode & Theme (5)
| Action | Parameters | Maps To |
|--------|-----------|---------|
| `toggleEcg` | `{which}` | `toggleEcg('Count'/'Sum')` |
| `setSumChartMode` | `{mode}` | `setSumChartMode('raw'/'movement')` |
| `toggleDarkMode` | `{}` | `toggleDarkMode()` |
| `setChartView` | `{mode}` | `toggleChartView('bar'/'list')` |
| `clearIsolation` | `{which}` | `clearIsolation('Count'/'Sum')` |

### Legend Isolation (2)
| Action | Parameters | Maps To |
|--------|-----------|---------|
| `isolateGroups` | `{which, groups:[...]}` | Match names -> indices, `toggleIsolate()` |
| `clearIsolation` | `{which}` | `clearIsolation()` |

### Comparison & Advanced Analysis (4)
| Action | Parameters | Maps To |
|--------|-----------|---------|
| `openComparison` | `{column, period1:[s,e], period2:[s,e]}` | Open modal, fill, `runComparison()` |
| `openAdvanced` | `{group, value, agg, period1:[s,e], period2:[s,e]}` | Open modal, fill, `runAdvancedAnalysis()` |
| `closeComparison` | `{}` | `closeComparisonModal()` |
| `closeAdvanced` | `{}` | `closeAdvancedAnalysisModal()` |

### Settings (4)
| Action | Parameters | Maps To |
|--------|-----------|---------|
| `openSettings` | `{}` | `openSettings()` |
| `closeSettings` | `{}` | `closeSettings()` |
| `setTopColumns` | `{columns:[{column,display_name},...]}` | Set config + `saveSettings()` |
| `addTopColumn` | `{column, display_name}` | `addColumnSelector()` |

### Downloads (6)
| Action | Parameters | Maps To |
|--------|-----------|---------|
| `downloadFiltered` | `{format}` | `downloadFiltered()` |
| `downloadTrend` | `{which}` | `downloadTrendLineExcel('Count'/'Sum')` |
| `downloadTop10` | `{column, displayName}` | `downloadChartData()` |
| `downloadColumnStats` | `{}` | `downloadColumnStats()` |
| `downloadComparison` | `{}` | `downloadComparison()` |
| `downloadAdvanced` | `{}` | `downloadAdvancedAnalysis()` |

### Other (4)
| Action | Parameters | Maps To |
|--------|-----------|---------|
| `exportPDF` | `{}` | `exportPDF()` |
| `refreshDashboard` | `{}` | `loadDashboard()` |
| `runRiskScan` | `{}` | All 9 audit checks |
| `generateReport` | `{}` | Risk scan + GPT-5.2 Pro narrative |

---

## 9 Audit Checks (`utils/audit_checks.py`)

All checks run on 100% of data locally via pandas. Zero token cost.

| # | Function | What It Does | Output |
|---|----------|-------------|--------|
| 1 | `check_duplicates(df, key_cols)` | `df.duplicated()` on key columns | Duplicate groups with row counts |
| 2 | `check_outliers(df, numeric_cols)` | IQR + Z-score per numeric column | Outlier rows with expected ranges |
| 3 | `check_concentration(df, cat_cols)` | `value_counts()` percentages | Top N with % share per column |
| 4 | `check_trend_anomalies(df, date_col, group_col)` | MoM % change, flag >2x average | Months + groups with spike/drop details |
| 5 | `check_missing_data(df)` | `isnull().sum()` per column | Columns with >5% missing + patterns |
| 6 | `check_round_numbers(df, numeric_cols)` | Modulo checks for suspicious rounding | Rows with round amounts near thresholds |
| 7 | `check_weekend_activity(df, date_col)` | Day-of-week analysis | Weekend/holiday transaction rows |
| 8 | `check_benfords_law(df, numeric_cols)` | First-digit distribution chi-squared test | Columns that deviate from expected distribution |
| 9 | `check_split_transactions(df, date_col, vendor_col, amount_col)` | Group by date+vendor, detect splits near limits | Groups of same-day transactions just below thresholds |

Each check returns:
```python
{
    "check_type": "duplicate",
    "level": "high",           # high / medium / low
    "title": "47 duplicate rows found",
    "detail": "12 Container IDs appear multiple times...",
    "evidence": [...],         # actual flagged rows (sent to GPT-5.2 Pro)
    "stats": {...}             # summary numbers
}
```

---

## Two-Tier Message Routing

```javascript
function handleMessage(text) {
    const parsed = parseCommand(text);     // local regex/keyword matching
    if (parsed.matched) {
        // FREE — show confirm dialog, execute on [Apply]
        showConfirmDialog(parsed.actions, parsed.description);
        saveChatMessage(text, parsed, 'local');      // save to SQLite via API
    } else {
        // PAID — send to GPT-5.2 Pro
        showTypingIndicator();
        fetch('/api/chat', { method: 'POST', body: JSON.stringify({ message: text }) })
            .then(r => r.json())
            .then(response => {
                displayAIResponse(response);         // show message + risks
                if (response.actions.length > 0) {
                    showConfirmDialog(response.actions); // confirm before executing
                }
            });
    }
}
```

---

## GPT-5.2 Pro System Prompt

```
You are an Internal Audit AI Assistant embedded in a data analysis dashboard.

YOU HAVE TWO ROLES:
1. ANALYST — identify risks, red flags, anomalies in audit data
2. CONTROLLER — operate the dashboard by returning actions

AVAILABLE DATA (provided in each message context):
- Project: {name}, {row_count} rows, {col_count} columns
- Columns: {column_list with types}
- Date range: {min} to {max}
- Current filters: {active date range}
- Audit scan results: {all 9 check outputs with flagged rows}
- Dashboard state: {current trend group, chart mode, etc.}

RESPONSE FORMAT (always valid JSON):
{
  "message": "Natural language explanation with evidence",
  "actions": [
    {"type": "setDateFilter", "start": "2025-01-01", "end": "2025-06-30"},
    {"type": "applyFilter"}
  ],
  "risks": [
    {"level": "high", "finding": "Vendor X handles 43% of all shipments..."}
  ]
}

RULES:
- Always cite specific numbers, percentages, row counts as evidence
- Rate findings: HIGH | MEDIUM | LOW
- When proposing dashboard actions, explain WHY (audit rationale)
- If user request is ambiguous, ask for clarification in "message"
- Match user's informal column references to actual column names from context
```

---

## Chat Panel UI

Slide-out panel on right side of dashboard:
- Toggle via chat button in title bar
- Shows chat history (loaded from SQLite)
- Input box at bottom with Send button
- "Risk Scan" quick-action button
- Messages styled differently: user (right-aligned), bot (left-aligned)
- Local responses: instant, no loading indicator
- AI responses: typing indicator while waiting
- Action proposals: card with action list + [Apply] [Cancel] buttons
- Risk findings: colored badges (HIGH/MEDIUM/LOW)

---

## Cost Estimate (GPT-5.2 Pro)

| Scenario | Tokens | Cost |
|----------|--------|------|
| Dashboard commands (local parser) | 0 | $0.00 |
| Risk scan + AI narrative | ~20K in + 2K out | ~$0.06 |
| Follow-up question (cached system prompt) | ~8K in + 1K out | ~$0.02 |
| Full risk report | ~25K in + 3K out | ~$0.09 |
| Monthly (50 queries/day, 70% local) | — | ~$1-3/month |

**Cost optimization:** The system prompt + column schema (~2K tokens) is sent with every AI request. GPT-5.2 Pro's cached input pricing ($0.175/M vs $1.75/M) means this repeated context costs 90% less after the first request in a session.

---

## Phase-Wise Execution

### Phase 1: Chat Panel UI + Local Command Parser
**Files:** `templates/dashboard.html`
**Dependencies:** None
**Token cost:** $0

**What to build:**
1. Chat panel HTML/CSS — slide-out right panel (toggle via chat button)
2. Chat input box with Send button + Enter key support
3. Message display (user right-aligned, bot left-aligned, timestamps)
4. `parseCommand(text)` — regex/keyword matching for all 39 dashboard actions
5. Action executor — maps parsed actions to existing JS functions
6. Confirm dialog — shows proposed actions with [Apply] [Cancel]
7. Visual feedback messages — "Filtered to Jan-Jun 2025"
8. Support for column name matching (both raw names and display names from settings)
9. Date parsing — handle "jan 2025", "january 2025", "Q1 2025", "H1 2025", etc.

**Parser patterns to implement:**
- `filter <date> to <date>` -> setDateFilter + applyFilter
- `top <N>` -> setTopN
- `group by <column>` -> setTrendGroup
- `ecg on/off [count/sum]` -> toggleEcg
- `dark mode` -> toggleDarkMode
- `movement/raw mode` -> setSumChartMode
- `baseline <month>` -> setBaseline
- `compare <period> vs <period> [column]` -> openComparison
- `download [excel/csv/trend/comparison/pdf]` -> relevant download
- `show only <group1>, <group2>` -> isolateGroups
- `show all` / `clear` -> clearIsolation
- `refresh` -> refreshDashboard
- `settings` -> openSettings
- `list view` / `bar view` -> setChartView
- `risk scan` / `scan` -> runRiskScan (wired in Phase 2)
- `report` -> generateReport (wired in Phase 5)

---

### Phase 2: Audit Checks Engine
**Files:** `utils/audit_checks.py` (new), `launcher.py`
**Dependencies:** Phase 1 (chat panel exists to display results)
**Token cost:** $0

**What to build:**
1. `utils/audit_checks.py` — module with 9 check functions:
   - `check_duplicates(df, key_cols)` — exact duplicate detection
   - `check_outliers(df, numeric_cols)` — IQR + Z-score
   - `check_concentration(df, cat_cols)` — value frequency percentages
   - `check_trend_anomalies(df, date_col, group_col)` — MoM spikes >2x
   - `check_missing_data(df)` — null % per column
   - `check_round_numbers(df, numeric_cols)` — suspicious round amounts
   - `check_weekend_activity(df, date_col)` — weekend/holiday transactions
   - `check_benfords_law(df, numeric_cols)` — first-digit distribution test
   - `check_split_transactions(df, date_col, vendor_col, amount_col)` — same-day splits near limits
   - `run_all_checks(df, settings)` — orchestrator, returns all findings
2. `launcher.py` — `/api/risk-scan` endpoint:
   - Loads 100% of data via `get_cached_dataframe()`
   - Calls `run_all_checks()`
   - Returns structured JSON with findings + flagged rows
3. Wire "risk scan" command in chat panel to call `/api/risk-scan`
4. Display findings in chat panel with risk level badges

---

### Phase 3: SQLite Persistence
**Files:** `utils/db.py` (new), `launcher.py`, `templates/dashboard.html`
**Dependencies:** Phase 1 (chat panel), Phase 2 (risk scan results to store)
**Token cost:** $0

**What to build:**
1. `utils/db.py` — SQLite helper module:
   - `get_db()` — returns connection to `Data/audit_bot.db`, auto-creates tables on first call
   - `save_message(project, role, content, actions, risks, source, tokens)` — insert chat message
   - `get_history(project, limit=50)` — fetch recent messages
   - `clear_history(project)` — delete all messages for project
   - `save_scan(project, results)` — insert risk scan + individual findings
   - `get_scans(project)` — list past scans
   - `get_scan_findings(scan_id)` — get findings for a scan
2. `launcher.py` — endpoints:
   - `GET /api/chat/history` — load chat history from SQLite
   - `DELETE /api/chat/history` — clear chat history
   - Update `/api/risk-scan` to store results in SQLite
3. `templates/dashboard.html`:
   - Load chat history on panel open
   - Save every message (local + AI) via API
   - "Clear History" button
   - Token usage counter display

---

### Phase 4: GPT-5.2 Pro AI Integration
**Files:** `utils/ai_chat.py` (new), `launcher.py`, `templates/dashboard.html`, `requirements.txt`, `.env`
**Dependencies:** Phase 1 (chat UI), Phase 2 (audit findings for context), Phase 3 (history for conversation context)
**Token cost:** Per-query (~$0.02-0.09)

**What to build:**
1. `utils/ai_chat.py` — OpenAI integration:
   - `init_client()` — OpenAI client from `.env` API key (model: `gpt-5.2-pro`)
   - `build_context(df, settings, scan_results, dashboard_state)` — assembles audit context for prompt
   - `chat(message, context, history)` — sends to GPT-5.2 Pro, returns parsed response
   - System prompt with audit expertise + action catalog + response format
   - Response parser — extracts message, actions, risks from JSON response
   - Token counting — track usage per request via `response.usage`
2. `launcher.py`:
   - `POST /api/chat` — receives message + dashboard state, builds context, routes to GPT-5.2 Pro, returns response, saves to SQLite
3. `templates/dashboard.html`:
   - Route unmatched commands to `/api/chat`
   - Typing indicator while waiting for AI
   - Display AI responses with markdown formatting
   - Display risk badges (HIGH/MEDIUM/LOW)
   - Action proposals from AI go through same [Apply] [Cancel] confirm flow
   - Send dashboard state (current filters, trend settings) with each AI request
4. `requirements.txt` — add `openai>=1.0.0`
5. `.env` — add `OPENAI_API_KEY=sk-...`

**GPT-5.2 Pro advantages over GPT-4.1:**
- 400K context window (vs 1M — still more than enough for audit data subsets)
- 128K max output (longer reports in a single response)
- Cached input pricing at $0.175/M (90% off) — system prompt + schema repeated every request costs nearly nothing
- `xhigh` reasoning effort for complex audit analysis

---

### Phase 5: Risk Report Generator
**Files:** `utils/ai_chat.py`, `templates/dashboard.html`
**Dependencies:** Phase 2 (audit checks) + Phase 4 (GPT-5.2 Pro)
**Token cost:** ~$0.09-0.15 per report

**What to build:**
1. "Generate Risk Report" button in chat panel
2. Report flow:
   - Run all 9 audit checks (Phase 2)
   - Send findings + flagged rows to GPT-5.2 Pro
   - GPT-5.2 Pro writes structured audit report:
     ```
     RISK ASSESSMENT REPORT
     Project: [name] | Period: [dates] | Records: [count]

     HIGH RISK FINDINGS
     1. [finding + evidence + recommendation]

     MEDIUM RISK FINDINGS
     ...

     LOW RISK / OBSERVATIONS
     ...

     RECOMMENDATIONS
     1. [action items]
     ```
3. Display formatted report in chat panel
4. "Download as PDF" button — printable report
5. "Download as Excel" — findings + flagged rows in worksheets (via `_write_xlsx_raw`)

---

### Phase 6: Smart Hybrid Commands
**Files:** `templates/dashboard.html`, `utils/ai_chat.py`
**Dependencies:** All previous phases
**Token cost:** Minimal (only ambiguous parts go to AI)

**What to build:**
1. Multi-step command detection:
   - "Filter to June, compare transporters, and tell me what's risky"
   - Local parser handles: filter + compare
   - AI handles: "tell me what's risky"
   - Both execute in sequence
2. Smart column matching:
   - "group by transporter" -> matches display name "Transporter Name" -> raw column "Number of forwarding agent"
   - Uses `currentSettings.top_columns` display name mapping
3. Ambiguity resolution:
   - "compare the periods" -> bot asks which periods in chat
   - "show me the top ones" -> bot asks which column
4. Context-aware suggestions:
   - After a risk scan: "Want me to filter to the period with the most anomalies?"
   - After comparison: "Should I isolate the top 3 transporters in the trend chart?"

---

## Phase Summary

| Phase | What | New Files | Token Cost | Depends On |
|-------|------|-----------|-----------|------------|
| 1 | Chat UI + Local Parser (39 actions) | — | $0 | — |
| 2 | 9 Audit Checks (pandas) | `utils/audit_checks.py` | $0 | Phase 1 |
| 3 | SQLite Persistence | `utils/db.py` | $0 | Phase 1, 2 |
| 4 | GPT-5.2 Pro Integration | `utils/ai_chat.py` | Per-query | Phase 1, 2, 3 |
| 5 | Risk Report Generator | — | Per-report | Phase 2, 4 |
| 6 | Smart Hybrid Commands | — | Minimal | All |

---

## GPT-5.2 Pro Model Reference

| Spec | Value |
|------|-------|
| Model ID | `gpt-5.2-pro` |
| Input pricing | $1.75/M tokens |
| Output pricing | $14.00/M tokens |
| Cached input | $0.175/M tokens (90% off) |
| Context window | 400,000 tokens |
| Max output | 128,000 tokens |
| Knowledge cutoff | August 2025 |
| Reasoning effort | medium, high, xhigh |
| Multimodal | Text + Image input |
| Release date | December 11, 2025 |

---

## Verification

After each phase:
```bash
# Python syntax
python3 -c "import py_compile; py_compile.compile('launcher.py', doraise=True)"

# JS syntax (dashboard)
grep -n '</script>' templates/dashboard.html | tail -1  # get line N
sed -n '1035,<N-1>p' templates/dashboard.html > /tmp/js.js && node --check /tmp/js.js

# SQLite schema
python3 -c "import sqlite3; c=sqlite3.connect('Data/audit_bot.db'); print(c.execute('SELECT name FROM sqlite_master').fetchall())"

# Test endpoints
curl -s http://127.0.0.1:5000/api/risk-scan | python3 -m json.tool
curl -s -X POST http://127.0.0.1:5000/api/chat -H 'Content-Type: application/json' -d '{"message":"test"}' | python3 -m json.tool
```

---

**Version:** 1.0
**Created:** 25-Feb-2026
**Developer:** Hamza Yahya - Internal Audit
