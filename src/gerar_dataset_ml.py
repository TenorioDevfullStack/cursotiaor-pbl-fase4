"""Gera um dataset agricola sintetico com variabilidade para treinar modelos de regressao.

O CSV de sensores do ESP32 (`dados_sensores.csv`) registra apenas o estado instantaneo
da simulacao e nao possui variancia suficiente para treinar modelos de aprendizado.
Este script cria um conjunto de dados maior e realista, no qual as variaveis-alvo
(rendimento da cultura e volume de irrigacao) dependem das variaveis de entrada por meio
de relacoes fisicas plausiveis somadas a um ruido aleatorio controlado.

Saida padrao: `dados_agricolas.csv`.
"""

import argparse
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd


COLUNAS = [
    "data",
    "temperatura",
    "umidade_ar",
    "umidade_solo",
    "ph",
    "nitrogenio",
    "fosforo",
    "potassio",
    "precipitacao_mm",
    "radiacao_solar",
    "volume_irrigacao",
    "rendimento",
]

UMIDADE_SOLO_IDEAL = 65.0
PH_IDEAL = 6.25


def gerar_dataset(n_amostras, semente):
    rng = np.random.default_rng(semente)

    # Variaveis climaticas e de solo independentes (drivers do sistema).
    temperatura = rng.normal(26.0, 4.5, n_amostras).clip(10, 42)
    umidade_ar = rng.normal(62.0, 14.0, n_amostras).clip(20, 100)
    nitrogenio = rng.normal(75.0, 22.0, n_amostras).clip(5, 140)
    fosforo = rng.normal(45.0, 16.0, n_amostras).clip(3, 100)
    potassio = rng.normal(120.0, 35.0, n_amostras).clip(20, 220)
    precipitacao_mm = rng.gamma(2.0, 3.0, n_amostras).clip(0, 60)
    radiacao_solar = rng.normal(20.0, 5.0, n_amostras).clip(5, 35)

    # Umidade do solo (%) e derivada do clima: aumenta com chuva e umidade do ar,
    # diminui com temperatura e radiacao solar (evapotranspiracao).
    umidade_solo = (
        50.0
        + 0.9 * precipitacao_mm
        + 0.25 * (umidade_ar - 62)
        - 0.8 * (temperatura - 26)
        - 0.6 * (radiacao_solar - 20)
        + rng.normal(0, 5.0, n_amostras)
    ).clip(10, 95)

    # pH do solo depende da quimica do solo: chuva intensa lixivia bases e tende a
    # acidificar (reduz pH), enquanto maior disponibilidade de potassio eleva o pH.
    ph = (
        6.3
        - 0.020 * (precipitacao_mm - 6)
        + 0.0035 * (potassio - 120)
        - 0.004 * (nitrogenio - 75)
        + rng.normal(0, 0.45, n_amostras)
    ).clip(4.0, 8.5)

    # Volume de irrigacao (L/m2): cresce com a falta de umidade no solo e com o calor,
    # e diminui com a chuva recente.
    deficit_umidade = (UMIDADE_SOLO_IDEAL - umidade_solo).clip(0, None)
    volume_irrigacao = (
        0.18 * deficit_umidade
        + 0.22 * (temperatura - 20).clip(0, None)
        - 0.30 * precipitacao_mm
        + 0.05 * (radiacao_solar - 15)
        + rng.normal(0, 0.8, n_amostras)
    ).clip(0, None)

    # Rendimento esperado (ton/ha): penaliza desvios de umidade e pH ideais,
    # cresce com a disponibilidade de nutrientes e com a radiacao solar.
    penalidade_umidade = -0.018 * (umidade_solo - UMIDADE_SOLO_IDEAL) ** 2 / 10
    penalidade_ph = -1.6 * (ph - PH_IDEAL) ** 2
    contrib_nutrientes = (
        0.020 * nitrogenio + 0.022 * fosforo + 0.012 * potassio
    )
    rendimento = (
        4.0
        + contrib_nutrientes
        + penalidade_umidade
        + penalidade_ph
        + 0.06 * radiacao_solar
        - 0.04 * (temperatura - 26) ** 2 / 5
        + 0.015 * precipitacao_mm
        + rng.normal(0, 0.6, n_amostras)
    ).clip(0.5, None)

    data_base = datetime(2026, 1, 1)
    datas = [data_base + timedelta(days=int(i)) for i in range(n_amostras)]

    dados = pd.DataFrame(
        {
            "data": [d.date().isoformat() for d in datas],
            "temperatura": temperatura.round(2),
            "umidade_ar": umidade_ar.round(2),
            "umidade_solo": umidade_solo.round(2),
            "ph": ph.round(2),
            "nitrogenio": nitrogenio.round(2),
            "fosforo": fosforo.round(2),
            "potassio": potassio.round(2),
            "precipitacao_mm": precipitacao_mm.round(2),
            "radiacao_solar": radiacao_solar.round(2),
            "volume_irrigacao": volume_irrigacao.round(2),
            "rendimento": rendimento.round(3),
        }
    )

    return dados[COLUNAS]


def main():
    parser = argparse.ArgumentParser(
        description="Gera um dataset agricola sintetico para treinar modelos de regressao."
    )
    parser.add_argument(
        "--amostras",
        type=int,
        default=500,
        help="Quantidade de registros a gerar. Padrao: 500",
    )
    parser.add_argument(
        "--semente",
        type=int,
        default=42,
        help="Semente do gerador aleatorio para reprodutibilidade. Padrao: 42",
    )
    parser.add_argument(
        "--saida",
        default="dados_agricolas.csv",
        help="Caminho do CSV de saida. Padrao: dados_agricolas.csv",
    )

    args = parser.parse_args()
    dados = gerar_dataset(args.amostras, args.semente)
    caminho = Path(args.saida)
    dados.to_csv(caminho, index=False)

    print(f"Dataset gerado: {caminho.resolve()}")
    print(f"Registros: {len(dados)}")
    print(dados.describe().round(2).to_string())


if __name__ == "__main__":
    main()
