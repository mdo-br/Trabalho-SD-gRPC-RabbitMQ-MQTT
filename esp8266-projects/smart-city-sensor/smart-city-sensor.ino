#include <ESP8266WiFi.h>
#include <WiFiUdp.h>
#include "pb_encode.h"
#include "smart_city_esp8266.pb.h"
#include "pb.h"
#include <WiFiClient.h>

// Configurações WiFi
const char* ssid = "";
const char* password = "19071981";

// Configurações de rede
const char* multicastIP = "224.1.1.1";  // Endereço multicast do gateway
const int multicastPort = 5007;         // Porta multicast do gateway
const int gatewayUDPPort = 12346;       // Porta UDP do Gateway (padrão)
const int localUDPPort = 8889;          // Porta UDP local

// Configurações do dispositivo
const char* deviceID = "esp8266_temp_01";

WiFiUDP udp;
WiFiUDP multicastUdp;

float temperature = 0.0;
float humidity = 0.0;
unsigned long lastSensorRead = 0;
const unsigned long sensorInterval = 5000; // 5 segundos

// Descoberta do gateway
String gatewayIP = "";
bool gatewayDiscovered = false;
unsigned long lastDiscoveryAttempt = 0;
const unsigned long discoveryInterval = 30000; // 30 segundos

// Callback para serializar o campo device_id
bool encode_device_id(pb_ostream_t *stream, const pb_field_t *field, void * const *arg) {
  const char *device_id = (const char *)(*arg);
  return pb_encode_tag_for_field(stream, field) &&
         pb_encode_string(stream, (const uint8_t*)device_id, strlen(device_id));
}

void setup() {
  Serial.begin(115200);
  Serial.println("\n=== Smart City Sensor ESP8266 (nanopb) ===");
  connectToWiFi();
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
    sendSensorData();
    lastSensorRead = millis();
  }
  delay(100);
}

void connectToWiFi() {
  Serial.print("Conectando ao WiFi: ");
  Serial.println(ssid);
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println();
  Serial.println("WiFi conectado!");
  Serial.print("IP: ");
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
  // Simular leitura de sensor (substitua por sensor real como DHT22)
  temperature = random(200, 350) / 10.0;  // 20.0 a 35.0°C
  humidity = random(400, 800) / 10.0;     // 40.0 a 80.0%
  Serial.printf("Temperatura: %.1f°C, Umidade: %.1f%%\n", temperature, humidity);
}

void sendSensorData() {
  smartcity_devices_DeviceUpdate msg = smartcity_devices_DeviceUpdate_init_zero;
  // Configura o callback para o campo device_id
  msg.device_id.funcs.encode = &encode_device_id;
  msg.device_id.arg = (void*)deviceID;
  msg.type = smartcity_devices_DeviceType_TEMPERATURE_SENSOR;
  msg.current_status = smartcity_devices_DeviceStatus_ACTIVE;
  msg.has_temperature_humidity = true;
  msg.temperature_humidity.temperature = temperature;
  msg.temperature_humidity.humidity = humidity;

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
    // Criar mensagem DeviceInfo
    smartcity_devices_DeviceInfo msg = smartcity_devices_DeviceInfo_init_zero;
    msg.device_id.funcs.encode = &encode_device_id;
    msg.device_id.arg = (void*)deviceID;
    msg.type = smartcity_devices_DeviceType_TEMPERATURE_SENSOR;
    msg.ip_address.funcs.encode = &encode_device_id;
    msg.ip_address.arg = (void*)WiFi.localIP().toString().c_str();
    msg.port = localUDPPort;
    msg.initial_state = smartcity_devices_DeviceStatus_ACTIVE;
    msg.is_actuator = false;
    msg.is_sensor = true;

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
    } else {
      Serial.println("Erro ao codificar DeviceInfo com nanopb!");
    }
  } else {
    Serial.println("Falha ao conectar ao gateway via TCP para registro!");
  }
} 