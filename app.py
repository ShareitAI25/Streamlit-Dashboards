import streamlit as st
import datetime
from modules.database import init_gemini, init_supabase
from modules.agent import get_agent_response
from modules.pdf_generator import generate_pdf_report

# Initialize Clients
client = init_gemini()
supabase = init_supabase()

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
        response_obj = get_agent_response(client, supabase, system_instruction, last_user_msg, selected_advertisers, date_range)
        
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
