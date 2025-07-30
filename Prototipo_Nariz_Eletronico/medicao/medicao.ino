#include <MQUnifiedsensor.h>

#define placa "Arduino UNO"
#define Voltage_Resolution 5.0
#define ADC_Bit_Resolution 10

// Pinos Analógicos dos Sensores
#define pinMQ3 A0
#define pinMQ5 A1
#define pinMQ6 A2
#define pinMQ8 A3

// Valores de R0 para os sensores
// Estes são os valores de R0 obtidos da calibração individual.
#define MQ3_CALIBRATED_R0_MEASURED 467.16
#define MQ5_CALIBRATED_R0_MEASURED 1920.54
#define MQ6_CALIBRATED_R0_MEASURED 3736.11
#define MQ8_CALIBRATED_R0_MEASURED 2038.38

// Valores do Resistor de Carga (RL) para cada módulo MQ.
#define RL_MQ3 10000.0
#define RL_MQ5 10000.0
#define RL_MQ6 10000.0
#define RL_MQ8 10000.0

MQUnifiedsensor MQ3(placa, Voltage_Resolution, ADC_Bit_Resolution, pinMQ3, "MQ-3");
MQUnifiedsensor MQ5(placa, Voltage_Resolution, ADC_Bit_Resolution, pinMQ5, "MQ-5");
MQUnifiedsensor MQ6(placa, Voltage_Resolution, ADC_Bit_Resolution, pinMQ6, "MQ-6");
MQUnifiedsensor MQ8(placa, Voltage_Resolution, ADC_Bit_Resolution, pinMQ8, "MQ-8");

void setup() {
  Serial.begin(9600);

  Serial.println("Inicializando Sensores MQ...");

  // Inicializa cada sensor
  MQ3.init();
  MQ5.init();
  MQ6.init();
  MQ8.init();

  MQ3.setRL(RL_MQ3);
  MQ5.setRL(RL_MQ5);
  MQ6.setRL(RL_MQ6);
  MQ8.setRL(RL_MQ8);

  // --- Define o Método de Regressão
  MQ3.setRegressionMethod(1);
  MQ5.setRegressionMethod(1);
  MQ6.setRegressionMethod(1);
  MQ8.setRegressionMethod(1);

  // Define os Coeficientes A e B para as Curvas de Calibração
  MQ3.setA(0.3934); MQ3.setB(-1.504);
  MQ5.setA(6.8551); MQ5.setB(-2.110);
  MQ6.setA(10.0);   MQ6.setB(-2.222);
  MQ8.setA(1012.7); MQ8.setB(-2.786);

  MQ3.setR0(MQ3_CALIBRATED_R0_MEASURED);
  MQ5.setR0(MQ5_CALIBRATED_R0_MEASURED);
  MQ6.setR0(MQ6_CALIBRATED_R0_MEASURED);
  MQ8.setR0(MQ8_CALIBRATED_R0_MEASURED);

  Serial.println("Sensores MQ Inicializados e Calibrados.");
  Serial.println("Enviando dados de PPM pela Serial...");
}

void loop() {
  // Atualiza as leituras dos sensores
  MQ3.update();
  MQ5.update();
  MQ6.update();
  MQ8.update();

  float mq3_ppm = MQ3.readSensor();
  float mq5_ppm = MQ5.readSensor();
  float mq6_ppm = MQ6.readSensor();
  float mq8_ppm = MQ8.readSensor();

  // Envia os valores para a porta serial separados por vírgula
  Serial.print(mq3_ppm, 2); Serial.print(",");
  Serial.print(mq5_ppm, 2); Serial.print(",");
  Serial.print(mq6_ppm, 2); Serial.print(",");
  Serial.println(mq8_ppm, 2);

  delay(1000); // Aguarda 1 segundo antes da próxima leitura/envio
}