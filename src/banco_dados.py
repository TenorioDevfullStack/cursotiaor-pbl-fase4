"""Banco de dados SQL (SQLite) do Assistente Agricola Inteligente - Fase 4.

Modela um banco relacional simples capaz de armazenar os dados coletados pelos
sensores IoT (reais do ESP32 ou simulados no Wokwi) e o dataset agronomico usado
pelos modelos de Machine Learning, seguindo a ideia de ingestao de dados de
Cognitive Data Science.

Diferente de `importar_csv_oracle.py` (que depende de um servidor Oracle e
credenciais), este modulo usa SQLite da biblioteca padrao do Python, portanto roda
e pode ser demonstrado sem nenhuma configuracao externa. O arquivo do banco e
criado localmente (`farmtech.db`).

Recursos:

- Criacao automatica do schema (tabelas `leituras_sensores` e `dados_agricolas`).
- Ingestao/populacao a partir dos CSVs com *upsert* (sem duplicar registros).
- Atualizacao automatica: o modo `--observar` monitora os CSVs e re-ingere a cada
  alteracao do arquivo, simulando a chegada continua de dados dos sensores.

Exemplos de uso:

    # Cria o banco e popula com os dois CSVs
    python banco_dados.py ingerir

    # Consulta um resumo dos dados armazenados
    python banco_dados.py resumo

    # Mantem o banco atualizado automaticamente conforme os CSVs mudam
    python banco_dados.py observar --intervalo 5
"""

import argparse
import sqlite3
import time
from datetime import datetime
from pathlib import Path


BANCO_PADRAO = "farmtech.db"
CSV_SENSORES_PADRAO = "dados_sensores_wokwi.csv"
CSV_AGRICOLA_PADRAO = "dados_agricolas.csv"


SCHEMA = """
CREATE TABLE IF NOT EXISTS leituras_sensores (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    data_hora     TEXT NOT NULL,
    timestamp_ms  INTEGER NOT NULL UNIQUE,
    umidade       REAL,
    ph            REAL,
    n_ok          INTEGER,
    p_ok          INTEGER,
    k_ok          INTEGER,
    chuva_prevista INTEGER,
    bomba         TEXT,
    criado_em     TEXT DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS dados_agricolas (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    data            TEXT NOT NULL UNIQUE,
    temperatura     REAL,
    umidade_ar      REAL,
    umidade_solo    REAL,
    ph              REAL,
    nitrogenio      REAL,
    fosforo         REAL,
    potassio        REAL,
    precipitacao_mm REAL,
    radiacao_solar  REAL,
    volume_irrigacao REAL,
    rendimento      REAL,
    criado_em       TEXT DEFAULT (datetime('now', 'localtime'))
);

CREATE INDEX IF NOT EXISTS idx_sensores_data_hora ON leituras_sensores (data_hora);
CREATE INDEX IF NOT EXISTS idx_agricolas_data ON dados_agricolas (data);
"""


COLUNAS_SENSORES = [
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

COLUNAS_AGRICOLA = [
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


def conectar(caminho_banco=BANCO_PADRAO):
    """Abre (ou cria) o banco SQLite e garante o schema."""
    conexao = sqlite3.connect(caminho_banco)
    conexao.row_factory = sqlite3.Row
    conexao.executescript(SCHEMA)
    conexao.commit()
    return conexao


def _ler_csv(caminho, colunas_esperadas):
    """Le um CSV simples usando a biblioteca padrao, validando o cabecalho."""
    import csv

    caminho = Path(caminho)
    if not caminho.exists():
        raise FileNotFoundError(f"CSV nao encontrado: {caminho}")

    with caminho.open(newline="", encoding="utf-8") as arquivo:
        leitor = csv.DictReader(arquivo)
        faltando = [c for c in colunas_esperadas if c not in (leitor.fieldnames or [])]
        if faltando:
            raise ValueError(
                f"Colunas ausentes em {caminho.name}: {', '.join(faltando)}"
            )
        return [linha for linha in leitor]


def _para_float(valor):
    try:
        return float(valor)
    except (TypeError, ValueError):
        return None


def _para_int(valor):
    try:
        return int(float(valor))
    except (TypeError, ValueError):
        return None


def ingerir_sensores(conexao, caminho_csv=CSV_SENSORES_PADRAO):
    """Popula `leituras_sensores` a partir do CSV de IoT (upsert por timestamp_ms)."""
    linhas = _ler_csv(caminho_csv, COLUNAS_SENSORES)
    registros = [
        (
            linha["data_hora"],
            _para_int(linha["timestamp_ms"]),
            _para_float(linha["umidade"]),
            _para_float(linha["ph"]),
            _para_int(linha["n_ok"]),
            _para_int(linha["p_ok"]),
            _para_int(linha["k_ok"]),
            _para_int(linha["chuva_prevista"]),
            str(linha["bomba"]).strip().upper(),
        )
        for linha in linhas
    ]

    sql = """
        INSERT INTO leituras_sensores
            (data_hora, timestamp_ms, umidade, ph, n_ok, p_ok, k_ok, chuva_prevista, bomba)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(timestamp_ms) DO UPDATE SET
            data_hora      = excluded.data_hora,
            umidade        = excluded.umidade,
            ph             = excluded.ph,
            n_ok           = excluded.n_ok,
            p_ok           = excluded.p_ok,
            k_ok           = excluded.k_ok,
            chuva_prevista = excluded.chuva_prevista,
            bomba          = excluded.bomba
    """
    conexao.executemany(sql, registros)
    conexao.commit()
    return len(registros)


def ingerir_agricolas(conexao, caminho_csv=CSV_AGRICOLA_PADRAO):
    """Popula `dados_agricolas` a partir do dataset de ML (upsert por data)."""
    linhas = _ler_csv(caminho_csv, COLUNAS_AGRICOLA)
    registros = [
        (
            linha["data"],
            _para_float(linha["temperatura"]),
            _para_float(linha["umidade_ar"]),
            _para_float(linha["umidade_solo"]),
            _para_float(linha["ph"]),
            _para_float(linha["nitrogenio"]),
            _para_float(linha["fosforo"]),
            _para_float(linha["potassio"]),
            _para_float(linha["precipitacao_mm"]),
            _para_float(linha["radiacao_solar"]),
            _para_float(linha["volume_irrigacao"]),
            _para_float(linha["rendimento"]),
        )
        for linha in linhas
    ]

    sql = """
        INSERT INTO dados_agricolas
            (data, temperatura, umidade_ar, umidade_solo, ph, nitrogenio, fosforo,
             potassio, precipitacao_mm, radiacao_solar, volume_irrigacao, rendimento)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(data) DO UPDATE SET
            temperatura      = excluded.temperatura,
            umidade_ar       = excluded.umidade_ar,
            umidade_solo     = excluded.umidade_solo,
            ph               = excluded.ph,
            nitrogenio       = excluded.nitrogenio,
            fosforo          = excluded.fosforo,
            potassio         = excluded.potassio,
            precipitacao_mm  = excluded.precipitacao_mm,
            radiacao_solar   = excluded.radiacao_solar,
            volume_irrigacao = excluded.volume_irrigacao,
            rendimento       = excluded.rendimento
    """
    conexao.executemany(sql, registros)
    conexao.commit()
    return len(registros)


def contar(conexao, tabela):
    return conexao.execute(f"SELECT COUNT(*) FROM {tabela}").fetchone()[0]


def resumo(conexao):
    """Imprime um resumo do que esta armazenado no banco."""
    n_sensores = contar(conexao, "leituras_sensores")
    n_agricolas = contar(conexao, "dados_agricolas")

    print(f"Tabela leituras_sensores: {n_sensores} registros")
    print(f"Tabela dados_agricolas:   {n_agricolas} registros")

    if n_sensores:
        ultima = conexao.execute(
            "SELECT data_hora, umidade, ph, bomba FROM leituras_sensores "
            "ORDER BY timestamp_ms DESC LIMIT 1"
        ).fetchone()
        print(
            "Ultima leitura IoT -> "
            f"data_hora={ultima['data_hora']}, umidade={ultima['umidade']}, "
            f"ph={ultima['ph']}, bomba={ultima['bomba']}"
        )

    if n_agricolas:
        media = conexao.execute(
            "SELECT AVG(rendimento), AVG(volume_irrigacao) FROM dados_agricolas"
        ).fetchone()
        print(
            "Dataset agronomico -> "
            f"rendimento medio={media[0]:.2f} ton/ha, "
            f"irrigacao media={media[1]:.2f} L/m2"
        )


def _ingerir_se_existir(conexao, caminho, funcao, rotulo):
    try:
        total = funcao(conexao, caminho)
        print(f"[{datetime.now():%H:%M:%S}] {rotulo}: {total} registros ingeridos.")
        return total
    except FileNotFoundError as erro:
        print(f"[{datetime.now():%H:%M:%S}] {rotulo} ignorado: {erro}")
        return 0


def ingerir_tudo(caminho_banco, csv_sensores, csv_agricola):
    with conectar(caminho_banco) as conexao:
        _ingerir_se_existir(conexao, csv_sensores, ingerir_sensores, "Sensores IoT")
        _ingerir_se_existir(conexao, csv_agricola, ingerir_agricolas, "Dados agronomicos")
        print()
        resumo(conexao)


def observar(caminho_banco, csv_sensores, csv_agricola, intervalo):
    """Mantem o banco atualizado: re-ingere os CSVs sempre que sao modificados."""
    print(
        "Observando mudancas nos CSVs (Ctrl+C para parar). "
        f"Intervalo: {intervalo}s\n"
    )
    mtimes = {}

    def mtime(caminho):
        p = Path(caminho)
        return p.stat().st_mtime if p.exists() else None

    with conectar(caminho_banco) as conexao:
        # Primeira carga imediata.
        _ingerir_se_existir(conexao, csv_sensores, ingerir_sensores, "Sensores IoT")
        _ingerir_se_existir(conexao, csv_agricola, ingerir_agricolas, "Dados agronomicos")
        mtimes[csv_sensores] = mtime(csv_sensores)
        mtimes[csv_agricola] = mtime(csv_agricola)

        try:
            while True:
                time.sleep(intervalo)
                atual_sensores = mtime(csv_sensores)
                atual_agricola = mtime(csv_agricola)

                if atual_sensores != mtimes.get(csv_sensores):
                    _ingerir_se_existir(conexao, csv_sensores, ingerir_sensores, "Sensores IoT (atualizado)")
                    mtimes[csv_sensores] = atual_sensores

                if atual_agricola != mtimes.get(csv_agricola):
                    _ingerir_se_existir(conexao, csv_agricola, ingerir_agricolas, "Dados agronomicos (atualizado)")
                    mtimes[csv_agricola] = atual_agricola
        except KeyboardInterrupt:
            print("\nObservacao encerrada.")


def main():
    parser = argparse.ArgumentParser(
        description="Banco SQL (SQLite) para os dados IoT e agronomicos da FarmTech."
    )
    parser.add_argument("--banco", default=BANCO_PADRAO, help="Arquivo SQLite. Padrao: farmtech.db")
    parser.add_argument("--csv-sensores", default=CSV_SENSORES_PADRAO, help="CSV de sensores IoT.")
    parser.add_argument("--csv-agricola", default=CSV_AGRICOLA_PADRAO, help="CSV agronomico para ML.")

    sub = parser.add_subparsers(dest="comando", required=True)
    sub.add_parser("ingerir", help="Cria o banco e popula com os CSVs (upsert).")
    sub.add_parser("resumo", help="Mostra um resumo dos dados armazenados.")
    p_obs = sub.add_parser("observar", help="Atualiza o banco automaticamente quando os CSVs mudam.")
    p_obs.add_argument("--intervalo", type=float, default=5.0, help="Segundos entre verificacoes. Padrao: 5")

    args = parser.parse_args()

    if args.comando == "ingerir":
        ingerir_tudo(args.banco, args.csv_sensores, args.csv_agricola)
    elif args.comando == "resumo":
        with conectar(args.banco) as conexao:
            resumo(conexao)
    elif args.comando == "observar":
        observar(args.banco, args.csv_sensores, args.csv_agricola, args.intervalo)


if __name__ == "__main__":
    main()
