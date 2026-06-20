# Roteiro do Vídeo — FarmTech Solutions (Fase 4)

**Duração-alvo:** até 5 minutos
**Tema:** Previsão Inteligente na Agricultura — pipeline de ML + dashboard Streamlit

> Critérios cobertos (FIAP):
> 1. Pipeline de Machine Learning com tratamento de dados, treinamento e validação do modelo de regressão.
> 2. Demonstração da aplicação Streamlit e suas principais funcionalidades.
> 3. Métricas e previsões obtidas pelo modelo e sua interpretação.

---

## Preparação (antes de gravar)

- [ ] Dashboard rodando: `python -m streamlit run dashboard_farmtech.py` → abrir `http://localhost:8501`.
- [ ] Banco populado: `python banco_dados.py ingerir` (gera `farmtech.db`).
- [ ] Terminal aberto e visível para mostrar o pipeline pela linha de comando.
- [ ] Editor (VS Code) com os arquivos `gerar_dataset_ml.py`, `modelo_ml.py` e `banco_dados.py` já abertos em abas.
- [ ] Fechar notificações, deixar a tela limpa, áudio testado.
- [ ] Cronômetro à vista para não passar de 5 min.

---

## Estrutura por blocos (com tempos)

### Bloco 0 — Abertura (0:00 – 0:25) · ~25s

**Tela:** rosto/câmera ou slide com o nome do projeto.

**Fala (sugestão):**
> "Olá! Sou [seu nome], do grupo FarmTech Solutions. Nesta Fase 4 aplicamos Inteligência
> Artificial sobre os dados agrícolas das fases anteriores. Vou mostrar três coisas:
> o pipeline de Machine Learning com tratamento, treino e validação; o dashboard em
> Streamlit; e as métricas, previsões e como interpretá-las."

**Dica:** seja direto — esse bloco é só para situar o avaliador.

---

### Bloco 1 — Pipeline de Machine Learning (0:25 – 2:00) · ~95s

> Critério 1: tratamento de dados + treinamento + validação.

**1.1 — Origem e tratamento dos dados (0:25 – 1:00)**

**Tela:** editor mostrando `gerar_dataset_ml.py` e o CSV `dados_agricolas.csv`.

**Fala:**
> "Os sensores do ESP32 registram o estado instantâneo, sem variância suficiente para treinar
> um modelo. Por isso geramos um dataset agronômico realista com `gerar_dataset_ml.py`: variáveis
> de clima e solo (temperatura, umidade do ar, NPK, precipitação, radiação) geram umidade do solo,
> pH, volume de irrigação e rendimento por relações físicas plausíveis somadas a ruído controlado.
> No tratamento, os valores são limitados a faixas físicas com `clip` e convertidos para numéricos."

**Mostrar (opcional, terminal):**
```bash
python gerar_dataset_ml.py --amostras 500
```

**1.2 — Bibliotecas e pipeline (1:00 – 1:30)**

**Tela:** `modelo_ml.py`, destacar `construir_pipeline` e os imports.

**Fala:**
> "Usamos **Scikit-Learn, Pandas e NumPy**. O pipeline encadeia `StandardScaler` para padronizar
> as variáveis e o modelo de regressão. Suportamos três regressões: **linear múltipla**,
> **polinomial de grau 2** e **Random Forest**, que é não linear. A divisão é treino/teste
> com `train_test_split` (75/25)."

**1.3 — Treino e validação (1:30 – 2:00)**

**Tela:** terminal.

**Fala:**
> "Treinamos e validamos pela linha de comando. Além das métricas no conjunto de teste, fazemos
> **validação cruzada com 5 folds** para confirmar a estabilidade do modelo."

**Mostrar (terminal):**
```bash
python modelo_ml.py --alvo rendimento --modelo random_forest
```
> Apontar na saída: MAE, MSE, RMSE, R², R² médio da validação cruzada e a importância das variáveis.

---

### Bloco 2 — Dashboard Streamlit e funcionalidades (2:00 – 3:40) · ~100s

> Critério 2: demonstração da aplicação e principais funcionalidades.

**Tela:** navegador em `http://localhost:8501`. Percorrer as abas.

**2.1 — Monitoramento IoT (2:00 – 2:20)**
> "A primeira aba mostra os dados dos sensores: umidade, pH, nutrientes, status da bomba, e
> sugestões de irrigação que cruzam o CSV com o clima atual via API OpenWeather."

**2.2 — Banco de Dados (2:20 – 2:40)**
> "Aqui está a integração sensores → banco → IA. Os dados IoT e o dataset agronômico são
> ingeridos num banco SQL (SQLite) com upsert, sem duplicar. Há também um modo de atualização
> automática que re-ingere quando o CSV muda."
> *(Clicar em "Ingerir/atualizar dados no banco" e mostrar as tabelas.)*

**2.3 — Machine Learning (2:40 – 3:05)**
> "Esta aba executa o pipeline e mostra as métricas, o gráfico de previsto vs real, os resíduos
> e a importância das variáveis. Na barra lateral troco a variável-alvo e o modelo de regressão."
> *(Trocar o modelo no selectbox para mostrar a reatividade.)*

**2.4 — Correlação e Tendências (3:05 – 3:20)**
> "Matriz de correlação entre as variáveis e a tendência de produtividade com média móvel."

**2.5 — Previsão Interativa (3:20 – 3:40)**
> "Por fim, os sliders simulam condições do campo e o modelo prevê em tempo real: rendimento,
> volume de irrigação e pH — e gera recomendações de manejo, incluindo a necessidade de
> fertilização de N, P e K com base nas faixas adequadas do solo."

---

### Bloco 3 — Métricas, previsões e interpretação (3:40 – 4:35) · ~55s

> Critério 3: métricas e previsões obtidas + interpretação.

**Tela:** aba Machine Learning + aba Previsão Interativa.

**Fala:**
> "Interpretando os resultados: o **R²** mostra quanto da variação do rendimento o modelo explica;
> quanto mais perto de 1, melhor. O **MAE** é o erro médio na mesma unidade do alvo, em ton/ha;
> **RMSE** penaliza mais os erros grandes. No gráfico de previsto vs real, quanto mais os pontos
> se alinham à diagonal, melhores as previsões; os resíduos espalhados em torno do zero indicam
> que não há viés sistemático.
>
> Na importância das variáveis, **pH e nitrogênio** aparecem como os fatores mais influentes no
> rendimento — coerente com a agronomia. Na previsão interativa, ao baixar o pH para fora da faixa
> 6,0–6,5 ou reduzir o nitrogênio, o rendimento previsto cai e o sistema sugere correção do solo
> e fertilização. É isso que transforma dado em decisão de manejo."

**Dica:** faça **uma** simulação ao vivo movendo um slider (ex.: pH ou nitrogênio) e mostre o número e a recomendação mudando.

---

### Bloco 4 — Encerramento (4:35 – 5:00) · ~25s

**Fala:**
> "Em resumo: integramos sensores IoT, banco de dados SQL e modelos de regressão num dashboard
> que entrega previsões e recomendações práticas ao gestor agrícola — o início da agricultura
> cognitiva. Obrigado!"

*(Mostrar rapidamente o README/links do projeto e os integrantes do grupo, se houver tempo.)*

---

## Checklist final de gravação

- [ ] Mostrei tratamento de dados (geração + clip/conversão).
- [ ] Mostrei o pipeline (StandardScaler + regressão) e os 3 modelos.
- [ ] Mostrei treino + validação cruzada no terminal.
- [ ] Demonstrei as 5 abas do Streamlit.
- [ ] Expliquei MAE, MSE, RMSE e R² e os interpretei.
- [ ] Fiz ao menos 1 previsão interativa ao vivo com recomendação.
- [ ] Vídeo ficou em ≤ 5 minutos.
- [ ] Áudio e tela legíveis.

## Comandos de apoio (copiar/colar)

```bash
# 1. Gerar dataset (tratamento de dados)
python gerar_dataset_ml.py --amostras 500

# 2. Popular o banco SQL
python banco_dados.py ingerir

# 3. Treinar e validar (mostrar métricas)
python modelo_ml.py --alvo rendimento --modelo random_forest
python modelo_ml.py --alvo volume_irrigacao --modelo linear

# 4. Subir o dashboard
python -m streamlit run dashboard_farmtech.py
```
