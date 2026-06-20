import argparse
import csv
import sys
from datetime import datetime
from pathlib import Path

import serial


CSV_HEADER = [
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


def abrir_csv(caminho):
    arquivo_existe = caminho.exists() and caminho.stat().st_size > 0
    arquivo = caminho.open("a", newline="", encoding="utf-8")
    escritor = csv.writer(arquivo)

    if not arquivo_existe:
        escritor.writerow(CSV_HEADER)
        arquivo.flush()

    return arquivo, escritor


def linha_sensor_para_registro(linha):
    if not linha.startswith("CSV,"):
        return None

    partes = linha.split(",")
    if len(partes) != 9:
        return None

    return [datetime.now().isoformat(timespec="seconds")] + partes[1:]


def gravar_linhas_csv(linhas, saida):
    caminho_saida = Path(saida)
    arquivo, escritor = abrir_csv(caminho_saida)
    total = 0

    try:
        for linha in linhas:
            registro = linha_sensor_para_registro(linha.strip())
            if registro is None:
                continue

            escritor.writerow(registro)
            total += 1
    finally:
        arquivo.close()

    print(f"Arquivo CSV: {caminho_saida.resolve()}")
    print(f"Registros gravados: {total}")


def coletar(porta, baudrate, saida):
    caminho_saida = Path(saida)
    arquivo, escritor = abrir_csv(caminho_saida)

    print(f"Coletando dados da porta {porta} em {baudrate} bps.")
    print(f"Arquivo CSV: {caminho_saida.resolve()}")
    print("Pressione Ctrl+C para encerrar.")

    try:
        with serial.Serial(porta, baudrate, timeout=1) as conexao:
            while True:
                linha = conexao.readline().decode("utf-8", errors="ignore").strip()
                if not linha:
                    continue

                registro = linha_sensor_para_registro(linha)
                if registro is None:
                    print(linha)
                    continue

                escritor.writerow(registro)
                arquivo.flush()
                print(f"Registrado: {registro}")
    except KeyboardInterrupt:
        print("\nColeta encerrada.")
    finally:
        arquivo.close()


def main():
    parser = argparse.ArgumentParser(
        description="Grava em CSV os dados de sensores enviados pelo ESP32 via Serial."
    )
    parser.add_argument(
        "--porta",
        default=None,
        help="Porta serial do ESP32. Exemplo no Windows: COM3",
    )
    parser.add_argument(
        "--entrada",
        default=None,
        help="Arquivo com texto copiado do Serial Monitor do Wokwi. Use '-' para ler do terminal.",
    )
    parser.add_argument(
        "--baudrate",
        type=int,
        default=115200,
        help="Velocidade da serial. Padrao: 115200",
    )
    parser.add_argument(
        "--saida",
        default="dados_sensores.csv",
        help="Caminho do arquivo CSV de saida. Padrao: dados_sensores.csv",
    )

    args = parser.parse_args()

    if args.entrada:
        if args.entrada == "-":
            print("Cole o texto do Serial Monitor e finalize com Ctrl+Z + Enter no Windows.")
            gravar_linhas_csv(sys.stdin, args.saida)
        else:
            with Path(args.entrada).open(encoding="utf-8") as entrada:
                gravar_linhas_csv(entrada, args.saida)
        return

    if args.porta:
        coletar(args.porta, args.baudrate, args.saida)
        return

    parser.error("informe --porta COMx ou --entrada arquivo.txt")


if __name__ == "__main__":
    main()
