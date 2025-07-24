esp8266-projects/temperature-sensor-board/temperature-sensor-board-v3.ino
mqttClient.loop();  // Process MQTT messages

# Guia de Implementação MQTT para Sensor ESP8266

## Visão Geral
Este guia apresenta a arquitetura e o código real do sensor de temperatura ESP8266 para o sistema Smart City. Toda a comunicação de dados, comandos e respostas é feita via MQTT, conforme o firmware atual.

## Arquitetura
- **Dados:** Sensor ESP8266 → MQTT → Gateway
- **Comandos:** Gateway → MQTT → Sensor ESP8266
- **Descoberta:** UDP multicast para encontrar o gateway
- **Registro:** TCP para compatibilidade, mas comandos e dados são 100% MQTT

## Bibliotecas Necessárias
```cpp
#include <ESP8266WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <DHT.h>
```

## Estrutura dos Tópicos MQTT
```cpp
String dataTopic = "smart_city/sensors/temp_sensor_esp_002";
String commandTopic = "smart_city/commands/sensors/temp_sensor_esp_002";
String responseTopic = "smart_city/commands/sensors/temp_sensor_esp_002/response";
```

## Formato das Mensagens

### Comando (JSON)
```json
{
  "command_type": "TURN_ACTIVE", // ou TURN_ACTIVE, TURN_OFF, TURN_IDLE, SET_FREQ, GET_STATUS
  "command_value": "",        // valor do comando, ex: frequência em ms para SET_FREQ
  "request_id": "req123",
  "timestamp": 1640995200000
}
```

### Exemplos de Comandos e Respostas

#### Comando TURN_IDLE
```json
{
  "command_type": "TURN_IDLE",
  "command_value": "",
  "request_id": "req456",
  "timestamp": 1640995201000
}
```
#### Resposta TURN_IDLE
```json
{
  "device_id": "temp_sensor_esp_002",
  "request_id": "req456",
  "success": true,
  "message": "Sensor em modo idle",
  "status": "IDLE",
  "temperature": 25.3,
  "humidity": 60.2,
  "timestamp": 1640995201000
}
```

#### Comando SET_FREQ
```json
{
  "command_type": "SET_FREQ",
  "command_value": "10000",
  "request_id": "req789",
  "timestamp": 1640995202000
}
```
#### Resposta SET_FREQ
```json
{
  "device_id": "temp_sensor_esp_002",
  "request_id": "req789",
  "success": true,
  "message": "Frequência alterada para 10000ms",
  "status": "ACTIVE",
  "frequency_ms": 10000,
  "timestamp": 1640995202000
}
```

#### Comando TURN_ON
```json
{
  "command_type": "TURN_ON",
  "command_value": "",
  "request_id": "req123",
  "timestamp": 1640995200000
}
```
#### Resposta TURN_ON
```json
{
  "device_id": "temp_sensor_esp_002",
  "request_id": "req123",
  "success": true,
  "message": "Sensor ativado",
  "status": "ACTIVE",
  "temperature": 25.3,
  "humidity": 60.2,
  "timestamp": 1640995200000
}
```
```json
{
  "device_id": "temp_sensor_esp_002",
  "request_id": "req456",
  "success": true,
  "message": "Sensor em modo idle",
  "status": "IDLE",
  "temperature": 25.3,
  "humidity": 60.2,
  "timestamp": 1640995201000
}
```

### Exemplo 2: Comando SET_FREQ
```json
{
  "command_type": "SET_FREQ",
  "command_value": "10000",
  "request_id": "req789",
  "timestamp": 1640995202000
}
```

### Resposta para SET_FREQ
```json
{
  "device_id": "temp_sensor_esp_002",
  "request_id": "req789",
  "success": true,
  "message": "Frequência alterada para 10000ms",
  "status": "ACTIVE",
  "frequency_ms": 10000,
  "timestamp": 1640995202000
}
```
// ...outros exemplos acima...

## Exemplo de Código Principal
```cpp
#include <ESP8266WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <DHT.h>

const char* ssid = "SEU_WIFI";
const char* password = "SUA_SENHA";
const char* mqtt_server = "192.168.3.129";
const int mqtt_port = 1883;
const char* device_id = "temp_sensor_esp_002";

WiFiClient wifiClient;
PubSubClient mqttClient(wifiClient);

String dataTopic = "smart_city/sensors/temp_sensor_esp_002";
String commandTopic = "smart_city/commands/sensors/temp_sensor_esp_002";
String responseTopic = "smart_city/commands/sensors/temp_sensor_esp_002/response";

void setup() {
  Serial.begin(115200);
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  mqttClient.setServer(mqtt_server, mqtt_port);
  mqttClient.setCallback(onMqttMessage);
  connectToMQTT();
}

void connectToMQTT() {
  while (!mqttClient.connected()) {
    if (mqttClient.connect(device_id)) {
      mqttClient.subscribe(commandTopic.c_str());
    } else {
      delay(5000);
    }
  }
}

void onMqttMessage(char* topic, byte* payload, unsigned int length) {
  String message = "";
  for (int i = 0; i < length; i++) {
    message += (char)payload[i];
  }
  if (String(topic) == commandTopic) {
    processCommand(message);
  }
}

void processCommand(String jsonMessage) {
  StaticJsonDocument<200> doc;
  DeserializationError error = deserializeJson(doc, jsonMessage);
  if (error) return;
  String commandType = doc["command_type"].as<String>();
  // ...processa comandos e envia resposta...
}

void sendSensorDataMQTT() {
  StaticJsonDocument<300> doc;
  doc["device_id"] = device_id;
  doc["temperature"] = lastTemperature;
  doc["humidity"] = lastHumidity;
  doc["status"] = getStatusString();
  doc["timestamp"] = millis();
  doc["version"] = isUsingSimulatedData ? "mqtt_test" : "mqtt_real";
  doc["data_source"] = isUsingSimulatedData ? "simulated" : "dht11";
  String jsonString;
  serializeJson(doc, jsonString);
  mqttClient.publish(dataTopic.c_str(), jsonString.c_str());
}
```

## Testes
- Use o `mosquitto_pub` para enviar comandos MQTT ao sensor
- Use o `mosquitto_sub` para monitorar dados e respostas

## Vantagens da Solução
- Comunicação unificada e confiável
- Reconexão automática ao MQTT
- Formato JSON fácil de integrar
- Suporte a múltiplos sensores
- Tópicos e comandos padronizados
- Respostas detalhadas para cada comando

## Requisitos de Hardware
- ESP8266 (NodeMCU, Wemos D1 Mini, etc.)
- Sensor DHT11

## Requisitos de Software
- PubSubClient
- ArduinoJson
- DHT sensor library

## Conclusão
Este README apresenta a arquitetura e o código real do sensor ESP8266 com comunicação MQTT no sistema Smart City. Os tópicos, comandos e formatos de mensagem refletem exatamente o funcionamento do firmware atual, garantindo integração, escalabilidade e confiabilidade.
