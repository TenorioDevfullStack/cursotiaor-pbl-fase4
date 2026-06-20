#include "DHT.h"

// --- 1. CONFIGURAÇÃO DE HARDWARE ---
#define DHTPIN 15
#define DHTTYPE DHT22
#define LDR_PIN 34
#define PIN_N 12
#define PIN_P 13
#define PIN_K 14
#define RELE_PIN 2

DHT dht(DHTPIN, DHTTYPE);

// --- 2. VARIÁVEIS DE CONTROLE ---
bool chuvaPrevista = false;
const float UMIDADE_MINIMA = 60.0;
const float PH_MIN = 6.0;
const float PH_MAX = 6.5;

void setup() {
  Serial.begin(115200);
  dht.begin();
  
  // Configura botões com Pull-up interno
  pinMode(PIN_N, INPUT_PULLUP);
  pinMode(PIN_P, INPUT_PULLUP);
  pinMode(PIN_K, INPUT_PULLUP);
  
  pinMode(RELE_PIN, OUTPUT);
  
  Serial.println("--- FarmTech Solutions: Sistema C++ Iniciado ---");
  Serial.println("Comandos Serial: 'C' para Chuva, 'S' para Sol");
  Serial.println("CSV_HEADER,timestamp_ms,umidade,ph,n_ok,p_ok,k_ok,chuva_prevista,bomba");
}

void loop() {
  // A. Verificar Entrada Serial (Integração Python API)
  if (Serial.available() > 0) {
    char comando = Serial.read();
    if (comando == 'C' || comando == 'c') {
      chuvaPrevista = true;
      Serial.println("\n>> ALERTA API: Chuva detectada. Irrigacao suspensa.");
    } else if (comando == 'S' || comando == 's') {
      chuvaPrevista = false;
      Serial.println("\n>> INFO API: Sem previsao de chuva. Operacao normal.");
    }
  }

  // B. Leitura dos Sensores
  float umid = dht.readHumidity();
  
  int leituraLDR = analogRead(LDR_PIN);
  // Mapeia 0-4095 para pH 0.0-14.0
  float ph = (leituraLDR / 4095.0) * 14.0;
  
  // Botões (LOW = Pressionado/Nutriente OK)
  bool n_ok = digitalRead(PIN_N) == LOW;
  bool p_ok = digitalRead(PIN_P) == LOW;
  bool k_ok = digitalRead(PIN_K) == LOW;

  // C. Lógica de Decisão
  bool soloSeco = umid < UMIDADE_MINIMA;
  bool phRuim = (ph < PH_MIN || ph > PH_MAX);
  bool faltaNutriente = (!n_ok || !p_ok || !k_ok);

  // Aciona se houver erro E não for chover
  if ((soloSeco || phRuim || faltaNutriente) && !chuvaPrevista) {
    digitalWrite(RELE_PIN, HIGH);
    imprimirStatus(umid, ph, n_ok, p_ok, k_ok, "LIGADA");
    imprimirCsv(umid, ph, n_ok, p_ok, k_ok, "LIGADA");
  } else {
    digitalWrite(RELE_PIN, LOW);
    imprimirStatus(umid, ph, n_ok, p_ok, k_ok, "DESLIGADA");
    imprimirCsv(umid, ph, n_ok, p_ok, k_ok, "DESLIGADA");
  }

  delay(2000); // Aguarda 2 segundos para próxima leitura
}

// Função auxiliar para limpar o Monitor Serial
void imprimirStatus(float u, float p, bool n, bool phos, bool k, String st) {
  Serial.print("Umid: "); Serial.print(u); Serial.print("% | ");
  Serial.print("pH: "); Serial.print(p, 1); Serial.print(" | ");
  Serial.print("NPK: "); Serial.print(n); Serial.print(phos); Serial.print(k);
  Serial.print(" | Chuva: "); Serial.print(chuvaPrevista ? "SIM" : "NAO");
  Serial.print(" | BOMBA: "); Serial.println(st);
}

// Linha estruturada para o script Python gravar em CSV
void imprimirCsv(float u, float p, bool n, bool phos, bool k, String st) {
  Serial.print("CSV,");
  Serial.print(millis()); Serial.print(",");
  Serial.print(u); Serial.print(",");
  Serial.print(p, 1); Serial.print(",");
  Serial.print(n ? 1 : 0); Serial.print(",");
  Serial.print(phos ? 1 : 0); Serial.print(",");
  Serial.print(k ? 1 : 0); Serial.print(",");
  Serial.print(chuvaPrevista ? 1 : 0); Serial.print(",");
  Serial.println(st);
}
