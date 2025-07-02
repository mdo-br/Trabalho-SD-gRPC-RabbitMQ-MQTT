# RelayActuator - Implementação Java

## Visão Geral

Este é um atuador de relé implementado em Java que se integra ao sistema Smart City, seguindo o mesmo protocolo dos dispositivos ESP8266.

## Características

- **Linguagem:** Java 8+
- **Protocolo:** Protocol Buffers (Google Protobuf)
- **Comunicação:** TCP (comandos) + UDP (status) + Multicast (descoberta)
- **Arquitetura:** Multithreaded com threads separadas para cada funcionalidade

## Funcionalidades

### 1. Descoberta Automática
- Escuta pacotes multicast UDP na porta 5007
- Descobre automaticamente o gateway na rede
- Registra-se via TCP no gateway

### 2. Comandos TCP
- Recebe comandos `TURN_ON` e `TURN_OFF`
- Processa comandos em threads separadas
- Responde com confirmação de status

### 3. Status UDP
- Envia status atual via UDP a cada 30 segundos
- Notifica mudanças de estado imediatamente
- Usa envelope SmartCityMessage

## Estrutura do Código

```java
public class RelayActuator {
    // Threads principais:
    // 1. listenForDiscoveryRequests() - Descoberta multicast
    // 2. listenForTcpCommands() - Comandos TCP
    // 3. startStatusScheduler() - Status periódico
}
```

## Compilação e Execução

### Pré-requisitos
- Java 8 ou superior
- Gradle (opcional, para build automatizado)
- Protocol Buffers compiler (`protoc`)

### 1. Compilar Protocol Buffers
```bash
# Gerar classes Java do proto
protoc --java_out=../proto/generated --proto_path=../proto ../proto/smart_city.proto
```

### 2. Compilar com Gradle
```bash
# Compilar o projeto
./gradlew build

# Executar o atuador
./gradlew run --args="relay_java_001"
```

### 3. Compilar Manualmente
```bash
# Compilar
javac -cp ".:../proto/generated:protobuf-java-3.21.7.jar" RelayActuator.java

# Executar
java -cp ".:../proto/generated:protobuf-java-3.21.7.jar" com.smartcity.actuators.RelayActuator relay_java_001
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
java RelayActuator relay_java_001

# Ou ID automático (UUID)
java RelayActuator
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

## Vantagens da Implementação Java

### 1. Robustez
- Gerenciamento automático de memória
- Tratamento de exceções robusto
- Logging estruturado

### 2. Performance
- Multithreading nativo
- Sockets Java otimizados
- Protocol Buffers eficientes

### 3. Manutenibilidade
- Código orientado a objetos
- Separação clara de responsabilidades
- Fácil extensão

### 4. Portabilidade
- Roda em qualquer JVM
- Não depende de hardware específico
- Fácil deploy em servidores

## Troubleshooting

### Problemas Comuns

1. **Erro de compilação protobuf:**
   ```bash
   # Verificar se protoc está instalado
   protoc --version
   ```

2. **Erro de rede:**
   ```bash
   # Verificar se as portas estão livres
   netstat -tuln | grep 6002
   ```

3. **Gateway não descoberto:**
   ```bash
   # Verificar multicast
   sudo tcpdump -i any udp port 5007
   ```

### Logs de Debug
```bash
# Executar com logs detalhados
java -Djava.util.logging.config.file=logging.properties RelayActuator
```

## Expansão

Para adicionar novos tipos de atuadores:

1. **Criar nova classe** estendendo a funcionalidade base
2. **Implementar comandos específicos** no método `handleTcpCommand`
3. **Adicionar novos campos** no Protocol Buffer se necessário
4. **Configurar novo DeviceType** no enum

## Comparação com ESP8266

| Aspecto | Java | ESP8266 |
|---------|------|---------|
| **Recursos** | Ilimitados | Limitados |
| **Rede** | Estável | Pode desconectar |
| **Memória** | Abundante | Escassa |
| **Energia** | Alta | Baixa |
| **Custo** | Alto | Baixo |
| **Portabilidade** | Baixa | Alta |

## Conclusão

A implementação Java oferece uma alternativa robusta e escalável para atuadores no sistema Smart City, especialmente útil para ambientes de produção onde confiabilidade e recursos são prioritários. 