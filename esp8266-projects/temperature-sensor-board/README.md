# Temperature Sensor Board - ESP8266

Este diretório contém o firmware para o sensor de temperatura da **placa desenvolvida**, baseado no código original com DHT11 e adaptado para a arquitetura do sistema de cidade inteligente.

## Características Específicas da Placa

- **Sensor Real:** DHT11 conectado ao pino digital 3
- **ID Único:** Configurável via variável `ID_PCB`
- **Leitura Inteligente:** Envia dados apenas quando há mudança nos valores
- **Protocolo:** Protocol Buffers (nanopb) em vez de MQTT
- **Comunicação:** TCP (registro) + UDP (dados sensoriados) + Multicast (descoberta)

## Diferenças do Sensor Anterior

| Característica | Sensor Anterior | Placa Desenvolvida |
|----------------|-----------------|-------------------|
| **Sensor** | Simulado | DHT11 Real |
| **ID** | `esp8266_temp_01` | `temp_board_001001001` |
| **Porta UDP** | 8889 | 8890 |
| **Intervalo** | 5s fixo | 5s com mudança |
| **Protocolo** | Protocol Buffers | Protocol Buffers |
| **Lógica** | Sempre envia | Envia apenas se mudou |

## Configuração

### 1. Configurar ID da Placa

Edite a variável `ID_PCB` no código:

```cpp
const String ID_PCB = "001001001";  // MODIFICAR AQUI
```

### 2. Configurar WiFi

Edite as credenciais WiFi:

```cpp
const char* ssid = "SUA_REDE_WIFI";
const char* password = "SUA_SENHA_WIFI";
```

### 3. Verificar Pino do Sensor

O DHT11 está configurado para o pino 3:

```cpp
#define DHTPIN 3  // PINO DIGITAL UTILIZADO PELO SENSOR
```

## Instalação e Upload

### Pré-requisitos

- [PlatformIO](https://platformio.org/) instalado
- Placa ESP8266 desenvolvida com DHT11
- Sensor DHT11 conectado ao pino 3

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
=== Temperature Sensor Board ESP8266 ===
Placa desenvolvida - Sensor de Temperatura DHT11
ID da Placa: 001001001
Conectando-se SUA_REDE_WIFI
Conectado na rede: SUA_REDE_WIFI  IP obtido: 192.168.x.x
Aguardando descoberta do gateway via multicast...
```

### Descoberta e Registro
```
Mensagem multicast recebida: 21 bytes
Gateway descoberto via multicast: 192.168.x.x
DeviceInfo enviado via TCP para 192.168.x.x:12345 (30 bytes)
```

### Leitura do Sensor
```
Temperatura = 23.50 °C      |       Umidade = 65.20
DeviceUpdate enviado via UDP para 192.168.x.x:12346 (41 bytes)
```

## Verificação no Sistema

### Listar Dispositivos
```bash
# No cliente CLI
Escolha uma opção: 1

--- Dispositivos Conectados ---
  ID: temp_board_001001001, Tipo: TEMPERATURE_SENSOR, IP: 192.168.x.x:8890, Status: ACTIVE
```

### Consultar Status
```bash
Escolha uma opção: 4
ID do Dispositivo: temp_board_001001001

--- Status de 'temp_board_001001001' ---
  Tipo: TEMPERATURE_SENSOR
  Status Atual: ACTIVE
  Temperatura: 23.5°C
  Umidade: 65.2%
```

## Características Técnicas

### Lógica de Envio de Dados

O sensor implementa a mesma lógica do código original:

1. **Leitura:** Lê temperatura e umidade do DHT11
2. **Comparação:** Compara com valores anteriores
3. **Envio:** Envia apenas se houve mudança
4. **Formato:** Protocol Buffers em vez de MQTT

### Estrutura de Mensagens

- **DeviceInfo:** Registro inicial via TCP
- **DeviceUpdate:** Dados sensoriados via UDP
- **Protocol:** Compatível com o sistema principal

### Pinagem

- **DHT11:** Pino 3 (configurável)
- **WiFi:** Interno do ESP8266
- **Serial:** 115200 baud

## Troubleshooting

### Problemas Comuns

- **DHT11 não lê:** Verificar conexões e pino
- **WiFi não conecta:** Verificar credenciais
- **Gateway não descoberto:** Verificar se Gateway está rodando
- **Dados não aparecem:** Verificar se há mudança nos valores

### Logs de Debug

```bash
# Verificar multicast
sudo tcpdump -i any udp port 5007

# Verificar dados UDP
sudo tcpdump -i any udp port 12346

# Verificar registro TCP
sudo tcpdump -i any tcp port 12345
```

## Expansão

Para adicionar mais sensores à placa:

1. **Novos Pinos:** Adicionar definições de pinos
2. **Novas Leituras:** Implementar funções de leitura
3. **Novos Dados:** Adicionar campos no Protocol Buffer
4. **Lógica:** Adaptar a lógica de envio

## Compatibilidade

- ✅ **Gateway Python:** Compatível
- ✅ **Cliente CLI:** Compatível
- ✅ **Protocol Buffers:** Compatível
- ✅ **Sistema Principal:** Totalmente integrado 