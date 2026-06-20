import argparse
import os
import sys
import shutil
import subprocess
from pathlib import Path

from coletar_sensores_csv import gravar_linhas_csv


FIRMWARE = Path(".pio/build/esp32dev/firmware.bin")
ELF = Path(".pio/build/esp32dev/firmware.elf")
ARQUIVO_ENV = Path(".env")


def limpar_valor_env(valor):
    return valor.strip().strip('"').strip("'")


def carregar_env_local(caminho=ARQUIVO_ENV):
    if not caminho.exists():
        return

    for linha in caminho.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue

        nome, valor = linha.split("=", 1)
        nome = nome.strip()
        if nome and nome not in os.environ:
            os.environ[nome] = limpar_valor_env(valor)


def encontrar_wokwi_cli():
    executavel = shutil.which("wokwi-cli")
    if executavel:
        return executavel

    home = Path.home()
    candidatos = [
        home / ".wokwi" / "bin" / "wokwi-cli.exe",
        home / ".wokwi" / "bin" / "wokwi-cli",
    ]

    for candidato in candidatos:
        if candidato.exists():
            return str(candidato)

    return None


def compilar_firmware(forcar):
    if not forcar and FIRMWARE.exists() and ELF.exists():
        return

    print("Compilando firmware com PlatformIO...")
    subprocess.run([sys.executable, "-m", "platformio", "run"], check=True)


def executar_wokwi(timeout, log_serial):
    executavel = encontrar_wokwi_cli()
    if executavel is None:
        raise RuntimeError(
            "wokwi-cli nao encontrado. Instale com: "
            "iwr https://wokwi.com/ci/install.ps1 -useb | iex"
        )

    if not os.environ.get("WOKWI_CLI_TOKEN"):
        raise RuntimeError(
            "Variavel WOKWI_CLI_TOKEN nao configurada. "
            "Crie um token no Wokwi CI Dashboard e configure antes de executar."
        )

    comando = [
        executavel,
        ".",
        "--timeout",
        str(timeout),
        "--timeout-exit-code",
        "0",
        "--serial-log-file",
        str(log_serial),
    ]

    print("Executando simulacao Wokwi CLI...")
    subprocess.run(comando, check=True)


def main():
    parser = argparse.ArgumentParser(
        description="Executa o Wokwi CLI e gera CSV com os dados dos sensores."
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=30000,
        help="Tempo de simulacao em milissegundos. Padrao: 30000",
    )
    parser.add_argument(
        "--log",
        default="serial_wokwi.log",
        help="Arquivo temporario com a saida serial. Padrao: serial_wokwi.log",
    )
    parser.add_argument(
        "--saida",
        default="dados_sensores.csv",
        help="Arquivo CSV final. Padrao: dados_sensores.csv",
    )
    parser.add_argument(
        "--sem-build",
        action="store_true",
        help="Nao compila o firmware antes de executar o Wokwi CLI.",
    )
    parser.add_argument(
        "--sobrescrever",
        action="store_true",
        help="Remove o CSV de saida antes de gravar os novos registros.",
    )

    args = parser.parse_args()
    log_serial = Path(args.log)
    caminho_saida = Path(args.saida)
    carregar_env_local()

    if not args.sem_build:
        compilar_firmware(forcar=True)
    executar_wokwi(args.timeout, log_serial)

    if not log_serial.exists():
        raise RuntimeError(f"Arquivo de log serial nao foi criado: {log_serial}")

    if args.sobrescrever and caminho_saida.exists():
        caminho_saida.unlink()

    with log_serial.open(encoding="utf-8") as linhas:
        gravar_linhas_csv(linhas, caminho_saida)


if __name__ == "__main__":
    main()
