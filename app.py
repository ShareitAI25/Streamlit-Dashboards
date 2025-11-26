import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
import time # Importamos time para simular que la IA "piensa"

# 1. Título de la aplicación
st.title("Mi Primera App con Streamlit + Chatbot")

# 2. Un texto de bienvenida
st.write("¡Hola! Esta es una aplicación web creada en pocos minutos con Python y Streamlit.")

# ---------------------------------------------------------
# TU CÓDIGO ORIGINAL (Sección de Sliders y Botones)
# ---------------------------------------------------------

# 3. Un componente interactivo: un control deslizante (slider)
st.header("Componente Interactivo")
valor_slider = st.slider("Elige un número del 1 al 10", min_value=1, max_value=10, value=5)

# Mostrar el valor seleccionado en el slider
st.write(f"Has seleccionado el número: {valor_slider}")

# 4. Un botón
st.header("Un botón simple")
if st.button("Haz clic aquí"):
    st.balloons()
    st.success("¡Gracias por hacer clic! Acabas de lanzar unos globos.")
else:
    st.write("Esperando a que hagas clic en el botón...")

# 5. Un histograma con datos aleatorios
st.header("Histograma de Datos Aleatorios")
st.write("Este histograma muestra la frecuencia de 1,000 números aleatorios.")

# Generar datos aleatorios
datos_aleatorios = np.random.randn(1000)

# Crear el histograma con Matplotlib
fig, ax = plt.subplots()
ax.hist(datos_aleatorios, bins=30, color='skyblue', edgecolor='black')
ax.set_title("Histograma de Distribución Normal")
ax.set_xlabel("Valor")
ax.set_ylabel("Frecuencia")

# Mostrar el gráfico en Streamlit
st.pyplot(fig)

# ---------------------------------------------------------
# NUEVA SECCIÓN: CHATBOT DE IA
# ---------------------------------------------------------

st.divider() # Una línea visual para separar secciones
st.header("🤖 Chatbot de Inteligencia Artificial")
st.caption("Este es un chat de demostración. Para hacerlo real, necesitarías conectar una API key (como OpenAI o Google Gemini).")

# 1. Inicializar el historial del chat en la sesión
# Esto es vital para que los mensajes no desaparezcan al hacer clic en otros botones
if "messages" not in st.session_state:
    st.session_state.messages = []

# 2. Mostrar los mensajes del historial al recargar la app
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# 3. Capturar la entrada del usuario
if prompt := st.chat_input("Escribe algo a la IA..."):
    
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