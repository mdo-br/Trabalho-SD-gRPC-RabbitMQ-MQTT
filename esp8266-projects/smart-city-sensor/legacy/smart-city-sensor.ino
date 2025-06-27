/*
 * Smart City Sensor - ESP8266
 * Sensor de temperatura para sistema de cidade inteligente
 * Comunica com o Gateway via UDP usando Protocol Buffers
 * Descoberta automática via multicast
 */

#include <ESP8266WiFi.h>
#include <WiFiUdp.h>

// Configurações WiFi
const char* ssid = "SMARTUFC";
const char* password = "#smart@1020";

// Configurações de rede
const char* multicastIP = "224.1.1.1";  // Endereço multicast do gateway
const int multicastPort = 5007;         // Porta multicast do gateway
const int gatewayUDPPort = 12346;       // Porta UDP do Gateway (padrão)
const int localUDPPort = 8889;          // Porta UDP local

// Configurações do dispositivo
const char* deviceID = "esp8266_temp_01";
const uint8_t deviceType = 5; // TEMPERATURE_SENSOR
const uint8_t deviceStatus = 4; // ACTIVE

// Objetos WiFi e UDP
WiFiUDP udp;
WiFiUDP multicastUdp;

// Variáveis de estado
float temperature = 0.0;
float humidity = 0.0;
unsigned long lastSensorRead = 0;
const unsigned long sensorInterval = 5000; // 5 segundos

// Informações do gateway descoberto
String gatewayIP = "";
bool gatewayDiscovered = false;
unsigned long lastDiscoveryAttempt = 0;
const unsigned long discoveryInterval = 30000; // 30 segundos

// Buffer para Protocol Buffers
uint8_t pb_buffer[512];
size_t pb_message_length;

void setup() {
  Serial.begin(115200);
  Serial.println("\n=== Smart City Sensor ESP8266 ===");
  
  // Conectar ao WiFi
  connectToWiFi();
  
  // Configurar UDP
  udp.begin(localUDPPort);
  
  // Configurar multicast UDP
  multicastUdp.beginMulticast(WiFi.localIP(), IPAddress(224,1,1,1), multicastPort);
  
  Serial.println("Sensor iniciado e pronto!");
  Serial.println("Aguardando descoberta do gateway via multicast...");
}

void loop() {
  // Verificar conexão WiFi
  if (WiFi.status() != WL_CONNECTED) {
    connectToWiFi();
  }
  
  // Processar mensagens de descoberta multicast
  processDiscoveryMessages();
  
  // Tentar descoberta periódica se não encontrou gateway
  if (!gatewayDiscovered && (millis() - lastDiscoveryAttempt >= discoveryInterval)) {
    Serial.println("Tentando descoberta ativa do gateway...");
    sendDiscoveryRequest();
    lastDiscoveryAttempt = millis();
  }
  
  // Ler sensor e enviar dados se gateway foi descoberto
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
    
    // Tentar decodificar como Protocol Buffers DiscoveryRequest
    // Como não temos a biblioteca protobuf no ESP8266, vamos usar uma abordagem simples
    // Assumindo que o gateway envia seu IP em algum formato conhecido
    
    // Verificar se é uma mensagem de descoberta do gateway
    // Vamos usar o IP de origem da mensagem multicast como IP do gateway
    IPAddress remoteIP = multicastUdp.remoteIP();
    if (remoteIP[0] != 0 && remoteIP[0] != 255) {  // IP válido
      gatewayIP = remoteIP.toString();
      gatewayDiscovered = true;
      Serial.printf("Gateway descoberto via multicast: %s\n", gatewayIP.c_str());
      
      // Enviar resposta de descoberta
      sendDiscoveryResponse();
    }
  }
}

void sendDiscoveryRequest() {
  // Enviar broadcast de descoberta
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
  if (!gatewayDiscovered) {
    Serial.println("Gateway não descoberto, não é possível enviar dados");
    return;
  }
  
  pb_message_length = 0;
  // Field 1: device_id (string)
  pb_message_length += encode_string_field(1, deviceID);
  // Field 2: type (enum)
  pb_message_length += encode_varint_field(2, deviceType);
  // Field 3: current_status (enum)
  pb_message_length += encode_varint_field(3, deviceStatus);
  // Field 4: temperature_humidity (sub-mensagem)
  pb_message_length += encode_temperature_humidity_field(4, temperature, humidity);
  // Enviar via UDP
  udp.beginPacket(gatewayIP.c_str(), gatewayUDPPort);
  udp.write(pb_buffer, pb_message_length);
  udp.endPacket();
  Serial.printf("Dados Protocol Buffers enviados para %s:%d (%d bytes)\n", gatewayIP.c_str(), gatewayUDPPort, pb_message_length);
}

void sendDiscoveryResponse() {
  // Criar mensagem DeviceInfo com Protocol Buffers manual
  pb_message_length = 0;
  
  // Field 1: device_id (string)
  pb_message_length += encode_string_field(1, deviceID);
  
  // Field 2: type (enum)
  pb_message_length += encode_varint_field(2, deviceType);
  
  // Field 3: ip_address (string)
  pb_message_length += encode_string_field(3, WiFi.localIP().toString().c_str());
  
  // Field 4: port (int32)
  pb_message_length += encode_varint_field(4, localUDPPort);
  
  // Field 5: initial_state (enum)
  pb_message_length += encode_varint_field(5, deviceStatus);
  
  // Field 6: is_actuator (bool)
  pb_message_length += encode_bool_field(6, false);
  
  // Field 7: is_sensor (bool)
  pb_message_length += encode_bool_field(7, true);
  
  // Enviar resposta de descoberta
  udp.beginPacket(gatewayIP.c_str(), gatewayUDPPort);
  udp.write(pb_buffer, pb_message_length);
  udp.endPacket();
  
  Serial.printf("Resposta de descoberta Protocol Buffers enviada para %s (%d bytes)\n", 
                gatewayIP.c_str(), pb_message_length);
}

// Funções auxiliares para codificação manual de Protocol Buffers

// Codificar campo string
size_t encode_string_field(uint8_t field_number, const char* value) {
  size_t start_pos = pb_message_length;
  
  // Codificar tag do campo (field_number << 3 | wire_type=2)
  pb_message_length += encode_varint((field_number << 3) | 2);
  
  // Codificar tamanho da string
  size_t str_len = strlen(value);
  pb_message_length += encode_varint(str_len);
  
  // Copiar string para o buffer
  memcpy(pb_buffer + pb_message_length, value, str_len);
  pb_message_length += str_len;
  
  return pb_message_length - start_pos;
}

// Codificar campo varint (int32, enum, bool)
size_t encode_varint_field(uint8_t field_number, uint32_t value) {
  size_t start_pos = pb_message_length;
  
  // Codificar tag do campo (field_number << 3 | wire_type=0)
  pb_message_length += encode_varint((field_number << 3) | 0);
  
  // Codificar valor varint
  pb_message_length += encode_varint(value);
  
  return pb_message_length - start_pos;
}

// Codificar campo double
size_t encode_double_field(uint8_t field_number, double value) {
  size_t start_pos = pb_message_length;
  
  // Codificar tag do campo (field_number << 3 | wire_type=1)
  pb_message_length += encode_varint((field_number << 3) | 1);
  
  // Codificar valor double (64 bits)
  uint64_t* double_as_int = (uint64_t*)&value;
  for (int i = 0; i < 8; i++) {
    pb_buffer[pb_message_length++] = (*double_as_int >> (i * 8)) & 0xFF;
  }
  
  return pb_message_length - start_pos;
}

// Codificar campo bool
size_t encode_bool_field(uint8_t field_number, bool value) {
  return encode_varint_field(field_number, value ? 1 : 0);
}

// Codificar varint
size_t encode_varint(uint64_t value) {
  size_t start_pos = pb_message_length;
  
  while (value >= 0x80) {
    pb_buffer[pb_message_length++] = (value & 0x7F) | 0x80;
    value >>= 7;
  }
  pb_buffer[pb_message_length++] = value & 0x7F;
  
  return pb_message_length - start_pos;
}

// Codificar sub-mensagem temperature_humidity
size_t encode_temperature_humidity_field(uint8_t field_number, double temp, double hum) {
  size_t start_pos = pb_message_length;
  pb_message_length += encode_varint((field_number << 3) | 2);
  uint8_t submsg[32];
  size_t submsg_len = 0;
  // temperature (field 1, wire_type=1)
  submsg_len += encode_varint_to(submsg, submsg_len, (1 << 3) | 1);
  submsg_len += encode_double_to(submsg, submsg_len, temp);
  // humidity (field 2, wire_type=1)
  submsg_len += encode_varint_to(submsg, submsg_len, (2 << 3) | 1);
  submsg_len += encode_double_to(submsg, submsg_len, hum);
  pb_message_length += encode_varint(submsg_len);
  memcpy(pb_buffer + pb_message_length, submsg, submsg_len);
  pb_message_length += submsg_len;
  return pb_message_length - start_pos;
}

// Funções auxiliares para codificar em buffer externo
size_t encode_varint_to(uint8_t* buf, size_t offset, uint64_t value) {
  size_t start = offset;
  while (value >= 0x80) {
    buf[offset++] = (value & 0x7F) | 0x80;
    value >>= 7;
  }
  buf[offset++] = value & 0x7F;
  return offset - start;
}
size_t encode_double_to(uint8_t* buf, size_t offset, double value) {
  uint64_t double_as_int;
  memcpy(&double_as_int, &value, 8);
  for (int i = 0; i < 8; i++) {
    buf[offset + i] = (double_as_int >> (i * 8)) & 0xFF;
  }
  return 8;
} 