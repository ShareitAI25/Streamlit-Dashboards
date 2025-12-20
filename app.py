import streamlit as st
import datetime
import pandas as pd
import uuid
from modules.database import (
    init_gemini,
    init_supabase,
    save_chat_message,
    load_chat_history,
    get_all_sessions,
    get_advertisers_cached,
    get_all_sessions_cached,
    load_chat_history_cached,
    update_chat_title,
)

# NOTE: Streamlit hot-reload can keep old imported modules in-memory.
# If `modules.database` was loaded before this helper existed, a direct
# `from modules.database import get_instance_ids_by_names_cached` can fail.
try:
    from modules.database import get_instance_ids_by_names_cached
except ImportError:
    try:
        import importlib
        import modules.database as _db

        importlib.reload(_db)
        get_instance_ids_by_names_cached = getattr(_db, "get_instance_ids_by_names_cached", None)
    except Exception:
        get_instance_ids_by_names_cached = None
from modules.agent import get_agent_response
from modules.pdf_generator import generate_pdf_report
from modules.visualizer import render_visualizer

# Initialize Clients (after auth gate)
client = None
supabase = None


def _get_auth_users() -> dict[str, str]:
    """Return a mapping of username -> password from st.secrets.

    Supported secrets formats:
    - AUTH_USERNAME + AUTH_PASSWORD
    - AUTH_USERS as a TOML dict/table
    - AUTH_USERS as a JSON string dict
    """
    users: dict[str, str] = {}

    username = st.secrets.get("AUTH_USERNAME")
    password = st.secrets.get("AUTH_PASSWORD")
    if isinstance(username, str) and isinstance(password, str) and username:
        users[username] = password

    auth_users = st.secrets.get("AUTH_USERS")
    if isinstance(auth_users, dict):
        for k, v in auth_users.items():
            if isinstance(k, str) and isinstance(v, str) and k:
                users[k] = v
    elif isinstance(auth_users, str) and auth_users.strip():
        try:
            import json

            parsed = json.loads(auth_users)
            if isinstance(parsed, dict):
                for k, v in parsed.items():
                    if isinstance(k, str) and isinstance(v, str) and k:
                        users[k] = v
        except Exception:
            pass

    return users


def _require_auth():
    if "is_authenticated" not in st.session_state:
        st.session_state.is_authenticated = False
    if "auth_user" not in st.session_state:
        st.session_state.auth_user = None

    if st.session_state.is_authenticated:
        return

    users = _get_auth_users()
    if not users:
        st.error(
            "Authentication is not configured. Add AUTH_USERNAME/AUTH_PASSWORD (or AUTH_USERS) to Streamlit secrets."
        )
        st.stop()

    st.title("Sign in")
    with st.form("login_form"):
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Sign in", type="primary")

    if submitted:
        if isinstance(u, str) and isinstance(p, str) and users.get(u) == p:
            st.session_state.is_authenticated = True
            st.session_state.auth_user = u
            st.rerun()
        else:
            st.error("Invalid username or password.")

    st.stop()


def _new_chat_id() -> str:
    return f"New Chat {uuid.uuid4().hex[:8]}"


def _scope_from_selection(selected_advertisers: list[str], selected_instance_ids: list[int]):
    if not selected_advertisers:
        return {"mode": "global"}

    scope = {
        "mode": "instance",
        "advertiser_name": selected_advertisers[0],
        "amc_instance_id": None,
    }
    if selected_instance_ids:
        scope["amc_instance_id"] = selected_instance_ids[0]
    return scope


def _ensure_session_state():
    if "chat_history_cache" not in st.session_state:
        st.session_state.chat_history_cache = {}
    if "chat_persisted" not in st.session_state:
        st.session_state.chat_persisted = {}
    if "chat_titles" not in st.session_state:
        st.session_state.chat_titles = {}
    if "chat_scope_lock" not in st.session_state:
        st.session_state.chat_scope_lock = {}
    if "date_range" not in st.session_state:
        today = datetime.date.today()
        last_30 = today - datetime.timedelta(days=30)
        st.session_state.date_range = (last_30, today)
    if "show_date_dialog" not in st.session_state:
        st.session_state.show_date_dialog = False


def _lock_chat_scope(chat_id: str, scope: dict):
    if chat_id not in st.session_state.chat_scope_lock:
        st.session_state.chat_scope_lock[chat_id] = scope


def _persist_message_if_needed(
    chat_id: str,
    role: str,
    content: str,
    *,
    sql_query: str | None = None,
    chart_config: dict | None = None,
    data_snapshot=None,
    scope: dict | None = None,
):
    """Persist a message to Supabase only if this chat is marked as persisted.

    If the chat is not persisted yet (draft), it becomes persisted on the first non-empty
    user message.
    """
    if not supabase:
        return

    if not content:
        return

    is_persisted = bool(st.session_state.chat_persisted.get(chat_id))
    is_first_persist = False

    if not is_persisted and role == "user":
        st.session_state.chat_persisted[chat_id] = True
        is_persisted = True
        is_first_persist = True

    if not is_persisted:
        return

    # Persist metadata on the first persisted message for this chat
    if is_first_persist:
        meta_payload: dict = {}

        if scope:
            meta_payload["scope"] = scope

        title = st.session_state.chat_titles.get(chat_id)
        if isinstance(title, str) and title.strip():
            meta_payload["title"] = title.strip()

        meta = {"_meta": meta_payload} if meta_payload else None
        if chart_config and isinstance(chart_config, dict):
            if meta:
                chart_config = {**chart_config, **meta}
        else:
            chart_config = meta

        # Invalidate cached session lists / history for fast pick-up
        # Pylance may not know Streamlit cache wrappers expose `.clear()`.
        for fn in (get_all_sessions_cached, load_chat_history_cached):
            try:
                clear_fn = getattr(fn, "clear", None)
                if callable(clear_fn):
                    clear_fn()
            except Exception:
                pass

    save_chat_message(
        supabase,
        chat_id,
        role,
        content,
        sql_query=sql_query,
        chart_config=chart_config,
        data_snapshot=data_snapshot,
    )

_ensure_session_state()

# Auth gate (protect the entire app, including DB/API clients)
_require_auth()

# Initialize Clients
client = init_gemini()
supabase = init_supabase()

# Defaults (avoid undefined variables)
advertisers: list[str] = []
selected_advertisers: list[str] = []
selected_instance_ids: list[int] = []
system_instruction = ""

PROMPT_TOOLTIPS: dict[str, str] = {
    "Show Time to Conversion": "Shows a distribution of time (days) to conversion, by campaign or bucket.",
    "Analyze NTB Metrics": "Analyzes New-to-Brand metrics (NTB purchases, % NTB) to understand acquisition.",
    "Overlap Analysis": "Explores overlaps/shared audiences for targeting opportunities.",
    "Show Spend Trend": "Visualizes spend/activity trends over time.",
    "List Advertisers": "Lists the advertisers/instances available in your AMC.",
    "Check System Status": "Verifies that the assistant and connection are working (quick diagnostic response).",
}

MARKETPLACE_FLAGS: dict[str, str] = {
    "US": "🇺🇸",
    "UK": "🇬🇧",
    "DE": "🇩🇪",
    "FR": "🇫🇷",
    "IT": "🇮🇹",
    "ES": "🇪🇸",
    "CA": "🇨🇦",
    "JP": "🇯🇵",
    "MX": "🇲🇽",
    "BR": "🇧🇷",
    "AU": "🇦🇺",
    "IN": "🇮🇳",
    "NL": "🇳🇱",
}

MARKETPLACE_NAMES: dict[str, str] = {
    "US": "United States",
    "UK": "United Kingdom",
    "DE": "Germany",
    "FR": "France",
    "IT": "Italy",
    "ES": "Spain",
    "CA": "Canada",
    "JP": "Japan",
    "MX": "Mexico",
    "BR": "Brazil",
    "AU": "Australia",
    "IN": "India",
    "NL": "Netherlands",
}

# ---------------------------------------------------------
# CSS TWEAKS (Cursor Pointer)
# ---------------------------------------------------------
st.markdown("""
    <style>
    /* Force pointer cursor on the FULL Selectbox control (not just the arrow) */
    .stSelectbox div[data-baseweb="select"],
    .stSelectbox div[data-baseweb="select"] * ,
    .stMultiSelect div[data-baseweb="select"],
    .stMultiSelect div[data-baseweb="select"] * {
        cursor: pointer !important;
    }

    /* Keep DateInput clickable look without affecting normal text inputs */
    div[data-testid="stDateInput"] div[data-baseweb="input"],
    div[data-testid="stDateInput"] div[data-baseweb="input"] * ,
    div[data-testid="stDateInput"] input {
        cursor: pointer !important;
    }

    /* Keep sidebar scrollable (avoid overflow hacks that break scrolling) */
    div[data-testid="stSidebarUserContent"] { overflow-y: auto; }

    /* Consistent centered button labels */
    .stButton > button {
        justify-content: center;
        text-align: center;
    }
    </style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# NUEVA SECCIÓN: CHATBOT DE IA
# ---------------------------------------------------------

# (Header moved inside conditional logic below)

# ---------------------------------------------------------
# SIDEBAR: CONFIGURACIÓN
# ---------------------------------------------------------
with st.sidebar:
    st.header("Navigation")

    if st.session_state.get("is_authenticated"):
        st.caption(f"Signed in as: {st.session_state.get('auth_user')}")
        if st.button("Logout", use_container_width=True):
            st.session_state.is_authenticated = False
            st.session_state.auth_user = None
            st.rerun()

    page = st.radio("Go to", ["AMC Assistant", "Data Visualizer"], label_visibility="collapsed")

    # --- Common Settings (Date + Marketplace) ---
    advertisers = get_advertisers_cached()

    with st.expander("Filters", expanded=False):
        marketplaces = ["US", "UK", "DE", "FR", "IT", "ES", "CA", "JP", "MX", "BR", "AU", "IN", "NL"]
        marketplace_labels = [
            f"{code} - {MARKETPLACE_NAMES.get(code, '')}" for code in marketplaces
        ]
        selected_marketplace_label = st.selectbox(
            "Marketplace",
            marketplace_labels,
            index=0,
        )
        selected_marketplace = (
            selected_marketplace_label.split(" - ")[0]
            if isinstance(selected_marketplace_label, str) and selected_marketplace_label.strip()
            else marketplaces[0]
        )

        # Date range picker lives in a dialog (prevents clipping inside sidebar)
        current_range = st.session_state.date_range
        if isinstance(current_range, (tuple, list)) and len(current_range) == 2:
            st.caption(f"Date Range: {current_range[0]} → {current_range[1]}")
        else:
            st.caption("Date Range: not set")

        if st.button("Change Date Range", use_container_width=True):
            st.session_state.show_date_dialog = True

    # Always expose date_range as a local variable used later in the app.
    date_range = st.session_state.date_range

    # Date Range dialog (modal; avoids sidebar clipping)
    if st.session_state.get("show_date_dialog"):
        if hasattr(st, "dialog"):
            @st.dialog("Choose a date range")
            def _date_range_dialog():
                new_range = st.date_input(
                    "Date Range",
                    st.session_state.date_range,
                    format="YYYY-MM-DD",
                )

                c1, c2 = st.columns(2)
                apply_clicked = c1.button("Apply", type="primary", use_container_width=True)
                cancel_clicked = c2.button("Cancel", use_container_width=True)

                if apply_clicked:
                    if isinstance(new_range, (tuple, list)) and len(new_range) == 2:
                        st.session_state.date_range = (new_range[0], new_range[1])
                    st.session_state.show_date_dialog = False
                    st.rerun()

                if cancel_clicked:
                    st.session_state.show_date_dialog = False
                    st.rerun()

            _date_range_dialog()
        else:
            st.warning(
                "Your Streamlit version does not support st.dialog. Please update Streamlit or move the Date Range control outside the sidebar."
            )
            st.session_state.show_date_dialog = False

    # --- Assistant Specific Settings ---
    if page == "AMC Assistant":
        # Auto-create a new (draft) chat on first entry.
        if "did_autocreate_chat" not in st.session_state:
            st.session_state.did_autocreate_chat = True
            st.session_state.draft_chat_id = _new_chat_id()
            st.session_state.current_chat_id = st.session_state.draft_chat_id
            st.session_state.chat_persisted[st.session_state.draft_chat_id] = False
            st.session_state.messages = []
            st.session_state.last_loaded_chat_id = st.session_state.current_chat_id

        if "draft_chat_id" not in st.session_state:
            st.session_state.draft_chat_id = _new_chat_id()
            st.session_state.chat_persisted[st.session_state.draft_chat_id] = False

        # DB sessions
        db_sessions = get_all_sessions_cached() or get_all_sessions(supabase)
        db_sessions = db_sessions or []
        for sid in db_sessions:
            st.session_state.chat_persisted[sid] = True

        # Combined list (draft first)
        all_sessions = [st.session_state.draft_chat_id] + [s for s in db_sessions if s != st.session_state.draft_chat_id]
        st.session_state.all_sessions = all_sessions

        if "current_chat_id" not in st.session_state:
            st.session_state.current_chat_id = st.session_state.draft_chat_id

        with st.expander("Chats", expanded=True):
            if st.button("➕ New chat"):
                st.session_state.draft_chat_id = _new_chat_id()
                st.session_state.chat_persisted[st.session_state.draft_chat_id] = False
                st.session_state.current_chat_id = st.session_state.draft_chat_id
                st.session_state.messages = []
                st.session_state.last_loaded_chat_id = st.session_state.current_chat_id
                st.rerun()

            def _format_chat_option(option_id: str) -> str:
                # 1. Draft
                if option_id == st.session_state.draft_chat_id:
                    return "➕ New Chat (Draft)"
                
                # 2. Known Title (from session state)
                title = st.session_state.chat_titles.get(option_id)
                if title:
                    return title
                
                # 3. Fallback
                return f"Chat {option_id[:6]}..."

            selected_chat_id = st.selectbox(
                "Chat",
                st.session_state.all_sessions,
                index=(
                    st.session_state.all_sessions.index(st.session_state.current_chat_id)
                    if st.session_state.current_chat_id in st.session_state.all_sessions
                    else 0
                ),
                format_func=_format_chat_option,
                label_visibility="collapsed",
            )
        
        if selected_chat_id != st.session_state.current_chat_id:
            st.session_state.current_chat_id = selected_chat_id
            # No explicit rerun needed: widget interaction already reruns the script.
        
        # --- Per-chat scope selection (Global OR Single Advertiser). Locked after first question. ---
        chat_id = st.session_state.current_chat_id
        locked_scope = st.session_state.chat_scope_lock.get(chat_id)

        # For persisted (non-draft) chats without stored scope, lock as global by default.
        if (
            st.session_state.chat_persisted.get(chat_id)
            and chat_id != st.session_state.draft_chat_id
            and not locked_scope
        ):
            st.session_state.chat_scope_lock[chat_id] = {"mode": "global", "legacy": True}
            locked_scope = st.session_state.chat_scope_lock.get(chat_id)

        scope_options = ["🌎 Global"] + advertisers

        with st.expander("Context", expanded=True):
            if locked_scope and isinstance(locked_scope, dict):
                locked_mode = locked_scope.get("mode")
                if locked_mode == "instance" and locked_scope.get("advertiser_name") in advertisers:
                    selected_scope_label = str(locked_scope.get("advertiser_name"))
                else:
                    selected_scope_label = "🌎 Global"

                st.selectbox(
                    "Advertiser (locked)",
                    scope_options,
                    index=scope_options.index(
                        selected_scope_label if isinstance(selected_scope_label, str) else "🌎 Global"
                    ),
                    disabled=True,
                )
            else:
                selected_scope_label = st.selectbox(
                    "Advertiser (Global = All)",
                    scope_options,
                    index=0,
                    key=f"scope_select_{chat_id}",
                )

        if not isinstance(selected_scope_label, str) or selected_scope_label == "🌎 Global":
            selected_advertisers = []
        else:
            selected_advertisers = [selected_scope_label]

        # Resolve selected instance IDs (used to scope all AMC queries)
        selected_instance_ids = []
        if selected_advertisers and callable(get_instance_ids_by_names_cached):
            resolved_ids = get_instance_ids_by_names_cached(tuple(selected_advertisers))
            if isinstance(resolved_ids, (list, tuple, set)):
                resolved_ids_list = list(resolved_ids)
            else:
                resolved_ids_list = []
            selected_instance_ids = [int(x) for x in resolved_ids_list if isinstance(x, int)]
        
        # Logic & Context Handling
        if not selected_advertisers:
            st.caption("Context: Global")
            system_instruction = (
                "You have access to data for ALL advertisers. "
                "Do not filter by advertiser unless specifically asked in the user's question."
            )
        else:
            st.caption(f"Context: {', '.join(selected_advertisers)}")
            system_instruction = (
                f"SCOPE RESTRICTION: You are strictly limited to the following AMC instances: {selected_advertisers}. "
                "You MUST scope every query to these instances using `amc_query_execution.amc_instance_id` (or a join to `amc_instance`)."
            )

        with st.expander("Quick actions", expanded=False):
            quick_prompts = [
                "Show Time to Conversion",
                "Analyze NTB Metrics",
                "Overlap Analysis",
                "Show Spend Trend",
                "List Advertisers",
            ]

            for qp in quick_prompts:
                if st.button(
                    qp,
                    key=f"sidebar_{qp}",
                    use_container_width=True,
                    help=PROMPT_TOOLTIPS.get(qp),
                ):
                    if "messages" not in st.session_state:
                        st.session_state.messages = []
                    scope = _scope_from_selection(selected_advertisers, selected_instance_ids)
                    _lock_chat_scope(st.session_state.current_chat_id, scope)
                    st.session_state.messages.append({"role": "user", "content": qp})
                    _persist_message_if_needed(
                        st.session_state.current_chat_id,
                        "user",
                        qp,
                        scope=scope,
                    )
                    st.rerun()

        with st.expander("Advanced", expanded=False):
            st.caption("Technical details")
            
            # --- Custom Instructions ---
            custom_instructions = st.text_area(
                "Custom System Instructions",
                help="Add specific rules, persona details, or constraints for the AI agent.",
                key="custom_instructions"
            )
            
            if custom_instructions and custom_instructions.strip():
                system_instruction += f"\n\nADDITIONAL USER INSTRUCTIONS:\n{custom_instructions.strip()}"

            with st.expander("System prompt", expanded=False):
                st.code(system_instruction, language="text")

            with st.expander("Database schema", expanded=False):
                schema_info = {
                "amc_instance": {
                    "columns": ["amc_instance_id", "company_id", "region_id", "name", "instance_id"],
                    "description": "Registry of AMC Instances (Advertisers)."
                },
                "amc_query_execution": {
                    "columns": ["amc_query_execution_id", "created_at", "amc_instance_id"],
                    "description": "Log of executed AMC queries."
                },
                "amc_asin_cross_purchase": {
                    "columns": ["lead_asin", "follow_up_asin", "cross_purchased_count", "avg_days_between_purchases", "amc_query_execution_id"],
                    "description": "Products purchased together (Lead -> Follow-up)."
                },
                "amc_campaign_ntb_metrics": {
                    "columns": ["campaign_id", "new_to_brand_purchases", "ntb_purchases_percent", "amc_query_execution_id"],
                    "description": "New-To-Brand metrics by campaign."
                },
                
                "amc_time_to_conversion": {
                    "columns": ["time_to_conversion_bucket", "purchases", "campaign_id", "amc_query_execution_id"],
                    "description": "Distribution of days to conversion."
                },
                "amc_lifestyle": {
                    "columns": ["amc_lifestyle_id", "name"],
                    "description": "Lifestyle segment definitions."
                },
                "amc_lifestyle_size": {
                    "columns": ["size", "amc_lifestyle_id", "amc_query_execution_id"],
                    "description": "Size of lifestyle segments."
                },
                "amc_ntb_gateaway": {
                    "columns": ["asin", "users_with_purchases", "ntb_users", "amc_query_execution_id"],
                    "description": "Gateway ASINs driving NTB users."
                }
                }
                st.json(schema_info)

            if st.button("🗑️ Clear current chat"):
                st.warning("Delete functionality not yet implemented in DB.")
    
    else:
        # Visualizer Specific Sidebar
        st.info("Use the main panel to configure your charts.")
        # We still need system_instruction variable to be defined to avoid errors if referenced later
        system_instruction = ""

# ---------------------------------------------------------
# MAIN CONTENT ROUTING
# ---------------------------------------------------------

if page == "Data Visualizer":
    render_visualizer(supabase, advertisers)
    st.stop()

# ---------------------------------------------------------
# AMC ASSISTANT CONTENT
# ---------------------------------------------------------

st.divider() # Una línea visual para separar secciones
st.header("☁️ Amazon Marketing Cloud (AMC) Assistant")
st.caption("Ask me about your campaign performance, audience overlaps, or SQL queries for AMC.")

# Load Chat History from DB
if "messages" not in st.session_state or st.session_state.get("last_loaded_chat_id") != st.session_state.current_chat_id:
    with st.spinner("Loading chat history..."):
        chat_id = st.session_state.current_chat_id

        # Draft chat: do not hit DB until it has messages.
        if not st.session_state.chat_persisted.get(chat_id, True):
            st.session_state.messages = []
            st.session_state.chat_history_cache[chat_id] = []
            st.session_state.last_loaded_chat_id = chat_id
        elif chat_id in st.session_state.chat_history_cache:
            st.session_state.messages = st.session_state.chat_history_cache[chat_id]
            st.session_state.last_loaded_chat_id = chat_id
        else:
            raw_history = load_chat_history_cached(chat_id) or load_chat_history(supabase, chat_id)
            processed_history = []
            for msg in raw_history:
                if not isinstance(msg, dict):
                    continue

                data_df = None
                data_snapshot = msg.get("data_snapshot")
                if isinstance(data_snapshot, (list, tuple, dict)) and data_snapshot:
                    try:
                        data_df = pd.DataFrame(data_snapshot)
                    except Exception:
                        data_df = None

                processed_history.append(
                    {
                        "role": msg.get("role"),
                        "content": msg.get("content"),
                        "sql": msg.get("sql_query"),
                        "data": data_df,
                        "chart_config": msg.get("chart_config"),
                    }
                )

                # Read metadata if present
                chart_cfg = msg.get("chart_config")
                if isinstance(chart_cfg, dict):
                    meta = chart_cfg.get("_meta")
                    if isinstance(meta, dict):
                        scope = meta.get("scope")
                        if isinstance(scope, dict) and chat_id not in st.session_state.chat_scope_lock:
                            st.session_state.chat_scope_lock[chat_id] = scope

                        title = meta.get("title")
                        if isinstance(title, str) and title.strip():
                            st.session_state.chat_titles[chat_id] = title.strip()

            st.session_state.chat_history_cache[chat_id] = processed_history
            st.session_state.messages = processed_history

        st.session_state.last_loaded_chat_id = chat_id

        # Legacy sessions without stored scope: lock as global once there is history.
        if st.session_state.messages and chat_id not in st.session_state.chat_scope_lock:
            st.session_state.chat_scope_lock[chat_id] = {"mode": "global", "legacy": True}

# Use the current chat's messages
current_messages = st.session_state.messages

# Chat title (shown above messages)
chat_id = st.session_state.current_chat_id
default_title = st.session_state.chat_titles.get(chat_id)
if not isinstance(default_title, str) or not default_title.strip():
    default_title = "New chat" if not st.session_state.chat_persisted.get(chat_id, True) else "Chat"
default_title = default_title.strip()

st.markdown(f"### {default_title}")
with st.expander("Rename chat", expanded=False):
    with st.form(key=f"rename_chat_form_{chat_id}"):
        new_title = st.text_input("Name", value=default_title)
        submitted = st.form_submit_button("Save")
    if submitted:
        new_title_clean = (new_title or "").strip()
        if not new_title_clean:
            st.warning("Chat name cannot be empty.")
        else:
            st.session_state.chat_titles[chat_id] = new_title_clean
            if st.session_state.chat_persisted.get(chat_id, False):
                update_chat_title(supabase, chat_id, new_title_clean)
                for fn in (get_all_sessions_cached, load_chat_history_cached):
                    try:
                        clear_fn = getattr(fn, "clear", None)
                        if callable(clear_fn):
                            clear_fn()
                    except Exception:
                        pass
            st.rerun()

# 2. Mostrar los mensajes del historial al recargar la app
for message in current_messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        
        # Render rich content if available
        if message.get("sql"):
            with st.expander("View Generated SQL"):
                st.code(message["sql"], language="sql")
        
        if message.get("data") is not None:
            st.dataframe(message["data"])
            
            # Dynamic Chart Rendering
            try:
                chart_config = message.get("chart_config")
                if chart_config:
                    if chart_config.get("type") == "bar":
                        st.bar_chart(message["data"], x=chart_config.get("x"), y=chart_config.get("y"))
                    elif chart_config.get("type") == "line":
                        # Fallback check for columns
                        if chart_config.get("x") in message["data"].columns and chart_config.get("y") in message["data"].columns:
                            st.line_chart(message["data"], x=chart_config.get("x"), y=chart_config.get("y"))
            except Exception as e:
                st.warning(f"Could not render chart: {e}")

# Starter Prompts (Only if chat is empty)
if not current_messages:
    st.markdown("### 🚀 Try a starter prompt:")
    
    # Row 1
    col1, col2, col3 = st.columns(3)
    prompt_to_run = None
    
    with col1:
        if st.button(
            "Show Time to Conversion",
            use_container_width=True,
            help=PROMPT_TOOLTIPS.get("Show Time to Conversion"),
        ):
            prompt_to_run = "Show Time to Conversion"
    with col2:
        if st.button(
            "Analyze NTB Metrics",
            use_container_width=True,
            help=PROMPT_TOOLTIPS.get("Analyze NTB Metrics"),
        ):
            prompt_to_run = "Analyze NTB Metrics"


    # Row 2
    col4, col5, col6 = st.columns(3)
    with col4:
        if st.button(
            "Show Spend Trend",
            use_container_width=True,
            help=PROMPT_TOOLTIPS.get("Show Spend Trend"),
        ):
            prompt_to_run = "Show Spend Trend"
    with col5:
        if st.button(
            "List Advertisers",
            use_container_width=True,
            help=PROMPT_TOOLTIPS.get("List Advertisers"),
        ):
            prompt_to_run = "List Advertisers"
    with col6:
        if st.button(
            "Check System Status",
            use_container_width=True,
            help=PROMPT_TOOLTIPS.get("Check System Status"),
        ):
            prompt_to_run = "Check System Status"
            
    if prompt_to_run:
        # Add user message to local state
        scope = _scope_from_selection(selected_advertisers, selected_instance_ids)
        _lock_chat_scope(st.session_state.current_chat_id, scope)
        st.session_state.messages.append({"role": "user", "content": prompt_to_run})
        _persist_message_if_needed(
            st.session_state.current_chat_id,
            "user",
            prompt_to_run,
            scope=scope,
        )
        st.rerun()

# 3. Capturar la entrada del usuario
if prompt := st.chat_input("Type your message here..."):
    
    # A. Mostrar mensaje del usuario
    with st.chat_message("user"):
        st.markdown(prompt)
    
    # Update local state
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    # Guardar mensaje del usuario en historial
    scope = _scope_from_selection(selected_advertisers, selected_instance_ids)
    _lock_chat_scope(st.session_state.current_chat_id, scope)
    _persist_message_if_needed(
        st.session_state.current_chat_id,
        "user",
        prompt,
        scope=scope,
    )
    st.rerun()

# Process Response (if last message is user)
if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
    last_user_msg = st.session_state.messages[-1]["content"]
    
    # B. Generar respuesta de la IA (Simulación)
    with st.chat_message("assistant"):
        # Call Mock Agent
        # Pass history excluding the current new message
        history_to_pass = st.session_state.messages[:-1]
        response_obj = get_agent_response(
            client,
            supabase,
            system_instruction,
            last_user_msg,
            selected_advertisers,
            date_range,
            chat_history=history_to_pass,
            selected_instance_ids=selected_instance_ids,
        )
        
        # Display Text
        st.markdown(response_obj["text"])
        
        # Display SQL
        if response_obj["sql"]:
            with st.expander("View Generated SQL"):
                st.code(response_obj["sql"], language="sql")
            
        # Display Data
        if response_obj["data"] is not None:
            st.dataframe(response_obj["data"])
            
            # Dynamic Chart Rendering
            try:
                chart_config = response_obj.get("chart_config")
                if chart_config:
                    if chart_config.get("type") == "bar":
                        st.bar_chart(response_obj["data"], x=chart_config.get("x"), y=chart_config.get("y"))
                    elif chart_config.get("type") == "line":
                        if chart_config.get("x") in response_obj["data"].columns and chart_config.get("y") in response_obj["data"].columns:
                            st.line_chart(response_obj["data"], x=chart_config.get("x"), y=chart_config.get("y"))
            except Exception as e:
                st.warning(f"Could not render chart: {e}")
            
            # PDF Download Button
            try:
                pdf_bytes = generate_pdf_report(last_user_msg, response_obj["text"], response_obj["data"])
                st.download_button(
                    label="📄 Download Professional PDF Report",
                    data=pdf_bytes,
                    file_name="amc_insight_report.pdf",
                    mime="application/pdf"
                )
            except Exception as e:
                st.error(f"Could not generate PDF: {e}")
    
    # Guardar respuesta completa en historial
    data_to_save = None
    if response_obj["data"] is not None:
        try:
            data_to_save = response_obj["data"].to_dict(orient="records")
        except:
            pass

    # Append to local state to prevent re-execution loop
    st.session_state.messages.append({
        "role": "assistant",
        "content": response_obj["text"],
        "sql": response_obj["sql"],
        "data": response_obj["data"],
        "chart_config": response_obj.get("chart_config")
    })

    save_chat_message(
        supabase,
        st.session_state.current_chat_id,
        "assistant",
        response_obj["text"],
        sql_query=response_obj["sql"],
        chart_config=response_obj.get("chart_config"),
        data_snapshot=data_to_save,
    )
    
    # Force reload to update UI with new message
    st.rerun()
