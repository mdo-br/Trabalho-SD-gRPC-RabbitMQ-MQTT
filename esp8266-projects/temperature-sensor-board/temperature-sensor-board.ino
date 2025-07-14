/*
 * ESP8266 Temperature Sensor Board - MQTT Full Support
 * 
 * Este código implementa uma placa ESP8266 que funciona como sensor de temperatura
 * e umidade no sistema Smart City, com suporte completo a MQTT para dados e comandos.
 * 
 * Funcionalidades:
 * - Descoberta automática do gateway via multicast UDP (mantido)
 * - Registro no gateway via TCP (mantido para compatibilidade)
 * - Leitura de temperatura e umidade do sensor DHT11
 * - Envio de dados via MQTT
 * - Recebimento de comandos via MQTT
 * - Envio de respostas via MQTT
 * - Detecção de mudanças nos valores para otimizar transmissão
 * 
 * Protocolos:
 * - Protocol Buffers para descoberta e registro (mantido)
 * - MQTT para dados, comandos e respostas
 * - TCP para registro inicial (mantido)
 * - UDP para descoberta multicast (mantido)
 * 
 * Hardware:
 * - ESP8266 (NodeMCU, Wemos D1 Mini, etc.)
 * - Sensor DHT11 conectado ao pino D3
 * - Biblioteca DHT para leitura do sensor
 * - Biblioteca PubSubClient para MQTT
 * - Biblioteca ArduinoJson para parsing JSON
 */

#include <ESP8266WiFi.h>
#include <WiFiUdp.h>
#include <WiFiServer.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include "pb_encode.h"
#include "pb_decode.h"
#include "smart_city.pb.h"
#include "pb.h"
#include <WiFiClient.h>
#include <DHT.h>

// --- Configurações do Sensor DHT11 ---
#define DHTTYPE DHT11                // Tipo do sensor (DHT11 ou DHT22)
#define DHTPIN D3                    // Pino digital conectado ao sensor
DHT dht(DHTPIN, DHTTYPE);            // Objeto do sensor DHT

// --- Configurações de Rede WiFi ---
const char* ssid = "ATLab";           // Nome da rede WiFi - CONFIGURAR
const char* password = "@TLab#0506";   // Senha da rede WiFi - CONFIGURAR

// --- Configurações MQTT ---
const char* mqtt_server = "192.168.3.129";  // Endereço do broker MQTT
const int mqtt_port = 1883;                 // Porta do broker MQTT
const char* device_id = "temp_sensor_esp_001";  // ID único do dispositivo

// --- Configurações de Rede do Sistema ---
const char* multicastIP = "224.1.1.1";  // Endereço multicast para descoberta
const int multicastPort = 5007;         // Porta multicast
const int gatewayUDPPort = 12346;       // Porta UDP do gateway
const int localUDPPort = 8890;          // Porta UDP local
const int localTCPPort = 6001;          // Porta TCP local para registro

// --- Tópicos MQTT ---
String dataTopic = "smart_city/sensors/" + String(device_id);
String commandTopic = "smart_city/commands/sensors/" + String(device_id);
String responseTopic = "smart_city/commands/sensors/" + String(device_id) + "/response";

// --- Variáveis de Estado ---
smartcity_devices_DeviceStatus currentStatus = smartcity_devices_DeviceStatus_IDLE;
unsigned long captureIntervalMs = 5000;  // Intervalo de captura padrão: 5 segundos
float lastTemperature = 0.0;
float lastHumidity = 0.0;
unsigned long lastSensorReading = 0;
unsigned long lastDataSent = 0;
bool gatewayFound = false;
String gatewayIP = "";
int gatewayTCPPort = 0;

// --- Objetos de Rede ---
WiFiUDP multicastUdp;
WiFiClient wifiClient;
PubSubClient mqttClient(wifiClient);

// --- Declarações de Funções ---
void connectToWiFi();
void connectToMQTT();
void onMqttMessage(char* topic, byte* payload, unsigned int length);
void processCommand(String jsonMessage);
void sendCommandResponse(String requestId, bool success, String message);
void discoverGateway();
void registerWithGateway();
void sendSensorDataMQTT();
void readSensorData();
String getStatusString();
String getLocalIP();
bool encode_ip_address(pb_ostream_t *stream, const pb_field_t *field, void * const *arg);
bool decode_string(pb_istream_t *stream, const pb_field_t *field, void **arg);

// --- Função de Inicialização ---
void setup() {
  // Inicializa comunicação serial para debug
  Serial.begin(115200);
  Serial.println("\n=== Temperature Sensor Board ESP8266 (MQTT) ===");
  Serial.print("Device ID: ");
  Serial.println(device_id);
  Serial.print("Data Topic: ");
  Serial.println(dataTopic);
  Serial.print("Command Topic: ");
  Serial.println(commandTopic);
  Serial.print("Response Topic: ");
  Serial.println(responseTopic);
  
  // Conecta ao WiFi
  connectToWiFi();
  
  // Inicializa o sensor DHT11
  dht.begin();
  
  // Configura cliente MQTT
  mqttClient.setServer(mqtt_server, mqtt_port);
  mqttClient.setCallback(onMqttMessage);
  
  // Conecta ao MQTT
  connectToMQTT();
  
  // Inicializa descoberta multicast
  multicastUdp.beginMulticast(WiFi.localIP(), IPAddress(224,1,1,1), multicastPort);
  
  Serial.println("Aguardando descoberta do gateway via multicast...");
  
  // Configurar status inicial
  currentStatus = smartcity_devices_DeviceStatus_IDLE;
  
  Serial.println("Sensor ESP8266 inicializado com sucesso!");
}

// --- Loop Principal ---
void loop() {
  // Manter conexão MQTT
  if (!mqttClient.connected()) {
    connectToMQTT();
  }
  mqttClient.loop();
  
  // Descobrir gateway se ainda não encontrado
  if (!gatewayFound) {
    discoverGateway();
  }
  
  // Ler dados do sensor periodicamente
  if (millis() - lastSensorReading >= 2000) {  // Lê sensor a cada 2 segundos
    readSensorData();
    lastSensorReading = millis();
  }
  
  // Enviar dados via MQTT se estiver ativo
  if (currentStatus == smartcity_devices_DeviceStatus_ACTIVE) {
    if (millis() - lastDataSent >= captureIntervalMs) {
      sendSensorDataMQTT();
      lastDataSent = millis();
    }
  }
  
  delay(100);  // Pequeno delay para não sobrecarregar o loop
}

// --- Implementação das Funções ---

void connectToWiFi() {
  Serial.print("Conectando ao WiFi ");
  Serial.print(ssid);
  WiFi.begin(ssid, password);
  
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  
  Serial.println();
  Serial.println("WiFi conectado!");
  Serial.print("Endereço IP: ");
  Serial.println(WiFi.localIP());
}

void connectToMQTT() {
  while (!mqttClient.connected()) {
    Serial.print("Tentando conexão MQTT...");
    
    if (mqttClient.connect(device_id)) {
      Serial.println("conectado!");
      
      // Inscrever no tópico de comandos
      mqttClient.subscribe(commandTopic.c_str());
      Serial.print("Inscrito no tópico: ");
      Serial.println(commandTopic);
      
    } else {
      Serial.print("falhou, rc=");
      Serial.print(mqttClient.state());
      Serial.println(" tentando novamente em 5 segundos");
      delay(5000);
    }
  }
}

void onMqttMessage(char* topic, byte* payload, unsigned int length) {
  String message = "";
  for (int i = 0; i < length; i++) {
    message += (char)payload[i];
  }
  
  Serial.println("Mensagem MQTT recebida no tópico: " + String(topic));
  Serial.println("Mensagem: " + message);
  
  // Verificar se é um comando
  if (String(topic) == commandTopic) {
    processCommand(message);
  }
}

void processCommand(String jsonMessage) {
  StaticJsonDocument<200> doc;
  DeserializationError error = deserializeJson(doc, jsonMessage);
  
  if (error) {
    Serial.println("Erro ao fazer parse do JSON do comando");
    sendCommandResponse("", false, "Formato JSON inválido");
    return;
  }
  
  // Extrair dados do comando
  String commandType = doc["command_type"].as<String>();
  String commandValue = doc["command_value"].as<String>();
  String requestId = doc["request_id"].as<String>();
  
  Serial.println("Comando recebido: " + commandType + " " + commandValue);
  
  // Processar comando
  bool success = true;
  String responseMessage = "";
  
  if (commandType == "TURN_ON" || commandType == "TURN_ACTIVE") {
    currentStatus = smartcity_devices_DeviceStatus_ACTIVE;
    responseMessage = "Sensor ativado";
    lastDataSent = 0;  // Forçar envio imediato
    
  } else if (commandType == "TURN_OFF" || commandType == "TURN_IDLE") {
    currentStatus = smartcity_devices_DeviceStatus_IDLE;
    responseMessage = "Sensor em modo idle";
    
  } else if (commandType == "SET_FREQ") {
    int newFreqMs = commandValue.toInt();
    if (newFreqMs > 0) {
      captureIntervalMs = newFreqMs;
      responseMessage = "Frequência alterada para " + String(captureIntervalMs) + "ms";
    } else {
      success = false;
      responseMessage = "Valor de frequência inválido";
    }
    
  } else if (commandType == "GET_STATUS") {
    responseMessage = "Status atual: " + getStatusString();
    
  } else {
    success = false;
    responseMessage = "Comando desconhecido: " + commandType;
  }
  
  // Enviar resposta
  sendCommandResponse(requestId, success, responseMessage);
}

void sendCommandResponse(String requestId, bool success, String message) {
  StaticJsonDocument<400> doc;
  doc["device_id"] = device_id;
  doc["request_id"] = requestId;
  doc["success"] = success;
  doc["message"] = message;
  doc["status"] = getStatusString();
  doc["frequency_ms"] = captureIntervalMs;
  doc["timestamp"] = millis();
  
  // Adicionar dados atuais do sensor se disponíveis
  if (lastTemperature > 0 && lastHumidity > 0) {
    doc["temperature"] = lastTemperature;
    doc["humidity"] = lastHumidity;
  }
  
  String jsonString;
  serializeJson(doc, jsonString);
  
  if (mqttClient.publish(responseTopic.c_str(), jsonString.c_str())) {
    Serial.println("Resposta enviada: " + jsonString);
  } else {
    Serial.println("Erro ao enviar resposta MQTT");
  }
}

void discoverGateway() {
  int packetSize = multicastUdp.parsePacket();
  if (packetSize > 0) {
    Serial.print("Pacote multicast recebido de ");
    Serial.print(multicastUdp.remoteIP());
    Serial.print(":");
    Serial.println(multicastUdp.remotePort());
    
    // Ler dados do pacote
    uint8_t buffer[512];
    int len = multicastUdp.read(buffer, sizeof(buffer));
    
    // Decodificar mensagem protobuf
    pb_istream_t stream = pb_istream_from_buffer(buffer, len);
    smartcity_devices_SmartCityMessage message = smartcity_devices_SmartCityMessage_init_zero;
    
    if (pb_decode(&stream, smartcity_devices_SmartCityMessage_fields, &message)) {
      if (message.message_type == smartcity_devices_MessageType_DISCOVERY_REQUEST) {
        // Extrair informações do gateway
        char gateway_ip[64];
        char *gateway_ip_ptr = gateway_ip;
        message.discovery_request.gateway_ip.funcs.decode = decode_string;
        message.discovery_request.gateway_ip.arg = &gateway_ip_ptr;
        
        // Reprocessar para obter o IP
        stream = pb_istream_from_buffer(buffer, len);
        if (pb_decode(&stream, smartcity_devices_SmartCityMessage_fields, &message)) {
          gatewayIP = String(gateway_ip);
          gatewayTCPPort = message.discovery_request.gateway_tcp_port;
          gatewayFound = true;
          
          Serial.print("Gateway encontrado: ");
          Serial.print(gatewayIP);
          Serial.print(":");
          Serial.println(gatewayTCPPort);
          
          // Registrar no gateway
          registerWithGateway();
        }
      }
    }
  }
}

void registerWithGateway() {
  if (!gatewayFound) return;
  
  Serial.print("Registrando no gateway: ");
  Serial.print(gatewayIP);
  Serial.print(":");
  Serial.println(gatewayTCPPort);
  
  WiFiClient client;
  if (client.connect(gatewayIP.c_str(), gatewayTCPPort)) {
    // Criar mensagem de registro
    smartcity_devices_SmartCityMessage message = smartcity_devices_SmartCityMessage_init_zero;
    message.message_type = smartcity_devices_MessageType_DEVICE_INFO;
    
    // Configurar DeviceInfo
    message.device_info.device_id.funcs.encode = encode_ip_address;
    message.device_info.device_id.arg = (void*)device_id;
    
    message.device_info.type = smartcity_devices_DeviceType_TEMPERATURE_SENSOR;
    
    String localIP = getLocalIP();
    message.device_info.ip_address.funcs.encode = encode_ip_address;
    message.device_info.ip_address.arg = (void*)localIP.c_str();
    
    message.device_info.port = localTCPPort;
    message.device_info.initial_state = currentStatus;
    message.device_info.is_actuator = false;
    message.device_info.is_sensor = true;
    
    // Indicar que é sensor MQTT
    message.device_info.capabilities_count = 3;
    
    // Capability 1: communication = mqtt
    message.device_info.capabilities[0].key.funcs.encode = encode_ip_address;
    message.device_info.capabilities[0].key.arg = (void*)"communication";
    message.device_info.capabilities[0].value.funcs.encode = encode_ip_address;
    message.device_info.capabilities[0].value.arg = (void*)"mqtt";
    
    // Capability 2: command_topic
    message.device_info.capabilities[1].key.funcs.encode = encode_ip_address;
    message.device_info.capabilities[1].key.arg = (void*)"command_topic";
    message.device_info.capabilities[1].value.funcs.encode = encode_ip_address;
    message.device_info.capabilities[1].value.arg = (void*)commandTopic.c_str();
    
    // Capability 3: response_topic
    message.device_info.capabilities[2].key.funcs.encode = encode_ip_address;
    message.device_info.capabilities[2].key.arg = (void*)"response_topic";
    message.device_info.capabilities[2].value.funcs.encode = encode_ip_address;
    message.device_info.capabilities[2].value.arg = (void*)responseTopic.c_str();
    
    // Codificar e enviar
    uint8_t buffer[512];
    pb_ostream_t stream = pb_ostream_from_buffer(buffer, sizeof(buffer));
    
    if (pb_encode(&stream, smartcity_devices_SmartCityMessage_fields, &message)) {
      // Enviar com delimitador de tamanho
      uint8_t size = stream.bytes_written;
      client.write(&size, 1);
      client.write(buffer, size);
      client.flush();
      
      Serial.println("Registro enviado com sucesso!");
    } else {
      Serial.println("Erro ao codificar mensagem de registro");
    }
    
    client.stop();
  } else {
    Serial.println("Erro ao conectar no gateway para registro");
  }
}

void readSensorData() {
  float temperature = dht.readTemperature();
  float humidity = dht.readHumidity();
  
  if (!isnan(temperature) && !isnan(humidity)) {
    lastTemperature = temperature;
    lastHumidity = humidity;
    
    Serial.print("Sensor lido: ");
    Serial.print(temperature);
    Serial.print("°C, ");
    Serial.print(humidity);
    Serial.println("%");
  } else {
    Serial.println("Erro ao ler sensor DHT11");
  }
}

void sendSensorDataMQTT() {
  if (lastTemperature == 0.0 && lastHumidity == 0.0) {
    readSensorData();  // Tentar ler novamente
  }
  
  if (lastTemperature > 0.0 || lastHumidity > 0.0) {
    StaticJsonDocument<300> doc;
    doc["device_id"] = device_id;
    doc["temperature"] = lastTemperature;
    doc["humidity"] = lastHumidity;
    doc["status"] = getStatusString();
    doc["frequency_ms"] = captureIntervalMs;
    doc["timestamp"] = millis();
    doc["version"] = "mqtt";
    
    String jsonString;
    serializeJson(doc, jsonString);
    
    if (mqttClient.publish(dataTopic.c_str(), jsonString.c_str())) {
      Serial.println("Dados MQTT enviados: " + jsonString);
    } else {
      Serial.println("Erro ao enviar dados MQTT");
    }
  }
}

String getStatusString() {
  switch (currentStatus) {
    case smartcity_devices_DeviceStatus_ACTIVE:
      return "ACTIVE";
    case smartcity_devices_DeviceStatus_IDLE:
      return "IDLE";
    case smartcity_devices_DeviceStatus_OFF:
      return "OFF";
    default:
      return "UNKNOWN";
  }
}

String getLocalIP() {
  return WiFi.localIP().toString();
}

bool encode_ip_address(pb_ostream_t *stream, const pb_field_t *field, void * const *arg) {
  const char *ip_address = (const char *)(*arg);
  return pb_encode_tag_for_field(stream, field) &&
         pb_encode_string(stream, (const uint8_t*)ip_address, strlen(ip_address));
}

bool decode_string(pb_istream_t *stream, const pb_field_t *field, void **arg) {
  char *buffer = (char *)(*arg);
  size_t length = stream->bytes_left;
  if (length >= 64) length = 63;
  bool status = pb_read(stream, (pb_byte_t*)buffer, length);
  buffer[length] = '\0';
  return status;
}
