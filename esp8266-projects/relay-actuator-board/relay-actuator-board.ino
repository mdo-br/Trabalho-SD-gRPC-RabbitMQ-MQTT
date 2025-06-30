#include <ESP8266WiFi.h>
#include <WiFiUdp.h>
#include <WiFiServer.h>
#include "pb_encode.h"
#include "pb_decode.h"
#include "smart_city_esp8266.pb.h"
#include "pb.h"
#include <WiFiClient.h>

// --- Configurações ---
#define pinRELE 3
unsigned long prevTime = millis();
long msgInterval = 30000;
String lampStatus = "OFF";

const char* SSID = "brisa-3604536";
const char* PASSWORD = "9jqkpom5";

const char* multicastIP = "224.1.1.1";
const int multicastPort = 5007;
const int gatewayUDPPort = 12346;
const int localUDPPort = 8891;
const int localTCPPort = 8891;

const String ID_PCB = "001001002";
const String deviceID = "relay_board_" + ID_PCB;

WiFiUDP udp;
WiFiUDP multicastUdp;
WiFiServer tcpServer(localTCPPort);

String gatewayIP = "";
bool gatewayDiscovered = false;
unsigned long lastDiscoveryAttempt = 0;
const unsigned long discoveryInterval = 30000;
String deviceIP = "";

// --- Funções auxiliares Protobuf ---
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

bool decode_string(pb_istream_t *stream, const pb_field_t *field, void **arg) {
  char *buffer = (char *)(*arg);
  size_t length = stream->bytes_left;
  if (length >= 64) length = 63;
  bool status = pb_read(stream, (pb_byte_t*)buffer, length);
  buffer[length] = '\0';
  return status;
}

// --- Setup ---
void setup() {
  Serial.begin(115200);
  pinMode(pinRELE, OUTPUT);

  conectaWiFi();
  udp.begin(localUDPPort);
  multicastUdp.beginMulticast(WiFi.localIP(), IPAddress(224,1,1,1), multicastPort);
  tcpServer.begin();
  Serial.println("Aguardando descoberta do gateway via multicast...");
}

// --- Loop principal ---
void loop() {
  unsigned long currentTime = millis();
  if (currentTime - prevTime >= msgInterval) {
    sendStatusUpdate();
    prevTime = currentTime;
  }

  mantemConexoes();
  processDiscoveryMessages();
  processTCPCommands();
}

// --- Manutenção de conexões ---
void mantemConexoes() {
  if (WiFi.status() != WL_CONNECTED) {
    conectaWiFi();
  }

  if (!gatewayDiscovered && (millis() - lastDiscoveryAttempt >= discoveryInterval)) {
    Serial.println("Tentando descoberta ativa do gateway...");
    sendDiscoveryRequest();
    lastDiscoveryAttempt = millis();
  }
}

// --- Conexão WiFi ---
void conectaWiFi() {
  if (WiFi.status() == WL_CONNECTED) return;

  Serial.println("Conectando-se a WiFi...");
  WiFi.begin(SSID, PASSWORD);
  while (WiFi.status() != WL_CONNECTED) {
    delay(100);
    Serial.print(".");
  }
  Serial.println("\nWiFi conectado. IP: " + WiFi.localIP().toString());
}

// --- Processa mensagens multicast ---
void processDiscoveryMessages() {
  int packetSize = multicastUdp.parsePacket();
  if (packetSize) {
    uint8_t incomingPacket[255];
    multicastUdp.read(incomingPacket, 255);
    IPAddress remoteIP = multicastUdp.remoteIP();
    if (remoteIP[0] != 0 && remoteIP[0] != 255) {
      gatewayIP = remoteIP.toString();
      gatewayDiscovered = true;
      Serial.println("Gateway descoberto via multicast: " + gatewayIP);
      sendDiscoveryResponse();
    }
  }
}

// --- Processa comandos TCP ---
void processTCPCommands() {
  WiFiClient client = tcpServer.available();
  if (client) {
    Serial.printf("Comando TCP recebido de %s\n", client.remoteIP().toString().c_str());

    // Aguarda até ter pelo menos 1 byte para leitura
    while (!client.available()) delay(1);

    // Ler o varint (máx. 5 bytes)
    uint8_t varint[5];
    int varint_len = 0;
    while (client.available() && varint_len < 5) {
      varint[varint_len] = client.read();
      if ((varint[varint_len] & 0x80) == 0) break;
      varint_len++;
    }

    // Decodifica o tamanho da mensagem
    size_t msg_len = 0;
    for (int i = 0; i <= varint_len; i++) {
      msg_len |= (varint[i] & 0x7F) << (7 * i);
    }

    // Aguarda até o payload completo estar disponível
    while (client.available() < msg_len) delay(1);

    // Lê o payload
    uint8_t buffer[128] = {0};
    int bytes_read = client.readBytes(buffer, msg_len);

    Serial.printf("Bytes lidos: %d (esperado: %d)\n", bytes_read, (int)msg_len);
    Serial.print("Payload (hex): ");
    for (int i = 0; i < bytes_read && i < 20; i++) {
      Serial.printf("%02x ", buffer[i]);
    }
    Serial.println();

    // Decodifica Protobuf
    char cmd_buffer[64] = {0};
    smartcity_devices_DeviceCommand command = smartcity_devices_DeviceCommand_init_zero;
    command.command_type.funcs.decode = &decode_string;
    command.command_type.arg = cmd_buffer;

    pb_istream_t stream = pb_istream_from_buffer(buffer, bytes_read);
    if (pb_decode(&stream, smartcity_devices_DeviceCommand_fields, &command)) {
      String commandType = String(cmd_buffer);
      Serial.printf("Comando decodificado: '%s'\n", commandType.c_str());
      deviceControl(commandType);
    } else {
      Serial.println("ERRO: Falha ao decodificar comando Protobuf!");
    }

    client.stop();
  }
}


// --- Aplica comandos ao relé ---
void deviceControl(String msg) {
  Serial.printf("Processando comando: '%s'\n", msg.c_str());

  if (msg == "TURN_ON") {
    digitalWrite(pinRELE, HIGH);
    lampStatus = "ON";
    sendStatusUpdate();
    Serial.println("RELÉ LIGADO - Status: ON");
  } else if (msg == "TURN_OFF") {
    digitalWrite(pinRELE, LOW);
    lampStatus = "OFF";
    sendStatusUpdate();
    Serial.println("RELÉ DESLIGADO - Status: OFF");
  } else {
    Serial.println("Comando não reconhecido.");
  }
}

// --- Envia atualização de status (UDP) ---
void sendStatusUpdate() {
  smartcity_devices_DeviceUpdate msg = smartcity_devices_DeviceUpdate_init_zero;
  msg.device_id.funcs.encode = &encode_device_id;
  msg.device_id.arg = (void*)deviceID.c_str();
  msg.type = smartcity_devices_DeviceType_ALARM;
  msg.current_status = (lampStatus == "ON") ? smartcity_devices_DeviceStatus_ON : smartcity_devices_DeviceStatus_OFF;

  uint8_t buffer[128];
  pb_ostream_t stream = pb_ostream_from_buffer(buffer, sizeof(buffer));
  if (pb_encode(&stream, smartcity_devices_DeviceUpdate_fields, &msg) && gatewayDiscovered) {
    udp.beginPacket(gatewayIP.c_str(), gatewayUDPPort);
    udp.write(buffer, stream.bytes_written);
    udp.endPacket();
    Serial.printf("Status enviado via UDP para %s:%d (%d bytes)\n", 
                  gatewayIP.c_str(), gatewayUDPPort, (int)stream.bytes_written);
  }
}

// --- Solicitação de descoberta (broadcast) ---
void sendDiscoveryRequest() {
  String discoveryMsg = "DEVICE_DISCOVERY;ID:" + deviceID + ";TYPE:RELAY_ACTUATOR;IP:" + WiFi.localIP().toString();
  udp.beginPacket("255.255.255.255", multicastPort);
  udp.write((uint8_t*)discoveryMsg.c_str(), discoveryMsg.length());
  udp.endPacket();
  Serial.println("Solicitação de descoberta enviada");
}

// --- Resposta ao Gateway com DeviceInfo ---
void sendDiscoveryResponse() {
  WiFiClient client;
  if (client.connect(gatewayIP.c_str(), 12345)) {
    deviceIP = WiFi.localIP().toString();

    smartcity_devices_DeviceInfo msg = smartcity_devices_DeviceInfo_init_zero;
    msg.device_id.funcs.encode = &encode_device_id;
    msg.device_id.arg = (void*)deviceID.c_str();
    msg.type = smartcity_devices_DeviceType_ALARM;
    msg.ip_address.funcs.encode = &encode_ip_address;
    msg.ip_address.arg = (void*)deviceIP.c_str();
    msg.port = localUDPPort;
    msg.initial_state = smartcity_devices_DeviceStatus_OFF;
    msg.is_actuator = true;
    msg.is_sensor = false;

    uint8_t buffer[128];
    pb_ostream_t stream = pb_ostream_from_buffer(buffer, sizeof(buffer));
    if (pb_encode(&stream, smartcity_devices_DeviceInfo_fields, &msg)) {
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
      Serial.printf("DeviceInfo enviado para gateway (%d bytes)\n", (int)stream.bytes_written);
    }
  }
}
