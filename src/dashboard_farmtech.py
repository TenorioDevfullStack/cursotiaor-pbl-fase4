import os
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st

import banco_dados
import modelo_ml


CSV_PADRAO = "dados_sensores_wokwi.csv"
DATASET_ML_PADRAO = "dados_agricolas.csv"
BANCO_PADRAO = "farmtech.db"
ARQUIVO_ENV = Path(".env")
UMIDADE_MINIMA = 60.0
PH_MIN = 6.0
PH_MAX = 6.5


COLUNAS_ESPERADAS = [
    "data_hora",
    "timestamp_ms",
    "umidade",
    "ph",
    "n_ok",
    "p_ok",
    "k_ok",
    "chuva_prevista",
    "bomba",
]


def formatar_numero(valor, casas=1, sufixo=""):
    if pd.isna(valor):
        return "Sem dado"
    return f"{float(valor):.{casas}f}{sufixo}"


def valor_binario(valor, padrao=0):
    if pd.isna(valor):
        return padrao
    try:
        return 1 if int(valor) == 1 else 0
    except (TypeError, ValueError):
        return padrao


def status_ok(valor):
    if pd.isna(valor):
        return "Sem dado"
    return "OK" if valor_binario(valor) == 1 else "Baixo"


def classe_irrigacao(valor):
    texto = str(valor).strip().upper()
    if texto == "LIGADA":
        return "LIGADA"
    if texto == "DESLIGADA":
        return "DESLIGADA"
    return "DESCONHECIDA"


def ler_dados(caminho_csv):
    caminho = Path(caminho_csv)
    if not caminho.exists():
        return pd.DataFrame(columns=COLUNAS_ESPERADAS), f"Arquivo nao encontrado: {caminho}"

    try:
        dados = pd.read_csv(caminho)
    except Exception as erro:
        return pd.DataFrame(columns=COLUNAS_ESPERADAS), f"Falha ao ler CSV: {erro}"

    colunas_faltando = [coluna for coluna in COLUNAS_ESPERADAS if coluna not in dados.columns]
    if colunas_faltando:
        return (
            pd.DataFrame(columns=COLUNAS_ESPERADAS),
            "Colunas ausentes no CSV: " + ", ".join(colunas_faltando),
        )

    if dados.empty:
        return pd.DataFrame(columns=COLUNAS_ESPERADAS), "CSV sem registros."

    dados = dados[COLUNAS_ESPERADAS].copy()
    dados["data_hora"] = pd.to_datetime(dados["data_hora"], errors="coerce")

    for coluna in ["timestamp_ms", "umidade", "ph", "n_ok", "p_ok", "k_ok", "chuva_prevista"]:
        dados[coluna] = pd.to_numeric(dados[coluna], errors="coerce")

    dados["bomba"] = dados["bomba"].fillna("DESCONHECIDA").astype(str).str.upper()
    dados["tempo_s"] = dados["timestamp_ms"] / 1000

    if dados["data_hora"].nunique(dropna=True) > 1:
        dados["eixo_tempo"] = dados["data_hora"]
        titulo_eixo = "Horario"
    else:
        dados["eixo_tempo"] = dados["tempo_s"]
        titulo_eixo = "Tempo de simulacao (s)"

    return dados, titulo_eixo


def limpar_valor_env(valor):
    return valor.strip().strip('"').strip("'")


def ler_chave_dotenv(caminho=ARQUIVO_ENV):
    if not caminho.exists():
        return ""

    for linha in caminho.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue

        nome, valor = linha.split("=", 1)
        if nome.strip() == "OPENWEATHER_API_KEY":
            return limpar_valor_env(valor)

    return ""


def obter_chave_openweather():
    chave_ambiente = os.environ.get("OPENWEATHER_API_KEY", "").strip()
    if chave_ambiente:
        return chave_ambiente, "variavel de ambiente"

    chave_dotenv = ler_chave_dotenv()
    if chave_dotenv:
        return chave_dotenv, ".env"

    try:
        chave_secrets = st.secrets.get("OPENWEATHER_API_KEY", "").strip()
        if chave_secrets:
            return chave_secrets, "Streamlit secrets"
    except Exception:
        pass

    return "", ""


@st.cache_data(ttl=600)
def consultar_clima(cidade, api_key):
    if not cidade or not api_key:
        return None

    resposta = requests.get(
        "https://api.openweathermap.org/data/2.5/weather",
        params={
            "q": cidade,
            "appid": api_key,
            "units": "metric",
            "lang": "pt_br",
        },
        timeout=10,
    )
    resposta.raise_for_status()
    payload = resposta.json()
    clima = payload["weather"][0]
    clima_principal = clima.get("main", "")
    descricao = clima.get("description", "").capitalize()
    chuva_detectada = clima_principal in {"Rain", "Drizzle", "Thunderstorm"} or bool(payload.get("rain"))

    return {
        "cidade": payload.get("name", cidade),
        "temperatura": payload.get("main", {}).get("temp"),
        "umidade_ar": payload.get("main", {}).get("humidity"),
        "clima": clima_principal,
        "descricao": descricao,
        "chuva": chuva_detectada,
    }


def montar_sugestoes(ultima_leitura, clima):
    sugestoes = []
    chuva_sensor = valor_binario(ultima_leitura.get("chuva_prevista", 0)) == 1
    chuva_clima = bool(clima["chuva"]) if clima else None
    chuva_considerada = chuva_clima if chuva_clima is not None else chuva_sensor
    origem_chuva = "OpenWeather" if chuva_clima is not None else "CSV"

    umidade = ultima_leitura.get("umidade")
    ph = ultima_leitura.get("ph")
    p_ok = ultima_leitura.get("p_ok")
    k_ok = ultima_leitura.get("k_ok")
    bomba = classe_irrigacao(ultima_leitura.get("bomba"))

    if chuva_considerada:
        sugestoes.append(
            (
                "warning",
                f"Suspender irrigacao: chuva detectada ou prevista pela origem {origem_chuva}.",
            )
        )
    elif pd.notna(umidade) and umidade < UMIDADE_MINIMA:
        sugestoes.append(
            (
                "error",
                f"Irrigar agora: umidade em {umidade:.1f}%, abaixo do minimo de {UMIDADE_MINIMA:.0f}%.",
            )
        )
    else:
        sugestoes.append(("success", "Manter irrigacao sob monitoramento: umidade dentro do limite."))

    if pd.notna(ph) and not (PH_MIN <= ph <= PH_MAX):
        sugestoes.append(
            (
                "warning",
                f"Ajustar pH do solo: leitura em {ph:.1f}, fora da faixa ideal de {PH_MIN:.1f} a {PH_MAX:.1f}.",
            )
        )

    nutrientes_baixos = []
    if pd.notna(p_ok) and valor_binario(p_ok) == 0:
        nutrientes_baixos.append("P")
    if pd.notna(k_ok) and valor_binario(k_ok) == 0:
        nutrientes_baixos.append("K")

    if nutrientes_baixos:
        sugestoes.append(
            (
                "warning",
                "Repor nutrientes antes da proxima fertirrigacao: " + ", ".join(nutrientes_baixos) + ".",
            )
        )

    if chuva_considerada and bomba == "LIGADA":
        sugestoes.append(("error", "Bomba ligada com chuva prevista: revisar acionamento para evitar desperdicio."))

    return sugestoes


def exibir_sugestoes(sugestoes):
    for tipo, texto in sugestoes:
        if tipo == "success":
            st.success(texto)
        elif tipo == "error":
            st.error(texto)
        else:
            st.warning(texto)


def grafico_umidade(dados, eixo_x, titulo_eixo):
    figura = go.Figure()
    figura.add_trace(
        go.Scatter(
            x=dados[eixo_x],
            y=dados["umidade"],
            mode="lines+markers",
            name="Umidade",
            line={"color": "#1f77b4", "width": 3},
        )
    )
    figura.add_hline(
        y=UMIDADE_MINIMA,
        line_dash="dash",
        line_color="#d62728",
        annotation_text="Minimo",
        annotation_position="top left",
    )
    figura.update_layout(
        title="Umidade do solo",
        xaxis_title=titulo_eixo,
        yaxis_title="Umidade (%)",
        margin={"l": 20, "r": 20, "t": 55, "b": 20},
        height=330,
    )
    return figura


def grafico_ph(dados, eixo_x, titulo_eixo):
    figura = go.Figure()
    figura.add_trace(
        go.Scatter(
            x=dados[eixo_x],
            y=dados["ph"],
            mode="lines+markers",
            name="pH",
            line={"color": "#2ca02c", "width": 3},
        )
    )
    figura.add_hrect(
        y0=PH_MIN,
        y1=PH_MAX,
        fillcolor="#2ca02c",
        opacity=0.16,
        line_width=0,
        annotation_text="Faixa ideal",
        annotation_position="top left",
    )
    figura.update_layout(
        title="pH do solo",
        xaxis_title=titulo_eixo,
        yaxis_title="pH",
        margin={"l": 20, "r": 20, "t": 55, "b": 20},
        height=330,
    )
    return figura


def grafico_irrigacao(dados, eixo_x, titulo_eixo):
    figura = go.Figure()
    figura.add_trace(
        go.Scatter(
            x=dados[eixo_x],
            y=dados["bomba"].eq("LIGADA").astype(int),
            mode="lines",
            name="Bomba ligada",
            line={"shape": "hv", "color": "#d62728", "width": 3},
        )
    )
    figura.add_trace(
        go.Scatter(
            x=dados[eixo_x],
            y=dados["chuva_prevista"].fillna(0),
            mode="lines",
            name="Chuva prevista",
            line={"shape": "hv", "color": "#17becf", "width": 2},
        )
    )
    figura.update_yaxes(
        tickmode="array",
        tickvals=[0, 1],
        ticktext=["Nao", "Sim"],
        range=[-0.15, 1.15],
    )
    figura.update_layout(
        title="Status da irrigacao e chuva",
        xaxis_title=titulo_eixo,
        yaxis_title="Status",
        margin={"l": 20, "r": 20, "t": 55, "b": 20},
        height=330,
    )
    return figura


def grafico_nutrientes(ultima_leitura):
    nutrientes = pd.DataFrame(
        {
            "nutriente": ["N", "P", "K"],
            "status": [
                valor_binario(ultima_leitura.get("n_ok", 0)),
                valor_binario(ultima_leitura.get("p_ok", 0)),
                valor_binario(ultima_leitura.get("k_ok", 0)),
            ],
        }
    )
    figura = go.Figure(
        go.Bar(
            x=nutrientes["nutriente"],
            y=nutrientes["status"],
            marker_color=["#7f7f7f" if valor == 0 else "#2ca02c" for valor in nutrientes["status"]],
            text=["OK" if valor == 1 else "Baixo" for valor in nutrientes["status"]],
            textposition="outside",
        )
    )
    figura.update_yaxes(
        tickmode="array",
        tickvals=[0, 1],
        ticktext=["Baixo", "OK"],
        range=[0, 1.2],
    )
    figura.update_layout(
        title="Nutrientes na ultima leitura",
        xaxis_title="Nutriente",
        yaxis_title="Status",
        margin={"l": 20, "r": 20, "t": 55, "b": 20},
        height=330,
    )
    return figura


@st.cache_data(ttl=600)
def carregar_dataset_ml(caminho):
    return modelo_ml.carregar_dados(caminho)


@st.cache_resource(show_spinner=False)
def treinar_modelo_cache(caminho, alvo, modelo_nome):
    dados = modelo_ml.carregar_dados(caminho)
    return modelo_ml.treinar_e_avaliar(dados, alvo, modelo_nome)


def grafico_previsto_real(resultado):
    y_teste = resultado["y_teste"]
    y_pred = resultado["y_pred"]
    minimo = float(min(y_teste.min(), y_pred.min()))
    maximo = float(max(y_teste.max(), y_pred.max()))

    figura = go.Figure()
    figura.add_trace(
        go.Scatter(
            x=y_teste,
            y=y_pred,
            mode="markers",
            name="Amostras de teste",
            marker={"color": "#1f77b4", "opacity": 0.7},
        )
    )
    figura.add_trace(
        go.Scatter(
            x=[minimo, maximo],
            y=[minimo, maximo],
            mode="lines",
            name="Previsao ideal",
            line={"color": "#d62728", "dash": "dash"},
        )
    )
    figura.update_layout(
        title="Valor previsto vs valor real",
        xaxis_title="Real",
        yaxis_title="Previsto",
        margin={"l": 20, "r": 20, "t": 55, "b": 20},
        height=360,
    )
    return figura


def grafico_residuos(resultado):
    y_pred = resultado["y_pred"]
    residuos = resultado["y_teste"] - y_pred

    figura = go.Figure()
    figura.add_trace(
        go.Scatter(
            x=y_pred,
            y=residuos,
            mode="markers",
            name="Residuos",
            marker={"color": "#2ca02c", "opacity": 0.7},
        )
    )
    figura.add_hline(y=0, line_dash="dash", line_color="#d62728")
    figura.update_layout(
        title="Residuos (real - previsto)",
        xaxis_title="Previsto",
        yaxis_title="Residuo",
        margin={"l": 20, "r": 20, "t": 55, "b": 20},
        height=360,
    )
    return figura


def grafico_importancia(resultado):
    importancia = modelo_ml.importancia_features(resultado)
    if importancia is None:
        return None

    importancia = importancia.sort_values("importancia")
    figura = go.Figure(
        go.Bar(
            x=importancia["importancia"],
            y=[modelo_ml.ROTULOS_FEATURES.get(f, f) for f in importancia["feature"]],
            orientation="h",
            marker_color="#1f77b4",
        )
    )
    figura.update_layout(
        title="Importancia das variaveis",
        xaxis_title="Peso relativo",
        margin={"l": 20, "r": 20, "t": 55, "b": 20},
        height=360,
    )
    return figura


def grafico_correlacao(dados):
    colunas = modelo_ml.FEATURES + [a for a in modelo_ml.ALVOS if a in dados.columns]
    colunas = list(dict.fromkeys(colunas))
    matriz = dados[colunas].corr().round(2)
    figura = px.imshow(
        matriz,
        text_auto=True,
        color_continuous_scale="RdBu_r",
        zmin=-1,
        zmax=1,
        aspect="auto",
    )
    figura.update_layout(
        title="Matriz de correlacao",
        margin={"l": 20, "r": 20, "t": 55, "b": 20},
        height=560,
    )
    return figura


def grafico_tendencia(dados, alvo):
    coluna_x = "data" if "data" in dados.columns else dados.index
    figura = go.Figure()
    figura.add_trace(
        go.Scatter(
            x=dados[coluna_x] if isinstance(coluna_x, str) else coluna_x,
            y=dados[alvo],
            mode="lines",
            name=modelo_ml.ALVOS.get(alvo, alvo),
            line={"color": "#1f77b4", "width": 2},
        )
    )
    media_movel = dados[alvo].rolling(window=14, min_periods=1).mean()
    figura.add_trace(
        go.Scatter(
            x=dados[coluna_x] if isinstance(coluna_x, str) else coluna_x,
            y=media_movel,
            mode="lines",
            name="Media movel (14)",
            line={"color": "#d62728", "width": 3},
        )
    )
    figura.update_layout(
        title=f"Tendencia de {modelo_ml.ALVOS.get(alvo, alvo)}",
        xaxis_title="Data",
        yaxis_title=modelo_ml.ALVOS.get(alvo, alvo),
        margin={"l": 20, "r": 20, "t": 55, "b": 20},
        height=380,
    )
    return figura


def aba_monitoramento(caminho_csv, cidade, api_key):
    dados, status_csv = ler_dados(caminho_csv)

    if dados.empty:
        st.error(status_csv if isinstance(status_csv, str) else "CSV sem registros.")
        return

    eixo_x = "eixo_tempo"
    titulo_eixo = status_csv
    ultima = dados.iloc[-1]

    try:
        clima = consultar_clima(cidade, api_key)
    except Exception as erro:
        clima = None
        st.warning(f"Clima indisponivel: {erro}")

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Umidade", formatar_numero(ultima["umidade"], sufixo="%"))
    col2.metric("pH", formatar_numero(ultima["ph"]))
    col3.metric("Fosforo (P)", status_ok(ultima["p_ok"]))
    col4.metric("Potassio (K)", status_ok(ultima["k_ok"]))
    col5.metric("Irrigacao", classe_irrigacao(ultima["bomba"]))

    clima_col, sugestao_col = st.columns([1, 2])

    with clima_col:
        st.subheader("Clima")
        if clima:
            st.metric("Cidade", clima["cidade"])
            st.metric("Temperatura", formatar_numero(clima["temperatura"], sufixo=" C"))
            st.metric("Umidade do ar", formatar_numero(clima["umidade_ar"], casas=0, sufixo="%"))
            st.metric("Condicao", clima["descricao"] or clima["clima"])
        else:
            chuva_csv = "Sim" if valor_binario(ultima.get("chuva_prevista", 0)) == 1 else "Nao"
            st.metric("Chuva prevista no CSV", chuva_csv)
            st.info("Configure OPENWEATHER_API_KEY para consultar o clima atual.")

    with sugestao_col:
        st.subheader("Sugestoes de irrigacao")
        exibir_sugestoes(montar_sugestoes(ultima, clima))

    graf_col1, graf_col2 = st.columns(2)
    graf_col1.plotly_chart(grafico_umidade(dados, eixo_x, titulo_eixo), use_container_width=True)
    graf_col2.plotly_chart(grafico_ph(dados, eixo_x, titulo_eixo), use_container_width=True)

    graf_col3, graf_col4 = st.columns(2)
    graf_col3.plotly_chart(grafico_irrigacao(dados, eixo_x, titulo_eixo), use_container_width=True)
    graf_col4.plotly_chart(grafico_nutrientes(ultima), use_container_width=True)

    st.dataframe(
        dados.sort_index(ascending=False),
        use_container_width=True,
        hide_index=True,
    )


def aba_machine_learning(caminho_dataset, alvo, modelo_nome):
    st.subheader("Pipeline de Machine Learning (Scikit-Learn)")
    st.caption(
        "Pipeline: divisao treino/teste -> StandardScaler -> modelo de regressao -> "
        "avaliacao com MAE, MSE, RMSE e R2 + validacao cruzada (5 folds)."
    )

    try:
        resultado = treinar_modelo_cache(caminho_dataset, alvo, modelo_nome)
    except FileNotFoundError as erro:
        st.error(str(erro))
        return None

    metricas = resultado["metricas"]
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("MAE", f"{metricas['MAE']:.3f}")
    col2.metric("MSE", f"{metricas['MSE']:.3f}")
    col3.metric("RMSE", f"{metricas['RMSE']:.3f}")
    col4.metric("R2", f"{metricas['R2']:.3f}")

    st.caption(
        f"R2 medio na validacao cruzada: {metricas['R2_cv_media']:.3f} "
        f"(desvio {metricas['R2_cv_desvio']:.3f})."
    )

    graf_col1, graf_col2 = st.columns(2)
    graf_col1.plotly_chart(grafico_previsto_real(resultado), use_container_width=True)
    graf_col2.plotly_chart(grafico_residuos(resultado), use_container_width=True)

    figura_importancia = grafico_importancia(resultado)
    if figura_importancia is not None:
        st.plotly_chart(figura_importancia, use_container_width=True)
    else:
        st.info("Importancia de variaveis nao disponivel para a regressao polinomial.")

    return resultado


def aba_correlacao_tendencias(caminho_dataset, alvo):
    st.subheader("Correlacao e tendencias de produtividade")

    try:
        dados = carregar_dataset_ml(caminho_dataset)
    except FileNotFoundError as erro:
        st.error(str(erro))
        return

    st.plotly_chart(grafico_correlacao(dados), use_container_width=True)
    st.plotly_chart(grafico_tendencia(dados, alvo), use_container_width=True)


def aba_previsao(caminho_dataset, resultados_treino):
    st.subheader("Previsao interativa e recomendacoes de manejo")

    try:
        dados = carregar_dataset_ml(caminho_dataset)
    except FileNotFoundError as erro:
        st.error(str(erro))
        return

    st.caption("Ajuste as condicoes do campo e o modelo preve as variaveis criticas em tempo real.")

    entrada = {}
    colunas_form = st.columns(3)
    for indice, feature in enumerate(modelo_ml.FEATURES):
        coluna = colunas_form[indice % 3]
        serie = dados[feature]
        entrada[feature] = coluna.slider(
            modelo_ml.ROTULOS_FEATURES.get(feature, feature),
            min_value=float(serie.min()),
            max_value=float(serie.max()),
            value=float(serie.median()),
        )

    previsoes = {}
    for alvo in ["rendimento", "volume_irrigacao", "ph"]:
        resultado = resultados_treino.get(alvo)
        if resultado is None:
            continue
        entrada_alvo = {f: entrada[f] for f in resultado["features"]}
        previsoes[alvo] = modelo_ml.prever(resultado, entrada_alvo)

    col1, col2, col3 = st.columns(3)
    if "rendimento" in previsoes:
        col1.metric("Rendimento previsto", f"{previsoes['rendimento']:.2f} ton/ha")
    if "volume_irrigacao" in previsoes:
        col2.metric("Volume de irrigacao", f"{previsoes['volume_irrigacao']:.2f} L/m2")
    if "ph" in previsoes:
        col3.metric("pH previsto", f"{previsoes['ph']:.2f}")

    st.markdown("#### Recomendacoes de manejo")
    condicoes = {n: entrada.get(n) for n in modelo_ml.FAIXAS_NUTRIENTES}
    for tipo, texto in modelo_ml.recomendar_manejo(previsoes, condicoes):
        if tipo == "success":
            st.success(texto)
        elif tipo == "warning":
            st.warning(texto)
        else:
            st.info(texto)


def aba_banco_dados(caminho_banco, csv_sensores, csv_agricola):
    st.subheader("Banco de dados SQL (SQLite)")
    st.caption(
        "Ingestao e atualizacao dos dados IoT e agronomicos em um banco relacional. "
        "Os mesmos dados alimentam os modelos de Machine Learning."
    )

    if not Path(caminho_banco).exists():
        st.info(
            f"Banco '{caminho_banco}' ainda nao existe. Clique abaixo para criar e popular "
            "(equivale a `python banco_dados.py ingerir`)."
        )

    if st.button("Ingerir/atualizar dados no banco"):
        with conectar_e_ingerir(caminho_banco, csv_sensores, csv_agricola) as mensagem:
            st.success(mensagem)

    if not Path(caminho_banco).exists():
        return

    with banco_dados.conectar(caminho_banco) as conexao:
        n_sensores = banco_dados.contar(conexao, "leituras_sensores")
        n_agricolas = banco_dados.contar(conexao, "dados_agricolas")

        col1, col2 = st.columns(2)
        col1.metric("Leituras de sensores (IoT)", n_sensores)
        col2.metric("Registros agronomicos (ML)", n_agricolas)

        if n_sensores:
            st.markdown("##### Ultimas leituras dos sensores")
            df_sensores = pd.read_sql_query(
                "SELECT data_hora, umidade, ph, n_ok, p_ok, k_ok, chuva_prevista, bomba "
                "FROM leituras_sensores ORDER BY timestamp_ms DESC LIMIT 20",
                conexao,
            )
            st.dataframe(df_sensores, use_container_width=True, hide_index=True)

        if n_agricolas:
            st.markdown("##### Amostra do dataset agronomico")
            df_agricola = pd.read_sql_query(
                "SELECT * FROM dados_agricolas ORDER BY data DESC LIMIT 20",
                conexao,
            )
            st.dataframe(df_agricola, use_container_width=True, hide_index=True)


class conectar_e_ingerir:
    """Context manager utilitario que ingere os CSVs e devolve uma mensagem de status."""

    def __init__(self, caminho_banco, csv_sensores, csv_agricola):
        self.caminho_banco = caminho_banco
        self.csv_sensores = csv_sensores
        self.csv_agricola = csv_agricola

    def __enter__(self):
        with banco_dados.conectar(self.caminho_banco) as conexao:
            n_sensores = n_agricolas = 0
            try:
                n_sensores = banco_dados.ingerir_sensores(conexao, self.csv_sensores)
            except (FileNotFoundError, ValueError):
                pass
            try:
                n_agricolas = banco_dados.ingerir_agricolas(conexao, self.csv_agricola)
            except (FileNotFoundError, ValueError):
                pass
        return (
            f"Banco atualizado: {n_sensores} leituras IoT e "
            f"{n_agricolas} registros agronomicos."
        )

    def __exit__(self, *args):
        return False


def main():
    st.set_page_config(page_title="FarmTech Dashboard", layout="wide")

    st.title("FarmTech - Assistente Agricola Inteligente")

    with st.sidebar:
        st.header("Monitoramento IoT")
        caminho_csv = st.text_input("Arquivo CSV de sensores", value=CSV_PADRAO)
        cidade = st.text_input("Cidade para clima", value="Sao Paulo")
        api_key, origem_chave = obter_chave_openweather()
        if origem_chave:
            st.caption(f"OpenWeather ativo via {origem_chave}.")
        else:
            st.caption("Configure OPENWEATHER_API_KEY para ativar o clima em tempo real.")

        st.divider()
        st.header("Banco de dados")
        caminho_banco = st.text_input("Arquivo SQLite", value=BANCO_PADRAO)

        st.divider()
        st.header("Machine Learning")
        caminho_dataset = st.text_input("Dataset agricola", value=DATASET_ML_PADRAO)
        alvo = st.selectbox(
            "Variavel-alvo",
            options=list(modelo_ml.ALVOS),
            format_func=lambda chave: modelo_ml.ALVOS[chave],
        )
        modelo_nome = st.selectbox(
            "Modelo de regressao",
            options=list(modelo_ml.MODELOS),
            index=list(modelo_ml.MODELOS).index("random_forest"),
            format_func=lambda chave: modelo_ml.MODELOS[chave],
        )

    aba_iot, aba_bd, aba_ml, aba_corr, aba_prev = st.tabs(
        [
            "Monitoramento IoT",
            "Banco de Dados",
            "Machine Learning",
            "Correlacao e Tendencias",
            "Previsao Interativa",
        ]
    )

    with aba_iot:
        aba_monitoramento(caminho_csv, cidade, api_key)

    with aba_bd:
        aba_banco_dados(caminho_banco, caminho_csv, caminho_dataset)

    with aba_ml:
        aba_machine_learning(caminho_dataset, alvo, modelo_nome)

    with aba_corr:
        aba_correlacao_tendencias(caminho_dataset, alvo)

    with aba_prev:
        try:
            resultados_treino = {
                nome: treinar_modelo_cache(caminho_dataset, nome, modelo_nome)
                for nome in ["rendimento", "volume_irrigacao", "ph"]
            }
            aba_previsao(caminho_dataset, resultados_treino)
        except FileNotFoundError as erro:
            st.error(str(erro))


if __name__ == "__main__":
    main()
