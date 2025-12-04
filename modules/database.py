import streamlit as st
from google import genai
from supabase import create_client, Client

def init_gemini():
    """Initialize the Gemini client using secrets."""
    try:
        api_key = st.secrets.get("GEMINI_API_KEY")
        if api_key:
            return genai.Client(api_key=api_key)
    except Exception as e:
        st.error(f"Error initializing Gemini: {e}")
    return None

def init_supabase():
    """Initialize the Supabase client using secrets."""
    try:
        url = st.secrets.get("SUPABASE_URL")
        key = st.secrets.get("SUPABASE_SERVICE_ROLE_KEY")
        if url and key:
            return create_client(url, key)
    except Exception as e:
        st.error(f"Error initializing Supabase: {e}")
    return None
