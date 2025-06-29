/*
 * Temperature Sensor Board - ESP8266
 * Sensor de temperatura para placa desenvolvida
 * Baseado no código original com DHT11 e adaptado para Protocol Buffers
 * Comunica com o Gateway via UDP usando Protocol Buffers
 * Descoberta automática via multicast
 */

#include <ESP8266WiFi.h>
#include <WiFiUdp.h>
#include "pb_encode.h"
#include "smart_city_esp8266.pb.h"
#include "pb.h"
#include <WiFiClient.h>
#include <DHT.h>

// Configurações do Sensor DHT11
#define DHTTYPE DHT11
#define DHTPIN 3  // PINO DIGITAL UTILIZADO PELO SENSOR
DHT dht(DHTPIN, DHTTYPE);

// Configurações WiFi
const char* ssid = "brisa-3604536";//"SUA_REDE_WIFI";
const char* password = "9jqkpom5";//"SUA_SENHA_WIFI";

// Configurações de rede
const char* multicastIP = "224.1.1.1";  // Endereço multicast do gateway
const int multicastPort = 5007;         // Porta multicast do gateway
const int gatewayUDPPort = 12346;       // Porta UDP do Gateway (padrão)
const int localUDPPort = 8890;          // Porta UDP local (diferente do outro sensor)

// Configurações do dispositivo
const String ID_PCB = "001001001";      // ID referente a placa, MODIFICAR AQUI
const String deviceID = "temp_board_" + ID_PCB;  // ID único para esta placa

WiFiUDP udp;
WiFiUDP multicastUdp;

float temperature = 0.0;
float humidity = 0.0;
float temperatureAnt = 0.0;
float humidityAnt = 0.0;
unsigned long lastSensorRead = 0;
const unsigned long sensorInterval = 5000; // 5 segundos (mesmo do código original)

// Descoberta do gateway
String gatewayIP = "";
bool gatewayDiscovered = false;
unsigned long lastDiscoveryAttempt = 0;
const unsigned long discoveryInterval = 30000; // 30 segundos

// Variável para armazenar o IP como string estática
String deviceIP = "";

// Callback para serializar o campo device_id
bool encode_device_id(pb_ostream_t *stream, const pb_field_t *field, void * const *arg) {
  const char *device_id = (const char *)(*arg);
  return pb_encode_tag_for_field(stream, field) &&
         pb_encode_string(stream, (const uint8_t*)device_id, strlen(device_id));
}

// Callback para serializar o campo ip_address
bool encode_ip_address(pb_ostream_t *stream, const pb_field_t *field, void * const *arg) {
  const char *ip_address = (const char *)(*arg);
  return pb_encode_tag_for_field(stream, field) &&
         pb_encode_string(stream, (const uint8_t*)ip_address, strlen(ip_address));
}

void setup() {
  Serial.begin(115200);
  Serial.println("\n=== Temperature Sensor Board ESP8266 ===");
  Serial.println("Placa desenvolvida - Sensor de Temperatura DHT11");
  Serial.print("ID da Placa: ");
  Serial.println(ID_PCB);
  
  connectToWiFi();
  dht.begin(); // Inicializa o sensor DHT11
  udp.begin(localUDPPort);
  multicastUdp.beginMulticast(WiFi.localIP(), IPAddress(224,1,1,1), multicastPort);
  Serial.println("Aguardando descoberta do gateway via multicast...");
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    connectToWiFi();
  }
  processDiscoveryMessages();
  if (!gatewayDiscovered && (millis() - lastDiscoveryAttempt >= discoveryInterval)) {
    Serial.println("Tentando descoberta ativa do gateway...");
    sendDiscoveryRequest();
    lastDiscoveryAttempt = millis();
  }
  if (gatewayDiscovered && (millis() - lastSensorRead >= sensorInterval)) {
    readSensor();
    lastSensorRead = millis();
  }
  delay(100);
}

void connectToWiFi() {
  if (WiFi.status() == WL_CONNECTED) {
    return;
  }

  Serial.println();
  Serial.println("Conectando-se");
  Serial.print(ssid);

  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(100);
    Serial.print(".");
  }
  
  Serial.println();
  Serial.print("Conectado na rede: ");
  Serial.print(ssid);  
  Serial.print("  IP obtido: ");
  Serial.println(WiFi.localIP());
}

void processDiscoveryMessages() {
  int packetSize = multicastUdp.parsePacket();
  if (packetSize) {
    uint8_t incomingPacket[255];
    int len = multicastUdp.read(incomingPacket, 255);
    Serial.printf("Mensagem multicast recebida: %d bytes\n", len);
    IPAddress remoteIP = multicastUdp.remoteIP();
    if (remoteIP[0] != 0 && remoteIP[0] != 255) {
      gatewayIP = remoteIP.toString();
      gatewayDiscovered = true;
      Serial.printf("Gateway descoberto via multicast: %s\n", gatewayIP.c_str());
      sendDiscoveryResponse();
    }
  }
}

void sendDiscoveryRequest() {
  String discoveryMsg = "DEVICE_DISCOVERY;ID:" + String(deviceID) + ";TYPE:TEMPERATURE_SENSOR;IP:" + WiFi.localIP().toString();
  udp.beginPacket("255.255.255.255", multicastPort);
  udp.write((uint8_t*)discoveryMsg.c_str(), discoveryMsg.length());
  udp.endPacket();
  Serial.println("Solicitação de descoberta enviada");
}

void readSensor() {
  // Leitura real do sensor DHT11 (baseado no código original)
  temperatureAnt = temperature;
  temperature = dht.readTemperature(); 

  humidityAnt = humidity;
  humidity = dht.readHumidity();
    
  // Enviar dados apenas se houver mudança (como no código original)
  if(temperature != temperatureAnt && !(isnan(temperature))){
    Serial.print("Temperatura = "); 
    Serial.print(temperature); 
    Serial.print(" °C      |       "); 
    Serial.print("Umidade = "); 
    Serial.print(humidity); 
    Serial.println();
    
    sendSensorData();
  }

  if(humidity != humidityAnt && !(isnan(humidity))){
    Serial.print("Temperatura = "); 
    Serial.print(temperature); 
    Serial.print(" °C      |       "); 
    Serial.print("Umidade = "); 
    Serial.print(humidity); 
    Serial.println();
    
    sendSensorData();
  }
}

void sendSensorData() {
  smartcity_devices_DeviceUpdate msg = smartcity_devices_DeviceUpdate_init_zero;
  // Configura o callback para o campo device_id
  msg.device_id.funcs.encode = &encode_device_id;
  msg.device_id.arg = (void*)deviceID.c_str();
  msg.type = smartcity_devices_DeviceType_TEMPERATURE_SENSOR;
  msg.current_status = smartcity_devices_DeviceStatus_ACTIVE;
  msg.which_data = smartcity_devices_DeviceUpdate_temperature_humidity_tag;
  msg.data.temperature_humidity.temperature = temperature;
  msg.data.temperature_humidity.humidity = humidity;

  uint8_t buffer[128];
  pb_ostream_t stream = pb_ostream_from_buffer(buffer, sizeof(buffer));
  bool status = pb_encode(&stream, smartcity_devices_DeviceUpdate_fields, &msg);

  if (status) {
    // Enviar dados sensoriados via UDP (porta 12346)
    udp.beginPacket(gatewayIP.c_str(), gatewayUDPPort);
    udp.write(buffer, stream.bytes_written);
    udp.endPacket();
    Serial.printf("DeviceUpdate enviado via UDP para %s:%d (%d bytes)\n", gatewayIP.c_str(), gatewayUDPPort, (int)stream.bytes_written);
  } else {
    Serial.println("Erro ao codificar com nanopb!");
  }
}

void sendDiscoveryResponse() {
  // Enviar DeviceInfo via TCP para se registrar no gateway
  WiFiClient client;
  if (client.connect(gatewayIP.c_str(), 12345)) { // Porta TCP do gateway
    // Atualizar o IP do dispositivo
    deviceIP = WiFi.localIP().toString();
    
    // Criar mensagem DeviceInfo
    smartcity_devices_DeviceInfo msg = smartcity_devices_DeviceInfo_init_zero;
    msg.device_id.funcs.encode = &encode_device_id;
    msg.device_id.arg = (void*)deviceID.c_str();
    msg.type = smartcity_devices_DeviceType_TEMPERATURE_SENSOR;
    msg.ip_address.funcs.encode = &encode_ip_address;
    msg.ip_address.arg = (void*)deviceIP.c_str();
    msg.port = localUDPPort;
    msg.initial_state = smartcity_devices_DeviceStatus_ACTIVE;
    msg.is_actuator = false;
    msg.is_sensor = true;

    // DEBUG: imprimir campos antes de serializar
    Serial.println("[DEBUG] DeviceInfo a ser enviado:");
    Serial.print("  device_id: "); Serial.println(deviceID);
    Serial.print("  type: "); Serial.println((int)msg.type);
    Serial.print("  ip_address: "); Serial.println(deviceIP);
    Serial.print("  port: "); Serial.println(msg.port);
    Serial.print("  initial_state: "); Serial.println((int)msg.initial_state);
    Serial.print("  is_actuator: "); Serial.println(msg.is_actuator);
    Serial.print("  is_sensor: "); Serial.println(msg.is_sensor);

    uint8_t buffer[128];
    pb_ostream_t stream = pb_ostream_from_buffer(buffer, sizeof(buffer));
    bool status = pb_encode(&stream, smartcity_devices_DeviceInfo_fields, &msg);

    if (status) {
      // Enviar o tamanho da mensagem como varint
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
      // Enviar o payload protobuf
      client.write(buffer, stream.bytes_written);
      client.stop();
      Serial.printf("DeviceInfo enviado via TCP para %s:12345 (%d bytes)\n", gatewayIP.c_str(), (int)stream.bytes_written);
      // DEBUG: imprimir bytes enviados
      Serial.print("[DEBUG] Bytes enviados: ");
      for (size_t i = 0; i < stream.bytes_written; ++i) {
        Serial.printf("%02x ", buffer[i]);
      }
      Serial.println();
    } else {
      Serial.println("Erro ao codificar DeviceInfo com nanopb!");
    }
  } else {
    Serial.println("Falha ao conectar ao gateway via TCP para registro!");
  }
} 