esp8266-projects/temperature-sensor-board/temperature-sensor-board-v3.ino
mqttClient.loop();  // Process MQTT messages

# Guia de Implementação MQTT para Sensor ESP8266

## Visão Geral
Este guia apresenta a arquitetura e o código atual para comunicação MQTT do sensor de temperatura ESP8266, utilizado no sistema Smart City. Toda a comunicação de dados e comandos é feita via MQTT, garantindo integração total e confiável.

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
  "command_type": "TURN_ON",
  "command_value": "",
  "request_id": "req123",
  "timestamp": 1640995200000
}
```

### Resposta (JSON)
```json
{
  "device_id": "temp_sensor_esp_002",
  "request_id": "req123",
  "success": true,
  "message": "Sensor ativado",
  "status": "ACTIVE",
  "frequency_ms": 5000,
  "temperature": 25.3,
  "humidity": 60.2,
  "timestamp": 1640995200000
}
```

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

void sendSensorDataMQTT(float temperature, float humidity) {
  StaticJsonDocument<300> doc;
  doc["device_id"] = device_id;
  doc["temperature"] = temperature;
  doc["humidity"] = humidity;
  doc["status"] = "ACTIVE";
  doc["timestamp"] = millis();
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

## Requisitos de Hardware
- ESP8266 (NodeMCU, Wemos D1 Mini, etc.)
- Sensor DHT11

## Requisitos de Software
- PubSubClient
- ArduinoJson
- DHT sensor library

## Conclusão
Este README apresenta a arquitetura e o código atual para sensores ESP8266 com comunicação MQTT no sistema Smart City. Toda a lógica de comandos, respostas e envio de dados é feita via MQTT, facilitando integração, escalabilidade e confiabilidade.
