# Sensor de Temperatura com Comandos TCP

## Visão Geral

O sensor de temperatura ESP8266 foi modificado para receber comandos TCP, similar ao atuador de relé. Agora o sensor pode ser controlado remotamente para alterar sua frequência de envio de dados e pausar/reativar o envio de dados sensoriados.

## Funcionalidades Adicionadas

### 1. Servidor TCP
- **Porta:** 5000 (configurável via `localTCPPort`)
- **Protocolo:** Protocol Buffers com delimitador varint
- **Funcionalidade:** Recebe comandos do gateway via TCP

### 2. Comandos Suportados

#### `SET_FREQ <valor_ms>`
- **Descrição:** Define a frequência de envio de dados sensoriados
- **Parâmetro:** Valor em milissegundos (1000-60000 ms)
- **Exemplo:** `SET_FREQ 10000` (envia dados a cada 10 segundos)

#### `ACTIVE`
- **Descrição:** Ativa o envio de dados sensoriados
- **Parâmetro:** Nenhum
- **Comportamento:** Sensor volta a enviar dados via UDP

#### `IDLE`
- **Descrição:** Pausa o envio de dados sensoriados
- **Parâmetro:** Nenhum
- **Comportamento:** Sensor para de enviar dados via UDP

## Modificações no Código

### 1. Inclusões Adicionais
```cpp
#include <WiFiServer.h>
#include "pb_decode.h"
```

### 2. Novas Variáveis
```cpp
WiFiServer tcpServer(localTCPPort);    // Servidor TCP para comandos
unsigned long sensorInterval = 5000;   // Intervalo configurável
bool deviceRegistered = false;         // Evita registro repetido
bool sensorActive = true;              // Estado do sensor
```

### 3. Novas Funções

#### `processTCPCommands()`
- Processa comandos TCP recebidos
- Decodifica mensagens Protocol Buffers
- Chama `processCommand()` para executar comandos

#### `processCommand(String commandType, String commandValue)`
- Executa os comandos específicos
- Valida parâmetros (ex: frequência entre 1s e 60s)
- Envia confirmação via UDP

#### `sendStatusUpdate()`
- Envia atualização de status via UDP
- Inclui dados de temperatura/umidade atuais
- Status: ACTIVE ou IDLE

### 4. Modificações no Loop Principal
```cpp
// Lê sensor apenas se ativo
if (gatewayDiscovered && sensorActive && (millis() - lastSensorRead >= sensorInterval)) {
  readSensor();
  lastSensorRead = millis();
}

// Processa comandos TCP
processTCPCommands();
```

### 5. Registro no Gateway
- **Porta TCP:** Agora registra a porta TCP (5000) em vez da UDP
- **is_actuator:** Definido como `true` (pode receber comandos)
- **is_sensor:** Mantido como `true` (também é sensor)

## Como Usar

### 1. Compilação
```bash
cd esp8266-projects/temperature-sensor-board
pio run
```

### 2. Upload para ESP8266
```bash
pio run --target upload
```

### 3. Envio de Comandos via Cliente

#### Usando o Cliente Python
```python
from smart_city_client import SmartCityClient

client = SmartCityClient('192.168.0.20', 12345)

# Alterar frequência para 10 segundos
client.send_device_command('temp_board_001001001', 'SET_FREQ', '10000')

# Pausar envio de dados
client.send_device_command('temp_board_001001001', 'IDLE')

# Reativar envio de dados
client.send_device_command('temp_board_001001001', 'ACTIVE')
```

#### Usando o Script de Exemplo
```bash
cd src/client-test
python3 temperature_sensor_commands.py
```

## Monitoramento Serial

O sensor envia mensagens detalhadas via Serial para debug:

```
=== Temperature Sensor Board ESP8266 ===
ID da Placa: 001001001
WiFi conectado. IP: 192.168.0.100
Aguardando descoberta do gateway via multicast...
Gateway descoberto via multicast: 192.168.0.20
DeviceInfo enviado via TCP (45 bytes)
Comando TCP recebido de 192.168.0.20
Comando decodificado: 'SET_FREQ' com valor: '10000'
Processando comando: 'SET_FREQ' com valor: '10000'
Frequência alterada para 10000 ms
Status enviado via UDP para 192.168.0.20:12346 (52 bytes)
```

## Estados do Sensor

### ACTIVE
- ✅ Lê sensor DHT11 periodicamente
- ✅ Envia dados sensoriados via UDP
- ✅ Responde a comandos TCP
- ✅ Status: `smartcity_devices_DeviceStatus_ACTIVE`

### IDLE
- ✅ Lê sensor DHT11 periodicamente
- ❌ **NÃO** envia dados sensoriados via UDP
- ✅ Responde a comandos TCP
- ✅ Status: `smartcity_devices_DeviceStatus_IDLE`

## Configurações

### Frequência de Envio
- **Padrão:** 5000 ms (5 segundos)
- **Mínimo:** 1000 ms (1 segundo)
- **Máximo:** 60000 ms (60 segundos)
- **Configurável:** Via comando `SET_FREQ`

### Portas
- **TCP (Comandos):** 5000
- **UDP (Dados):** 8890
- **Multicast:** 224.1.1.1:5007

## Compatibilidade

- ✅ **Gateway:** Funciona com gateway existente
- ✅ **Cliente:** Funciona com cliente existente
- ✅ **Protocol Buffers:** Usa mesma definição de protocolo
- ✅ **Descoberta:** Mantém descoberta multicast

## Troubleshooting

### Sensor não responde a comandos
1. Verifique se o gateway está enviando comandos para a porta TCP correta (5000)
2. Confirme se o sensor está registrado como atuador (`is_actuator = true`)
3. Verifique logs do Serial para erros de decodificação

### Dados não são enviados
1. Verifique se o sensor está no estado `ACTIVE`
2. Confirme se a frequência está configurada corretamente
3. Verifique se o gateway foi descoberto

### Erro de compilação
1. Certifique-se de que os arquivos nanopb estão atualizados
2. Verifique se todas as bibliotecas estão instaladas
3. Confirme se o ESP8266 core está instalado 