import os
import requests
import time
from pathlib import Path

# --- CONFIGURAÇÕES ---
CIDADE = os.environ.get("OPENWEATHER_CITY", "Sao Paulo")
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


def obter_api_key():
    carregar_env_local()
    return os.environ.get("OPENWEATHER_API_KEY", "").strip()


def consultar_clima():
    api_key = obter_api_key()
    if not api_key:
        print("Configure OPENWEATHER_API_KEY no ambiente ou no arquivo .env.")
        return

    url = (
        "http://api.openweathermap.org/data/2.5/weather"
        f"?q={CIDADE}&appid={api_key}&units=metric&lang=pt_br"
    )

    print(f"\nConsultando clima para: {CIDADE}...")
    try:
        resposta = requests.get(url, timeout=10)
        dados = resposta.json()

        if resposta.status_code == 200:
            temp = dados['main']['temp']
            clima = dados['weather'][0]['description'].upper()
            clima_principal = dados['weather'][0]['main'] # Rain, Clear, Clouds, etc.

            print(f"SUCESSO! | Temperatura: {temp}°C | {clima}")

            # Lógica de Decisão para enviar ao Wokwi
            if clima_principal == "Rain":
                print(">> [ALERTA] Chuva detectada! Digite 'C' no Wokwi.")
            else:
                print(">> [INFO] Sem chuva. Digite 'S' no Wokwi.")
        else:
            print(f"ERRO na API: {dados.get('message', 'Erro desconhecido')}")
            
    except Exception as e:
        print(f"Falha na conexão: {e}")

# Loop de verificação (a cada 30 segundos)
if __name__ == "__main__":
    print("--- FarmTech Solutions: Integrador de Clima ---")
    while True:
        consultar_clima()
        print("\nPróxima verificação em 30 segundos... (Ctrl+C para parar)")
        time.sleep(30)
