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
            respuesta_ia = "¡Hola! Soy tu asistente de Amazon Marketing Cloud. Puedo ayudarte a generar consultas SQL, analizar audiencias o revisar el rendimiento de tus campañas. ¿Por dónde empezamos?"
            
        elif "sql" in prompt_lower or "query" in prompt_lower or "consulta" in prompt_lower:
            respuesta_ia = "Claro, aquí tienes un ejemplo de una consulta SQL para ver el solapamiento de audiencias en AMC:\n\n```sql\nSELECT\n  user_id,\n  COUNT(DISTINCT campaign_id) as campaigns_seen\nFROM impressions\nGROUP BY user_id\nHAVING campaigns_seen > 1\n```\n¿Quieres que la adapte a tus tablas?"
            
        elif "audiencia" in prompt_lower or "audience" in prompt_lower:
            respuesta_ia = "Para analizar tus audiencias, podemos cruzar los datos de impresiones con las conversiones. En AMC, esto nos permite ver qué segmentos tienen mayor propensión a compra después de ver un anuncio de Display."
            
        elif "campaña" in prompt_lower or "campaign" in prompt_lower:
            respuesta_ia = "El rendimiento de tus campañas parece estable. Según los últimos datos simulados, el ROAS ha aumentado un 15% en la categoría de 'Electrónica'. ¿Quieres ver un desglose por ASIN?"
            
        else:
            respuesta_ia = f"Entendido. Has preguntado sobre: '{prompt}'. Para darte una respuesta precisa sobre AMC, necesitaría conectarme a tu instancia. Por ahora, puedo explicarte conceptos o ayudarte con la sintaxis SQL."

        # Simular efecto de escritura (typewriter effect)
        for chunk in respuesta_ia.split():
            full_response += chunk + " "
            time.sleep(0.05)
            message_placeholder.markdown(full_response + "▌")
        
        message_placeholder.markdown(full_response)
    
    # Guardar respuesta de la IA en historial
    st.session_state.messages.append({"role": "assistant", "content": full_response})