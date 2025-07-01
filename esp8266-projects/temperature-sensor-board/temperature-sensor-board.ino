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
 * - Recebimento de comandos TCP (SET_FREQ, ACTIVE, IDLE)
 * 
 * Protocolos:
 * - Protocol Buffers para serialização de mensagens
 * - TCP para registro no gateway e comandos
 * - UDP para dados sensoriados e descoberta multicast
 * 
 * Hardware:
 * - ESP8266 (NodeMCU, Wemos D1 Mini, etc.)
 * - Sensor DHT11 conectado ao pino 3
 * - Biblioteca DHT para leitura do sensor
 */

#include <ESP8266WiFi.h>
#include <WiFiUdp.h>
#include <WiFiServer.h>
#include "pb_encode.h"
#include "pb_decode.h"
#include "smart_city.pb.h"
#include "pb.h"
#include <WiFiClient.h>
#include <DHT.h>

// --- Configurações do Sensor DHT11 ---
#define DHTTYPE DHT11                // Tipo do sensor (DHT11 ou DHT22)
#define DHTPIN 3                     // Pino digital conectado ao sensor
DHT dht(DHTPIN, DHTTYPE);            // Objeto do sensor DHT

// --- Configurações de Rede WiFi ---
const char* ssid = "ATLab";           // Nome da rede WiFi - CONFIGURAR
const char* password = "@TLab#0506";   // Senha da rede WiFi - CONFIGURAR

// --- Configurações de Rede do Sistema ---
const char* multicastIP = "224.1.1.1";  // Endereço multicast para descoberta
const int multicastPort = 5007;         // Porta multicast
const int gatewayUDPPort = 12346;       // Porta UDP do gateway
const int localUDPPort = 8890;          // Porta UDP local (diferente de outros dispositivos)
const int localTCPPort = 5000;          // Porta TCP local para comandos

// --- Configurações do Dispositivo ---
const String ID_PCB = "001001002";      // ID único da placa - MODIFICAR SE NECESSÁRIO
const String deviceID = "temp_board_" + ID_PCB;  // ID completo do dispositivo

// --- Objetos de Rede ---
WiFiUDP udp;                           // Socket UDP para comunicação
WiFiUDP multicastUdp;                  // Socket UDP multicast para descoberta
WiFiServer tcpServer(localTCPPort);    // Servidor TCP para comandos

// --- Variáveis de Dados do Sensor ---
float temperature = 0.0;               // Temperatura atual em °C
float humidity = 0.0;                  // Umidade atual em %
float temperatureAnt = 0.0;            // Temperatura anterior (para detectar mudanças)
float humidityAnt = 0.0;               // Umidade anterior (para detectar mudanças)
unsigned long lastSensorRead = 0;      // Última leitura do sensor
unsigned long sensorInterval = 5000;   // Intervalo entre leituras (5 segundos) - CONFIGURÁVEL

// --- Variáveis de Estado ---
String gatewayIP = "";                 // IP do gateway descoberto
bool gatewayDiscovered = false;        // Flag indicando se o gateway foi encontrado
unsigned long lastDiscoveryAttempt = 0; // Última tentativa de descoberta
const unsigned long discoveryInterval = 30000; // Intervalo entre tentativas (30s)
String deviceIP = "";                  // IP local do dispositivo
bool deviceRegistered = false;         // Flag para evitar registro repetido
bool sensorActive = true;              // Estado do sensor (ACTIVE/IDLE)

// --- Variáveis para registro TCP periódico ---
unsigned long lastRegisterAttempt = 0;
const unsigned long registerInterval = 30000; // 30 segundos

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
  tcpServer.begin();
  
  Serial.println("Aguardando descoberta do gateway via multicast...");
}

// --- Loop Principal ---
void loop() {
  unsigned long currentTime = millis();
  // Reconecta WiFi se necessário
  if (WiFi.status() != WL_CONNECTED) {
    connectToWiFi();
  }
  
  // Processa mensagens de descoberta multicast
  processDiscoveryMessages();
  
  // Tenta descoberta ativa se ainda não encontrou o gateway
  if (!gatewayDiscovered && (currentTime - lastDiscoveryAttempt >= discoveryInterval)) {
    sendDiscoveryRequest();
    lastDiscoveryAttempt = currentTime;
  }
  
  // Lê sensor periodicamente se gateway foi descoberto e sensor está ativo
  if (gatewayDiscovered && sensorActive && (currentTime - lastSensorRead >= sensorInterval)) {
    Serial.printf("Lendo sensor (ativo, intervalo: %d ms)\n", sensorInterval);
    readSensor();
    lastSensorRead = currentTime;
  } else if (gatewayDiscovered && !sensorActive && (currentTime - lastSensorRead >= 10000)) {
    // Log a cada 10 segundos quando sensor está pausado
    static unsigned long lastPauseLog = 0;
    if (currentTime - lastPauseLog >= 10000) {
      Serial.println("Sensor PAUSADO - Não lendo/enviando dados");
      lastPauseLog = currentTime;
    }
  }
  
  // Processa comandos TCP
  processTCPCommands();
  
  // Registro TCP periódico
  if (gatewayDiscovered && (currentTime - lastRegisterAttempt >= registerInterval)) {
    sendDiscoveryResponse();
    lastRegisterAttempt = currentTime;
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
      
      // Registra-se no gateway apenas uma vez
      if (!deviceRegistered) {
        sendDiscoveryResponse();
        deviceRegistered = true;
      }
    }
  }
}

// --- Processamento de Comandos TCP ---
void processTCPCommands() {
  WiFiClient client = tcpServer.available();
  if (client) {
    Serial.println("\n[INFO] Cliente TCP conectado para comando");
    while (client.connected()) {
      if (client.available()) {
        // Lê o tamanho da mensagem (varint)
        uint32_t len = 0;
        uint8_t shift = 0;
        while (true) {
          int b = client.read();
          if (b == -1) break;
          len |= (b & 0x7F) << shift;
          if (!(b & 0x80)) break;
          shift += 7;
        }
        if (len == 0) {
          Serial.println("[ERRO] Tamanho do envelope inválido");
          break;
        }
        // Lê o buffer do envelope
        uint8_t buffer[256];
        size_t readBytes = client.read(buffer, len);
        if (readBytes != len) {
          Serial.println("[ERRO] Falha ao ler envelope completo");
          break;
        }
        // Decodifica o envelope SmartCityMessage
        smartcity_devices_SmartCityMessage envelope = smartcity_devices_SmartCityMessage_init_zero;
        pb_istream_t istream = pb_istream_from_buffer(buffer, len);
        if (!pb_decode(&istream, smartcity_devices_SmartCityMessage_fields, &envelope)) {
          Serial.println("[ERRO] Falha ao decodificar envelope SmartCityMessage");
          break;
        }
        // Verifica se é um comando para o dispositivo
        if (envelope.message_type == smartcity_devices_MessageType_CLIENT_REQUEST && envelope.which_payload == smartcity_devices_SmartCityMessage_client_request_tag) {
          smartcity_devices_ClientRequest* req = &envelope.payload.client_request;
          if (req->has_command) {
            smartcity_devices_DeviceCommand* cmd = &req->command;
            Serial.print("[DEBUG] Comando recebido: ");
            Serial.println(cmd->command_type);
            processCommand(
                String(cmd->command_type),
                String(cmd->command_value)
            );
            // --- Envia status atualizado como resposta TCP ---
            smartcity_devices_DeviceUpdate msg = smartcity_devices_DeviceUpdate_init_zero;
            msg.device_id.funcs.encode = &encode_device_id;
            msg.device_id.arg = (void*)deviceID.c_str();
            msg.type = smartcity_devices_DeviceType_TEMPERATURE_SENSOR;
            msg.current_status = sensorActive ? smartcity_devices_DeviceStatus_ACTIVE : smartcity_devices_DeviceStatus_IDLE;
            msg.which_data = smartcity_devices_DeviceUpdate_frequency_ms_tag;
            msg.data.frequency_ms = sensorInterval;
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
      }
    }
    client.stop();
    Serial.println("[INFO] Cliente TCP desconectado");
  }
}

// --- Processamento de Comandos ---
void processCommand(String commandType, String commandValue) {
  Serial.println("\n--- EXECUTANDO COMANDO ---");
  Serial.printf("Tipo: '%s' | Valor: '%s'\n", commandType.c_str(), commandValue.c_str());
  Serial.printf("Status atual antes: %s\n", sensorActive ? "ACTIVE" : "IDLE");

  if (commandType == "SET_FREQ") {
    // Define nova frequência de envio (em milissegundos)
    int newInterval = commandValue.toInt();
    Serial.printf("Tentando alterar frequência para: %d ms\n", newInterval);
    
    if (newInterval >= 1000 && newInterval <= 60000) {  // Entre 1s e 60s
      sensorInterval = newInterval;
      Serial.printf("SUCESSO: Frequência alterada para %d ms\n", sensorInterval);
      sendStatusUpdate();  // Envia confirmação do status
    } else {
      Serial.printf("ERRO: Frequência inválida %d. Deve estar entre 1000 e 60000 ms.\n", newInterval);
    }
  } else if (commandType == "TURN_ACTIVE") {
    // Ativa o envio de dados sensoriados
    sensorActive = true;
    Serial.println("SUCESSO: Sensor ATIVADO (TURN_ACTIVE) - Enviando dados sensoriados");
    sendStatusUpdate();  // Envia confirmação do status
  } else if (commandType == "TURN_IDLE") {
    // Pausa o envio de dados sensoriados
    sensorActive = false;
    Serial.println("SUCESSO: Sensor PAUSADO (TURN_IDLE) - Não enviando dados sensoriados");
    sendStatusUpdate();  // Envia confirmação do status
  } else {
    Serial.printf("ERRO: Comando não reconhecido: '%s'\n", commandType.c_str());
  }
  
  Serial.printf("Status final: %s\n", sensorActive ? "ACTIVE" : "IDLE");
  Serial.println("--- FIM DO COMANDO ---\n");
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

  // Verifica se os valores são válidos (não NaN)
  if (!isnan(temperature) && !isnan(humidity)) {
    Serial.printf("Temperatura = %.1f °C | Umidade = %.1f %%\n", temperature, humidity);
    
    // Envia dados apenas se houve mudança (otimização de rede)
    if (temperature != temperatureAnt || humidity != humidityAnt) {
      sendSensorData();  // Envia dados para o gateway
    }
  } else {
    Serial.println("Falha na leitura do sensor DHT!");
  }
}

// --- Envio de Dados Sensoriados (UDP) ---
void sendSensorData() {
  // Cria mensagem DeviceUpdate com dados do sensor
  smartcity_devices_DeviceUpdate msg = smartcity_devices_DeviceUpdate_init_zero;
  msg.device_id.funcs.encode = &encode_device_id;
  msg.device_id.arg = (void*)deviceID.c_str();
  msg.type = smartcity_devices_DeviceType_TEMPERATURE_SENSOR;
  msg.current_status = sensorActive ? smartcity_devices_DeviceStatus_ACTIVE : smartcity_devices_DeviceStatus_IDLE;
  // Configura dados de temperatura e umidade usando oneof
  msg.which_data = smartcity_devices_DeviceUpdate_temperature_humidity_tag;
  msg.data.temperature_humidity.temperature = temperature;
  msg.data.temperature_humidity.humidity = humidity;
  // Preenche também a frequência de envio (oneof frequency_ms)
  // (Opcional: pode enviar em outro DeviceUpdate, mas aqui é útil para debug)
  // msg.which_data = smartcity_devices_DeviceUpdate_frequency_ms_tag;
  // msg.data.frequency_ms = sensorInterval;
  
  // Envia também a frequência atual em uma mensagem separada
  // (isso garante que o gateway sempre tenha a frequência atualizada)
  smartcity_devices_DeviceUpdate freqMsg = smartcity_devices_DeviceUpdate_init_zero;
  freqMsg.device_id.funcs.encode = &encode_device_id;
  freqMsg.device_id.arg = (void*)deviceID.c_str();
  freqMsg.type = smartcity_devices_DeviceType_TEMPERATURE_SENSOR;
  freqMsg.current_status = sensorActive ? smartcity_devices_DeviceStatus_ACTIVE : smartcity_devices_DeviceStatus_IDLE;
  freqMsg.which_data = smartcity_devices_DeviceUpdate_frequency_ms_tag;
  freqMsg.data.frequency_ms = sensorInterval;
  
  // Serializa e envia a mensagem de frequência via UDP
  uint8_t freqBuffer[128];
  pb_ostream_t freqStream = pb_ostream_from_buffer(freqBuffer, sizeof(freqBuffer));
  if (pb_encode(&freqStream, smartcity_devices_DeviceUpdate_fields, &freqMsg)) {
    udp.beginPacket(gatewayIP.c_str(), gatewayUDPPort);
    udp.write(freqBuffer, freqStream.bytes_written);
    udp.endPacket();
    Serial.printf("Frequência enviada via UDP: %d ms (%d bytes)\n", sensorInterval, freqStream.bytes_written);
  }
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

// --- Envio de Atualização de Status (UDP) ---
void sendStatusUpdate() {
  smartcity_devices_DeviceUpdate update = smartcity_devices_DeviceUpdate_init_zero;
  update.device_id.funcs.encode = &encode_device_id;
  update.device_id.arg = (void*)deviceID.c_str();
  update.type = smartcity_devices_DeviceType_TEMPERATURE_SENSOR;
  update.current_status = sensorActive ? smartcity_devices_DeviceStatus_ACTIVE : smartcity_devices_DeviceStatus_IDLE;
  update.which_data = smartcity_devices_DeviceUpdate_frequency_ms_tag;
  update.data.frequency_ms = sensorInterval;
  // Cria envelope SmartCityMessage
  smartcity_devices_SmartCityMessage envelope = smartcity_devices_SmartCityMessage_init_zero;
  envelope.message_type = smartcity_devices_MessageType_DEVICE_UPDATE;
  envelope.payload.device_update = update;
  envelope.which_payload = smartcity_devices_SmartCityMessage_device_update_tag;
  // Serializa e envia via UDP
  uint8_t buffer[256];
  pb_ostream_t stream = pb_ostream_from_buffer(buffer, sizeof(buffer));
  if (pb_encode(&stream, smartcity_devices_SmartCityMessage_fields, &envelope) && gatewayDiscovered) {
    udp.beginPacket(gatewayIP.c_str(), gatewayUDPPort);
    udp.write(buffer, stream.bytes_written);
    udp.endPacket();
    Serial.printf("Status (envelope) enviado via UDP para %s:%d (%d bytes)\n", gatewayIP.c_str(), gatewayUDPPort, (int)stream.bytes_written);
  }
}

// --- Resposta ao Gateway com DeviceInfo (TCP) ---
void sendDiscoveryResponse() {
  WiFiClient client;
  if (client.connect(gatewayIP.c_str(), 12345)) {
    deviceIP = WiFi.localIP().toString();

    // Cria mensagem DeviceInfo para registro
    smartcity_devices_DeviceInfo deviceInfo = smartcity_devices_DeviceInfo_init_zero;
    deviceInfo.device_id.funcs.encode = &encode_device_id;
    deviceInfo.device_id.arg = (void*)deviceID.c_str();
    deviceInfo.type = smartcity_devices_DeviceType_TEMPERATURE_SENSOR;
    deviceInfo.ip_address.funcs.encode = &encode_ip_address;
    deviceInfo.ip_address.arg = (void*)deviceIP.c_str();
    deviceInfo.port = localTCPPort;
    deviceInfo.initial_state = smartcity_devices_DeviceStatus_ACTIVE;
    deviceInfo.is_actuator = false;
    deviceInfo.is_sensor = true;

    // Cria envelope SmartCityMessage
    smartcity_devices_SmartCityMessage envelope = smartcity_devices_SmartCityMessage_init_zero;
    envelope.message_type = smartcity_devices_MessageType_DEVICE_INFO;
    envelope.payload.device_info = deviceInfo;
    envelope.which_payload = smartcity_devices_SmartCityMessage_device_info_tag;

    // Serializa a mensagem
    uint8_t buffer[256];
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
      client.write(varint, varint_len);
      client.write(buffer, stream.bytes_written);
      client.stop();
      Serial.printf("DeviceInfo (envelope) enviado para gateway (%d bytes)\n", (int)stream.bytes_written);
    }
  }
}