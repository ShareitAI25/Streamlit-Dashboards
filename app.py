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
    selected_advertiser = st.selectbox("Selecciona un Advertiser:", advertisers)
    
    st.divider()
    st.info(f"Analizando datos para: **{selected_advertiser}**")
    st.markdown("---")
    st.caption("AMC Instance ID: amc123456789")

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
        
        if "hola" in prompt_lower or "hello" in prompt_lower:
            respuesta_ia = f"¡Hola! Estoy conectado a la instancia de **{selected_advertiser}**. ¿Qué necesitas analizar hoy sobre este anunciante?"
            
        elif "sql" in prompt_lower or "query" in prompt_lower or "consulta" in prompt_lower:
            respuesta_ia = f"Generando consulta para **{selected_advertiser}**...\n\nAquí tienes una SQL para ver el solapamiento de audiencias:\n```sql\nSELECT\n  user_id,\n  COUNT(DISTINCT campaign_id) as campaigns_seen\nFROM impressions\nWHERE advertiser_name = '{selected_advertiser}'\nGROUP BY user_id\nHAVING campaigns_seen > 1\n```"
            
        elif "audiencia" in prompt_lower or "audience" in prompt_lower:
            respuesta_ia = f"Analizando audiencias de **{selected_advertiser}**... He detectado que el segmento 'Compradores Recientes' tiene un alto solapamiento con tus campañas de Display."
            
        elif "campaña" in prompt_lower or "campaign" in prompt_lower:
            respuesta_ia = f"El rendimiento de las campañas de **{selected_advertiser}** es positivo. El ROAS promedio esta semana es de 4.5. ¿Quieres desglosarlo por ASIN?"
            
        else:
            respuesta_ia = f"Entendido. Consultando base de datos de **{selected_advertiser}** sobre: '{prompt}'. (Simulación: Aquí se ejecutaría la query real en AMC)."

        # Simular efecto de escritura (typewriter effect)
        for chunk in respuesta_ia.split():
            full_response += chunk + " "
            time.sleep(0.05)
            message_placeholder.markdown(full_response + "▌")
        
        message_placeholder.markdown(full_response)
    
    # Guardar respuesta de la IA en historial
    st.session_state.messages.append({"role": "assistant", "content": full_response})