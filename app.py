import streamlit as st
import google.generativeai as genai
import json
import requests
import re
import datetime
import airportsdata

genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
chave_serpapi = st.secrets["SERPAPI_API_KEY"]

@st.cache_data
def carregar_locais():
    airports = airportsdata.load('iata')
    lista = []
    for iata, info in airports.items():
        cidade = info.get('city', 'desconhecida')
        pais = info.get('country', '')
        nome = info.get('name', '')
        lista.append(f"{cidade}, {pais} - {nome} ({iata})")
    return sorted(lista)

def extrair_iata(texto):
    if not texto:
        return ""
    match = re.search(r'\(([a-zA-Z]{3})\)', texto)
    if match:
        return match.group(1).upper()
    return texto.strip().upper()

def extrair_cidade(texto):
    if not texto:
        return ""
    return texto.split(",")[0].strip()

def limpar_preco(valor):
    try:
        if isinstance(valor, (int, float)):
            return float(valor)
        numeros = re.findall(r'[\d\.]+', str(valor).replace(',', '.'))
        return float(numeros[0]) if numeros else 0.0
    except:
        return 0.0

def buscar_voos(origem: str, destino: str, data_ida: str, data_volta: str = "", tipo: str = "ida e volta", flex: str = "exata", pessoas: int = 1):
    origem_iata = extrair_iata(origem)
    destino_iata = extrair_iata(destino)
    url = "https://serpapi.com/search"
    params = {
        "engine": "google_flights",
        "departure_id": origem_iata,
        "arrival_id": destino_iata,
        "outbound_date": data_ida,
        "adults": pessoas,
        "hl": "pt-br",
        "currency": "BRL",
        "api_key": chave_serpapi
    }
    if tipo == "ida e volta" and data_volta:
        params["return_date"] = data_volta
        params["type"] = "1"
    elif tipo == "somente ida":
        params["type"] = "2"

    try:
        resposta = requests.get(url, params=params)
        dados = resposta.json()

        if "error" in dados:
            return json.dumps({"erro": f"erro na api: {dados['error']}"})

        melhores_voos = dados.get("best_flights", [])
        outros_voos = dados.get("other_flights", [])
        todos_voos = melhores_voos + outros_voos

        resultados = []
        for voo in todos_voos[:5]:
            voos_internos = voo.get("flights", [{}])[0]
            preco_limpo = limpar_preco(voo.get("price", 0))
            resultados.append({
                "companhia": voos_internos.get("airline", "indisponivel"),
                "voo": voos_internos.get("flight_number", "indisponivel"),
                "preco": preco_limpo,
                "paradas": len(voo.get("layovers", []))
            })

        if not resultados:
             return json.dumps({"erro": "nenhum voo encontrado para essas datas."})

        return json.dumps({"opcoes_reais": resultados})
    except Exception as e:
        return json.dumps({"erro": f"falha na comunicação: {str(e)}"})

def buscar_hoteis(destino: str, bairro: str, checkin: str, checkout: str, min_nota: float, pessoas: int = 1):
    cidade = extrair_cidade(destino)
    query = f"hoteis em {cidade} {bairro}".strip()
    url = "https://serpapi.com/search"
    params = {
        "engine": "google_hotels",
        "q": query,
        "check_in_date": checkin,
        "check_out_date": checkout,
        "adults": pessoas,
        "hl": "pt-br",
        "currency": "BRL",
        "api_key": chave_serpapi
    }
    try:
        resposta = requests.get(url, params=params)
        dados = resposta.json()

        if "error" in dados:
            return json.dumps({"erro": f"erro na api: {dados['error']}"})

        propriedades = dados.get("properties", [])
        resultados = []
        for prop in propriedades:
            nota_str = prop.get("overall_rating", 0)
            try:
                nota = float(nota_str)
            except:
                nota = 0.0
                
            if nota >= min_nota:
                imagens = prop.get("images", [])
                url_imagem = imagens[0].get("thumbnail", "") if imagens else ""
                preco_limpo = limpar_preco(prop.get("rate_per_night", {}).get("lowest", 0))

                resultados.append({
                    "nome": prop.get("name", "indisponivel"),
                    "preco": preco_limpo,
                    "avaliacao": nota,
                    "resumo": prop.get("description", "sem descricao"),
                    "imagem": url_imagem
                })
                
            if len(resultados) >= 4:
                break

        if not resultados:
             return json.dumps({"erro": f"nenhum hotel encontrado com nota maior ou igual a {min_nota}."})

        return json.dumps({"opcoes_reais": resultados})
    except Exception as e:
        return json.dumps({"erro": f"falha: {str(e)}"})

instrucoes = "você é uma especialista em viagens, se chama clau e atua na agência clau a viajante. apresente-se apenas uma vez. use as informações do perfil do usuário para criar roteiros personalizados. converse de forma natural."
model = genai.GenerativeModel(model_name="gemini-2.5-flash", system_instruction=instrucoes, tools=[buscar_voos, buscar_hoteis])

st.set_page_config(layout="wide", page_title="clau a viajante")
st.title("✈️ clau a viajante - planejamento de roteiros")

lista_locais = carregar_locais()

tab_chat, tab_busca = st.tabs(["💬 chat e roteiro", "🔍 buscador completo"])

with tab_chat:
    with st.expander("📝 perfil da viagem (preencha para guiar a clau)", expanded=True):
        with st.form("form_perfil"):
            col_a, col_b = st.columns(2)
            with col_a:
                origem_chat = st.text_input("de onde você vai sair? (cidade ou aeroporto)")
                destino_chat = st.text_input("para onde quer ir? (cidade ou aeroporto)")
                col_ida_chat, col_volta_chat = st.columns(2)
                with col_ida_chat:
                    ida_chat = st.date_input("data de ida", value=None)
                with col_volta_chat:
                    volta_chat = st.date_input("data de volta", value=None)
            with col_b:
                num_pessoas_chat = st.number_input("quantidade de pessoas", min_value=1, value=2)
                estilo_viagem = st.selectbox("estilo da viagem", ["romântica", "mochilão", "em família", "luxo", "aventura"])
                orcamento = st.selectbox("orçamento", ["econômico", "conforto", "sem limites"])
                clima_preferido = st.text_input("preferências (clima, atrações, bairros)")

            submit_perfil = st.form_submit_button("enviar perfil para a clau")
            
            if submit_perfil:
                if "chat" not in st.session_state:
                    st.session_state.chat = model.start_chat(enable_automatic_function_calling=True)
                resumo_perfil = f"olá clau. saio de {origem_chat} para {destino_chat} com {num_pessoas_chat} pessoa(s). ida: {ida_chat}, volta: {volta_chat}. estilo: {estilo_viagem}. orçamento: {orcamento}. preferências: {clima_preferido}. sugira um roteiro."
                st.session_state.chat.send_message(resumo_perfil)
                st.success("perfil enviado!")

    if "chat" not in st.session_state:
        st.session_state.chat = model.start_chat(enable_automatic_function_calling=True)

    for msg in st.session_state.chat.history:
        if msg.role == "user":
            st.chat_message("user").write(msg.parts[0].text)
        elif msg.role == "model":
            texto = "".join(part.text for part in msg.parts if hasattr(part, "text") and part.text)
            if texto:
                st.chat_message("assistant").write(texto)

    prompt = st.chat_input("fale com a clau...")
    if prompt:
        st.chat_message("user").write(prompt)
        resposta = st.session_state.chat.send_message(prompt)
        st.chat_message("assistant").write(resposta.text)

with tab_busca:
    st.subheader("pesquisa unificada: voos e hotéis")

    with st.form("form_busca_completa"):
        col_tipo, col_flex, col_pessoas = st.columns(3)
        with col_tipo:
            tipo_voo = st.radio("tipo de voo", ["ida e volta", "somente ida"], horizontal=True)
        with col_flex:
            flexibilidade = st.selectbox("flexibilidade de datas", ["exata", "+/- 1 dia", "+/- 3 dias"])
        with col_pessoas:
            num_pessoas = st.number_input("quantidade de pessoas", min_value=1, value=2)

        hoje = datetime.date.today()
        padrao_ida = hoje + datetime.timedelta(days=30)

        col1, col2 = st.columns(2)
        with col1:
            origem = st.selectbox("origem (cidade ou aeroporto)", lista_locais, index=None)
            ida = st.date_input("data de ida", min_value=hoje, value=padrao_ida)
            bairro_pref = st.text_input("bairro, cidade ou ponto turístico para o hotel?")
        with col2:
            destino = st.selectbox("destino (cidade ou aeroporto)", lista_locais, index=None)
            padrao_volta = ida + datetime.timedelta(days=7)
            volta = st.date_input("data de volta", min_value=ida, value=padrao_volta)
            nota_minima = st.slider("nota mínima do hotel (0 a 5)", 0.0, 5.0, 4.0, 0.5)

        buscar = st.form_submit_button("pesquisar opções reais")

    if buscar:
        if not origem or not destino:
            st.warning("selecione a origem e o destino.")
        else:
            with st.spinner("buscando voos e hotéis..."):
                formato_ida = ida.strftime("%Y-%m-%d")
                formato_volta = volta.strftime("%Y-%m-%d") if tipo_voo == "ida e volta" else ""
                
                noites = max(1, (volta - ida).days) if tipo_voo == "ida e volta" else 1

                dados_voos_json = buscar_voos(origem, destino, formato_ida, formato_volta, tipo_voo, flexibilidade, num_pessoas)
                voos_result = json.loads(dados_voos_json)

                if tipo_voo == "ida e volta":
                    checkout_hotel = formato_volta
                else:
                    checkout_hotel = (ida + datetime.timedelta(days=1)).strftime("%Y-%m-%d")

                dados_hoteis_json = buscar_hoteis(destino, bairro_pref, formato_ida, checkout_hotel, nota_minima, num_pessoas)
                hoteis_result = json.loads(dados_hoteis_json)
                
                st.session_state.resultados_busca = {
                    "voos": voos_result,
                    "hoteis": hoteis_result,
                    "noites": noites,
                    "destino": extrair_cidade(destino),
                    "num_pessoas": num_pessoas
                }

    if "resultados_busca" in st.session_state:
        res = st.session_state.resultados_busca
        voos = res["voos"]
        hoteis = res["hoteis"]
        noites = res["noites"]
        num_pessoas_busca = res["num_pessoas"]
        
        st.divider()
        st.subheader(f"opções para {res['destino']}")
        
        col_res_v, col_res_h = st.columns(2)
        
        with col_res_v:
            st.write(f"### ✈️ passagens aéreas (preço por pessoa)")
            if "erro" in voos:
                st.error(voos["erro"])
                voos_lista = []
            else:
                voos_lista = voos.get("opcoes_reais", [])
                for v in voos_lista:
                    with st.container(border=True):
                        st.write(f"**{v['companhia']}** | voo: {v['voo']} | paradas: {v['paradas']}")
                        st.write(f"**r$ {v['preco']:.2f}**")

        with col_res_h:
            st.write(f"### 🏨 hospedagem (diária para {num_pessoas_busca} pessoas)")
            if "erro" in hoteis:
                st.error(hoteis["erro"])
                hoteis_lista = []
            else:
                hoteis_lista = hoteis.get("opcoes_reais", [])
                for h in hoteis_lista:
                    with st.container(border=True):
                        if h['imagem']:
                            st.image(h['imagem'], use_container_width=True)
                        st.write(f"**{h['nome']}** | ⭐ {h['avaliacao']}")
                        st.write(f"**r$ {h['preco']:.2f} / noite**")
                        
        if voos_lista and hoteis_lista:
            st.divider()
            st.write("### 🛒 monte seu pacote")
            
            def format_voo(v):
                return f"{v['companhia']} ({v['voo']}) - r$ {v['preco']:.2f} por pessoa"
                
            def format_hotel(h):
                return f"{h['nome']} (⭐ {h['avaliacao']}) - r$ {h['preco']:.2f} / noite"
            
            sel_v, sel_h = st.columns(2)
            with sel_v:
                voo_escolhido = st.radio("escolha o voo:", voos_lista, format_func=format_voo)
            with sel_h:
                hotel_escolhido = st.radio("escolha o hotel:", hoteis_lista, format_func=format_hotel)
                
            if voo_escolhido and hotel_escolhido:
                total_voo = voo_escolhido['preco'] * num_pessoas_busca
                total_hotel = hotel_escolhido['preco'] * noites
                total_pacote = total_voo + total_hotel
                
                st.success(f"**resumo:** voos ({num_pessoas_busca}x r$ {voo_escolhido['preco']:.2f} = **r$ {total_voo:.2f}**) + hotel ({noites} noites = **r$ {total_hotel:.2f}**)")
                st.info(f"### 💰 valor total estimado: r$ {total_pacote:.2f}")