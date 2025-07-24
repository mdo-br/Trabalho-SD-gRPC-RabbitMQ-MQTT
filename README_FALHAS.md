# Tratamento de Falhas no Sistema Smart City

Este documento descreve as estratégias de tolerância e tratamento de falhas implementadas no projeto Smart City, que utiliza gRPC, RabbitMQ/MQTT e comunicação TCP/UDP para monitoramento e controle distribuído de dispositivos IoT.

## Estratégias Gerais

O sistema foi projetado para operar de forma robusta em ambientes distribuídos e sujeitos a falhas de rede, dispositivos ou software. As principais estratégias incluem:

- **Redescobrimento automático:** Dispositivos IoT (sensores e atuadores) "escutam" descoberta periódica do gateway via multicast UDP. Caso percam a conexão ou mudem de rede, podem redescobrir os parâmetros necessários sem intervenção manual.
- **Registro periódico:** Dispositivos respodem mensagens de descoberta ao gateway a cada 30 segundos. Isso permite ao gateway detectar dispositivos offline e manter uma lista atualizada dos ativos.
- **Timeouts e reconexão:** Todas as conexões TCP e gRPC utilizam timeouts configuráveis. Em caso de falha ou ausência de resposta, o sistema tenta reconectar ou reporta o erro de forma clara.
- **Detecção de falhas:** O gateway monitora o status dos dispositivos registrados. Se um dispositivo não renovar seu registro dentro do intervalo esperado, é considerado offline e removido da lista de ativos.
- **Mensagens de erro detalhadas:** APIs e serviços gRPC retornam mensagens de erro informativas, facilitando o diagnóstico por operadores e desenvolvedores.
- **Persistência e filas:** O uso de RabbitMQ/MQTT garante que mensagens de sensores sejam armazenadas em filas persistentes, evitando perda de dados em caso de indisponibilidade temporária do gateway ou broker.

## Exemplos de Tratamento de Falhas


### 1. Falha de Conexão TCP/gRPC
- O servidor gRPC utiliza timeouts ao conectar-se a atuadores. Se a conexão falhar, retorna um status de erro ao gateway e registra o evento no log.
- Dispositivos tentam registrar automaticamente ao gateway em caso de falha.

**Exemplo de código (Python):**
```python
# src/grpc_server/actuator_bridge_server.py
def send_tcp_command_to_device(device_ip: str, device_port: int, command: smart_city_pb2.DeviceCommand) -> smart_city_pb2.DeviceUpdate:
    try:
        with socket.create_connection((device_ip, device_port), timeout=TIMEOUT_TCP) as sock:
            # ...envio do comando...
            data = envelope.SerializeToString()
            sock.sendall(encode_varint(len(data)) + data)
            # ...leitura da resposta...
    except Exception as e:
        logger.error(f"Erro ao comunicar com dispositivo {device_ip}:{device_port}: {e}")
        raise

class ActuatorServiceServicer(actuator_service_pb2_grpc.ActuatorServiceServicer):
    def LigarDispositivo(self, request, context):
        try:
            command = smart_city_pb2.DeviceCommand()
            command.device_id = request.device_id
            command.command_type = "TURN_ON"
            command.command_value = ""
            device_update = send_tcp_command_to_device(request.ip, request.port, command)
            return actuator_service_pb2.StatusResponse(
                status="ON",
                message=f"Dispositivo {request.device_id} ligado com sucesso. Status: {smart_city_pb2.DeviceStatus.Name(device_update.current_status)}"
            )
        except Exception as e:
            logger.error(f"Erro ao ligar dispositivo {request.device_id}: {e}")
            return actuator_service_pb2.StatusResponse(
                status="ERROR",
                message=f"Erro ao ligar dispositivo: {str(e)}"
            )
```


### 2. Falha de Registro de Dispositivo
- Se um dispositivo não conseguir registrar-se no gateway, ele tenta novamente após um intervalo.
- O gateway remove dispositivos que não renovam o registro, evitando comandos para dispositivos offline.

**Exemplo de código (ESP8266 C++):**
```cpp
// relay-actuator-board.ino
// Registro TCP periódico no loop principal
void loop() {
  unsigned long currentTime = millis();
  // Registro TCP periódico
  if (gatewayDiscovered && (currentTime - lastRegisterAttempt >= registerInterval)) {
    sendDiscoveryResponse();
    lastRegisterAttempt = currentTime;
  }
  // ...outros processos...
}

void sendDiscoveryResponse() {
  WiFiClient client;
  if (client.connect(gatewayIP.c_str(), 12345)) {
    // ...monta e envia DeviceInfo...
    client.stop();
    Serial.printf("DeviceInfo (envelope) enviado para gateway\n");
  }
}
```


### 3. Falha na Comunicação MQTT
**Trecho de código: Descoberta do gateway e configuração dinâmica do MQTT**
```cpp
void discoverGateway() {
  int packetSize = multicastUdp.parsePacket();
  if (packetSize > 0) {
    // ...leitura do pacote multicast...
    pb_istream_t stream = pb_istream_from_buffer(buffer, len);
    smartcity_devices_SmartCityMessage message = smartcity_devices_SmartCityMessage_init_zero;
    bool ok = pb_decode(&stream, smartcity_devices_SmartCityMessage_fields, &message);
    if (ok) {
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
        // ...registro no gateway...
    }
  }
}
```
Esse trecho mostra como o sensor ESP8266 descobre o gateway via multicast UDP, extrai o IP e porta do broker MQTT da mensagem recebida e configura dinamicamente os parâmetros de conexão MQTT. Isso permite que o sensor se adapte automaticamente a mudanças de rede ou broker, aumentando a resiliência do sistema.
- Sensores e gateway implementam lógica de reconexão ao broker MQTT.
- Mensagens não entregues são armazenadas em filas persistentes pelo RabbitMQ, garantindo entrega futura.

**Exemplo de código real (ESP8266 C++):**
```cpp
void sendSensorDataMQTT() {
  Serial.println("[DEBUG] sendSensorDataMQTT() chamada!");
  // Verificar se o cliente MQTT está conectado
  if (!mqttClient.connected()) {
    Serial.println("Cliente MQTT não conectado, pulando envio de dados...");
    return;
  }
  // ...monta mensagem JSON...
  bool publishResult = mqttClient.publish(dataTopic.c_str(), jsonString.c_str());
  Serial.print("[DEBUG] Resultado da publicação MQTT: ");
  Serial.println(publishResult ? "SUCESSO" : "FALHA");
  if (!publishResult) {
    Serial.print("[DEBUG] Estado do cliente MQTT: ");
    Serial.println(mqttClient.state());
  }
}
```
Esse trecho, presente no sensor de temperatura ESP8266, verifica se o cliente MQTT está conectado antes de tentar enviar dados. Se não estiver conectado, o envio é abortado e uma mensagem de erro é registrada. Após tentar publicar, o resultado é verificado e, em caso de falha, o estado do cliente MQTT é exibido para diagnóstico.


### 4. Falha de Dispositivo
- O gateway detecta dispositivos inativos e pode alertar operadores via API ou frontend.
- Dispositivos podem ser reiniciados ou reconfigurados remotamente via comandos gRPC/MQTT.

**Exemplo de código (Python):**
```python
# src/gateway/smart_city_gateway.py
def register_device(device_info):
    with device_lock:
        device_id = device_info.device_id
        device_data = {
            'id': device_id,
            'last_seen': time.time(),
            # ...outros campos...
        }
        connected_devices[device_id] = device_data
        # ...

def remove_inactive_devices():
    now = time.time()
    with device_lock:
        for dev_id, dev in list(connected_devices.items()):
            if now - dev['last_seen'] > 60:
                logger.info(f"Dispositivo {dev_id} removido por inatividade.")
                del connected_devices[dev_id]
```

## Boas Práticas Adotadas
- Uso de logs detalhados para todas as operações críticas.
- Retorno de status e mensagens claras em todas as APIs.
- Separação de responsabilidades entre componentes para facilitar isolamento e recuperação de falhas.
- Testes automatizados para cenários de falha e recuperação.

## Conclusão


## Exemplos de Mensagens de Falha (smart_city.proto)

### 1. Falha ao enviar comando para dispositivo offline
```json
{
  "message_type": "GATEWAY_RESPONSE",
  "gateway_response": {
    "type": "ERROR",
    "message": "Falha ao enviar comando: dispositivo não encontrado ou offline.",
    "command_status": "FAILED"
  }
}
```

### 2. Falha de atualização de status do dispositivo
```json
{
  "message_type": "DEVICE_UPDATE",
  "device_update": {
    "device_id": "relay_001001001",
    "type": "RELAY",
    "current_status": "ERROR",
    "custom_config_status": "Erro ao processar comando: parâmetro inválido."
  }
}
```

### 3. Falha de registro de dispositivo
```json
{
  "message_type": "GATEWAY_RESPONSE",
  "gateway_response": {
    "type": "ERROR",
    "message": "Registro não realizado: dispositivo já registrado ou dados inválidos."
  }
}
```

Esses exemplos seguem os tipos e campos definidos no arquivo smart_city.proto, facilitando o tratamento automatizado e o diagnóstico por desenvolvedores.

---

O sistema Smart City foi projetado para ser resiliente, tolerante a falhas e fácil de manter. As estratégias de tratamento de falhas garantem alta disponibilidade e confiabilidade, mesmo em ambientes de rede instáveis ou com dispositivos sujeitos a desconexões frequentes.
