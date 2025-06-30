#include <ESP8266WiFi.h>
#include <WiFiUdp.h>
#include "pb_encode.h"
#include "smart_city_esp8266.pb.h"
#include "pb.h"
#include <WiFiClient.h>
#include <DHT.h>

// Configurações do Sensor DHT11
#define DHTTYPE DHT11
#define DHTPIN 3
DHT dht(DHTPIN, DHTTYPE);

// Configurações WiFi
const char* ssid = "ssid"; //sua rede wifi
const char* password = "password"; // sua senha wifi

// Configurações de rede
const char* multicastIP = "224.1.1.1";
const int multicastPort = 5007;
const int gatewayUDPPort = 12346;
const int localUDPPort = 8890;

// Configurações do dispositivo
const String ID_PCB = "001001001";
const String deviceID = "temp_board_" + ID_PCB;

WiFiUDP udp;
WiFiUDP multicastUdp;

float temperature = 0.0;
float humidity = 0.0;
float temperatureAnt = 0.0;
float humidityAnt = 0.0;
unsigned long lastSensorRead = 0;
const unsigned long sensorInterval = 5000;

String gatewayIP = "";
bool gatewayDiscovered = false;
unsigned long lastDiscoveryAttempt = 0;
const unsigned long discoveryInterval = 30000;

String deviceIP = "";

bool encode_device_id(pb_ostream_t *stream, const pb_field_t *field, void * const *arg) {
  const char *device_id = (const char *)(*arg);
  return pb_encode_tag_for_field(stream, field) &&
         pb_encode_string(stream, (const uint8_t*)device_id, strlen(device_id));
}

bool encode_ip_address(pb_ostream_t *stream, const pb_field_t *field, void * const *arg) {
  const char *ip_address = (const char *)(*arg);
  return pb_encode_tag_for_field(stream, field) &&
         pb_encode_string(stream, (const uint8_t*)ip_address, strlen(ip_address));
}

void setup() {
  Serial.begin(115200);
  Serial.println("\n=== Temperature Sensor Board ESP8266 ===");
  Serial.print("ID da Placa: ");
  Serial.println(ID_PCB);
  
  connectToWiFi();
  dht.begin();
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
  if (WiFi.status() == WL_CONNECTED) return;

  Serial.println();
  Serial.print("Conectando-se a ");
  Serial.println(ssid);

  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(100);
    Serial.print(".");
  }

  Serial.println("\nWiFi conectado. IP: " + WiFi.localIP().toString());
}

void processDiscoveryMessages() {
  int packetSize = multicastUdp.parsePacket();
  if (packetSize) {
    uint8_t incomingPacket[255];
    int len = multicastUdp.read(incomingPacket, 255);
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
  String discoveryMsg = "DEVICE_DISCOVERY;ID:" + deviceID + ";TYPE:TEMPERATURE_SENSOR;IP:" + WiFi.localIP().toString();
  udp.beginPacket("255.255.255.255", multicastPort);
  udp.write((uint8_t*)discoveryMsg.c_str(), discoveryMsg.length());
  udp.endPacket();
  Serial.println("Solicitação de descoberta enviada");
}

void readSensor() {
  temperatureAnt = temperature;
  humidityAnt = humidity;
  temperature = dht.readTemperature();
  humidity = dht.readHumidity();

  if (temperature != temperatureAnt || humidity != humidityAnt) {
    Serial.printf("Temperatura = %.1f °C | Umidade = %.1f %%\n", temperature, humidity);
    if (!isnan(temperature) && !isnan(humidity)) {
      sendSensorData();
    }
  }
}

void sendSensorData() {
  smartcity_devices_DeviceUpdate msg = smartcity_devices_DeviceUpdate_init_zero;
  msg.device_id.funcs.encode = &encode_device_id;
  msg.device_id.arg = (void*)deviceID.c_str();
  msg.type = smartcity_devices_DeviceType_TEMPERATURE_SENSOR;
  msg.current_status = smartcity_devices_DeviceStatus_ACTIVE;

  // Usa oneof para dados de sensor
  msg.which_data = smartcity_devices_DeviceUpdate_temperature_humidity_tag;
  msg.data.temperature_humidity.temperature = temperature;
  msg.data.temperature_humidity.humidity = humidity;

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

void sendDiscoveryResponse() {
  WiFiClient client;
  if (client.connect(gatewayIP.c_str(), 12345)) {
    deviceIP = WiFi.localIP().toString();

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

    uint8_t buffer[128];
    pb_ostream_t stream = pb_ostream_from_buffer(buffer, sizeof(buffer));
    if (pb_encode(&stream, smartcity_devices_DeviceInfo_fields, &msg)) {
      // varint (tamanho)
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
      client.stop();
      Serial.printf("DeviceInfo enviado via TCP (%d bytes)\n", stream.bytes_written);
    } else {
      Serial.println("Erro ao codificar DeviceInfo com nanopb!");
    }
  } else {
    Serial.println("Falha ao conectar ao gateway via TCP para registro!");
  }
}