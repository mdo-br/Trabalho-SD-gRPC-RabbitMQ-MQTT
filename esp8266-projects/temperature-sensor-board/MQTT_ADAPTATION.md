/*
 * ESP8266 Temperature Sensor Board V2 - MQTT Version
 * 
 * Versão adaptada para o Trabalho 2 que:
 * - Mantém descoberta multicast UDP
 * - Mantém registro TCP no gateway
 * - MUDA: Envia dados via MQTT ao invés de UDP
 * - Mantém recebimento de comandos TCP
 * 
 * Configurações necessárias:
 * - Instalar biblioteca PubSubClient para MQTT
 * - Configurar broker MQTT (RabbitMQ)
 * - Ajustar tópicos MQTT
 */

// Adicionar ao início do arquivo temperature-sensor-board.ino:

#include <PubSubClient.h>

// --- Configurações MQTT ---
const char* mqtt_server = "192.168.3.129";  // IP do servidor RabbitMQ
const int mqtt_port = 1883;                 // Porta MQTT
const char* mqtt_topic = "smart_city/sensors/temp_board_001001001";  // Tópico específico

// --- Objetos MQTT ---
WiFiClient espClient;
PubSubClient mqttClient(espClient);

// --- Funções MQTT ---
void setupMQTT() {
  mqttClient.setServer(mqtt_server, mqtt_port);
  Serial.println("MQTT configurado");
}

void connectMQTT() {
  while (!mqttClient.connected()) {
    Serial.println("Conectando ao MQTT...");
    String clientId = "ESP8266_" + String(WiFi.macAddress());
    
    if (mqttClient.connect(clientId.c_str())) {
      Serial.println("MQTT conectado");
    } else {
      Serial.print("Falha MQTT, rc=");
      Serial.print(mqttClient.state());
      Serial.println(" tentando novamente em 5 segundos");
      delay(5000);
    }
  }
}

void publishSensorData() {
  if (!mqttClient.connected()) {
    connectMQTT();
  }
  
  // Criar JSON com dados do sensor
  String jsonData = "{";
  jsonData += "\"device_id\":\"" + deviceID + "\",";
  jsonData += "\"temperature\":" + String(temperature) + ",";
  jsonData += "\"humidity\":" + String(humidity) + ",";
  jsonData += "\"status\":\"" + (sensorActive ? "ACTIVE" : "IDLE") + "\",";
  jsonData += "\"timestamp\":" + String(millis()) + ",";
  jsonData += "\"frequency_ms\":" + String(sensorInterval);
  jsonData += "}";
  
  // Publicar no tópico MQTT
  if (mqttClient.publish(mqtt_topic, jsonData.c_str())) {
    Serial.println("Dados MQTT publicados: " + jsonData);
  } else {
    Serial.println("Erro ao publicar MQTT");
  }
  
  mqttClient.loop();
}

// --- Modificações no setup() ---
void setup() {
  // ... código existente ...
  
  // Adicionar após WiFi.begin():
  setupMQTT();
  connectMQTT();
  
  // ... resto do código ...
}

// --- Modificações no loop() ---
void loop() {
  // Manter MQTT conectado
  if (!mqttClient.connected()) {
    connectMQTT();
  }
  mqttClient.loop();
  
  // ... resto do código existente ...
  
  // SUBSTITUIR sendSensorDataUDP() por publishSensorData()
  if (sensorActive && (millis() - lastSensorRead >= sensorInterval)) {
    readSensorData();
    publishSensorData();  // ← MUDANÇA PRINCIPAL
    lastSensorRead = millis();
  }
  
  // ... resto do código ...
}

/*
 * RESUMO DAS MUDANÇAS NECESSÁRIAS:
 * 
 * 1. Adicionar biblioteca PubSubClient
 * 2. Configurar servidor MQTT
 * 3. Substituir envio UDP por publish MQTT
 * 4. Manter descoberta multicast
 * 5. Manter registro TCP
 * 6. Manter comandos TCP
 * 
 * BIBLIOTECAS NECESSÁRIAS (platformio.ini):
 * lib_deps = 
 *   DHT sensor library
 *   PubSubClient
 */
