import streamlit as st
from supabase import create_client
import pandas as pd
import json


@st.cache_resource(show_spinner=False)
def _get_cached_supabase_client():
    """Create and cache the Supabase client for the current Streamlit session."""
    url = st.secrets.get("SUPABASE_URL")
    key = st.secrets.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        return None
    return create_client(url, key)


@st.cache_resource(show_spinner=False)
def _get_cached_gemini_client():
    """Create and cache the Gemini client for the current Streamlit session."""
    api_key = st.secrets.get("GEMINI_API_KEY")
    if not api_key:
        return None

    try:
        from google import genai

        return genai.Client(api_key=api_key)
    except ImportError as e:
        st.error(
            "⚠️ Error crítico de librería: No se pudo importar `google.genai`. "
            "Tu instalación parece corrupta. Ejecuta: `pip install --upgrade --force-reinstall google-genai`\n\n"
            f"Detalle: {e}"
        )
        return None

def init_gemini():
    """Initialize Gemini Client with safe import."""
    return _get_cached_gemini_client()

def init_supabase():
    """Initialize Supabase Client."""
    return _get_cached_supabase_client()


@st.cache_data(ttl=60 * 60, show_spinner=False)
def get_advertisers_cached():
    """Fetch distinct advertiser names from Supabase (cached)."""
    supabase = _get_cached_supabase_client()
    if not supabase:
        return []

    try:
        response = supabase.table("amc_instance").select("name").execute()
        data = response.data or []
        advertisers: list[str] = []
        for item in data:
            if isinstance(item, dict):
                name = item.get("name")
                if isinstance(name, str) and name:
                    advertisers.append(name)

        # Preserve stable ordering for UI
        return sorted(set(advertisers))
    except Exception as e:
        st.error(f"Error fetching advertisers from Supabase: {e}")
        return []


@st.cache_data(ttl=5 * 60, show_spinner=False)
def get_all_sessions_cached():
    """Retrieve all unique chat session IDs (cached)."""
    supabase = _get_cached_supabase_client()
    if not supabase:
        return []

    try:
        response = supabase.table("amc_chat_history").select("session_id").execute()
        data = response.data or []
        sessions: set[str] = set()
        for item in data:
            if isinstance(item, dict):
                sid = item.get("session_id")
                if isinstance(sid, str) and sid:
                    sessions.add(sid)

        return sorted(sessions, reverse=True)
    except Exception as e:
        st.error(f"Error fetching sessions: {e}")
        return []


@st.cache_data(ttl=2 * 60, show_spinner=False)
def load_chat_history_cached(session_id: str):
    """Load chat history for a session (cached)."""
    supabase = _get_cached_supabase_client()
    if not supabase:
        return []

    try:
        response = (
            supabase.table("amc_chat_history")
            .select("*")
            .eq("session_id", session_id)
            .order("created_at", desc=False)
            .execute()
        )
        return response.data or []
    except Exception as e:
        st.error(f"Error loading chat history: {e}")
        return []


@st.cache_data(ttl=5 * 60, show_spinner=False)
def _get_execution_ids_for_instances(instance_ids: list[int]):
    supabase = _get_cached_supabase_client()
    if not supabase:
        return []
    try:
        response = supabase.table("amc_query_execution").select("amc_query_execution_id").in_("amc_instance_id", instance_ids).execute()
        return [item["amc_query_execution_id"] for item in response.data]
    except:
        return []


@st.cache_data(ttl=5 * 60, show_spinner=False)
def fetch_table_cached(table_id: str, limit: int, instance_ids: list[int] = None):
    """Fetch table rows as a DataFrame for the visualizer (cached)."""
    supabase = _get_cached_supabase_client()
    if not supabase:
        return pd.DataFrame()

    try:
        query = supabase.table(table_id).select("*")

        if instance_ids:
            if table_id in ["amc_instance", "amc_query_execution"]:
                query = query.in_("amc_instance_id", instance_ids)
            elif table_id != "ads_report":
                # For other AMC tables, filter by execution IDs belonging to the instance
                exec_ids = _get_execution_ids_for_instances(instance_ids)
                if exec_ids:
                    query = query.in_("amc_query_execution_id", exec_ids)
                else:
                    # If no executions for this instance, return empty
                    return pd.DataFrame()

        response = query.limit(int(limit)).execute()
        data = response.data or []
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"Error loading data from {table_id}: {e}")
        return pd.DataFrame()


@st.cache_data(ttl=10 * 60, show_spinner=False)
def get_instance_ids_by_names_cached(instance_names: tuple[str, ...]):
    """Resolve `amc_instance_id` values from instance names (cached)."""
    supabase = _get_cached_supabase_client()
    if not supabase or not instance_names:
        return []

    try:
        response = (
            supabase.table("amc_instance")
            .select("amc_instance_id, name")
            .in_("name", list(instance_names))
            .execute()
        )
        data = response.data or []
        ids: set[int] = set()
        for item in data:
            if isinstance(item, dict):
                raw_id = item.get("amc_instance_id")
                if isinstance(raw_id, int):
                    ids.add(raw_id)

        return sorted(ids)
    except Exception as e:
        st.error(f"Error resolving instance IDs: {e}")
        return []


@st.cache_data(ttl=5 * 60, show_spinner=False)
def get_company_marketplace_ids_for_instance_ids_cached(
    instance_ids: tuple[int, ...],
    start_date: str | None,
    end_date: str | None,
):
    """Derive company_marketplace_id values for the given AMC instance(s) and optional date window.

    This is used to filter `ads_report` (which is keyed by company_marketplace_id) to match
    the selected AMC instance(s) via:
      amc_query_execution -> amc_query_execution_company_marketplace
    """
    supabase = _get_cached_supabase_client()
    if not supabase or not instance_ids:
        return []

    try:
        exec_query = supabase.table("amc_query_execution").select("amc_query_execution_id")
        exec_query = exec_query.in_("amc_instance_id", list(instance_ids))

        # Overlap logic: execution window intersects user window
        if start_date and end_date:
            exec_query = exec_query.lte("start_date", end_date).gte("end_date", start_date)

        exec_resp = exec_query.limit(5000).execute()
        exec_rows = exec_resp.data or []
        exec_ids: list[int] = []
        for row in exec_rows:
            if isinstance(row, dict):
                raw_exec_id = row.get("amc_query_execution_id")
                if isinstance(raw_exec_id, int):
                    exec_ids.append(raw_exec_id)

        if not exec_ids:
            return []

        cm_resp = (
            supabase.table("amc_query_execution_company_marketplace")
            .select("company_marketplace_id")
            .in_("amc_query_execution_id", exec_ids)
            .limit(5000)
            .execute()
        )
        cm_rows = cm_resp.data or []
        cm_ids: set[int] = set()
        for row in cm_rows:
            if isinstance(row, dict):
                raw_cm_id = row.get("company_marketplace_id")
                if isinstance(raw_cm_id, int):
                    cm_ids.add(raw_cm_id)

        return sorted(cm_ids)
    except Exception as e:
        st.error(f"Error resolving company marketplace IDs: {e}")
        return []

def save_chat_message(supabase, session_id, role, content, sql_query=None, chart_config=None, data_snapshot=None):
    """
    Saves a chat message to the 'amc_chat_history' table in Supabase.
    
    Args:
        supabase: The Supabase client instance.
        session_id (str): The unique identifier for the chat session.
        role (str): 'user' or 'assistant'.
        content (str): The text content of the message.
        sql_query (str, optional): The SQL query executed (if any).
        chart_config (dict, optional): Configuration for the chart (if any).
        data_snapshot (list/dict, optional): The data used for the chart (if any).
    """
    if not supabase:
        return None
        
    data = {
        "session_id": session_id,
        "role": role,
        "content": content,
        "sql_query": sql_query,
        "chart_config": chart_config,
        "data_snapshot": data_snapshot
    }
    
    try:
        response = supabase.table("amc_chat_history").insert(data).execute()
        return response
    except Exception as e:
        st.error(f"Error saving chat message: {e}")
        return None


def update_chat_title(supabase, session_id: str, title: str):
    """Persist a chat title for a session.

    Since there is no separate sessions table, we store metadata in the most recent
    row for that session inside `chart_config._meta.title`.
    """
    if not supabase:
        return None

    if not isinstance(session_id, str) or not session_id:
        return None

    if not isinstance(title, str):
        return None

    title = title.strip()
    if not title:
        return None

    try:
        latest = (
            supabase.table("amc_chat_history")
            .select("id, chart_config")
            .eq("session_id", session_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        rows = latest.data or []
        if not rows or not isinstance(rows[0], dict):
            return None

        row_id = rows[0].get("id")
        if not isinstance(row_id, int):
            return None

        existing_cfg = rows[0].get("chart_config")
        if isinstance(existing_cfg, dict):
            merged = dict(existing_cfg)
        else:
            merged = {}

        existing_meta = merged.get("_meta")
        if isinstance(existing_meta, dict):
            meta = dict(existing_meta)
        else:
            meta = {}

        meta["title"] = title
        merged["_meta"] = meta

        return (
            supabase.table("amc_chat_history")
            .update({"chart_config": merged})
            .eq("id", row_id)
            .execute()
        )
    except Exception as e:
        st.error(f"Error updating chat title: {e}")
        return None

def load_chat_history(supabase, session_id):
    """
    Loads chat history for a specific session from Supabase.
    
    Returns:
        list: A list of message dictionaries.
    """
    if not supabase:
        return []
        
    try:
        response = supabase.table("amc_chat_history")\
            .select("*")\
            .eq("session_id", session_id)\
            .order("created_at", desc=False)\
            .execute()
        return response.data
    except Exception as e:
        st.error(f"Error loading chat history: {e}")
        return []

def get_all_sessions(supabase):
    """
    Retrieves all unique session IDs from Supabase.
    
    Returns:
        list: A list of unique session_id strings.
    """
    if not supabase:
        return []
    
    try:
        # Fetch all session_ids (Note: In a production app, you'd want a separate 'sessions' table)
        response = supabase.table("amc_chat_history").select("session_id").execute()
        
        if response.data:
            # Extract unique session IDs using a set
            unique_sessions = sorted(list(set(item['session_id'] for item in response.data)), reverse=True)
            return unique_sessions
        return []
    except Exception as e:
        st.error(f"Error fetching sessions: {e}")
        return []
