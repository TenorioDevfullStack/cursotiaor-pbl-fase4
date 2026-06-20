"""Pipeline de Machine Learning (Scikit-Learn) do Assistente Agricola Inteligente.

Treina modelos de regressao para prever variaveis criticas do campo a partir dos
dados de sensores/simulacao, avalia o desempenho com MAE, MSE, RMSE e R2 e oferece
funcoes de previsao e recomendacao de manejo.

Pode ser usado de duas formas:

- Como modulo importado pela dashboard Streamlit (`dashboard_farmtech.py`).
- Direto pela linha de comando, para treinar, avaliar e salvar o modelo:

    python modelo_ml.py --alvo rendimento --modelo random_forest
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error,
    r2_score,
)
from sklearn.model_selection import cross_val_score, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import PolynomialFeatures, StandardScaler


DATASET_PADRAO = "dados_agricolas.csv"

# Variaveis de entrada (preditoras) disponiveis no dataset agricola.
FEATURES = [
    "temperatura",
    "umidade_ar",
    "umidade_solo",
    "ph",
    "nitrogenio",
    "fosforo",
    "potassio",
    "precipitacao_mm",
    "radiacao_solar",
]

# Variaveis-alvo que os modelos sabem prever.
ALVOS = {
    "rendimento": "Rendimento esperado (ton/ha)",
    "volume_irrigacao": "Volume de irrigacao (L/m2)",
    "umidade_solo": "Umidade do solo (%)",
    "ph": "pH do solo",
}

# Modelos de regressao suportados.
MODELOS = {
    "linear": "Regressao Linear Multipla",
    "polinomial": "Regressao Polinomial (grau 2)",
    "random_forest": "Random Forest (nao linear)",
}

ROTULOS_FEATURES = {
    "temperatura": "Temperatura (C)",
    "umidade_ar": "Umidade do ar (%)",
    "umidade_solo": "Umidade do solo (%)",
    "ph": "pH do solo",
    "nitrogenio": "Nitrogenio (mg/kg)",
    "fosforo": "Fosforo (mg/kg)",
    "potassio": "Potassio (mg/kg)",
    "precipitacao_mm": "Precipitacao (mm)",
    "radiacao_solar": "Radiacao solar (MJ/m2)",
}

# Faixas minimas adequadas de nutrientes no solo (mg/kg). Abaixo do minimo o
# sistema sugere fertilizacao; a quantidade sugerida e proporcional ao deficit.
FAIXAS_NUTRIENTES = {
    "nitrogenio": {"min": 60.0, "rotulo": "Nitrogenio (N)"},
    "fosforo": {"min": 30.0, "rotulo": "Fosforo (P)"},
    "potassio": {"min": 100.0, "rotulo": "Potassio (K)"},
}


def carregar_dados(caminho=DATASET_PADRAO):
    caminho = Path(caminho)
    if not caminho.exists():
        raise FileNotFoundError(
            f"Dataset nao encontrado: {caminho}. Gere com: python gerar_dataset_ml.py"
        )
    return pd.read_csv(caminho)


def features_disponiveis(alvo):
    """Retorna as features validas para um alvo, evitando usar o proprio alvo como entrada."""
    return [coluna for coluna in FEATURES if coluna != alvo]


def construir_pipeline(modelo_nome):
    if modelo_nome == "linear":
        return Pipeline(
            [
                ("scaler", StandardScaler()),
                ("regressor", LinearRegression()),
            ]
        )
    if modelo_nome == "polinomial":
        return Pipeline(
            [
                ("scaler", StandardScaler()),
                ("poly", PolynomialFeatures(degree=2, include_bias=False)),
                ("regressor", LinearRegression()),
            ]
        )
    if modelo_nome == "random_forest":
        return Pipeline(
            [
                (
                    "regressor",
                    RandomForestRegressor(
                        n_estimators=300,
                        max_depth=None,
                        random_state=42,
                        n_jobs=-1,
                    ),
                ),
            ]
        )
    raise ValueError(f"Modelo desconhecido: {modelo_nome}. Opcoes: {list(MODELOS)}")


def treinar_e_avaliar(dados, alvo, modelo_nome, tamanho_teste=0.25, semente=42):
    """Treina o modelo e devolve pipeline ajustado, metricas e dados de teste."""
    if alvo not in ALVOS:
        raise ValueError(f"Alvo invalido: {alvo}. Opcoes: {list(ALVOS)}")

    colunas_features = features_disponiveis(alvo)
    X = dados[colunas_features]
    y = dados[alvo]

    X_treino, X_teste, y_treino, y_teste = train_test_split(
        X, y, test_size=tamanho_teste, random_state=semente
    )

    pipeline = construir_pipeline(modelo_nome)
    pipeline.fit(X_treino, y_treino)

    y_pred = pipeline.predict(X_teste)

    mae = mean_absolute_error(y_teste, y_pred)
    mse = mean_squared_error(y_teste, y_pred)
    rmse = float(np.sqrt(mse))
    r2 = r2_score(y_teste, y_pred)

    # Validacao cruzada (R2) para avaliar estabilidade do modelo.
    cv_scores = cross_val_score(
        construir_pipeline(modelo_nome), X, y, cv=5, scoring="r2"
    )

    return {
        "pipeline": pipeline,
        "alvo": alvo,
        "modelo_nome": modelo_nome,
        "features": colunas_features,
        "metricas": {
            "MAE": mae,
            "MSE": mse,
            "RMSE": rmse,
            "R2": r2,
            "R2_cv_media": float(cv_scores.mean()),
            "R2_cv_desvio": float(cv_scores.std()),
        },
        "y_teste": np.asarray(y_teste),
        "y_pred": np.asarray(y_pred),
        "X_teste": X_teste.reset_index(drop=True),
    }


def importancia_features(resultado):
    """Extrai a importancia/coeficiente das features conforme o modelo treinado."""
    pipeline = resultado["pipeline"]
    features = resultado["features"]
    regressor = pipeline.named_steps["regressor"]

    if hasattr(regressor, "feature_importances_") and "poly" not in pipeline.named_steps:
        valores = regressor.feature_importances_
        return pd.DataFrame(
            {"feature": features, "importancia": valores}
        ).sort_values("importancia", ascending=False)

    if isinstance(regressor, LinearRegression) and "poly" not in pipeline.named_steps:
        valores = np.abs(regressor.coef_)
        return pd.DataFrame(
            {"feature": features, "importancia": valores}
        ).sort_values("importancia", ascending=False)

    return None


def prever(resultado, entrada):
    """Faz uma previsao a partir de um dicionario {feature: valor}."""
    features = resultado["features"]
    linha = pd.DataFrame([{coluna: entrada[coluna] for coluna in features}])
    return float(resultado["pipeline"].predict(linha)[0])


def recomendar_fertilizacao(condicoes):
    """Avalia a necessidade de fertilizacao a partir dos niveis de N, P e K.

    `condicoes` e um dicionario com chaves opcionais nitrogenio, fosforo e potassio
    (mg/kg). Retorna uma lista de tuplas (tipo, texto) no mesmo formato das demais
    recomendacoes, com a dose sugerida proporcional ao deficit em relacao a faixa
    minima adequada.
    """
    recomendacoes = []
    deficientes = []

    for nutriente, faixa in FAIXAS_NUTRIENTES.items():
        valor = condicoes.get(nutriente)
        if valor is None:
            continue
        if valor < faixa["min"]:
            deficit = faixa["min"] - valor
            recomendacoes.append(
                (
                    "warning",
                    f"Fertilizar com {faixa['rotulo']}: nivel em {valor:.0f} mg/kg, "
                    f"abaixo do minimo de {faixa['min']:.0f} mg/kg "
                    f"(repor ~{deficit:.0f} mg/kg).",
                )
            )
            deficientes.append(faixa["rotulo"])

    if not deficientes and any(condicoes.get(n) is not None for n in FAIXAS_NUTRIENTES):
        recomendacoes.append(
            ("success", "Fertilizacao dispensavel: niveis de N, P e K dentro do adequado.")
        )

    return recomendacoes


def recomendar_manejo(previsoes, condicoes=None):
    """Gera recomendacoes de manejo a partir das previsoes dos modelos.

    `previsoes` e um dicionario com chaves opcionais: volume_irrigacao, rendimento, ph.
    `condicoes` (opcional) traz os niveis atuais de nutrientes (nitrogenio, fosforo,
    potassio) usados para sugerir a necessidade de fertilizacao.
    """
    recomendacoes = []

    volume = previsoes.get("volume_irrigacao")
    if volume is not None:
        if volume <= 0.5:
            recomendacoes.append(
                ("success", "Irrigacao dispensavel: volume previsto proximo de zero.")
            )
        elif volume < 4.0:
            recomendacoes.append(
                ("info", f"Irrigacao leve recomendada: aplicar cerca de {volume:.1f} L/m2.")
            )
        else:
            recomendacoes.append(
                ("warning", f"Irrigacao intensa recomendada: aplicar cerca de {volume:.1f} L/m2.")
            )

    rendimento = previsoes.get("rendimento")
    if rendimento is not None:
        if rendimento >= 6.0:
            recomendacoes.append(
                ("success", f"Rendimento previsto alto: {rendimento:.2f} ton/ha. Manter o manejo atual.")
            )
        elif rendimento >= 4.0:
            recomendacoes.append(
                ("info", f"Rendimento previsto moderado: {rendimento:.2f} ton/ha. Ha espaco para otimizar nutrientes.")
            )
        else:
            recomendacoes.append(
                ("warning", f"Rendimento previsto baixo: {rendimento:.2f} ton/ha. Revisar pH, umidade e fertilizacao.")
            )

    ph = previsoes.get("ph")
    if ph is not None and not (6.0 <= ph <= 6.5):
        recomendacoes.append(
            ("warning", f"pH previsto fora da faixa ideal ({ph:.2f}). Avaliar correcao do solo.")
        )

    if condicoes:
        recomendacoes.extend(recomendar_fertilizacao(condicoes))

    if not recomendacoes:
        recomendacoes.append(("info", "Sem recomendacoes especificas para os dados informados."))

    return recomendacoes


def main():
    parser = argparse.ArgumentParser(
        description="Treina e avalia modelos de regressao para variaveis agricolas."
    )
    parser.add_argument("--dataset", default=DATASET_PADRAO, help="CSV de entrada.")
    parser.add_argument(
        "--alvo",
        default="rendimento",
        choices=list(ALVOS),
        help="Variavel-alvo da regressao.",
    )
    parser.add_argument(
        "--modelo",
        default="random_forest",
        choices=list(MODELOS),
        help="Algoritmo de regressao.",
    )
    args = parser.parse_args()

    dados = carregar_dados(args.dataset)
    resultado = treinar_e_avaliar(dados, args.alvo, args.modelo)

    print(f"Alvo:   {ALVOS[args.alvo]}")
    print(f"Modelo: {MODELOS[args.modelo]}")
    print("Metricas de avaliacao (conjunto de teste):")
    for nome, valor in resultado["metricas"].items():
        print(f"  {nome:12s}: {valor:.4f}")

    importancia = importancia_features(resultado)
    if importancia is not None:
        print("\nImportancia das variaveis:")
        print(importancia.to_string(index=False))


if __name__ == "__main__":
    main()
