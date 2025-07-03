# Dispositivos Java - Smart City

## Visão Geral

Este projeto contém **dois dispositivos simulados implementados em Java** para integração com o sistema distribuído Smart City:

1. **RelayActuator:** Atuador de relé que responde a comandos TCP e envia seu status via UDP.
2. **TemperatureHumiditySensor:** Sensor de temperatura e umidade que envia dados periodicamente via UDP e responde a comandos TCP.

Ambos os dispositivos implementam o mesmo protocolo utilizado por dispositivos físicos (como os ESP8266), usando Protocol Buffers (protobuf) para comunicação estruturada.

## Características Gerais

- **Linguagem:** Java 21+
- **Protocolo:** Protocol Buffers (Google Protobuf)
- **Comunicação:** TCP (comandos) + UDP (dados/status) + Multicast (descoberta)
- **Arquitetura:** Multithreaded com descoberta automática do Gateway

# RelayActuator - Implementação Java

## Visão Geral

Este é um atuador de relé implementado em Java que se integra ao sistema Smart City, seguindo o mesmo protocolo dos dispositivos ESP8266.

## Características

- **Linguagem:** Java 21+
- **Protocolo:** Protocol Buffers (Google Protobuf)
- **Comunicação:** TCP (comandos) + UDP (status) + Multicast (descoberta)
- **Arquitetura:** Multithreaded com threads separadas para cada funcionalidade

## Funcionalidades Comuns

Ambos os dispositivos:

- Descobrem o gateway automaticamente via multicast UDP
- Registram-se no gateway via conexão TCP (`DeviceInfo`)
- Usam mensagens `SmartCityMessage` baseadas em Protobuf

## Compilação e Execução com Maven



### Pré-requisitos

- Java 21 ou superior
- Maven 3.8+ instalado
- Protocol Buffers Compiler (`protoc`) v3.25.1

### 1. Verifique se o `protoc` está instalado

```bash
protoc --version
# Deve retornar: libprotoc 3.25.1
```

Se necessário, instale:

```bash
# Debian/Ubuntu
sudo apt install protobuf-compiler
```

### 2. Compilar o Projeto

```bash
# Compila e gera os .jar com dependências
mvn clean package
```

Ao final, dois arquivos serão gerados em `target/`:

- `relay-actuator.jar`
- `temperature-humidity-sensor.jar`

### 3. Executar o Atuador

```bash
java -jar target/relay-actuator.jar relay_java_001
```

### 4. Executar o Sensor

```bash
java -jar target/temperature-humidity-sensor.jar temp_sensor_001
```

## Configuração

### Portas e Endereços

```java
private static final String MULTICAST_GROUP = "224.1.1.1";
private static final int MULTICAST_PORT = 5007;
private static final int ACTUATOR_TCP_PORT = 6002;
```

### ID do Dispositivo

```bash
# Via argumento de linha de comando
java -jar relay-actuator.jar relay_java_001

# Ou ID automático (UUID)
java -jar relay-actuator.jar
```

## Logs e Debug

O sistema usa `java.util.logging` para logs estruturados:

```
INFO: Relé Atuador relay_java_001 inicializado com estado: OFF
INFO: Relé Atuador aguardando requisições de descoberta multicast...
INFO: Relé Atuador aguardando comandos TCP...
INFO: Relé Atuador relay_java_001 enviou DeviceInfo (envelope) para o Gateway
INFO: Relé Atuador relay_java_001 recebeu comando TCP: TURN_ON
INFO: RELÉ relay_java_001 LIGADO!
```

## Integração com o Sistema

### Compatibilidade

- ✅ **Gateway Python:** Totalmente compatível
- ✅ **Cliente Python:** Funciona com comandos existentes
- ✅ **Protocol Buffers:** Mesmo protocolo dos ESP8266
- ✅ **Descoberta:** Mesmo sistema multicast

### Comandos Suportados

```python
# Via cliente Python
client.send_device_command('relay_java_001', 'TURN_ON')
client.send_device_command('relay_java_001', 'TURN_OFF')
client.get_device_status('relay_java_001')
```

### Problemas Comuns

1. **Erro de compilação do Protobuf:**
   ```bash
   # Verifique se protoc está instalado corretamente
   protoc --version
   ```

2. **Erro de rede:**
   ```bash
   # Verifique se as portas estão livres
   netstat -tuln | grep 6002
   ```

3. **Gateway não descoberto:**
   ```bash
   # Verifique tráfego multicast
   sudo tcpdump -i any udp port 5007
   ```

### Logs de Debug

```bash
# Executar com logs detalhados
java -Djava.util.logging.config.file=logging.properties -jar relay-actuator.jar
```

---

## TemperatureHumiditySensor - Implementação Java

Este é um sensor de temperatura e umidade desenvolvido em Java que segue o mesmo protocolo dos dispositivos ESP8266.

### Características

- **Linguagem:** Java 21+
- **Protocolo:** Protocol Buffers (Google Protobuf)
- **Comunicação:** TCP (comandos) + UDP (dados sensoriados) + Multicast (descoberta)
- **Arquitetura:** Multithreaded com agendamento periódico de envio de dados

### Funcionalidades

1. **Descoberta Automática**
   - Recebe mensagens multicast UDP do Gateway
   - Responde com `DeviceInfo` via TCP

2. **Envio de Dados via UDP**
   - Envia `DeviceUpdate` com temperatura e umidade a cada N segundos (configurável)
   - Apenas no estado `ACTIVE`

3. **Comandos TCP**
   - `TURN_ACTIVE`: inicia envio periódico
   - `TURN_IDLE`: pausa envio
   - `SET_FREQ`: define frequência de envio (em ms)
   
### Execução

Após compilar com:

```bash
mvn clean package
```

Execute o sensor com um ID:

```bash
java -jar target/temperature-humidity-sensor.jar temp_sensor_001
```

### Logs

```
INFO: Sensor temp_sensor_001 inicializado com estado: ACTIVE
INFO: Sensor temp_sensor_001 aguardando requisições de descoberta multicast...
INFO: Sensor temp_sensor_001 enviou DeviceInfo (envelope) para o Gateway
INFO: Sensor temp_sensor_001 enviou DeviceUpdate UDP (envelope): Temp=23.4°C, Hum=45.2%
```

### Exemplo de Comando Recebido

```json
{
  "commandType": "SET_FREQ",
  "commandValue": "30000"
}
```

O sensor passará a enviar dados a cada 30 segundos.

---