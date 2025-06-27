# Projetos ESP8266 - Cidade Inteligente

Este diretório contém projetos para ESP8266 que se integram ao sistema de cidade inteligente, implementando sensores e atuadores reais.

## Projetos Disponíveis

### 1. Smart City Sensor
- **Diretório:** [`smart-city-sensor/`](smart-city-sensor/)
- **Firmware:** [`smart-city-sensor.ino`](smart-city-sensor/smart-city-sensor.ino)
- **Função:** Sensor de temperatura/umidade
- **Comunicação:** Descoberta via UDP multicast, envio de dados via TCP
- **Protocolo:** Protocol Buffers reais (nanopb)
- **Documentação detalhada:** [Leia o README específico do sensor](smart-city-sensor/README.md)

## Configuração do Ambiente

### Pré-requisitos
- PlatformIO instalado (CLI ou VSCode)
- ESP8266 Core instalado
- Arduino CLI opcional
- Cursor configurado com extensões Arduino/C++ (opcional)

### Configuração do PATH
Adicione ao seu `~/.bashrc` ou `~/.zshrc`:
```bash
export PATH="$PATH:/home/mdo/Projetos/Trabalho-SD/bin"
```

## Compilação e Upload

### Usando PlatformIO (Recomendado)
```bash
cd smart-city-sensor
pio run --target upload
pio device monitor
```

### Usando Arduino CLI (para projetos legados)
```bash
# Compilar
arduino-cli compile --fqbn esp8266:esp8266:nodemcuv2 smart-city-sensor

# Upload (conecte o ESP8266 via USB)
arduino-cli upload --fqbn esp8266:esp8266:nodemcuv2 -p /dev/ttyUSB0 smart-city-sensor

# Monitor serial
arduino-cli monitor -p /dev/ttyUSB0
```

## Configuração de Rede

1. **Editar credenciais WiFi** no arquivo `.ino`:
   ```cpp
   const char* ssid = "SUA_REDE_WIFI";
   const char* password = "SUA_SENHA_WIFI";
   ```

2. **Configuração de multicast e portas:**
   Os valores padrão são compatíveis com o gateway Python do projeto principal.

## Integração com o Sistema

### Fluxo de Comunicação
1. ESP8266 conecta ao WiFi
2. Descobre o Gateway via UDP multicast
3. Envia dados de sensor via TCP usando Protocol Buffers
4. Responde a comandos de descoberta multicast

### Protocolo de Mensagens
- **Dados de Sensor:** Protocol Buffers (nanopb)
- **Descoberta:** Mensagens compatíveis com o gateway Python
- **Comandos:** Expansível para controle de atuadores

## Próximos Passos

1. **Adicionar sensores físicos** (DHT22, etc.)
2. **Criar atuadores** (relés, LEDs, etc.)
3. **Adicionar autenticação** e segurança

## Troubleshooting

### Problemas Comuns
- **Erro de compilação:** Verificar se ESP8266 Core está instalado
- **Upload falha:** Verificar permissões da porta USB
- **WiFi não conecta:** Verificar credenciais e sinal
- **Comunicação falha:** Verificar IP do Gateway e firewall

### Logs Úteis
```bash
# Verificar dispositivos USB
ls /dev/ttyUSB*

# Verificar permissões
sudo usermod -a -G dialout $USER

# Monitorar rede
sudo tcpdump -i any udp port 8888
``` 