# Makefile - Guia de Uso do Sistema Smart City

Este documento descreve o uso do Makefile para compilar, testar e executar o sistema Smart City IoT distribuído.

## Visão Geral da Arquitetura

O sistema Smart City é distribuído em duas partes principais:

### Infraestrutura (Raspberry Pi 3)
- **RabbitMQ MQTT Broker** (porta 1883)
- **Servidor gRPC** (porta 50051)
- **Gateway** (coordenador do sistema) - pode rodar em qualquer máquina

### Dispositivos (Qualquer máquina)
- **Sensores Java** (MQTT)
- **Atuadores Java** (gRPC)
- **ESP8266** (MQTT)
- **Clientes de teste**

## Comandos Essenciais

### Configuração Inicial

```bash
# Configuração completa na Raspberry Pi 3
make setup-local INFRA=1

# Configuração em máquina de desenvolvimento
make setup-local
```

### Comandos de Infraestrutura (Raspberry Pi 3)

**Importante:** Use sempre `INFRA=1` para comandos de infraestrutura!

```bash
# Configurar RabbitMQ com plugin MQTT
make rabbitmq INFRA=1

# Executar servidor gRPC
make run-grpc INFRA=1

# Testar conexão MQTT
make test-mqtt INFRA=1

# Validar sistema completo
make validate-v3 INFRA=1

# Monitorar sistema
make monitor-system INFRA=1

# Demo completa
make demo INFRA=1
```

### Comandos de Dispositivos (Qualquer máquina)

```bash
# Executar gateway
make run-gateway

# Executar sensor Java
make run-sensor

# Executar atuador Java
make run-actuator

# Executar atuador com ID e porta específicos
make run-actuator ACTUATOR_ID=relay_002 ACTUATOR_PORT=6003

# Executar cliente de teste
make run-client

# Executar API REST
make run-api

# Monitorar atuador local
make monitor-actuator
```

## Fluxo de Trabalho Completo

### 1. Configuração Inicial

```bash
# Na Raspberry Pi 3 (Infraestrutura)
make setup INFRA=1

# Em qualquer máquina (Dispositivos)
make setup
```

### 2. Execução da Infraestrutura

```bash
# Na Raspberry Pi 3 - Execute em terminais separados:

# Terminal 1: Servidor gRPC
make run-grpc INFRA=1

# Terminal 2: Gateway
make run-gateway

# Terminal 3: Testes
make test-mqtt INFRA=1
```

### 3. Execução dos Dispositivos

```bash
# Em máquinas separadas ou terminais diferentes:

# Sensor de temperatura
make run-sensor

# Atuador relay
make run-actuator

# Cliente de teste
make run-client
```

## Comandos de Desenvolvimento

### Compilação

```bash
# Gerar código Protocol Buffers
make proto

# Compilar Java
make java

# Gerar JARs
make build-jars

# Compilação completa
make setup-local
```

### Testes

```bash
# Testes específicos do atuador
make test-actuator-commands

# Teste de consulta de status
make test-status

# Teste gRPC completo
make test-grpc-full

# Teste comandos MQTT (na Raspberry Pi 3)
make test-mqtt-commands INFRA=1

# Teste ESP8266 (na Raspberry Pi 3)
make test-esp8266-mqtt INFRA=1
```

### Validação

```bash
# Validação geral
make validate

# Validação V3 (na Raspberry Pi 3)
make validate-v3 INFRA=1

# Status do projeto
make status
```

## Comandos de Monitoramento

### Monitoramento Local

```bash
# Monitorar atuador local
make monitor-actuator
```

### Monitoramento de Sistema (Raspberry Pi 3)

```bash
# Monitorar sistema completo
make monitor-system INFRA=1
```

## Comandos de Limpeza

```bash
# Limpeza básica
make clean

# Limpar logs
make clean-logs

# Limpeza completa
make clean-all
```

## Exemplos Práticos

### Exemplo 1: Configuração Inicial Completa

```bash
# 1. Na Raspberry Pi 3
make setup-local INFRA=1

# 2. Em máquina de desenvolvimento
make setup-local
```

### Exemplo 2: Execução de Demo Completa

```bash
# Na Raspberry Pi 3
make demo INFRA=1

# Em terminais separados em outras máquinas
make run-sensor
make run-actuator
make run-client
```

### Exemplo 3: Desenvolvimento e Teste

```bash
# 1. Compilar tudo
make build-jars

# 2. Executar infraestrutura (Raspberry Pi 3)
make run-grpc INFRA=1

# 3. Executar gateway
make run-gateway

# 4. Testar atuador
make test-actuator-commands

# 5. Testar status
make test-status
```

### Exemplo 4: Múltiplos Atuadores

```bash
# Terminal 1: Atuador 1
make run-actuator ACTUATOR_ID=relay_001 ACTUATOR_PORT=6002

# Terminal 2: Atuador 2
make run-actuator ACTUATOR_ID=relay_002 ACTUATOR_PORT=6003

# Terminal 3: Atuador 3
make run-actuator ACTUATOR_ID=relay_003 ACTUATOR_PORT=6004
```

## Solução de Problemas

### Problema: Comando não executa na Raspberry Pi 3

```bash
# Erro
make run-grpc

# Correto
make run-grpc INFRA=1
```

### Problema: Dependências não instaladas

```bash
# Instalar dependências
make install

# Ou configuração completa
make setup-local
```

### Problema: Protocol Buffers não gerados

```bash
# Gerar Protocol Buffers
make proto

# Verificar status
make status
```

### Problema: JARs não compilados

```bash
# Compilar Java
make java

# Ou gerar JARs
make build-jars
```

## Variáveis de Ambiente

### INFRA
- **Valor:** `1` (para Raspberry Pi 3)
- **Uso:** Identifica comandos de infraestrutura
- **Exemplo:** `make run-grpc INFRA=1`

### ACTUATOR_ID
- **Valor:** ID do atuador (padrão: `relay_001`)
- **Uso:** Identificar atuador específico
- **Exemplo:** `make run-actuator ACTUATOR_ID=relay_002`

### ACTUATOR_PORT
- **Valor:** Porta TCP do atuador (padrão: `6002`)
- **Uso:** Porta para comunicação TCP
- **Exemplo:** `make run-actuator ACTUATOR_PORT=6003`

## Estrutura de Portas

| Serviço | Porta | Localização |
|---------|-------|-------------|
| RabbitMQ MQTT | 1883 | Raspberry Pi 3 |
| Servidor gRPC | 50051 | Raspberry Pi 3 |
| Gateway TCP | 12345 | Qualquer máquina |
| Multicast Discovery | 12346 | Qualquer máquina |
| Atuador TCP | 6002+ | Qualquer máquina |
| API REST | 8000 | Qualquer máquina |

## Ajuda

Para ver todos os comandos disponíveis:

```bash
make help
```

Para mais informações sobre o projeto, consulte o `README.md` principal.
