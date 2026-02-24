"""
AI Chat Integration — OpenAI GPT-5.2 Pro client for audit analysis.
Handles context assembly, chat completions, response parsing, and report generation.
"""
import os
import json
from utils.logging import get_logger

log = get_logger(__name__)

_client = None
MODEL = 'gpt-5.2'

SYSTEM_PROMPT = """You are an Internal Audit AI Assistant embedded in a data analysis dashboard.

YOU HAVE TWO ROLES:
1. ANALYST — identify risks, red flags, anomalies in audit data
2. CONTROLLER — operate the dashboard by returning actions

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

AVAILABLE ACTIONS (use "type" field):
- setDateFilter {start, end} — set date range
- applyFilter — apply current filter
- clearDateFilter — reset to full range
- setTrendGroup {column} — group trend by column
- setTrendValue {column} — set value column for SUM
- setTopN {n} — show top N (5/10/15/20/25)
- setSpecificGroups {groups:[...]} — filter to specific groups
- setBaseline {month} — set baseline month (YYYY-MM)
- toggleEcg {which} — toggle ECG theme (Count/Sum)
- setSumChartMode {mode} — set raw/movement mode
- toggleDarkMode — toggle dark/light theme
- setChartView {mode} — bar/list view
- clearIsolation {which} — clear legend isolation
- openComparison — open compare periods modal
- openAdvanced — open advanced analysis modal
- downloadFiltered {format} — download xlsx/csv
- downloadTrend {which} — download trend (Count/Sum)
- exportPDF — export dashboard PDF
- refreshDashboard — refresh all data

RULES:
- Always cite specific numbers, percentages, row counts as evidence
- Rate findings: HIGH, MEDIUM, LOW
- When proposing dashboard actions, explain WHY (audit rationale)
- If user request is ambiguous, ask for clarification in "message"
- Match user's informal column references to actual column names from context
- If no actions are needed, return empty "actions" array
- If no risks to report, return empty "risks" array
- Keep messages concise and actionable
"""

REPORT_PROMPT = """Based on the audit scan results provided, write a structured Risk Assessment Report.

FORMAT:
RISK ASSESSMENT REPORT
Project: {project} | Period: {date_range} | Records: {row_count}

HIGH RISK FINDINGS
1. [finding title]
   Evidence: [specific numbers, rows, percentages]
   Impact: [business impact assessment]
   Recommendation: [actionable next steps]

MEDIUM RISK FINDINGS
...

LOW RISK / OBSERVATIONS
...

SUMMARY OF RECOMMENDATIONS
1. [prioritized action items]

Be specific, cite exact numbers from the findings, and provide actionable audit recommendations.
Do NOT use JSON format for the report — use plain text with the structure above.
"""


def init_client():
    """Initialize OpenAI client from environment variable or .env file."""
    global _client
    api_key = os.environ.get('OPENAI_API_KEY', '')

    # Try loading from .env file if not in environment
    if not api_key:
        env_paths = [
            os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'),
            os.path.join(os.getcwd(), '.env'),
        ]
        for env_path in env_paths:
            if os.path.exists(env_path):
                try:
                    with open(env_path, 'r') as f:
                        for line in f:
                            line = line.strip()
                            if line.startswith('OPENAI_API_KEY='):
                                api_key = line.split('=', 1)[1].strip().strip('"').strip("'")
                                break
                except Exception:
                    pass
            if api_key:
                break

    if not api_key:
        log.warning("OPENAI_API_KEY not found — AI chat will be unavailable")
        return False

    try:
        from openai import OpenAI
        _client = OpenAI(api_key=api_key)
        log.info("OpenAI client initialized (model: %s)", MODEL)
        return True
    except ImportError:
        log.warning("openai package not installed — AI chat unavailable")
        return False
    except Exception as e:
        log.error("OpenAI client init failed: %s", e)
        return False


def is_available():
    """Check if AI chat is available."""
    return _client is not None


def build_context(df, settings, scan_results=None, dashboard_state=None):
    """Build context string for the AI with project data summary."""
    ctx_parts = []

    # Basic project info
    ctx_parts.append(f"Dataset: {len(df)} rows x {len(df.columns)} columns")

    # Column info with types
    col_info = []
    for col in df.columns:
        if col == '_upload_id':
            continue
        dtype = str(df[col].dtype)
        nunique = df[col].nunique()
        null_pct = round(df[col].isnull().sum() / len(df) * 100, 1)
        col_info.append(f"  - {col} ({dtype}, {nunique} unique, {null_pct}% null)")
    ctx_parts.append("Columns:\n" + "\n".join(col_info[:50]))  # cap at 50 columns

    # Date range
    date_col = settings.get('date_column', '')
    if date_col and date_col in df.columns:
        try:
            dates = df[date_col].dropna()
            if len(dates) > 0:
                ctx_parts.append(f"Date range: {dates.min()} to {dates.max()} (column: {date_col})")
        except Exception:
            pass

    # Settings — display name mappings
    top_cols = settings.get('top_columns', [])
    if top_cols:
        mappings = [f"  - {tc['column']} (displayed as \"{tc.get('display_name', tc['column'])}\")"
                    for tc in top_cols]
        ctx_parts.append("Configured dashboard columns:\n" + "\n".join(mappings))

    # Dashboard state
    if dashboard_state:
        state_parts = []
        if dashboard_state.get('startDate'):
            state_parts.append(f"Active filter: {dashboard_state['startDate']} to {dashboard_state.get('endDate', '?')}")
        if dashboard_state.get('trendGroup'):
            state_parts.append(f"Trend grouped by: {dashboard_state['trendGroup']}")
        if dashboard_state.get('trendValue'):
            state_parts.append(f"Trend value column: {dashboard_state['trendValue']}")
        if state_parts:
            ctx_parts.append("Current dashboard state:\n  " + "\n  ".join(state_parts))

    # Scan results summary
    if scan_results:
        findings = scan_results if isinstance(scan_results, list) else scan_results.get('findings', [])
        if findings:
            ctx_parts.append(f"\nAudit scan results ({len(findings)} findings):")
            for f in findings[:20]:
                level = f.get('level', '?').upper()
                ctx_parts.append(f"  [{level}] {f.get('title', '')} — {f.get('detail', '')}")
                # Include evidence summary (truncated)
                evidence = f.get('evidence', [])
                if evidence and len(evidence) > 0:
                    ev_str = json.dumps(evidence[:5], default=str)
                    if len(ev_str) > 500:
                        ev_str = ev_str[:500] + '...'
                    ctx_parts.append(f"    Evidence sample: {ev_str}")

    return "\n\n".join(ctx_parts)


def chat(message, context, history=None):
    """Send message to GPT-5.2 Pro and return parsed response."""
    if not _client:
        return {
            'message': 'AI is not available. Please set OPENAI_API_KEY in your .env file.',
            'actions': [],
            'risks': [],
            'tokens_used': 0,
            'source': 'ai'
        }

    messages = [{'role': 'system', 'content': SYSTEM_PROMPT}]

    # Add context as a system message
    if context:
        messages.append({'role': 'system', 'content': f"CURRENT DATA CONTEXT:\n{context}"})

    # Add recent history for conversation continuity
    if history:
        for h in history[-6:]:  # last 6 messages for context
            role = h.get('role', 'user')
            content = h.get('content', '')
            if role in ('user', 'assistant') and content:
                messages.append({'role': role, 'content': content})

    messages.append({'role': 'user', 'content': message})

    try:
        response = _client.chat.completions.create(
            model=MODEL,
            messages=messages,
            temperature=0.3,
            max_completion_tokens=4096,
            response_format={"type": "json_object"}
        )

        content = response.choices[0].message.content
        tokens = response.usage.total_tokens if response.usage else 0

        # Parse JSON response
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            parsed = {'message': content, 'actions': [], 'risks': []}

        return {
            'message': parsed.get('message', content),
            'actions': parsed.get('actions', []),
            'risks': parsed.get('risks', []),
            'tokens_used': tokens,
            'source': 'ai'
        }

    except Exception as e:
        log.error("GPT-5.2 Pro chat error: %s", e)
        error_msg = str(e)
        if 'api_key' in error_msg.lower() or 'auth' in error_msg.lower():
            error_msg = 'Invalid API key. Check your .env file.'
        elif 'rate' in error_msg.lower():
            error_msg = 'Rate limited. Please wait a moment and try again.'
        elif 'model' in error_msg.lower():
            error_msg = f'Model {MODEL} not available. Check your OpenAI plan.'
        return {
            'message': f'AI error: {error_msg}',
            'actions': [],
            'risks': [],
            'tokens_used': 0,
            'source': 'ai'
        }


def generate_report(df, settings, scan_results):
    """Generate a structured risk assessment report via GPT-5.2 Pro."""
    if not _client:
        return {
            'report': 'AI is not available. Please set OPENAI_API_KEY in your .env file.',
            'tokens_used': 0
        }

    context = build_context(df, settings, scan_results)

    # Build the report prompt with specifics
    date_col = settings.get('date_column', '')
    date_range = 'N/A'
    if date_col and date_col in df.columns:
        try:
            dates = df[date_col].dropna()
            if len(dates) > 0:
                date_range = f"{dates.min()} to {dates.max()}"
        except Exception:
            pass

    prompt = REPORT_PROMPT.format(
        project=settings.get('_project_name', 'Unknown'),
        date_range=date_range,
        row_count=len(df)
    )

    messages = [
        {'role': 'system', 'content': prompt},
        {'role': 'system', 'content': f"DATA CONTEXT:\n{context}"},
        {'role': 'user', 'content': 'Generate the full risk assessment report based on the audit scan findings above.'}
    ]

    try:
        response = _client.chat.completions.create(
            model=MODEL,
            messages=messages,
            temperature=0.2,
            max_completion_tokens=8192
        )

        content = response.choices[0].message.content
        tokens = response.usage.total_tokens if response.usage else 0

        return {
            'report': content,
            'tokens_used': tokens
        }

    except Exception as e:
        log.error("Report generation error: %s", e)
        return {
            'report': f'Report generation failed: {str(e)}',
            'tokens_used': 0
        }
