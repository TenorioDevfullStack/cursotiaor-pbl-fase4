# FarmTech Solutions - Documentacao do Projeto

## Links

- Video demonstrativo: https://youtu.be/mPI2g-Q3YFI
- Repositorio GitHub: https://github.com/TenorioDevfullStack/meugit-cursotiaor-pbl-fase3-pastas

## Visao geral

O projeto FarmTech Solutions implementa um sistema de monitoramento e controle de fertirrigacao usando ESP32, sensores simulados no Wokwi, integracao com clima, armazenamento em CSV, importacao para Oracle e dashboard Streamlit.

A solucao acompanha:

- umidade do solo;
- pH;
- nutrientes N, P e K;
- previsao ou deteccao de chuva;
- status da bomba de irrigacao;
- sugestoes de irrigacao baseadas no clima e nas leituras dos sensores.

## Arquitetura

1. ESP32 no Wokwi faz a leitura dos sensores e controla o rele da bomba.
2. O firmware envia linhas estruturadas no formato `CSV,...` pela Serial.
3. Scripts Python capturam a saida serial e geram `dados_sensores.csv`.
4. O CSV pode ser importado para Oracle.
5. A dashboard Streamlit consome o CSV e a API OpenWeather para visualizacao e sugestoes.

## Componentes principais

- `src/sketch.ino`: firmware do ESP32.
- `coletar_sensores_csv.py`: coleta dados da Serial ou de um arquivo de log e grava CSV.
- `gerar_csv_wokwi_cli.py`: executa o Wokwi CLI e gera CSV automaticamente.
- `importar_csv_oracle.py`: importa o CSV para uma tabela Oracle.
- `dashboard_farmtech.py`: dashboard Streamlit com monitoramento IoT e Machine Learning.
- `gerar_dataset_ml.py`: gera o dataset agricola sintetico (`dados_agricolas.csv`).
- `modelo_ml.py`: pipeline Scikit-Learn de regressao (treino, avaliacao, previsao, manejo).
- `dados_sensores_wokwi.csv`: exemplo de CSV gerado a partir da simulacao.

## Fluxo de dados

O ESP32 imprime linhas no formato:

```csv
CSV,timestamp_ms,umidade,ph,n_ok,p_ok,k_ok,chuva_prevista,bomba
```

O script Python converte essas linhas para o arquivo:

```csv
data_hora,timestamp_ms,umidade,ph,n_ok,p_ok,k_ok,chuva_prevista,bomba
```

## Banco de dados Oracle

A tabela usada para armazenar os dados dos sensores possui os campos de data/hora, timestamp, umidade, pH, nutrientes, chuva prevista e status da bomba.

Print do banco de dados:

![Print do banco Oracle - tabela SENSORES](print-BD/bd-oracle.png)

## Machine Learning (Scikit-Learn)

A Fase 4 acrescenta um pipeline de aprendizado supervisionado de regressao.

Etapas do pipeline (`modelo_ml.py`):

1. Carregamento do dataset agricola (`dados_agricolas.csv`).
2. Divisao em treino e teste (`train_test_split`, 75% / 25%).
3. Pre-processamento com `StandardScaler` (e `PolynomialFeatures` no modelo polinomial).
4. Treinamento do modelo de regressao escolhido.
5. Avaliacao com as metricas **MAE, MSE, RMSE e R2** no conjunto de teste.
6. Validacao cruzada com 5 folds (R2) para medir estabilidade.
7. Importancia das variaveis (coeficientes ou `feature_importances_`).
8. Previsao e geracao de recomendacoes de manejo.

Modelos suportados: Regressao Linear Multipla, Regressao Polinomial (grau 2) e
Random Forest (nao linear).

Variaveis-alvo: rendimento esperado, volume de irrigacao, umidade do solo e pH.

O dataset e gerado por `gerar_dataset_ml.py`, que cria relacoes fisicas plausiveis entre
clima, solo, nutrientes e as variaveis-alvo, somadas a ruido aleatorio controlado, fornecendo
a variabilidade necessaria para treinar os modelos.

Execucao por linha de comando:

```bash
python gerar_dataset_ml.py --amostras 500
python modelo_ml.py --alvo rendimento --modelo random_forest
```

## Dashboard

A dashboard foi criada com Streamlit e organiza a solucao em quatro abas:

- **Monitoramento IoT:** cards com umidade, pH, fosforo, potassio e status da irrigacao;
  graficos historicos de umidade e pH; grafico de bomba ligada e chuva prevista; status dos
  nutrientes; sugestoes de irrigacao com base na OpenWeather ou na coluna `chuva_prevista`.
- **Machine Learning:** metricas MAE, MSE, RMSE e R2; validacao cruzada; grafico previsto vs
  real; residuos; importancia das variaveis.
- **Correlacao e Tendencias:** matriz de correlacao e tendencia de produtividade com media movel.
- **Previsao Interativa:** sliders das condicoes do campo geram previsoes em tempo real e
  recomendacoes de manejo.

Execucao:

```bash
streamlit run dashboard_farmtech.py
```

## Integracao com OpenWeather

A chave da API nao e exibida no front-end. Ela deve ser configurada localmente por uma das opcoes:

```powershell
$env:OPENWEATHER_API_KEY="sua_chave_openweather"
```

Ou no arquivo `.env`:

```env
OPENWEATHER_API_KEY=sua_chave_openweather
```

O arquivo `.env` esta no `.gitignore` para evitar envio de informacoes sensiveis ao GitHub.

## Geracao do CSV pelo Wokwi CLI

Para rodar a simulacao automaticamente pelo Wokwi CLI, configure:

```env
WOKWI_CLI_TOKEN=seu_token_wokwi
```

Depois execute:

```bash
python gerar_csv_wokwi_cli.py --sobrescrever
```

Esse comando compila o firmware, executa a simulacao, salva `serial_wokwi.log` e gera `dados_sensores.csv`.

## Importacao para Oracle

Configure as credenciais do Oracle por variaveis de ambiente:

```powershell
$env:ORACLE_USER="seu_usuario"
$env:ORACLE_PASSWORD="sua_senha"
$env:ORACLE_DSN="host:1521/service_name"
```

Depois execute:

```bash
python importar_csv_oracle.py
```

## Evidencias

- Print Oracle: `print-BD/bd-oracle.png`
- Video demonstrativo: https://youtu.be/mPI2g-Q3YFI
- Repositorio GitHub: https://github.com/TenorioDevfullStack/meugit-cursotiaor-pbl-fase3-pastas
