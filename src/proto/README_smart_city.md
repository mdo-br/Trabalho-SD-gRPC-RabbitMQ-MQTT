# smart_city.proto — Protocolo IoT para Cidade Inteligente

Este arquivo define o protocolo de comunicação (Protocol Buffers) entre sensores, atuadores, gateway e clientes em um sistema de Cidade Inteligente.

## Estrutura Geral
- **Descoberta de dispositivos** (multicast UDP)
- **Registro e atualização de status** (TCP/UDP)
- **Comandos e controle** (TCP)
- **Consulta e monitoramento** (TCP)

---

## Principais Mensagens

### 1. DiscoveryRequest
Solicitação enviada pelo gateway para descobrir dispositivos na rede.
```json
{
  "gateway_ip": "192.168.1.100",
  "gateway_tcp_port": 12345,
  "gateway_udp_port": 12346
}
```

### 2. DeviceInfo
Resposta do dispositivo ao gateway, informando suas capacidades.
```json
{
  "device_id": "temp_board_001001001",
  "type": "TEMPERATURE_SENSOR",
  "ip_address": "192.168.1.101",
  "port": 5000,
  "initial_state": "ACTIVE",
  "is_actuator": false,
  "is_sensor": true,
  "capabilities": {"brand": "DHT11", "model": "basic"}
}
```

### 3. DeviceUpdate
Atualização periódica de status ou dados sensoriados.
```json
{
  "device_id": "temp_board_001001001",
  "type": "TEMPERATURE_SENSOR",
  "current_status": "ACTIVE",
  "temperature_humidity": {
    "temperature": 25.3,
    "humidity": 60.1
  },
  "frequency_ms": 5000
}
```

### 4. DeviceCommand
Comando enviado do gateway para um dispositivo.
```json
{
  "device_id": "relay_001001001",
  "type": "RELAY",
  "command_type": "TURN_ON",
  "command_value": "ON"
}
```

### 5. ClientRequest
Requisição do cliente para o gateway (exemplo: consultar status).
```json
{
  "type": "GET_DEVICE_STATUS",
  "target_device_id": "temp_board_001001001"
}
```

### 6. GatewayResponse
Resposta do gateway ao cliente.
```json
{
  "type": "DEVICE_STATUS_UPDATE",
  "device_status": {
    "device_id": "temp_board_001001001",
    "type": "TEMPERATURE_SENSOR",
    "current_status": "ACTIVE",
    "temperature_humidity": {
      "temperature": 25.3,
      "humidity": 60.1
    },
    "frequency_ms": 5000
  }
}
```

### 7. Envelope: SmartCityMessage
Todas as mensagens podem ser encapsuladas neste envelope para facilitar roteamento e parsing.
```json
{
  "message_type": "DEVICE_UPDATE",
  "device_update": {
    "device_id": "temp_board_001001001",
    "type": "TEMPERATURE_SENSOR",
    "current_status": "ACTIVE",
    "temperature_humidity": {
      "temperature": 25.3,
      "humidity": 60.1
    },
    "frequency_ms": 5000
  }
}
```

---

## Dicas de Integração
- Use o campo `oneof` para enviar apenas o tipo de dado relevante (ex: temperatura/umidade, qualidade do ar, etc).
- Sempre preencha o campo `device_id` para identificação única.
- O campo `frequency_ms` pode ser usado para informar a frequência de envio dos sensores.
- Utilize o envelope `SmartCityMessage` para padronizar a comunicação entre todos os módulos.

---

## Enums Importantes
- **DeviceType**: CAMERA, POST, TRAFFIC_LIGHT, AIR_QUALITY_SENSOR, TEMPERATURE_SENSOR, RELAY, etc.
- **DeviceStatus**: ON, OFF, IDLE, ACTIVE, ERROR, RED, GREEN

---

## Exemplo de Fluxo
1. Gateway envia `DiscoveryRequest` (UDP multicast)
2. Dispositivo responde com `DeviceInfo` (UDP ou TCP)
3. Dispositivo registra-se via TCP
4. Sensor envia `DeviceUpdate` (UDP) com dados sensoriados
5. Cliente consulta status via `ClientRequest` (TCP)
6. Gateway responde com `GatewayResponse` contendo os dados mais recentes

---

Para mais detalhes, consulte o arquivo `smart_city.proto` e os exemplos acima. 