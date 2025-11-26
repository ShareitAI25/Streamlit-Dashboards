import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
import time # Importamos time para simular que la IA "piensa"
import pandas as pd
import datetime
import random



# ---------------------------------------------------------
# NUEVA SECCIÓN: CHATBOT DE IA
# ---------------------------------------------------------

st.divider() # Una línea visual para separar secciones
st.header("☁️ Amazon Marketing Cloud (AMC) Assistant")
st.caption("Ask me about your campaign performance, audience overlaps, or SQL queries for AMC.")

# ---------------------------------------------------------
# SIDEBAR: CONFIGURACIÓN
# ---------------------------------------------------------
with st.sidebar:
    st.header("⚙️ Configuración")
    
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
        "Selecciona Advertisers (Vacío = Global):", 
        advertisers,
        help="Deja vacío para consultar todos los anunciantes. Selecciona uno o más para filtrar."
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
        st.info("🌎 **Contexto Global**\n\nAcceso a TODOS los anunciantes.")
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
    with st.expander("🔍 Ver System Prompt"):
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
# MOCK AGENT LOGIC
# ---------------------------------------------------------
def get_mock_agent_response(user_query, selected_advertisers, date_range=None):
    """
    Simulates the LLM + SQL Agent.
    Returns a dict with: text, sql, data (DataFrame)
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

    # 2. Generate Mock SQL
    # We'll just make a generic query that looks relevant
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

    # 3. Generate Mock Data
    # Create a date range
    dates = pd.date_range(end=datetime.date.today(), periods=10).tolist()
    
    # Create fake campaigns
    campaigns = [f"Campaign_{i}" for i in range(1, 6)]
    
    data_rows = []
    for _ in range(20): # Generate 20 random rows
        data_rows.append({
            "date": random.choice(dates),
            "campaign": random.choice(campaigns),
            "spend": round(random.uniform(100, 5000), 2),
            "impressions": random.randint(1000, 50000)
        })
    
    df = pd.DataFrame(data_rows).sort_values("date")

    # 4. Generate Text Response
    text_response = (
        f"Based on your request '{user_query}', I have retrieved performance data "
        f"under the **{context_msg}** for the period **{date_msg}**.\n\n"
        "Here is the SQL query I generated and the resulting data:"
    )

    return {
        "text": text_response,
        "sql": sql_query,
        "data": df
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
        
        if "data" in message:
            st.dataframe(message["data"])
            # Simple chart
            if "date" in message["data"].columns and "spend" in message["data"].columns:
                st.line_chart(message["data"], x="date", y="spend")

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
        response_obj = get_mock_agent_response(last_user_msg, selected_advertisers, date_range)
        
        # Display Text
        st.markdown(response_obj["text"])
        
        # Display SQL
        with st.expander("View Generated SQL"):
            st.code(response_obj["sql"], language="sql")
            
        # Display Data
        st.dataframe(response_obj["data"])
        st.line_chart(response_obj["data"], x="date", y="spend")
    
    # Guardar respuesta completa en historial
    st.session_state.chats[st.session_state.current_chat_id].append({
        "role": "assistant", 
        "content": response_obj["text"],
        "sql": response_obj["sql"],
        "data": response_obj["data"]
    })