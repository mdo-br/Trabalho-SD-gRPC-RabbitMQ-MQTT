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
#include "smart_city_devices.pb.h"
#include "pb.h"
#include <WiFiClient.h>
#include <DHT.h>

// --- Configurações do Sensor DHT11 ---
#define DHTTYPE DHT11                // Tipo do sensor (DHT11 ou DHT22)
#define DHTPIN D3                    // Pino digital conectado ao sensor
DHT dht(DHTPIN, DHTTYPE);            // Objeto do sensor DHT

// --- Configurações de Rede WiFi ---
const char* ssid = "homeoffice";           // Nome da rede WiFi - CONFIGURAR
const char* password = "19071981";   // Senha da rede WiFi - CONFIGURAR

// --- Configurações MQTT ---
char mqtt_server[64] = "";  // Endereço do broker MQTT (dinâmico, aprendido via descoberta)
int mqtt_port = 1883;      // Porta do broker MQTT (dinâmico)
const char* device_id = "temp_sensor_esp_001";  // ID único do dispositivo
const char* mqtt_user = "smartcity";            // Usuário MQTT
const char* mqtt_password = "smartcity123";     // Senha MQTT

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
int gatewayTCPPort = 0; // Porta TCP do gateway (dinâmica, aprendida via descoberta)

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

// Adicionar função de encode de string para nanopb
bool encode_string_field(pb_ostream_t *stream, const pb_field_t *field, void * const *arg) {
    const char *str = (const char *)(*arg);
    return pb_encode_tag_for_field(stream, field) &&
           pb_encode_string(stream, (const uint8_t*)str, strlen(str));
}

// Corrigir encode_capabilities para usar pb_callback_t corretamente
bool encode_capabilities(pb_ostream_t *stream, const pb_field_t *field, void * const *arg) {
    smartcity_devices_DeviceInfo_CapabilitiesEntry entry;
    // 1º par
    char key1[] = "communication";
    char value1[] = "mqtt";
    entry.key.funcs.encode = encode_string_field;
    entry.key.arg = key1;
    entry.value.funcs.encode = encode_string_field;
    entry.value.arg = value1;
    if (!pb_encode_tag_for_field(stream, field)) return false;
    if (!pb_encode_submessage(stream, smartcity_devices_DeviceInfo_CapabilitiesEntry_fields, &entry)) return false;
    // 2º par
    char key2[] = "command_topic";
    char value2[64];
    strncpy(value2, commandTopic.c_str(), sizeof(value2));
    value2[sizeof(value2)-1] = '\0';
    entry.key.arg = key2;
    entry.value.arg = value2;
    if (!pb_encode_tag_for_field(stream, field)) return false;
    if (!pb_encode_submessage(stream, smartcity_devices_DeviceInfo_CapabilitiesEntry_fields, &entry)) return false;
    // 3º par
    char key3[] = "response_topic";
    char value3[64];
    strncpy(value3, responseTopic.c_str(), sizeof(value3));
    value3[sizeof(value3)-1] = '\0';
    entry.key.arg = key3;
    entry.value.arg = value3;
    if (!pb_encode_tag_for_field(stream, field)) return false;
    if (!pb_encode_submessage(stream, smartcity_devices_DeviceInfo_CapabilitiesEntry_fields, &entry)) return false;
    return true;
}

// Corrigir decode do campo mqtt_broker_ip
// Antes de decodificar, configure o callback e buffer:
// char broker_ip[64] = "";
// char *broker_ip_ptr = broker_ip;
// message.payload.discovery_request.mqtt_broker_ip.funcs.decode = decode_string;
// message.payload.discovery_request.mqtt_broker_ip.arg = &broker_ip_ptr;

// Função de encode para device_id (igual ao backup)
bool encode_device_id(pb_ostream_t *stream, const pb_field_t *field, void * const *arg) {
  Serial.println("[DEBUG] encode_device_id chamado!");
  const char *device_id = (const char *)(*arg);
  Serial.print("[DEBUG] Valor device_id: ");
  Serial.println(device_id);
  return pb_encode_tag_for_field(stream, field) &&
         pb_encode_string(stream, (const uint8_t*)device_id, strlen(device_id));
}

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
  
  // Inicializa descoberta multicast
  multicastUdp.beginMulticast(WiFi.localIP(), IPAddress(224,1,1,1), multicastPort);
  
  Serial.println("Aguardando descoberta do gateway via multicast...");
  
  // Configurar status inicial
  currentStatus = smartcity_devices_DeviceStatus_IDLE;
  
  Serial.println("Sensor ESP8266 inicializado com sucesso!");
}

// --- Loop Principal ---
void loop() {
  // Descobrir gateway se ainda não encontrado
  if (!gatewayFound) {
    discoverGateway();
  } else {
    // Só tente conectar ao MQTT depois de descobrir o gateway/broker
    if (!mqttClient.connected()) {
      connectToMQTT();
    }
    mqttClient.loop();
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
    Serial.print("Tentando conexão MQTT em: ");
    Serial.print(mqtt_server);
    Serial.print(":");
    Serial.println(mqtt_port);
    // Tenta conectar com autenticação
    if (mqttClient.connect(device_id, mqtt_user, mqtt_password)) {
      Serial.println("Conectado ao broker MQTT!");
      // (Re)inscreva-se nos tópicos necessários aqui, se for o caso
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
    Serial.print("Buffer recebido: ");
    for (int i = 0; i < len; i++) {
        Serial.print(buffer[i], HEX);
        Serial.print(" ");
    }
    Serial.println();
    
    // Decodificar mensagem protobuf
    pb_istream_t stream = pb_istream_from_buffer(buffer, len);
    smartcity_devices_SmartCityMessage message = smartcity_devices_SmartCityMessage_init_zero;

    // --- Decode ---
    bool ok = pb_decode(&stream, smartcity_devices_SmartCityMessage_fields, &message);
    Serial.print("pb_decode retornou: ");
    Serial.println(ok ? "true" : "false");

    // --- Debug do oneof ---
    Serial.print("which_payload: ");
    Serial.println(message.which_payload); // Deve ser igual ao valor do campo discovery_request_tag

    // --- Debug dos campos ---
    Serial.print("gateway_ip recebido: ");
    Serial.println(message.payload.discovery_request.gateway_ip);
    Serial.print("broker_ip recebido: ");
    Serial.println(message.payload.discovery_request.mqtt_broker_ip);

    if (ok) {
        // Use o IP do gateway do remetente UDP para garantir robustez
        IPAddress remoteIP = multicastUdp.remoteIP();
        gatewayIP = remoteIP.toString();
        gatewayTCPPort = message.payload.discovery_request.gateway_tcp_port;
        gatewayFound = true;
        if (strlen(message.payload.discovery_request.mqtt_broker_ip) > 0) {
            strncpy(mqtt_server, message.payload.discovery_request.mqtt_broker_ip, sizeof(mqtt_server));
            mqtt_server[sizeof(mqtt_server)-1] = '\0';
        }
        if (message.payload.discovery_request.mqtt_broker_port != 0) {
            mqtt_port = message.payload.discovery_request.mqtt_broker_port;
        }
        Serial.print("Gateway encontrado: ");
        Serial.print(gatewayIP);
        Serial.print(":");
        Serial.println(gatewayTCPPort);
        Serial.print("Broker MQTT encontrado: ");
        Serial.print(mqtt_server);
        Serial.print(":");
        Serial.println(mqtt_port);
        // Registrar no gateway
        registerWithGateway();
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
    // Preencher DeviceInfo usando callback (igual ao backup)
    Serial.print("DeviceID enviado: ");
    Serial.println(device_id);
    Serial.print("IP enviado: ");
    Serial.println(getLocalIP());
    message.payload.device_info.device_id.funcs.encode = encode_device_id;
    message.payload.device_info.device_id.arg = (void*)device_id;
    message.payload.device_info.type = smartcity_devices_DeviceType_TEMPERATURE_SENSOR;
    String localIP = getLocalIP();
    message.payload.device_info.ip_address.funcs.encode = encode_ip_address;
    message.payload.device_info.ip_address.arg = (void*)localIP.c_str();
    message.payload.device_info.port = localTCPPort;
    message.payload.device_info.initial_state = currentStatus;
    message.payload.device_info.is_actuator = false;
    message.payload.device_info.is_sensor = true;
    // capabilities removido
    // --- Debug which_payload ---
    Serial.print("[DEBUG] which_payload antes do encode: ");
    Serial.println(message.which_payload);
    // Corrigir: selecionar o campo oneof correto
    message.which_payload = smartcity_devices_SmartCityMessage_device_info_tag;
    // Codificar e enviar
    uint8_t buffer[512];
    pb_ostream_t stream = pb_ostream_from_buffer(buffer, sizeof(buffer));
    if (pb_encode(&stream, smartcity_devices_SmartCityMessage_fields, &message)) {
      // Debug: imprimir buffer serializado em hexadecimal
      Serial.print("[DEBUG] Buffer serializado: ");
      for (size_t i = 0; i < stream.bytes_written; i++) {
        if (buffer[i] < 16) Serial.print("0");
        Serial.print(buffer[i], HEX);
        Serial.print(" ");
      }
      Serial.println();
      // Codifica o tamanho como varint (protobuf-style)
      uint8_t varint[5];
      size_t varint_len = 0;
      size_t len = stream.bytes_written;
      do {
        uint8_t byte = len & 0x7F;
        len >>= 7;
        if (len) byte |= 0x80;
        varint[varint_len++] = byte;
      } while (len);
      client.write(varint, varint_len);
      client.write(buffer, stream.bytes_written);
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
  Serial.println("[DEBUG] encode_ip_address chamado!");
  const char *ip_address = (const char *)(*arg);
  Serial.print("[DEBUG] Valor ip_address: ");
  Serial.println(ip_address);
  return pb_encode_tag_for_field(stream, field) &&
         pb_encode_string(stream, (const uint8_t*)ip_address, strlen(ip_address));
}

bool decode_string(pb_istream_t *stream, const pb_field_t *field, void **arg) {
    Serial.println("decode_string chamado!");
    char *buffer = (char *)(*arg);
    size_t length = stream->bytes_left;
    if (length >= 64) length = 63;
    bool status = pb_read(stream, (pb_byte_t*)buffer, length);
    buffer[length] = '\0';
    Serial.print("decode_string resultado: ");
    Serial.println(buffer);
    return status;
}
