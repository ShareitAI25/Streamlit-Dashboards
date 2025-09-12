import streamlit as st
import numpy as np
import matplotlib.pyplot as plt

# 1. Título de la aplicación
st.title("Mi Primera App con Streamlit")

# 2. Un texto de bienvenida
st.write("¡Hola! Esta es una aplicación web creada en pocos minutos con Python y Streamlit.")

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

# 5. NUEVO: Un histograma con datos aleatorios
st.header("Histograma de Datos Aleatorios")
st.write("Este histograma muestra la frecuencia de 1,000 números aleatorios generados con una distribución normal.")

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