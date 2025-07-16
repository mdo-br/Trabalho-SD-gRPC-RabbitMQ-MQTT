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
 * - Resposta a consultas de status via TCP
 * - Controle de relé para acionar cargas (lâmpadas, motores, etc.)
 * 
 * Protocolos:
 * - Protocol Buffers para serialização de mensagens
 * - TCP para registro, comandos e consultas de status
 * - UDP apenas para descoberta multicast
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
#include "smart_city.pb.h"
#include "pb.h"
#include <WiFiClient.h>

// --- Configurações de Hardware ---
#define pinRELE 3                    // Pino digital conectado ao módulo relé
String lampStatus = "OFF";           // Status atual do relé

// --- Configurações de Rede WiFi ---
const char* SSID = "homeoffice";           // Nome da rede WiFi - CONFIGURAR
const char* PASSWORD = "19071981";   // Senha da rede WiFi - CONFIGURAR

// --- Configurações de Rede do Sistema ---
const char* multicastIP = "224.1.1.1";  // Endereço multicast para descoberta
const int multicastPort = 5007;         // Porta multicast
const int localTCPPort = 8891;          // Porta TCP local para comandos

// --- Configurações do Dispositivo ---
const String ID_PCB = "001001002";      // ID único da placa - MODIFICAR SE NECESSÁRIO
const String deviceID = "relay_board_" + ID_PCB;  // ID completo do dispositivo

// --- Objetos de Rede ---
WiFiUDP multicastUdp;                  // Socket UDP multicast para descoberta
WiFiServer tcpServer(localTCPPort);    // Servidor TCP para comandos

// --- Variáveis de Estado ---
String gatewayIP = "";                 // IP do gateway descoberto
bool gatewayDiscovered = false;        // Flag indicando se o gateway foi encontrado
unsigned long lastDiscoveryAttempt = 0; // Última tentativa de descoberta
const unsigned long discoveryInterval = 5000; // 5 segundos
String deviceIP = "";                  // IP local do dispositivo

// --- Variáveis para registro TCP periódico ---
unsigned long lastRegisterAttempt = 0;
const unsigned long registerInterval = 5000; // 5 segundos

// --- Buffer global para comando recebido ---
#define CMD_BUFFER_SIZE 32
char command_buffer[CMD_BUFFER_SIZE];

// --- Callback para decodificação de string (nanopb) ---
bool decode_string(pb_istream_t *stream, const pb_field_t *field, void **arg) {
  char *buffer = (char *)(*arg);
  size_t length = stream->bytes_left;
  if (length >= CMD_BUFFER_SIZE) length = CMD_BUFFER_SIZE - 1;
  bool status = pb_read(stream, (pb_byte_t*)buffer, length);
  buffer[length] = '\0';
  return status;
}

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
  Serial.println("\n=== ESP8266 Relay Actuator Board ===");
  Serial.print("ID da Placa: ");
  Serial.println(ID_PCB);
  
  // Configura pino do relé como saída
  pinMode(pinRELE, OUTPUT);
  digitalWrite(pinRELE, LOW);  // Inicia com relé desligado
  
  // Conecta ao WiFi
  conectaWiFi();
  
  // Inicializa sockets de rede
  multicastUdp.beginMulticast(WiFi.localIP(), IPAddress(224,1,1,1), multicastPort);
  tcpServer.begin();
  
  Serial.println("Aguardando descoberta do gateway via multicast...");
}

// --- Loop Principal ---
void loop() {
  unsigned long currentTime = millis();
  
  // Registro TCP periódico
  if (gatewayDiscovered && (currentTime - lastRegisterAttempt >= registerInterval)) {
    sendDiscoveryResponse();
    lastRegisterAttempt = currentTime;
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

  // Aguardando descoberta do gateway via multicast
  if (!gatewayDiscovered && (millis() - lastDiscoveryAttempt >= discoveryInterval)) {
    Serial.println("Aguardando descoberta do gateway via multicast...");
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
    Serial.printf("[DEBUG] Pacote UDP recebido! Tamanho: %d bytes, de %s:%d\n", packetSize, multicastUdp.remoteIP().toString().c_str(), multicastUdp.remotePort());
    uint8_t incomingPacket[255];
    int len = multicastUdp.read(incomingPacket, 255);
    Serial.print("[DEBUG] Conteúdo (hex): ");
    for (int i = 0; i < len && i < 32; i++) {
      Serial.printf("%02X ", incomingPacket[i]);
    }
    Serial.println();
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
    // Aguarda até ter pelo menos 1 byte para leitura, com timeout
    unsigned long start = millis();
    while (!client.available() && millis() - start < 100) delay(1);
    if (!client.available()) {
      client.stop();
      return; // Timeout, não processa
    }
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
    // Aguarda até o payload completo estar disponível, com timeout
    start = millis();
    while (client.available() < msg_len && millis() - start < 100) delay(1);
    if (client.available() < msg_len) {
      client.stop();
      return; // Timeout, não processa
    }
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
    smartcity_devices_SmartCityMessage envelope = smartcity_devices_SmartCityMessage_init_zero;
    pb_istream_t istream = pb_istream_from_buffer(buffer, bytes_read);
    if (pb_decode(&istream, smartcity_devices_SmartCityMessage_fields, &envelope)) {
      if (envelope.message_type == smartcity_devices_MessageType_CLIENT_REQUEST && envelope.which_payload == smartcity_devices_SmartCityMessage_client_request_tag) {
        smartcity_devices_ClientRequest* req = &envelope.payload.client_request;
        // Responde tanto a comandos quanto a GET_DEVICE_STATUS
        if (req->has_command || req->type == smartcity_devices_ClientRequest_RequestType_GET_DEVICE_STATUS) {
          smartcity_devices_DeviceCommand* cmd = req->has_command ? &req->command : nullptr;
          if (cmd) {
            Serial.print("[DEBUG] Comando recebido: ");
            Serial.println(cmd->command_type);
            processCommand(String(cmd->command_type));
          } else {
            Serial.println("[DEBUG] Solicitação GET_DEVICE_STATUS recebida (sem comando)");
          }
          // --- Envia status atualizado como resposta TCP ---
          smartcity_devices_DeviceUpdate msg = smartcity_devices_DeviceUpdate_init_zero;
          msg.device_id.funcs.encode = &encode_device_id;
          msg.device_id.arg = (void*)deviceID.c_str();
          msg.type = smartcity_devices_DeviceType_RELAY;
          msg.current_status = (lampStatus == "ON") ? smartcity_devices_DeviceStatus_ON : smartcity_devices_DeviceStatus_OFF;
          // Cria envelope SmartCityMessage
          smartcity_devices_SmartCityMessage resp_envelope = smartcity_devices_SmartCityMessage_init_zero;
          resp_envelope.message_type = smartcity_devices_MessageType_DEVICE_UPDATE;
          resp_envelope.which_payload = smartcity_devices_SmartCityMessage_device_update_tag;
          resp_envelope.payload.device_update = msg;
          // Serializa e envia via TCP
          uint8_t resp_buffer[128];
          pb_ostream_t resp_stream = pb_ostream_from_buffer(resp_buffer, sizeof(resp_buffer));
          if (pb_encode(&resp_stream, smartcity_devices_SmartCityMessage_fields, &resp_envelope)) {
            // Codifica o tamanho como varint
            uint8_t resp_varint[5];
            size_t resp_varint_len = 0;
            size_t resp_len = resp_stream.bytes_written;
            do {
              uint8_t byte = resp_len & 0x7F;
              resp_len >>= 7;
              if (resp_len) byte |= 0x80;
              resp_varint[resp_varint_len++] = byte;
            } while (resp_len);
            client.write(resp_varint, resp_varint_len);
            client.write(resp_buffer, resp_stream.bytes_written);
            Serial.printf("[DEBUG] Status (envelope) enviado via TCP para %s (%d bytes)\n", client.remoteIP().toString().c_str(), (int)resp_stream.bytes_written);
          } else {
            Serial.println("[ERRO] Falha ao serializar status para resposta TCP!");
          }
        }
      } else {
        Serial.println("[ERRO] Envelope recebido não é CLIENT_REQUEST");
      }
    } else {
      Serial.println("ERRO: Falha ao decodificar envelope Protobuf!");
    }
    client.stop();
  }
}

// --- Controle do Dispositivo (Relé) ---
void processCommand(String msg) {
  Serial.printf("Processando comando: '%s'\n", msg.c_str());

  if (msg == "TURN_ON") {
    // Liga o relé (HIGH = relé ativado)
    digitalWrite(pinRELE, HIGH);
    lampStatus = "ON";
    Serial.println("RELÉ LIGADO - Status: ON");
    Serial.print("[DEBUG] digitalWrite(pinRELE, HIGH) executado. Valor lido no pino: ");
    Serial.println(digitalRead(pinRELE));
  } else if (msg == "TURN_OFF") {
    // Desliga o relé (LOW = relé desativado)
    digitalWrite(pinRELE, LOW);
    lampStatus = "OFF";
    Serial.println("RELÉ DESLIGADO - Status: OFF");
    Serial.print("[DEBUG] digitalWrite(pinRELE, LOW) executado. Valor lido no pino: ");
    Serial.println(digitalRead(pinRELE));
  } else {
    Serial.println("Comando não reconhecido.");
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
    msg.type = smartcity_devices_DeviceType_RELAY;
    msg.ip_address.funcs.encode = &encode_ip_address;
    msg.ip_address.arg = (void*)deviceIP.c_str();
    msg.port = localTCPPort;  // Porta TCP do dispositivo (8891)
    msg.initial_state = (lampStatus == "ON") ? smartcity_devices_DeviceStatus_ON : smartcity_devices_DeviceStatus_OFF;  // Estado atual do relé
    msg.is_actuator = true;   // Este dispositivo é um atuador
    msg.is_sensor = false;    // Este dispositivo não é um sensor

    // Cria envelope SmartCityMessage
    smartcity_devices_SmartCityMessage envelope = smartcity_devices_SmartCityMessage_init_zero;
    envelope.message_type = smartcity_devices_MessageType_DEVICE_INFO;
    envelope.which_payload = smartcity_devices_SmartCityMessage_device_info_tag;
    envelope.payload.device_info = msg;

    // Serializa a mensagem
    uint8_t buffer[128];
    pb_ostream_t stream = pb_ostream_from_buffer(buffer, sizeof(buffer));
    if (pb_encode(&stream, smartcity_devices_SmartCityMessage_fields, &envelope)) {
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
      Serial.printf("DeviceInfo (envelope) enviado para gateway (%d bytes)\n", (int)stream.bytes_written);
    }
  }
}
