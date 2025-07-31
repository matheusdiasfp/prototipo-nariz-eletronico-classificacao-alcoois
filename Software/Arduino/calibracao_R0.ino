#include <MQUnifiedsensor.h>

#define placa "Arduino UNO"
#define Voltage_Resolution 5.0
#define ADC_Bit_Resolution 10

// Valores do Resistor de Carga (RL) para cada módulo MQ.
#define RL_MQ3 10000.0
#define RL_MQ5 10000.0
#define RL_MQ6 10000.0
#define RL_MQ8 10000.0

// Pinos analógicos
#define pinMQ3 A0
#define pinMQ5 A1
#define pinMQ6 A2
#define pinMQ8 A3

// Razões Rs/Ro do ar limpo estimadas
#define RatioMQ3CleanAir_DS 60.0
#define RatioMQ5CleanAir_DS 6.5
#define RatioMQ6CleanAir_DS 10.0
#define RatioMQ8CleanAir_DS 70.0

MQUnifiedsensor MQ3(placa, Voltage_Resolution, ADC_Bit_Resolution, pinMQ3, "MQ-3");
MQUnifiedsensor MQ5(placa, Voltage_Resolution, ADC_Bit_Resolution, pinMQ5, "MQ-5");
MQUnifiedsensor MQ6(placa, Voltage_Resolution, ADC_Bit_Resolution, pinMQ6, "MQ-6");
MQUnifiedsensor MQ8(placa, Voltage_Resolution, ADC_Bit_Resolution, pinMQ8, "MQ-8");

// Função auxiliar para calcular Rs a partir da leitura analógica
float calculateRs(int analogValue, float RL) {
    if (analogValue == 0) return 999999999.0; // Evita divisão por zero, retorna um valor muito alto para Rs
    // Converter leitura analógica para tensão
    float sensorVoltage = analogValue * (Voltage_Resolution / (pow(2, ADC_Bit_Resolution) - 1));
    // Calcular Rs a partir da tensão do sensor e RL
    float Rs = ((Voltage_Resolution / sensorVoltage) - 1) * RL;
    return Rs;
}

void setup() {
  Serial.begin(9600);

  // Inicializa sensores
  MQ3.init(); MQ5.init(); MQ6.init(); MQ8.init();

  MQ3.setRL(RL_MQ3);
  MQ5.setRL(RL_MQ5);
  MQ6.setRL(RL_MQ6);
  MQ8.setRL(RL_MQ8);

  // Método de regressão
  MQ3.setRegressionMethod(1); MQ5.setRegressionMethod(1);
  MQ6.setRegressionMethod(1); MQ8.setRegressionMethod(1);

  // Curvas de calibração baseadas nos datasheets
  MQ3.setA(0.3934); MQ3.setB(-1.504);
  MQ5.setA(6.8551); MQ5.setB(-2.110);
  MQ6.setA(10.0);   MQ6.setB(-2.222);
  MQ8.setA(1012.7); MQ8.setB(-2.786);

  Serial.println("Calculando R0 para seu ambiente... Mantenha em ar limpo e estável.");
  Serial.println("Coletando leituras analógicas para calcular Rs em ar limpo...");
  Serial.println("Aguarde cerca de 30 segundos (60 amostras)...");

  float sumAnalog3 = 0, sumAnalog5 = 0, sumAnalog6 = 0, sumAnalog8 = 0;
  int numSamples = 60; // Número de amostras para média (30 segundos com delay de 500ms)

  for (int i = 0; i < numSamples; i++) {
    sumAnalog3 += analogRead(pinMQ3);
    sumAnalog5 += analogRead(pinMQ5);
    sumAnalog6 += analogRead(pinMQ6);
    sumAnalog8 += analogRead(pinMQ8);
    Serial.print(".");
    delay(500); // Meio segundo entre as amostras
  }
  Serial.println("\nCalculando R0...");

  // Calcula a média das leituras analógicas em ar limpo
  float avgAnalog3 = sumAnalog3 / numSamples;
  float avgAnalog5 = sumAnalog5 / numSamples;
  float avgAnalog6 = sumAnalog6 / numSamples;
  float avgAnalog8 = sumAnalog8 / numSamples;

  // Calcula o Rs médio em ar limpo a partir das médias analógicas
  float avgRsCleanAir_3 = calculateRs(avgAnalog3, RL_MQ3);
  float avgRsCleanAir_5 = calculateRs(avgAnalog5, RL_MQ5);
  float avgRsCleanAir_6 = calculateRs(avgAnalog6, RL_MQ6);
  float avgRsCleanAir_8 = calculateRs(avgAnalog8, RL_MQ8);

  // Calcula R0 usando o Rs médio em ar limpo e o Ratio do datasheet
  float calibratedR0_3 = avgRsCleanAir_3 / RatioMQ3CleanAir_DS;
  float calibratedR0_5 = avgRsCleanAir_5 / RatioMQ5CleanAir_DS;
  float calibratedR0_6 = avgRsCleanAir_6 / RatioMQ6CleanAir_DS;
  float calibratedR0_8 = avgRsCleanAir_8 / RatioMQ8CleanAir_DS;

  // Define os R0s calculados para os sensores na biblioteca
  MQ3.setR0(calibratedR0_3);
  MQ5.setR0(calibratedR0_5);
  MQ6.setR0(calibratedR0_6);
  MQ8.setR0(calibratedR0_8);

  Serial.print("MQ-3 Rs_clean_avg (Ohms): "); Serial.print(avgRsCleanAir_3, 2); Serial.print("\tR0 (Ohms): "); Serial.println(MQ3.getR0(), 2);
  Serial.print("MQ-5 Rs_clean_avg (Ohms): "); Serial.print(avgRsCleanAir_5, 2); Serial.print("\tR0 (Ohms): "); Serial.println(MQ5.getR0(), 2);
  Serial.print("MQ-6 Rs_clean_avg (Ohms): "); Serial.print(avgRsCleanAir_6, 2); Serial.print("\tR0 (Ohms): "); Serial.println(MQ6.getR0(), 2);
  Serial.print("MQ-8 Rs_clean_avg (Ohms): "); Serial.print(avgRsCleanAir_8, 2); Serial.print("\tR0 (Ohms): "); Serial.println(MQ8.getR0(), 2);

  Serial.println("Calibração manual de R0 concluída. Copie os valores de R0 acima para o código final.");
  Serial.println("Agora, as leituras em PPM começarão...");
}

void loop() {
  // Atualiza sensores
  MQ3.update(); MQ5.update(); MQ6.update(); MQ8.update();

  // Lê os valores em ppm
  float mq3_ppm = MQ3.readSensor();
  float mq5_ppm = MQ5.readSensor();
  float mq6_ppm = MQ6.readSensor();
  float mq8_ppm = MQ8.readSensor();

  // Envia apenas os valores dos sensores, separados por vírgula
  Serial.print(mq3_ppm, 2); Serial.print(",");
  Serial.print(mq5_ppm, 2); Serial.print(",");
  Serial.print(mq6_ppm, 2); Serial.print(",");
  Serial.println(mq8_ppm, 2);

  delay(1000);  // 1 leitura por segundo
}