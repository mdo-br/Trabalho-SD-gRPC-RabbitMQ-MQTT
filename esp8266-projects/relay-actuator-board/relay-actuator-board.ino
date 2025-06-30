/*
 * ESP8266 Relay Actuator Board - Placa de Atuador com Relé
 * 
 * Este código implementa uma placa ESP8266 que funciona como atuador de relé
 * no sistema Smart City. A placa pode receber comandos para ligar/desligar
 * um relé conectado ao pino 3.
 * 
 * Funcionalidades:
 * - Descoberta automática do gateway via multicast UDP
 * - Registro no gateway via TCP
 * - Recebimento de comandos via TCP (TURN_ON/TURN_OFF)
 * - Envio de status via UDP
 * - Controle de relé para acionar cargas (lâmpadas, motores, etc.)
 * 
 * Protocolos:
 * - Protocol Buffers para serialização de mensagens
 * - TCP para registro e comandos
 * - UDP para status e descoberta multicast
 * 
 * Hardware:
 * - ESP8266 (NodeMCU, Wemos D1 Mini, etc.)
 * - Módulo relé conectado ao pino 3
 * - Carga controlada (lâmpada, motor, etc.)
 */

#include <ESP8266WiFi.h>
#include <WiFiUdp.h>
#include <WiFiServer.h>
#include "pb_encode.h"
#include "pb_decode.h"
#include "smart_city_esp8266.pb.h"
#include "pb.h"
#include <WiFiClient.h>

// --- Configurações de Hardware ---
#define pinRELE 3                    // Pino digital conectado ao módulo relé
unsigned long prevTime = millis();   // Controle de tempo para envio periódico
long msgInterval = 30000;            // Intervalo para envio de status (30 segundos)
String lampStatus = "OFF";           // Status atual do relé

// --- Configurações de Rede WiFi ---
const char* SSID = "SSID";           // Nome da rede WiFi - CONFIGURAR
const char* PASSWORD = "PASSWORD";   // Senha da rede WiFi - CONFIGURAR

// --- Configurações de Rede do Sistema ---
const char* multicastIP = "224.1.1.1";  // Endereço multicast para descoberta
const int multicastPort = 5007;         // Porta multicast
const int gatewayUDPPort = 12346;       // Porta UDP do gateway
const int localUDPPort = 8891;          // Porta UDP local (diferente de outros dispositivos)
const int localTCPPort = 8891;          // Porta TCP local para comandos

// --- Configurações do Dispositivo ---
const String ID_PCB = "001001002";      // ID único da placa - MODIFICAR SE NECESSÁRIO
const String deviceID = "relay_board_" + ID_PCB;  // ID completo do dispositivo

// --- Objetos de Rede ---
WiFiUDP udp;                           // Socket UDP para comunicação
WiFiUDP multicastUdp;                  // Socket UDP multicast para descoberta
WiFiServer tcpServer(localTCPPort);    // Servidor TCP para comandos

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

/**
 * Callback para decodificar strings em mensagens Protocol Buffers
 * 
 * @param stream Stream de entrada do nanopb
 * @param field Campo sendo decodificado
 * @param arg Buffer para armazenar a string decodificada
 * @return true se decodificação foi bem-sucedida
 */
bool decode_string(pb_istream_t *stream, const pb_field_t *field, void **arg) {
  char *buffer = (char *)(*arg);
  size_t length = stream->bytes_left;
  if (length >= 64) length = 63;  // Limita o tamanho para evitar overflow
  bool status = pb_read(stream, (pb_byte_t*)buffer, length);
  buffer[length] = '\0';  // Adiciona terminador de string
  return status;
}

// --- Função de Inicialização ---
void setup() {
  // Inicializa comunicação serial para debug
  Serial.begin(115200);
  Serial.println("\n=== ESP8266 Relay Actuator Board ===");
  Serial.print("ID da Placa: ");
  Serial.println(ID_PCB);
  
  // Configura pino do relé como saída
  pinMode(pinRELE, OUTPUT);
  digitalWrite(pinRELE, LOW);  // Inicia com relé desligado
  
  // Conecta ao WiFi
  conectaWiFi();
  
  // Inicializa sockets de rede
  udp.begin(localUDPPort);
  multicastUdp.beginMulticast(WiFi.localIP(), IPAddress(224,1,1,1), multicastPort);
  tcpServer.begin();
  
  Serial.println("Aguardando descoberta do gateway via multicast...");
}

// --- Loop Principal ---
void loop() {
  unsigned long currentTime = millis();
  
  // Envia atualização de status periodicamente
  if (currentTime - prevTime >= msgInterval) {
    sendStatusUpdate();
    prevTime = currentTime;
  }

  // Mantém conexões e processa mensagens
  mantemConexoes();
  processDiscoveryMessages();
  processTCPCommands();
}

// --- Manutenção de Conexões ---
void mantemConexoes() {
  // Reconecta WiFi se necessário
  if (WiFi.status() != WL_CONNECTED) {
    conectaWiFi();
  }

  // Tenta descoberta ativa do gateway se ainda não encontrado
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
    multicastUdp.read(incomingPacket, 255);
    IPAddress remoteIP = multicastUdp.remoteIP();
    
    // Verifica se a mensagem veio de um IP válido (não broadcast)
    if (remoteIP[0] != 0 && remoteIP[0] != 255) {
      gatewayIP = remoteIP.toString();
      gatewayDiscovered = true;
      Serial.println("Gateway descoberto via multicast: " + gatewayIP);
      sendDiscoveryResponse();  // Registra-se no gateway
    }
  }
}

// --- Processamento de Comandos TCP ---
void processTCPCommands() {
  WiFiClient client = tcpServer.available();
  if (client) {
    Serial.printf("Comando TCP recebido de %s\n", client.remoteIP().toString().c_str());

    // Aguarda até ter pelo menos 1 byte para leitura
    while (!client.available()) delay(1);

    // --- Leitura do Varint (Tamanho da Mensagem) ---
    uint8_t varint[5];
    int varint_len = 0;
    while (client.available() && varint_len < 5) {
      varint[varint_len] = client.read();
      if ((varint[varint_len] & 0x80) == 0) break;  // Último byte do varint
      varint_len++;
    }

    // Decodifica o tamanho da mensagem do varint
    size_t msg_len = 0;
    for (int i = 0; i <= varint_len; i++) {
      msg_len |= (varint[i] & 0x7F) << (7 * i);
    }

    // Aguarda até o payload completo estar disponível
    while (client.available() < msg_len) delay(1);

    // --- Leitura do Payload Protocol Buffers ---
    uint8_t buffer[128] = {0};
    int bytes_read = client.readBytes(buffer, msg_len);

    Serial.printf("Bytes lidos: %d (esperado: %d)\n", bytes_read, (int)msg_len);
    Serial.print("Payload (hex): ");
    for (int i = 0; i < bytes_read && i < 20; i++) {
      Serial.printf("%02x ", buffer[i]);
    }
    Serial.println();

    // --- Decodificação Protocol Buffers ---
    char cmd_buffer[64] = {0};
    smartcity_devices_DeviceCommand command = smartcity_devices_DeviceCommand_init_zero;
    command.command_type.funcs.decode = &decode_string;
    command.command_type.arg = cmd_buffer;

    pb_istream_t stream = pb_istream_from_buffer(buffer, bytes_read);
    if (pb_decode(&stream, smartcity_devices_DeviceCommand_fields, &command)) {
      String commandType = String(cmd_buffer);
      Serial.printf("Comando decodificado: '%s'\n", commandType.c_str());
      deviceControl(commandType);  // Executa o comando
    } else {
      Serial.println("ERRO: Falha ao decodificar comando Protobuf!");
    }

    client.stop();
  }
}

// --- Controle do Dispositivo (Relé) ---
void deviceControl(String msg) {
  Serial.printf("Processando comando: '%s'\n", msg.c_str());

  if (msg == "TURN_ON") {
    // Liga o relé (HIGH = relé ativado)
    digitalWrite(pinRELE, HIGH);
    lampStatus = "ON";
    sendStatusUpdate();  // Envia confirmação do status
    Serial.println("RELÉ LIGADO - Status: ON");
  } else if (msg == "TURN_OFF") {
    // Desliga o relé (LOW = relé desativado)
    digitalWrite(pinRELE, LOW);
    lampStatus = "OFF";
    sendStatusUpdate();  // Envia confirmação do status
    Serial.println("RELÉ DESLIGADO - Status: OFF");
  } else {
    Serial.println("Comando não reconhecido.");
  }
}

// --- Envio de Atualização de Status (UDP) ---
void sendStatusUpdate() {
  // Cria mensagem DeviceUpdate com status atual
  smartcity_devices_DeviceUpdate msg = smartcity_devices_DeviceUpdate_init_zero;
  msg.device_id.funcs.encode = &encode_device_id;
  msg.device_id.arg = (void*)deviceID.c_str();
  msg.type = smartcity_devices_DeviceType_ALARM;
  msg.current_status = (lampStatus == "ON") ? smartcity_devices_DeviceStatus_ON : smartcity_devices_DeviceStatus_OFF;

  // Serializa e envia via UDP
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

// --- Solicitação de Descoberta (Broadcast) ---
void sendDiscoveryRequest() {
  // Envia mensagem de descoberta em broadcast
  String discoveryMsg = "DEVICE_DISCOVERY;ID:" + deviceID + ";TYPE:RELAY_ACTUATOR;IP:" + WiFi.localIP().toString();
  udp.beginPacket("255.255.255.255", multicastPort);
  udp.write((uint8_t*)discoveryMsg.c_str(), discoveryMsg.length());
  udp.endPacket();
  Serial.println("Solicitação de descoberta enviada");
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
    msg.type = smartcity_devices_DeviceType_ALARM;
    msg.ip_address.funcs.encode = &encode_ip_address;
    msg.ip_address.arg = (void*)deviceIP.c_str();
    msg.port = localUDPPort;
    msg.initial_state = smartcity_devices_DeviceStatus_OFF;
    msg.is_actuator = true;   // Este dispositivo é um atuador
    msg.is_sensor = false;    // Este dispositivo não é um sensor

    // Serializa a mensagem
    uint8_t buffer[128];
    pb_ostream_t stream = pb_ostream_from_buffer(buffer, sizeof(buffer));
    if (pb_encode(&stream, smartcity_devices_DeviceInfo_fields, &msg)) {
      // Codifica o tamanho como varint
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
      Serial.printf("DeviceInfo enviado para gateway (%d bytes)\n", (int)stream.bytes_written);
    }
  }
}
