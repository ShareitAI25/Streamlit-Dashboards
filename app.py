import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
import time # Importamos time para simular que la IA "piensa"



# ---------------------------------------------------------
# NUEVA SECCIÓN: CHATBOT DE IA
# ---------------------------------------------------------

st.divider() # Una línea visual para separar secciones
st.header("🤖 AMC Agent")
st.caption("This is just a prototype demo. The AI responses are simulated for demonstration purposes.")

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
        
        # Lógica simple de respuesta (Aquí es donde conectarías OpenAI/Gemini)
        # Por ahora es un "Eco" inteligente para la demo
        if "hola" in prompt.lower():
            respuesta_ia = "¡Hola! ¿En qué puedo ayudarte hoy con tu análisis de datos?"
        elif "grafico" in prompt.lower() or "gráfico" in prompt.lower():
            respuesta_ia = "Los gráficos de arriba fueron generados con Matplotlib. ¿Te gustaría saber cómo cambiarles el color?"
        else:
            respuesta_ia = f"Interesante... has dicho: '{prompt}'. Como soy una demo, solo repito cosas, ¡pero imagina las posibilidades!"

        # Simular efecto de escritura (typewriter effect)
        for chunk in respuesta_ia.split():
            full_response += chunk + " "
            time.sleep(0.05)
            message_placeholder.markdown(full_response + "▌")
        
        message_placeholder.markdown(full_response)
    
    # Guardar respuesta de la IA en historial
    st.session_state.messages.append({"role": "assistant", "content": full_response})