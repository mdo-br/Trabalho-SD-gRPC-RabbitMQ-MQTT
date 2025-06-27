# Smart City Sensor ESP8266

Este diretório contém o firmware para sensores inteligentes baseados em ESP8266, integrados ao sistema distribuído de cidade inteligente. O firmware simula um sensor de temperatura e umidade, comunicando-se com o Gateway central via UDP multicast para descoberta e TCP para envio de dados, utilizando Protocol Buffers (nanopb) para serialização de mensagens.

## Status do Sistema

✅ **ESP8266 100% Funcional** - Integrado e testado com o sistema completo:

- ✅ **Descoberta:** Recebe multicast e descobre o Gateway automaticamente
- ✅ **Registro:** Envia DeviceInfo via TCP para se registrar no Gateway
- ✅ **Dados Sensoriados:** Envia DeviceUpdate via UDP a cada 5 segundos
- ✅ **Protocol Buffers:** Serialização funcionando com nanopb
- ✅ **Integração:** Compatível com Gateway Python e Cliente CLI
- ✅ **Status:** Aparece como ACTIVE no sistema

## Visão Geral

- **Plataforma:** ESP8266 (NodeMCU v2)
- **Framework:** Arduino (via PlatformIO)
- **Comunicação:** UDP multicast (descoberta), TCP (registro), UDP (dados sensoriados)
- **Serialização:** Protocol Buffers (nanopb)
- **Integração:** Gateway Python, clientes CLI/Web, dispositivos Java

## Estrutura dos Arquivos

- `smart-city-sensor.ino`: Firmware principal do sensor ESP8266.
- `smart_city_esp8266.proto`: Definição das mensagens Protocol Buffers utilizadas.
- `pb_*.h/c`: Arquivos da biblioteca nanopb para serialização.
- `platformio.ini`: Configuração do ambiente PlatformIO, dependências e parâmetros de build/upload.
- `legacy/`: Versão anterior do firmware, sem nanopb (serialização manual).

## Funcionalidades

- Conexão automática à rede WiFi.
- Descoberta do Gateway via UDP multicast.
- Registro inicial via TCP (DeviceInfo).
- Envio periódico de leituras simuladas de temperatura e umidade via UDP.
- Serialização dos dados usando Protocol Buffers (nanopb).
- Comunicação compatível com o Gateway Python do sistema.

## Fluxo de Comunicação

1. **Descoberta:** ESP8266 escuta mensagens multicast do Gateway
2. **Registro:** Envia DeviceInfo via TCP para se registrar
3. **Dados:** Envia DeviceUpdate via UDP a cada 5 segundos com temperatura/umidade

## Mensagens Protocol Buffers

O arquivo [`smart_city_esp8266.proto`](smart_city_esp8266.proto) define as mensagens trocadas entre o sensor e o gateway:

```proto
syntax = "proto3";
package smartcity.devices;

enum DeviceType { UNKNOWN_DEVICE = 0; TEMPERATURE_SENSOR = 5; }
enum DeviceStatus { UNKNOWN_STATUS = 0; ACTIVE = 4; }

message TemperatureHumidityData {
  double temperature = 1;
  double humidity = 2;
}

message DeviceUpdate {
  string device_id = 1;
  DeviceType type = 2;
  DeviceStatus current_status = 3;
  TemperatureHumidityData temperature_humidity = 4;
}

message DeviceInfo {
  string device_id = 1;
  DeviceType type = 2;
  string ip_address = 3;
  int32 port = 4;
  DeviceStatus initial_state = 5;
  bool is_actuator = 6;
  bool is_sensor = 7;
}
```

### Exemplo de fluxo de comunicação

1. **Descoberta:** O sensor escuta mensagens multicast do gateway e responde com suas informações.
2. **Registro:** Envia DeviceInfo via TCP para se registrar no Gateway.
3. **Envio de dados:** Periodicamente, o sensor envia uma mensagem `DeviceUpdate` via UDP para o gateway, contendo temperatura e umidade atuais.

## Dependências

As dependências são gerenciadas automaticamente pelo PlatformIO:

- `ESP8266WiFi`
- `WiFiUdp`
- `ArduinoJson`
- `Adafruit DHT sensor library`
- `Adafruit Unified Sensor`
- `nanopb` (Protocol Buffers para sistemas embarcados)

Veja o arquivo [`platformio.ini`](platformio.ini) para detalhes.

## Instalação e Upload

### Pré-requisitos

- [PlatformIO](https://platformio.org/) instalado (CLI ou VSCode)
- Placa NodeMCU ESP8266 conectada via USB

### Passos

1. **Clone o repositório e acesse o diretório:**
   ```sh
   cd esp8266-projects/smart-city-sensor
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

## Configurações Importantes

- **SSID da rede WiFi:** Altere a variável `ssid` no início do arquivo `.ino` para sua rede.
- **Senha:** Ajuste a variável `password` se necessário.
- **Endereço multicast e portas:** Os valores padrão são compatíveis com o gateway Python do projeto.

## Teste e Verificação

### Logs Esperados no Monitor Serial

```
=== Smart City Sensor ESP8266 (nanopb) ===
Conectando ao WiFi: SUA_REDE_WIFI
WiFi conectado!
IP: 192.168.x.x
Aguardando descoberta do gateway via multicast...
Mensagem multicast recebida: 21 bytes
Gateway descoberto via multicast: 192.168.x.x
DeviceInfo enviado via TCP para 192.168.x.x:12345 (30 bytes)
Temperatura: 23.5°C, Umidade: 60.0%
DeviceUpdate enviado via UDP para 192.168.x.x:12346 (41 bytes)
```

### Verificação no Cliente

```bash
# No cliente CLI
Escolha uma opção: 1

--- Dispositivos Conectados ---
  ID: esp8266_temp_01, Tipo: TEMPERATURE_SENSOR, IP: 192.168.x.x:8889, Status: ACTIVE

Escolha uma opção: 4
ID do Dispositivo: esp8266_temp_01

--- Status de 'esp8266_temp_01' ---
  Tipo: TEMPERATURE_SENSOR
  Status Atual: ACTIVE
  Temperatura: 23.5°C
  Umidade: 60.0%
```

## Observações

- O firmware simula leituras de temperatura/umidade. Para uso real, substitua a função `readSensor()` para ler de um sensor físico (ex: DHT22).
- O diretório `legacy/` contém uma versão anterior do firmware, sem uso de nanopb, útil para referência ou fallback.
- O sensor é compatível com o protocolo e arquitetura definidos no projeto principal, podendo ser expandido para outros tipos de sensores/atuadores.

## Expansão

Para criar novos dispositivos ESP8266:
- Adapte o tipo de sensor/atuador e as mensagens Protocol Buffers conforme necessário.
- Gere os arquivos `.pb.h/.pb.c` usando o `nanopb` a partir do `.proto`.
- Siga o mesmo padrão de descoberta e comunicação.

## Troubleshooting

### Problemas Comuns

- **WiFi não conecta:** Verificar credenciais no código
- **Gateway não descoberto:** Verificar se o Gateway está rodando e multicast funcionando
- **Dados não aparecem:** Verificar se o ESP8266 está enviando via UDP na porta correta
- **Erro de compilação:** Verificar se nanopb está instalado

### Logs Úteis

```bash
# Verificar multicast na rede
sudo tcpdump -i any udp port 5007

# Verificar dados UDP
sudo tcpdump -i any udp port 12346

# Verificar registro TCP
sudo tcpdump -i any tcp port 12345
``` 