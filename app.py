import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
import time # Importamos time para simular que la IA "piensa"
import pandas as pd
import datetime
import random
import os
from fpdf import FPDF
from google import genai
from google.genai import types
from supabase import create_client, Client
# Initialize Gemini Client
try:
    # Try to get key from secrets, otherwise handle gracefully
    api_key = st.secrets.get("GEMINI_API_KEY")
    SUPABASE_URL = st.secrets.get("SUPABASE_URL")
    SUPABASE_SERVICE_ROLE_KEY = st.secrets.get("SUPABASE_SERVICE_ROLE_KEY")
    if api_key:
        client = genai.Client(api_key=api_key)
    else:
        client = None
except Exception as e:
    client = None
    # We will handle the error in the response function

SYSTEM_INSTRUCTION = "You are an expert Amazon Marketing Cloud (AMC) Analyst. You help users optimize campaigns, analyze ROAS, and identify New-To-Brand opportunities. Keep answers concise and professional."


# ---------------------------------------------------------
# NUEVA SECCIÓN: CHATBOT DE IA
# ---------------------------------------------------------

supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

st.divider() # Una línea visual para separar secciones
st.header("☁️ Amazon Marketing Cloud (AMC) Assistant")
st.caption("Ask me about your campaign performance, audience overlaps, or SQL queries for AMC.")

# ---------------------------------------------------------
# SIDEBAR: CONFIGURACIÓN
# ---------------------------------------------------------
with st.sidebar:
    st.header("⚙️ Settings")
    
    # --- Chat History Management ---
    if "chats" not in st.session_state:
        st.session_state.chats = {"Chat 1": []}
    if "current_chat_id" not in st.session_state:
        st.session_state.current_chat_id = "Chat 1"

    col_new, col_title = st.columns([1, 2])
    with col_new:
        if st.button("➕ New"):
            new_id = f"Chat {len(st.session_state.chats) + 1}"
            st.session_state.chats[new_id] = []
            st.session_state.current_chat_id = new_id
            st.rerun()
    with col_title:
        st.write(f"**{st.session_state.current_chat_id}**")

    # Chat Selector
    chat_options = list(st.session_state.chats.keys())
    selected_chat_id = st.selectbox(
        "Previous Chats", 
        chat_options, 
        index=chat_options.index(st.session_state.current_chat_id),
        label_visibility="collapsed"
    )
    
    if selected_chat_id != st.session_state.current_chat_id:
        st.session_state.current_chat_id = selected_chat_id
        st.rerun()
    
    st.divider()

    # Lista simulada de anunciantes
    advertisers = ["Brand A (Electronics)", "Brand B (Fashion)", "Brand C (Home & Kitchen)", "Global Corp"]
    
    # Refactor: Use multiselect for flexible context
    selected_advertisers = st.multiselect(
        "Select Advertisers (Empty = Global):", 
        advertisers,
        help="Leave empty to query all advertisers. Select one or more to filter."
    )
    
    # Date Range Picker
    today = datetime.date.today()
    last_30 = today - datetime.timedelta(days=30)
    date_range = st.date_input(
        "Date Range",
        (last_30, today),
        format="YYYY-MM-DD"
    )
    
    st.divider()
    
    # Logic & Context Handling
    if not selected_advertisers:
        # Global Context
        st.info("🌎 **Global Context**\n\nAccess to ALL advertisers.")
        system_instruction = (
            "You have access to data for ALL advertisers. "
            "Do not filter by advertiser unless specifically asked in the user's question."
        )
    else:
        # Filtered Context
        st.info(f"🎯 **Contexto Filtrado**\n\n{', '.join(selected_advertisers)}")
        system_instruction = (
            f"SCOPE RESTRICTION: You are strictly limited to the following advertisers: {selected_advertisers}. "
            "You MUST include a WHERE clause filtering by these specific names/IDs in every SQL query you generate."
        )

    st.markdown("---")
    st.caption("AMC Instance ID: amc123456789")
    
    # Debug: Show the constructed system prompt
    with st.expander("🔍 View System Prompt"):
        st.code(system_instruction, language="text")

    # Schema Viewer
    with st.expander("🗄️ Database Schema (Reference)"):
        schema_info = {
            "amc_consolidated": {
                "columns": ["campaign_name", "impressions", "spend", "roas", "date", "advertiser_name"],
                "description": "Consolidated campaign performance data."
            }
        }
        st.json(schema_info)

    # Quick Actions (Persistent)
    st.markdown("### 🎯 Quick Actions")
    quick_prompts = [
        "Analyze ROAS by Campaign",
        "Show New-To-Brand metrics",
        "Path to Conversion analysis"
    ]
    
    for qp in quick_prompts:
        if st.button(qp, key=f"sidebar_{qp}"):
            st.session_state.chats[st.session_state.current_chat_id].append({"role": "user", "content": qp})
            st.rerun()

    # Clear Chat Button (Current Chat Only)
    if st.button("🗑️ Clear Current Chat"):
        st.session_state.chats[st.session_state.current_chat_id] = []
        st.rerun()

# ---------------------------------------------------------
# PDF GENERATION HELPER
# ---------------------------------------------------------
def generate_pdf_report(user_query, insight_text, df):
    """
    Generates a PDF report using FPDF.
    Returns the PDF content as bytes.
    """
    pdf = FPDF()
    pdf.add_page()
    
    # Header
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, "AMC Insights Service", ln=True, align="C")
    pdf.ln(10)
    
    # Title (User Query)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, f"Query: {user_query}", ln=True)
    pdf.ln(5)
    
    # Executive Summary
    pdf.set_font("Arial", "", 11)
    # Multi_cell for text wrapping
    # Encode to latin-1 to handle some special chars, though basic FPDF has limits
    safe_text = insight_text.encode('latin-1', 'replace').decode('latin-1')
    pdf.multi_cell(0, 7, f"Executive Summary:\n{safe_text}")
    pdf.ln(10)
    
    # Data Table
    pdf.set_font("Arial", "B", 10)
    pdf.cell(0, 10, "Data Preview:", ln=True)
    
    # Table Header
    pdf.set_font("Arial", "B", 9)
    cols = df.columns.tolist()
    col_width = 190 / len(cols) # Distribute width roughly
    
    for col in cols:
        pdf.cell(col_width, 8, str(col), border=1)
    pdf.ln()
    
    # Table Rows
    pdf.set_font("Arial", "", 9)
    for index, row in df.head(20).iterrows(): # Limit to 20 rows for the PDF preview
        for col in cols:
            val = str(row[col])
            # Truncate if too long
            if len(val) > 20:
                val = val[:17] + "..."
            pdf.cell(col_width, 8, val, border=1)
        pdf.ln()
        
    # Return bytes
    # output(dest='S') returns a string in latin-1. We encode it to bytes.
    # Note: In newer FPDF versions, output() might return bytearray directly if dest='S' is not used or handled differently.
    # We will use output() without arguments which returns a string in older versions, or bytes in newer.
    # Let's try a safer approach for Streamlit compatibility.
    return pdf.output(dest='S').encode('latin-1')

# ---------------------------------------------------------
# AGENT LOGIC (REAL AI + MOCK DATA)
# ---------------------------------------------------------
def get_agent_response(user_query, selected_advertisers, date_range=None):
    """
    Generates response using Gemini API for text and Mock Logic for data/charts.
    Returns a dict with: text, sql, data (DataFrame), chart_config (dict)
    """
    # 1. Determine Context
    if not selected_advertisers:
        where_clause = ""
        context_msg = "Global Context"
    else:
        adv_list = ", ".join([f"'{adv}'" for adv in selected_advertisers])
        where_clause = f"WHERE advertiser_name IN ({adv_list})"
        context_msg = f"Filtered Context: {selected_advertisers}"

    # Date Range Context
    date_msg = "Last 30 Days"
    if date_range and len(date_range) == 2:
        start_date, end_date = date_range
        where_clause += f"\n    AND date BETWEEN '{start_date}' AND '{end_date}'"
        date_msg = f"{start_date} to {end_date}"

    # 2. Call Gemini API (Step A)
    ai_text = ""
    try:
        if client:
            # Append context to the query for better AI awareness
            full_prompt = f"{user_query}\n\n[Context: User is analyzing data for {context_msg} during {date_msg}.]"
            
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                config=types.GenerateContentConfig(system_instruction=SYSTEM_INSTRUCTION),
                contents=full_prompt
            )
            ai_text = response.text
        else:
            ai_text = "⚠️ Gemini API Key not found or client not initialized. Please check your secrets."
    except Exception as e:
        ai_text = f"⚠️ Error connecting to Gemini API: {str(e)}. Using fallback response."

    # 3. Hybrid Logic: Mock Data Generation (Step B)
    query_lower = user_query.lower()
    sql_query = None
    df = None
    chart_config = None
    
    # --- SCENARIO 1: CAMPAIGN AUDIT ---
    if any(k in query_lower for k in ["audit", "wasted", "efficiency"]):
        sql_query = f"""
        SELECT campaign_name, spend, impressions, roas, status
        FROM campaign_audit
        {where_clause}
        AND roas = 0
        ORDER BY spend DESC
        LIMIT 5;
        """
        
        data_rows = []
        for i in range(5):
            data_rows.append({
                "Campaign Name": f"Inefficient_Camp_{i+1}",
                "Spend": round(random.uniform(1000, 5000), 2),
                "Impressions": random.randint(10000, 50000),
                "ROAS": 0.0,
                "Status": "Inefficient"
            })
        df = pd.DataFrame(data_rows)
        chart_config = {"type": "bar", "x": "Campaign Name", "y": "Spend"}

    # --- SCENARIO 2: TIME-TO-CONVERSION ---
    elif any(k in query_lower for k in ["time", "conversion", "days"]):
        sql_query = f"""
        SELECT days_to_convert, count(*) as conversion_count
        FROM conversion_time_distribution
        {where_clause}
        GROUP BY days_to_convert
        ORDER BY days_to_convert ASC;
        """
        
        data_rows = []
        for i in range(1, 15):
            count = int(1000 * (1 / i)) # Decay
            data_rows.append({
                "Days_to_Convert": i,
                "Conversion_Count": count
            })
        df = pd.DataFrame(data_rows)
        chart_config = {"type": "bar", "x": "Days_to_Convert", "y": "Conversion_Count"}

    # --- SCENARIO 3: PRODUCT STRATEGY / GATEWAY ASINS ---
    elif any(k in query_lower for k in ["product", "asin", "strategy"]):
        sql_query = f"""
        SELECT asin, product_name, ntb_orders, total_sales
        FROM gateway_asins
        {where_clause}
        ORDER BY ntb_orders DESC
        LIMIT 5;
        """
        
        data_rows = []
        for i in range(5):
            data_rows.append({
                "ASIN": f"B00{random.randint(10000,99999)}",
                "Product Name": f"Product {i+1}",
                "NTB_Orders": random.randint(50, 500),
                "Total_Sales": round(random.uniform(5000, 20000), 2)
            })
        df = pd.DataFrame(data_rows)
        chart_config = {"type": "bar", "x": "ASIN", "y": "NTB_Orders"}

    # --- SCENARIO 4: DASHBOARD / PERFORMANCE (Explicit Request) ---
    elif any(k in query_lower for k in ["dashboard", "sales", "overview", "performance", "chart", "graph"]):
        sql_query = f"""
        SELECT 
            date, 
            campaign_name, 
            SUM(spend) as total_spend, 
            SUM(impressions) as total_impressions
        FROM amc_consolidated
        {where_clause}
        GROUP BY date, campaign_name
        ORDER BY date DESC
        LIMIT 100;
        """
        
        dates = pd.date_range(end=datetime.date.today(), periods=10).tolist()
        campaigns = [f"Campaign_{i}" for i in range(1, 6)]
        data_rows = []
        for _ in range(20):
            data_rows.append({
                "date": random.choice(dates),
                "campaign": random.choice(campaigns),
                "spend": round(random.uniform(100, 5000), 2),
                "impressions": random.randint(1000, 50000)
            })
        df = pd.DataFrame(data_rows).sort_values("date")
        chart_config = {"type": "line", "x": "date", "y": "spend"}

    return {
        "text": ai_text,
        "sql": sql_query,
        "data": df,
        "chart_config": chart_config
    }

# 1. Inicializar el historial del chat en la sesión (Legacy cleanup)
if "messages" in st.session_state:
    del st.session_state.messages

# Use the current chat's messages
current_messages = st.session_state.chats[st.session_state.current_chat_id]

# 2. Mostrar los mensajes del historial al recargar la app
for message in current_messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        
        # Render rich content if available
        if "sql" in message:
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
    col1, col2, col3 = st.columns(3)
    
    prompt_to_run = None
    
    with col1:
        if st.button("Analyze ROAS by Campaign"):
            prompt_to_run = "Analyze ROAS by Campaign"
    with col2:
        if st.button("Show New-To-Brand metrics"):
            prompt_to_run = "Show New-To-Brand metrics"
    with col3:
        if st.button("Path to Conversion analysis"):
            prompt_to_run = "Path to Conversion analysis"
            
    if prompt_to_run:
        # Add user message
        st.session_state.chats[st.session_state.current_chat_id].append({"role": "user", "content": prompt_to_run})
        st.rerun()

# 3. Capturar la entrada del usuario
if prompt := st.chat_input("Type your message here..."):
    
    # A. Mostrar mensaje del usuario
    with st.chat_message("user"):
        st.markdown(prompt)
    # Guardar mensaje del usuario en historial
    st.session_state.chats[st.session_state.current_chat_id].append({"role": "user", "content": prompt})
    
    # Trigger response generation
    prompt_to_run = prompt # Just to reuse logic if needed, but we process directly below

# Process Response (if last message is user)
if st.session_state.chats[st.session_state.current_chat_id] and st.session_state.chats[st.session_state.current_chat_id][-1]["role"] == "user":
    last_user_msg = st.session_state.chats[st.session_state.current_chat_id][-1]["content"]
    
    # B. Generar respuesta de la IA (Simulación)
    with st.chat_message("assistant"):
        # Call Mock Agent
        response_obj = get_agent_response(last_user_msg, selected_advertisers, date_range)
        
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
    st.session_state.chats[st.session_state.current_chat_id].append({
        "role": "assistant", 
        "content": response_obj["text"],
        "sql": response_obj["sql"],
        "data": response_obj["data"],
        "chart_config": response_obj.get("chart_config")
    })