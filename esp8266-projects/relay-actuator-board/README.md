# Atuador de Relé - ESP8266

## Descrição

Este é um atuador de relé para controle de lâmpada, baseado no ESP8266 e adaptado para a arquitetura de cidade inteligente com Protocol Buffers. O dispositivo permite ligar e desligar uma lâmpada remotamente através do Gateway.

## Características

- **Hardware**: ESP8266 (NodeMCU v2)
- **Tipo**: Atuador (Relé)
- **Comunicação**: Protocol Buffers + TCP/UDP
- **Descoberta**: Multicast automático
- **Controle**: Ligar/Desligar lâmpada

## Diferenças do Sensor de Temperatura

| Aspecto | Sensor de Temperatura | Atuador de Relé |
|---------|----------------------|-----------------|
| **Tipo** | Sensor (leitura) | Atuador (controle) |
| **Porta UDP** | 8890 | 8891 |
| **ID da Placa** | 001001001 | 001001002 |
| **DeviceType** | TEMPERATURE_SENSOR | ALARM |
| **is_actuator** | false | true |
| **is_sensor** | true | false |
| **Dados** | Temperatura/Umidade | Status ON/OFF |

## Hardware

### Conexões
- **Pino 3**: Controle do relé
- **VCC**: 5V para o relé
- **GND**: Terra comum

### Esquema
```
ESP8266 Pin 3 ──→ Relé ──→ Lâmpada
                │
                └──→ 5V, GND
```

## Configuração

### 1. Configurações WiFi
```cpp
const char* ssid = "SUA_REDE_WIFI";
const char* password = "SUA_SENHA_WIFI";
```

### 2. ID da Placa
```cpp
const String ID_PCB = "001001002";  // MODIFICAR AQUI
```

### 3. Pino do Relé
```cpp
#define PIN_RELAY 3  // PINO DIGITAL UTILIZADO PELO RELÉ
```

## Funcionamento

### 1. Inicialização
- Conecta ao WiFi
- Aguarda descoberta do Gateway via multicast
- Registra-se no Gateway como atuador

### 2. Operação Normal
- Envia status atual a cada 30 segundos
- Aguarda comandos do Gateway
- Controla relé conforme comandos recebidos

### 3. Controle do Relé
```cpp
void controlRelay(bool turnOn) {
  if (turnOn) {
    digitalWrite(PIN_RELAY, HIGH);
    relayStatus = true;
    Serial.println("Relé LIGADO - Lâmpada ON");
  } else {
    digitalWrite(PIN_RELAY, LOW);
    relayStatus = false;
    Serial.println("Relé DESLIGADO - Lâmpada OFF");
  }
}
```

## Mensagens Protocol Buffers

### DeviceInfo (Registro)
```protobuf
DeviceInfo {
  device_id: "relay_board_001001002"
  type: ALARM
  ip_address: "192.168.0.18"
  port: 8891
  initial_state: OFF
  is_actuator: true
  is_sensor: false
}
```

### DeviceUpdate (Status)
```protobuf
DeviceUpdate {
  device_id: "relay_board_001001002"
  type: ALARM
  current_status: ON  // ou OFF
}
```

## Instalação e Teste

### 1. Compilar
```bash
arduino-cli compile --fqbn esp8266:esp8266:nodemcuv2 .
```

### 2. Upload
```bash
arduino-cli upload -p /dev/ttyUSB0 --fqbn esp8266:esp8266:nodemcuv2 .
```

### 3. Monitor Serial
```bash
arduino-cli monitor -p /dev/ttyUSB0 --fqbn esp8266:esp8266:nodemcuv2 --config baudrate=115200
   ```

## Saídas Esperadas

### Inicialização
```
=== Relay Actuator Board ESP8266 ===
Placa desenvolvida - Atuador de Relé para Lâmpada
ID da Placa: 001001002
Conectado na rede: brisa-3604536  IP obtido: 192.168.0.18
Aguardando descoberta do gateway via multicast...
```

### Descoberta do Gateway
```
Mensagem multicast recebida: 20 bytes
Gateway descoberto via multicast: 192.168.0.13
[DEBUG] DeviceInfo a ser enviado:
  device_id: relay_board_001001002
  type: 6
  ip_address: 192.168.0.18
  port: 8891
  initial_state: 2
  is_actuator: 1
  is_sensor: 0
DeviceInfo enviado via TCP para 192.168.0.13:12345 (XX bytes)
```

### Controle do Relé
```
Relé LIGADO - Lâmpada ON
Status Update enviado via UDP para 192.168.0.13:12346 (XX bytes) - Status: ON
```

## Troubleshooting

### Problema: Relé não responde
- Verificar conexões elétricas
- Confirmar tensão de alimentação (5V)
- Testar pino com LED

### Problema: Não conecta ao Gateway
- Verificar configurações WiFi
- Confirmar que o Gateway está rodando
- Verificar multicast na rede

### Problema: Comandos não chegam
- Verificar se o dispositivo está registrado
- Confirmar porta UDP (8891)
- Verificar firewall da rede

## Segurança

⚠️ **ATENÇÃO**: Este dispositivo controla corrente elétrica!
- Use relé adequado para a potência da lâmpada
- Isole corretamente as conexões elétricas
- Teste em ambiente controlado antes de usar em produção 