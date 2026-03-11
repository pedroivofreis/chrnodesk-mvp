import zipfile

app_py = """import streamlit as st
import google.generativeai as genai
import json

genai.configure(api_key="AIzaSyAxzcLcDxqm3ANIcJHTi1noaPx9wUxf_wQ")

def buscar_voos(origem: str, destino: str, data_ida: str, data_volta: str = "", apenas_ida: bool = False, paradas: int = 0):
    return json.dumps([{"companhia": "latam", "voo": "la8080", "aeroporto_origem": origem, "aeroporto_destino": destino, "preco_estimado": 1200.00, "paradas": paradas}])

def buscar_hoteis(destino: str, checkin: str, checkout: str):
    return json.dumps([{"nome": "hotel central", "resumo": "ótima localização com café da manhã.", "avaliacao_booking": 8.8, "preco_estimado": 400.00}])

instrucoes = "você é uma especialista em viagens, se chama clau e atua na agência clau a viajante. apresente-se apenas uma vez. converse para montar o roteiro e depois use as ferramentas para trazer voos e hotéis com estimativas de custos."

model = genai.GenerativeModel(model_name="gemini-1.5-pro", system_instruction=instrucoes, tools=[buscar_voos, buscar_hoteis])

st.title("clau a viajante - mvp")

if "chat" not in st.session_state:
    st.session_state.chat = model.start_chat(enable_automatic_function_calling=True)

for msg in st.session_state.chat.history:
    if msg.role == "user":
        st.chat_message("user").write(msg.parts[0].text)
    elif msg.role == "model":
        texto = "".join(part.text for part in msg.parts if hasattr(part, "text") and part.text)
        if texto:
            st.chat_message("assistant").write(texto)

prompt = st.chat_input("digite sua mensagem")
if prompt:
    st.chat_message("user").write(prompt)
    resposta = st.session_state.chat.send_message(prompt)
    st.chat_message("assistant").write(resposta.text)
"""

requirements_txt = """streamlit
google-generativeai
"""

with open("app.py", "w", encoding="utf-8") as f:
    f.write(app_py)

with open("requirements.txt", "w", encoding="utf-8") as f:
    f.write(requirements_txt)

with zipfile.ZipFile("mvp_clau.zip", "w") as z:
    z.write("app.py")
    z.write("requirements.txt")