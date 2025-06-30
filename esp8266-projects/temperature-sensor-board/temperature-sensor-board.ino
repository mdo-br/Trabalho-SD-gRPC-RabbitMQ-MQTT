/*
 * ESP8266 Temperature Sensor Board - Placa de Sensor de Temperatura e Umidade
 * 
 * Este código implementa uma placa ESP8266 que funciona como sensor de temperatura
 * e umidade no sistema Smart City. A placa lê dados do sensor DHT11 e envia
 * periodicamente para o gateway.
 * 
 * Funcionalidades:
 * - Descoberta automática do gateway via multicast UDP
 * - Registro no gateway via TCP
 * - Leitura de temperatura e umidade do sensor DHT11
 * - Envio de dados sensoriados via UDP
 * - Detecção de mudanças nos valores para otimizar transmissão
 * 
 * Protocolos:
 * - Protocol Buffers para serialização de mensagens
 * - TCP para registro no gateway
 * - UDP para dados sensoriados e descoberta multicast
 * 
 * Hardware:
 * - ESP8266 (NodeMCU, Wemos D1 Mini, etc.)
 * - Sensor DHT11 conectado ao pino 3
 * - Biblioteca DHT para leitura do sensor
 */

#include <ESP8266WiFi.h>
#include <WiFiUdp.h>
#include "pb_encode.h"
#include "smart_city_esp8266.pb.h"
#include "pb.h"
#include <WiFiClient.h>
#include <DHT.h>

// --- Configurações do Sensor DHT11 ---
#define DHTTYPE DHT11                // Tipo do sensor (DHT11 ou DHT22)
#define DHTPIN 3                     // Pino digital conectado ao sensor
DHT dht(DHTPIN, DHTTYPE);            // Objeto do sensor DHT

// --- Configurações de Rede WiFi ---
const char* ssid = "ssid";           // Nome da rede WiFi - CONFIGURAR
const char* password = "password";   // Senha da rede WiFi - CONFIGURAR

// --- Configurações de Rede do Sistema ---
const char* multicastIP = "224.1.1.1";  // Endereço multicast para descoberta
const int multicastPort = 5007;         // Porta multicast
const int gatewayUDPPort = 12346;       // Porta UDP do gateway
const int localUDPPort = 8890;          // Porta UDP local (diferente de outros dispositivos)

// --- Configurações do Dispositivo ---
const String ID_PCB = "001001001";      // ID único da placa - MODIFICAR SE NECESSÁRIO
const String deviceID = "temp_board_" + ID_PCB;  // ID completo do dispositivo

// --- Objetos de Rede ---
WiFiUDP udp;                           // Socket UDP para comunicação
WiFiUDP multicastUdp;                  // Socket UDP multicast para descoberta

// --- Variáveis de Dados do Sensor ---
float temperature = 0.0;               // Temperatura atual em °C
float humidity = 0.0;                  // Umidade atual em %
float temperatureAnt = 0.0;            // Temperatura anterior (para detectar mudanças)
float humidityAnt = 0.0;               // Umidade anterior (para detectar mudanças)
unsigned long lastSensorRead = 0;      // Última leitura do sensor
const unsigned long sensorInterval = 5000;  // Intervalo entre leituras (5 segundos)

// --- Variáveis de Estado ---
String gatewayIP = "";                 // IP do gateway descoberto
bool gatewayDiscovered = false;        // Flag indicando se o gateway foi encontrado
unsigned long lastDiscoveryAttempt = 0; // Última tentativa de descoberta
const unsigned long discoveryInterval = 30000; // Intervalo entre tentativas (30s)
String deviceIP = "";                  // IP local do dispositivo

// --- Funções auxiliares para Protocol Buffers ---

/**
 * Callback para codificar o campo device_id em mensagens Protocol Buffers
 * 
 * @param stream Stream de saída do nanopb
 * @param field Campo sendo codificado
 * @param arg Argumento contendo o device_id como string
 * @return true se codificação foi bem-sucedida
 */
bool encode_device_id(pb_ostream_t *stream, const pb_field_t *field, void * const *arg) {
  const char *device_id = (const char *)(*arg);
  return pb_encode_tag_for_field(stream, field) &&
         pb_encode_string(stream, (const uint8_t*)device_id, strlen(device_id));
}

/**
 * Callback para codificar o campo ip_address em mensagens Protocol Buffers
 * 
 * @param stream Stream de saída do nanopb
 * @param field Campo sendo codificado
 * @param arg Argumento contendo o IP como string
 * @return true se codificação foi bem-sucedida
 */
bool encode_ip_address(pb_ostream_t *stream, const pb_field_t *field, void * const *arg) {
  const char *ip_address = (const char *)(*arg);
  return pb_encode_tag_for_field(stream, field) &&
         pb_encode_string(stream, (const uint8_t*)ip_address, strlen(ip_address));
}

// --- Função de Inicialização ---
void setup() {
  // Inicializa comunicação serial para debug
  Serial.begin(115200);
  Serial.println("\n=== Temperature Sensor Board ESP8266 ===");
  Serial.print("ID da Placa: ");
  Serial.println(ID_PCB);
  
  // Conecta ao WiFi
  connectToWiFi();
  
  // Inicializa o sensor DHT11
  dht.begin();
  
  // Inicializa sockets de rede
  udp.begin(localUDPPort);
  multicastUdp.beginMulticast(WiFi.localIP(), IPAddress(224,1,1,1), multicastPort);
  
  Serial.println("Aguardando descoberta do gateway via multicast...");
}

// --- Loop Principal ---
void loop() {
  // Reconecta WiFi se necessário
  if (WiFi.status() != WL_CONNECTED) {
    connectToWiFi();
  }
  
  // Processa mensagens de descoberta multicast
  processDiscoveryMessages();
  
  // Tenta descoberta ativa se ainda não encontrou o gateway
  if (!gatewayDiscovered && (millis() - lastDiscoveryAttempt >= discoveryInterval)) {
    sendDiscoveryRequest();
    lastDiscoveryAttempt = millis();
  }
  
  // Lê sensor periodicamente se gateway foi descoberto
  if (gatewayDiscovered && (millis() - lastSensorRead >= sensorInterval)) {
    readSensor();
    lastSensorRead = millis();
  }
  
  delay(100);  // Pequena pausa para não sobrecarregar o processador
}

// --- Conexão WiFi ---
void connectToWiFi() {
  if (WiFi.status() == WL_CONNECTED) return;

  Serial.println();
  Serial.print("Conectando-se a ");
  Serial.println(ssid);

  WiFi.begin(ssid, password);
  
  // Aguarda conexão com indicador visual
  while (WiFi.status() != WL_CONNECTED) {
    delay(100);
    Serial.print(".");
  }

  Serial.println("\nWiFi conectado. IP: " + WiFi.localIP().toString());
}

// --- Processamento de Mensagens Multicast ---
void processDiscoveryMessages() {
  int packetSize = multicastUdp.parsePacket();
  if (packetSize) {
    uint8_t incomingPacket[255];
    int len = multicastUdp.read(incomingPacket, 255);
    IPAddress remoteIP = multicastUdp.remoteIP();
    
    // Verifica se a mensagem veio de um IP válido (não broadcast)
    if (remoteIP[0] != 0 && remoteIP[0] != 255) {
      gatewayIP = remoteIP.toString();
      gatewayDiscovered = true;
      Serial.printf("Gateway descoberto via multicast: %s\n", gatewayIP.c_str());
      sendDiscoveryResponse();  // Registra-se no gateway
    }
  }
}

// --- Solicitação de Descoberta (Broadcast) ---
void sendDiscoveryRequest() {
  // Envia mensagem de descoberta em broadcast
  String discoveryMsg = "DEVICE_DISCOVERY;ID:" + deviceID + ";TYPE:TEMPERATURE_SENSOR;IP:" + WiFi.localIP().toString();
  udp.beginPacket("255.255.255.255", multicastPort);
  udp.write((uint8_t*)discoveryMsg.c_str(), discoveryMsg.length());
  udp.endPacket();
  Serial.println("Solicitação de descoberta enviada");
}

// --- Leitura do Sensor DHT11 ---
void readSensor() {
  // Armazena valores anteriores para detectar mudanças
  temperatureAnt = temperature;
  humidityAnt = humidity;
  
  // Lê novos valores do sensor
  temperature = dht.readTemperature();
  humidity = dht.readHumidity();

  // Envia dados apenas se houve mudança (otimização de rede)
  if (temperature != temperatureAnt || humidity != humidityAnt) {
    Serial.printf("Temperatura = %.1f °C | Umidade = %.1f %%\n", temperature, humidity);
    
    // Verifica se os valores são válidos (não NaN)
    if (!isnan(temperature) && !isnan(humidity)) {
      sendSensorData();  // Envia dados para o gateway
    }
  }
}

// --- Envio de Dados Sensoriados (UDP) ---
void sendSensorData() {
  // Cria mensagem DeviceUpdate com dados do sensor
  smartcity_devices_DeviceUpdate msg = smartcity_devices_DeviceUpdate_init_zero;
  msg.device_id.funcs.encode = &encode_device_id;
  msg.device_id.arg = (void*)deviceID.c_str();
  msg.type = smartcity_devices_DeviceType_TEMPERATURE_SENSOR;
  msg.current_status = smartcity_devices_DeviceStatus_ACTIVE;

  // Configura dados de temperatura e umidade usando oneof
  msg.which_data = smartcity_devices_DeviceUpdate_temperature_humidity_tag;
  msg.data.temperature_humidity.temperature = temperature;
  msg.data.temperature_humidity.humidity = humidity;

  // Serializa e envia via UDP
  uint8_t buffer[128];
  pb_ostream_t stream = pb_ostream_from_buffer(buffer, sizeof(buffer));
  if (pb_encode(&stream, smartcity_devices_DeviceUpdate_fields, &msg)) {
    udp.beginPacket(gatewayIP.c_str(), gatewayUDPPort);
    udp.write(buffer, stream.bytes_written);
    udp.endPacket();
    Serial.printf("DeviceUpdate enviado via UDP (%d bytes)\n", stream.bytes_written);
  } else {
    Serial.println("Erro ao codificar com nanopb!");
  }
}

// --- Resposta ao Gateway com DeviceInfo (TCP) ---
void sendDiscoveryResponse() {
  WiFiClient client;
  if (client.connect(gatewayIP.c_str(), 12345)) {  // Conecta na porta TCP do gateway
    deviceIP = WiFi.localIP().toString();

    // Cria mensagem DeviceInfo para registro
    smartcity_devices_DeviceInfo msg = smartcity_devices_DeviceInfo_init_zero;
    msg.device_id.funcs.encode = &encode_device_id;
    msg.device_id.arg = (void*)deviceID.c_str();
    msg.type = smartcity_devices_DeviceType_TEMPERATURE_SENSOR;
    msg.ip_address.funcs.encode = &encode_ip_address;
    msg.ip_address.arg = (void*)deviceIP.c_str();
    msg.port = localUDPPort;
    msg.initial_state = smartcity_devices_DeviceStatus_ACTIVE;
    msg.is_actuator = false;   // Este dispositivo é um sensor
    msg.is_sensor = true;      // Este dispositivo não é um atuador

    // Serializa a mensagem
    uint8_t buffer[128];
    pb_ostream_t stream = pb_ostream_from_buffer(buffer, sizeof(buffer));
    if (pb_encode(&stream, smartcity_devices_DeviceInfo_fields, &msg)) {
      // Codifica o tamanho como varint (formato Protocol Buffers)
      uint8_t varint[5];
      size_t varint_len = 0;
      size_t len = stream.bytes_written;
      do {
        uint8_t byte = len & 0x7F;
        len >>= 7;
        if (len) byte |= 0x80;
        varint[varint_len++] = byte;
      } while (len);
      
      // Envia varint + payload
      client.write(varint, varint_len);
      client.write(buffer, stream.bytes_written);
      client.stop();
      Serial.printf("DeviceInfo enviado via TCP (%d bytes)\n", stream.bytes_written);
    } else {
      Serial.println("Erro ao codificar DeviceInfo com nanopb!");
    }
  } else {
    Serial.println("Falha ao conectar ao gateway via TCP para registro!");
  }
}