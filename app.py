import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
import time # Importamos time para simular que la IA "piensa"
from pathlib import Path


st.header("🤖 Chatbot de Inteligencia Artificial")
st.caption("Este es un chat de demostración. Para hacerlo real, necesitarías conectar una API key (como OpenAI o Google Gemini).")

# 1. Inicializar el historial del chat en la sesión
# Esto es vital para que los mensajes no desaparezcan al hacer clic en otros botones
if "messages" not in st.session_state:
    st.session_state.messages = []

# 2. Mostrar los mensajes del historial al recargar la app
# Assets (put your icons in an `assets/` folder next to this file)
ASSETS_DIR = Path(__file__).parent / "assets"
USER_ICON = ASSETS_DIR / "user_icon.png"
BOT_ICON = ASSETS_DIR / "bot_icon.png"

def render_message(message: dict):
    role = message.get("role")
    content = message.get("content", "")

    if role == "user":
        col_msg, col_avatar = st.columns([9, 1])
        with col_msg:
            st.markdown(f"<div style='text-align:right'>{content}</div>", unsafe_allow_html=True)
        with col_avatar:
            if USER_ICON.exists():
                st.image(str(USER_ICON), width=40)
            else:
                st.markdown("🙂")
    else:
        col_avatar, col_msg = st.columns([1, 9])
        with col_avatar:
            if BOT_ICON.exists():
                st.image(str(BOT_ICON), width=40)
            else:
                st.markdown("🤖")
        with col_msg:
            st.markdown(content)

for message in st.session_state.messages:
    render_message(message)

# 3. Capturar la entrada del usuario
if prompt := st.chat_input("Escribe algo a la IA..."):

    # A. Guardar y mostrar mensaje del usuario
    st.session_state.messages.append({"role": "user", "content": prompt})
    render_message({"role": "user", "content": prompt})

    # B. Generar respuesta de la IA (Simulación)
    # Mostrar placeholder with avatar on the left
    col_avatar, col_msg = st.columns([1, 9])
    with col_avatar:
        if BOT_ICON.exists():
            st.image(str(BOT_ICON), width=40)
        else:
            st.markdown("🤖")

    message_placeholder = col_msg.empty()
    full_response = ""

    # Lógica simple de respuesta (Aquí es donde conectarías OpenAI/Gemini)
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