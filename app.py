import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
import time # Importamos time para simular que la IA "piensa"



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
    # Lista simulada de anunciantes
    advertisers = ["Brand A (Electronics)", "Brand B (Fashion)", "Brand C (Home & Kitchen)", "Global Corp"]
    
    # Refactor: Use multiselect for flexible context
    selected_advertisers = st.multiselect(
        "Selecciona Advertisers (Vacío = Global):", 
        advertisers,
        help="Deja vacío para consultar todos los anunciantes. Selecciona uno o más para filtrar."
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

# 1. Inicializar el historial del chat en la sesión
# Esto es vital para que los mensajes no desaparezcan al hacer clic en otros botones
if "messages" not in st.session_state:
    st.session_state.messages = []

# 2. Mostrar los mensajes del historial al recargar la app
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# 3. Capturar la entrada del usuario
if prompt := st.chat_input("Type your message here..."):
    
    # A. Mostrar mensaje del usuario
    with st.chat_message("user"):
        st.markdown(prompt)
    # Guardar mensaje del usuario en historial
    st.session_state.messages.append({"role": "user", "content": prompt})

    # B. Generar respuesta de la IA (Simulación)
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        full_response = ""
        
        # Lógica simple de respuesta (Simulación de AMC)
        prompt_lower = prompt.lower()
        
        # Determine context variables for simulation
        if not selected_advertisers:
            context_label = "Global (Todos los anunciantes)"
            where_clause_sql = "-- No advertiser filter (Global Analysis)"
        else:
            context_label = f"Filtrado ({', '.join(selected_advertisers)})"
            # Create SQL IN clause
            adv_list_str = ", ".join([f"'{adv}'" for adv in selected_advertisers])
            where_clause_sql = f"WHERE advertiser_name IN ({adv_list_str})"

        if "hola" in prompt_lower or "hello" in prompt_lower:
            respuesta_ia = f"¡Hola! Estoy operando en contexto **{context_label}**. ¿Qué insights necesitas hoy?"
            
        elif "sql" in prompt_lower or "query" in prompt_lower or "consulta" in prompt_lower:
            respuesta_ia = f"Generando consulta SQL para **{context_label}**:\n\n```sql\nSELECT\n  advertiser_name,\n  COUNT(DISTINCT user_id) as unique_users\nFROM impressions\n{where_clause_sql}\nGROUP BY advertiser_name\n```\n\nNota cómo el filtro se adapta a tu selección."
            
        elif "audiencia" in prompt_lower or "audience" in prompt_lower:
            respuesta_ia = f"Analizando audiencias para: **{context_label}**. He encontrado patrones de solapamiento interesantes entre los segmentos de 'Lujo' y 'Tecnología' dentro de este alcance."
            
        elif "campaña" in prompt_lower or "campaign" in prompt_lower:
            respuesta_ia = f"El reporte de campañas para **{context_label}** está listo. El ROAS agregado es de 3.8. ¿Quieres ver el desglose por anunciante o por fecha?"
            
        else:
            respuesta_ia = f"Entendido. Procesando solicitud sobre '{prompt}' en el contexto **{context_label}**.\n\n*Instrucción al Modelo (System Prompt):*\n> {system_instruction}"

        # Simular efecto de escritura (typewriter effect)
        for chunk in respuesta_ia.split():
            full_response += chunk + " "
            time.sleep(0.05)
            message_placeholder.markdown(full_response + "▌")
        
        message_placeholder.markdown(full_response)
    
    # Guardar respuesta de la IA en historial
    st.session_state.messages.append({"role": "assistant", "content": full_response})