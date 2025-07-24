# Temperature Sensor Board - ESP8266

Este diretório contém o firmware para o sensor de temperatura ESP8266 com DHT11, totalmente integrado ao sistema Smart City via MQTT, conforme o código real.

## Características Específicas da Placa

- **Sensor Real:** DHT11 conectado ao pino D3
- **ID Único:** Configurável via variável `device_id`
- **Leitura Inteligente:** Envia dados periodicamente e quando há mudança
- **Protocolo:** MQTT para dados, comandos e respostas
- **Comunicação:** MQTT (dados, comandos, respostas), Multicast UDP (descoberta), TCP (registro inicial)

## Diferenças do Sensor Anterior

| Característica | Sensor Anterior | Sensor Atual |
|----------------|-----------------|--------------|
| **Sensor** | DHT11 Real | DHT11 Real |
| **ID** | `esp8266_temp_01` | `temp_sensor_esp_002` |
| **Tópico MQTT** | Não usava | `smart_city/sensors/temp_sensor_esp_002` |
| **Intervalo** | 5s fixo | 5s padrão, configurável via comando |
| **Protocolo** | UDP/TCP | MQTT |
| **Lógica** | Sempre envia | Envia periodicamente e sob comando |

## Configuração

### 1. Configurar ID do Dispositivo
Edite a variável `device_id` no código:
```cpp
const char* device_id = "temp_sensor_esp_002";  // MODIFICAR SE NECESSÁRIO
```

### 2. Configurar WiFi
Edite as credenciais WiFi:
```cpp
const char* ssid = "SUA_REDE_WIFI";
const char* password = "SUA_SENHA_WIFI";
```

### 3. Verificar Pino do Sensor
O DHT11 está configurado para o pino D3:
```cpp
#define DHTPIN D3  // PINO DIGITAL UTILIZADO PELO SENSOR
```

## Instalação e Upload

### Pré-requisitos
- [PlatformIO](https://platformio.org/) ou Arduino IDE instalado
- Placa ESP8266 (NodeMCU, Wemos D1 Mini, etc.)
- Sensor DHT11 conectado ao pino D3

### Passos
1. **Acesse o diretório:**
   ```sh
   cd esp8266-projects/temperature-sensor-board
   ```
2. **Compile o firmware:**
   ```sh
   pio run
   ```
3. **Faça upload para o ESP8266:**
   ```sh
   pio run --target upload
   ```
4. **Abra o monitor serial:**
   ```sh
   pio device monitor
   ```

## Logs Esperados

### Inicialização
```
=== Temperature Sensor Board ESP8266 (MQTT) ===
Device ID: temp_sensor_esp_002
Data Topic: smart_city/sensors/temp_sensor_esp_002
Command Topic: smart_city/commands/sensors/temp_sensor_esp_002
Response Topic: smart_city/commands/sensors/temp_sensor_esp_002/response
WiFi conectado!
Endereço IP: 192.168.x.x
Aguardando descoberta do gateway via multicast...
```

### Descoberta e Registro
```
Pacote multicast recebido de 192.168.x.x:5007
Gateway encontrado: 192.168.x.x:12346
Broker MQTT encontrado: 192.168.x.x:1883
Registro enviado com sucesso!
```

### Leitura e Envio de Dados
```
[DEBUG] Leitura DHT11: Temperatura = 23.5 °C | Umidade = 65.2 %
✓ Dados MQTT enviados (SENSOR REAL): {"device_id":"temp_sensor_esp_002","temperature":23.5,"humidity":65.2,"status":"ACTIVE","timestamp":123456,"version":"mqtt_real","data_source":"dht11"}
```

### Comando Recebido
```
Mensagem MQTT recebida no tópico: smart_city/commands/sensors/temp_sensor_esp_002
Mensagem: {"command_type":"TURN_IDLE","command_value":"","request_id":"req456"}
Comando recebido: TURN_IDLE
[DEBUG] Processado - Success: true, Message: Sensor em modo idle
Resposta enviada: {"device_id":"temp_sensor_esp_002","request_id":"req456","success":true,"message":"Sensor em modo idle","status":"IDLE","temperature":23.5,"humidity":65.2,"timestamp":123456}
```

## Verificação no Sistema

### Listar Dispositivos (Gateway/Cliente)
```bash
--- Dispositivos Conectados ---
  ID: temp_sensor_esp_002, Tipo: TEMPERATURE_SENSOR, IP: 192.168.x.x, Status: ACTIVE
```

### Consultar Status
```bash
--- Status de 'temp_sensor_esp_002' ---
  Tipo: TEMPERATURE_SENSOR
  Status Atual: ACTIVE
  Temperatura: 23.5°C
  Umidade: 65.2%
```

## Características Técnicas

### Lógica de Envio de Dados
O sensor implementa a seguinte lógica:
1. **Leitura:** Lê temperatura e umidade do DHT11
2. **Envio:** Envia dados via MQTT periodicamente (intervalo configurável)
3. **Comando:** Recebe comandos via MQTT para alterar frequência, ativar/desativar, consultar status
4. **Formato:** Mensagens JSON via MQTT

### Estrutura de Mensagens

- **Registro:** DeviceInfo via TCP (descoberta/registro)
- **Dados:** JSON via MQTT no tópico `smart_city/sensors/temp_sensor_esp_002`
- **Comandos:** JSON via MQTT no tópico `smart_city/commands/sensors/temp_sensor_esp_002`
- **Respostas:** JSON via MQTT no tópico `smart_city/commands/sensors/temp_sensor_esp_002/response`

### Pinagem

- **DHT11:** Pino D3
- **WiFi:** Interno do ESP8266
- **Serial:** 115200 baud

## Troubleshooting

### Problemas Comuns
- **DHT11 não lê:** Verificar conexões e pino D3
- **WiFi não conecta:** Verificar credenciais
- **Gateway não descoberto:** Verificar se Gateway está rodando e multicast habilitado
- **MQTT não conecta:** Verificar broker, IP e porta
- **Comandos não funcionam:** Verificar tópicos e formato JSON

## Expansão

Para adicionar mais sensores à placa:
1. **Novos Pinos:** Adicionar definições de pinos
2. **Novas Leituras:** Implementar funções de leitura
3. **Novos Dados:** Adicionar campos nas mensagens JSON/MQTT
4. **Lógica:** Adaptar a lógica de envio e comandos