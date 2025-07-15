# Makefile para o projeto SmartCity - gRPC e MQTT
# Comandos para gerenciar Protocol Buffers, gRPC e outras tarefas

# Variáveis
PROTO_DIR = src/proto
SMART_CITY_PROTO = $(PROTO_DIR)/smart_city.proto
ACTUATOR_SERVICE_PROTO = $(PROTO_DIR)/actuator_service.proto
PYTHON_OUT = $(PROTO_DIR)

# Use INFRA=1 para rodar comandos de infraestrutura (RabbitMQ, gRPC) na Raspberry Pi 3

# Comando padrão
.PHONY: help
help:
	@echo "Comandos disponiveis para Smart City:"
	@echo "=== CONFIGURAÇÃO ==="
	@echo "  make setup         - Configura ambiente completo (deps + proto + rabbitmq)"
	@echo "  make setup-complete - Configuração completa automatizada"
	@echo "  make proto         - Gera código Python/gRPC a partir dos arquivos .proto"
	@echo "  make java          - Compila dispositivos Java com Maven"
	@echo "  make build-jars    - Gera JARs dos dispositivos Java"
	@echo "  make clean         - Remove arquivos gerados"
	@echo "  make clean-all     - Limpeza completa do projeto"
	@echo "  make install       - Instala dependências Python"
	@echo "  make status        - Mostra status do projeto"
	@echo ""
	@echo "=== INFRAESTRUTURA (Raspberry Pi 3) ==="
	@echo "  make rabbitmq INFRA=1      - Configura RabbitMQ com plugin MQTT"
	@echo "  make run-grpc INFRA=1      - Executa servidor ponte gRPC"
	@echo "  make test-mqtt INFRA=1     - Testa conexão MQTT"
	@echo "  make test-actuator INFRA=1 - Testa atuador via gRPC"
	@echo "  make demo INFRA=1          - Inicia demo completa"
	@echo "  make validate-v3 INFRA=1   - Valida sistema"
	@echo "  make monitor-system INFRA=1 - Monitora sistema na Raspberry Pi 3"
	@echo ""
	@echo "=== DISPOSITIVOS E GATEWAY ==="
	@echo "  make run-gateway   - Executa gateway"
	@echo "  make run-api       - Executa API server"
	@echo "  make run-client    - Executa cliente de teste"
	@echo "  make run-sensor    - Executa sensor Java (MQTT)"
	@echo "  make run-actuator  - Executa atuador Java (gRPC)"
	@echo "  make monitor-actuator - Monitora atuador local"
	@echo ""
	@echo "=== TESTES ==="
	@echo "  make test-actuator-commands - Testa comandos específicos do atuador"
	@echo "  make test-status   - Testa consulta de status"
	@echo "  make test-grpc-full - Testa comunicação gRPC completa"
	@echo "  make test-mqtt-commands INFRA=1 - Testa comandos MQTT"
	@echo "  make test-esp8266-mqtt INFRA=1  - Testa comandos MQTT ESP8266"
	@echo "  make validate      - Valida sistema"
	@echo ""
	@echo "=== LIMPEZA ==="
	@echo "  make clean-logs    - Remove logs temporários"
	@echo "  make clean-all     - Limpeza completa do projeto"

# Configuração completa do ambiente
.PHONY: setup
setup:
ifeq ($(INFRA),1)
	$(MAKE) install
	$(MAKE) rabbitmq INFRA=1
	$(MAKE) proto
	$(MAKE) java
else
	$(MAKE) install
	@echo "Pulando configuração do RabbitMQ (apenas na Raspberry Pi 3)."
	$(MAKE) proto
	$(MAKE) java
endif
	@echo "Ambiente configurado com sucesso!"
	@echo ""
	@echo "=== INSTRUÇÕES DE USO ==="
	@echo "NA RASPBERRY PI 3 (Infraestrutura):"
	@echo "1. make run-grpc INFRA=1    (servidor ponte gRPC)"
	@echo "2. make test-mqtt INFRA=1   (validar MQTT)"
	@echo ""
	@echo "EM QUALQUER MÁQUINA (Dispositivos):"
	@echo "1. make run-gateway         (gateway)"
	@echo "2. make run-sensor          (sensor Java)"
	@echo "3. make run-actuator        (atuador Java)"
	@echo "4. make run-client          (cliente de teste)"

# Gera código Python/gRPC a partir dos arquivos .proto
.PHONY: proto
proto:
	@echo "Gerando código Python e gRPC..."
	@chmod +x generate_proto.sh
	./generate_proto.sh

# Gera arquivos Java dos protos
.PHONY: java-proto
java-proto:
	@echo "Gerando arquivos Java dos protos..."
	@chmod +x generate_java_proto.sh
	./generate_java_proto.sh

# Compila dispositivos Java apenas se necessário
.PHONY: java
java: java-proto
	@echo "Compilando dispositivos Java..."
	mvn compile
	@echo "Compilação Java concluída!"

# Gera todos os JARs
.PHONY: build-jars
build-jars: java-proto
	@echo "Gerando JARs..."
	mvn package
	@echo "JARs gerados em target/"

# Configura RabbitMQ com plugin MQTT
.PHONY: rabbitmq
rabbitmq:
ifeq ($(INFRA),1)
	@echo "Configurando RabbitMQ (Raspberry Pi 3)..."
	@chmod +x setup_rabbitmq.sh
	./setup_rabbitmq.sh
else
	@echo "Este comando deve ser executado apenas na Raspberry Pi 3 (Infraestrutura)."
endif

# Remove arquivos gerados
.PHONY: clean
clean:
	@echo "Removendo arquivos gerados dos protos..."
	rm -f $(PROTO_DIR)/*_pb2.py
	rm -f $(PROTO_DIR)/*_pb2_grpc.py
	rm -rf $(PROTO_DIR)/__pycache__
	rm -rf target/generated-sources/protobuf/java/*
	@echo "Limpeza concluída. Lembre-se de rodar 'make java' para regenerar os protos antes de compilar Java."

# Instala dependências Python
.PHONY: install
install:
	@echo "Instalando dependências Python..."
	@if [ ! -d "venv" ]; then \
		echo "Criando ambiente virtual..."; \
		python3 -m venv venv; \
	fi
	@bash -c "source venv/bin/activate && pip install -r requirements.txt"
	@echo "Dependências instaladas"

# Executa servidor gRPC
.PHONY: run-grpc
run-grpc: install
ifeq ($(INFRA),1)
	@echo "Executando servidor ponte gRPC (Raspberry Pi 3)..."
	@bash -c "source venv/bin/activate && python3 src/grpc_server/actuator_bridge_server.py"
else
	@echo "Este comando deve ser executado apenas na Raspberry Pi 3 (Infraestrutura)."
	@echo "Use: make run-grpc INFRA=1"
endif

# Executa gateway
.PHONY: run-gateway
run-gateway: install proto
	@echo "Executando gateway..."
	@bash -c "source venv/bin/activate && python3 src/gateway/smart_city_gateway.py"

# Executa API server
.PHONY: run-api
run-api:
	@echo "Executando API server..."
	cd src/api && uvicorn src.api_server:app --reload --host 0.0.0.0 --port 8000

# Executa cliente de teste
.PHONY: run-client
run-client: install
	@echo "Executando cliente de teste..."
	@bash -c "source venv/bin/activate && python3 src/client-test/smart_city_client.py"

# Executa sensor Java (MQTT)
.PHONY: run-sensor
run-sensor: build-jars
	@echo "Executando sensor Java..."
	mvn exec:java -Dexec.mainClass="com.smartcity.sensors.TemperatureHumiditySensor"

# Executa atuador Java (RelayActuator)
# Parâmetros opcionais:
#   ACTUATOR_ID   - ID do atuador (padrão: relay_001)
#   ACTUATOR_PORT - Porta TCP do atuador (padrão: 6002)
# Exemplo: make run-actuator ACTUATOR_ID=relay_002 ACTUATOR_PORT=6003
.PHONY: run-actuator
ACTUATOR_ID ?= relay_001
ACTUATOR_PORT ?= 6002
run-actuator: build-jars
	@echo "Executando atuador Java com ID $(ACTUATOR_ID) e porta $(ACTUATOR_PORT)..."
	mvn exec:java -Dexec.mainClass="com.smartcity.actuators.RelayActuator" -Dexec.args="$(ACTUATOR_ID) $(ACTUATOR_PORT)"

# Testa conexão MQTT
.PHONY: test-mqtt
test-mqtt:
ifeq ($(INFRA),1)
	@echo "Testando conexão MQTT (Raspberry Pi 3)..."
	@echo "Publicando mensagem de teste..."
	mosquitto_pub -h localhost -t "smart_city/sensors/test" -m '{"device_id":"test","temperature":25.0,"humidity":60.0}'
	@echo "Escutando mensagens (Ctrl+C para parar)..."
	mosquitto_sub -h localhost -t "smart_city/sensors/+"
else
	@echo "Este comando deve ser executado apenas na Raspberry Pi 3 (Infraestrutura)."
	@echo "Use: make test-mqtt INFRA=1"
endif

# Testa atuadores via gRPC
.PHONY: test-actuator
test-actuator: install
ifeq ($(INFRA),1)
	@echo "Testando atuador via gRPC (Raspberry Pi 3)..."
	@echo "Nota: Execute 'make run-actuator' em outro terminal primeiro"
	@echo "Testando conexão gRPC com atuador relay_001..."
	@bash -c "source venv/bin/activate && timeout 10 python3 -c 'import grpc; import sys; sys.path.append(\"src/proto\"); from actuator_service_pb2 import DeviceRequest; from actuator_service_pb2_grpc import AtuadorServiceStub; channel = grpc.insecure_channel(\"localhost:50051\"); stub = AtuadorServiceStub(channel); request = DeviceRequest(device_id=\"relay_001\", ip=\"localhost\", port=6002); response = stub.ConsultarEstado(request); print(f\"Status: {response.status}\"); print(f\"Mensagem: {response.message}\")' || echo 'Erro: Servidor gRPC não disponível'"
else
	@echo "Este comando deve ser executado apenas na Raspberry Pi 3 (Infraestrutura)."
	@echo "Use: make test-actuator INFRA=1"
endif

# Testa comandos específicos do atuador
.PHONY: test-actuator-commands
test-actuator-commands: install
	@echo "Testando comandos específicos do atuador..."
	@echo "Nota: Execute 'make run-grpc INFRA=1' e 'make run-gateway' em outros terminais primeiro"
	@bash -c "source venv/bin/activate && python3 test_actuator_command.py"

# Testa consulta de status
.PHONY: test-status
test-status: install
	@echo "Testando consulta de status..."
	@echo "Nota: Execute 'make run-grpc INFRA=1' e 'make run-gateway' em outros terminais primeiro"
	@bash -c "source venv/bin/activate && python3 test_status_query.py"

# Testa comunicação gRPC completa
.PHONY: test-grpc-full
test-grpc-full: install
	@echo "Testando comunicação gRPC completa..."
	@echo "Nota: Execute 'make run-grpc INFRA=1' e 'make run-gateway' em outros terminais primeiro"
	@bash -c "source venv/bin/activate && python3 test_grpc_actuator_fixed.py"

# === TESTE COMANDOS MQTT ===
.PHONY: test-mqtt-commands
test-mqtt-commands: install
ifeq ($(INFRA),1)
	@echo "=== Testando Comandos MQTT (Raspberry Pi 3) ==="
	@bash -c "source venv/bin/activate && python3 test_mqtt_commands.py"
else
	@echo "Este comando deve ser executado apenas na Raspberry Pi 3 (Infraestrutura)."
	@echo "Use: make test-mqtt-commands INFRA=1"
endif

# === VALIDAÇÃO FINAL ===
.PHONY: validate
validate: install
	@echo "=== Validando Sistema Smart City ==="
	@bash -c "source venv/bin/activate && python3 validate_system.py"

# === DEMO COMPLETA ===
.PHONY: demo
demo: build-jars install
ifeq ($(INFRA),1)
	@echo "=== Iniciando Demo Smart City (Raspberry Pi 3) ==="
	@echo "Iniciando componentes em background..."
	@bash -c "source venv/bin/activate && python3 src/grpc_server/actuator_bridge_server.py &"
	sleep 3
	@bash -c "source venv/bin/activate && python3 src/gateway/smart_city_gateway.py &"
	sleep 3
	mvn exec:java -Dexec.mainClass="com.smartcity.sensors.TemperatureHumiditySensor" -Dexec.args="temp_001" &
	mvn exec:java -Dexec.mainClass="com.smartcity.sensors.TemperatureHumiditySensor" -Dexec.args="temp_002" &
	@echo "Demo iniciada! Pressione Ctrl+C para parar."
	@echo "Aguardando 5 segundos para estabilizar..."
	sleep 5
	@echo "Testando comandos MQTT..."
	@bash -c "source venv/bin/activate && python3 test_mqtt_commands.py"
	@echo "Demo V3 concluída!"
else
	@echo "Este comando deve ser executado apenas na Raspberry Pi 3 (Infraestrutura)."
	@echo "Use: make demo INFRA=1"
endif

# === COMANDOS DE VALIDAÇÃO V3 ===
.PHONY: validate-v3
validate-v3: build-jars install
ifeq ($(INFRA),1)
	@echo "=== Validando Sistema V3 (Raspberry Pi 3) ==="
	@echo "1. Verificando dependências..."
	@bash -c "source venv/bin/activate && python3 -c 'import paho.mqtt.client; print(\"✓ paho-mqtt OK\")'"
	@bash -c "source venv/bin/activate && python3 -c 'import grpc; print(\"✓ grpc OK\")'"
	@java -version
	@echo "2. Compilando código Java..."
	$(MAKE) java
	@echo "3. Testando conexão MQTT..."
	timeout 5 bash -c "source venv/bin/activate && python3 -c 'import paho.mqtt.client as mqtt; c=mqtt.Client(); c.connect(\"localhost\", 1883); print(\"✓ MQTT OK\")'" || echo "⚠ MQTT não acessível"
	@echo "4. Testando gRPC..."
	timeout 5 bash -c "source venv/bin/activate && python3 -c 'import grpc; grpc.insecure_channel(\"localhost:50051\"); print(\"✓ gRPC OK\")'" || echo "⚠ gRPC não acessível"
	@echo "Validação concluída!"
else
	@echo "Este comando deve ser executado apenas na Raspberry Pi 3 (Infraestrutura)."
	@echo "Use: make validate-v3 INFRA=1"
endif

# Mostra status do projeto
.PHONY: status
status:
	@echo "=== Status do Projeto Smart City ==="
	@echo "Arquivos .proto:"
	@if [ -f "$(SMART_CITY_PROTO)" ]; then \
		echo "smart_city.proto encontrado"; \
	else \
		echo "smart_city.proto nao encontrado"; \
	fi
	@if [ -f "$(ACTUATOR_SERVICE_PROTO)" ]; then \
		echo "actuator_service.proto encontrado"; \
	else \
		echo "actuator_service.proto nao encontrado"; \
	fi
	@echo ""
	@echo "Codigo Python gerado:"
	@if [ -f "$(PYTHON_OUT)/smart_city_pb2.py" ]; then \
		echo "smart_city_pb2.py gerado"; \
	else \
		echo "smart_city_pb2.py nao gerado"; \
	fi
	@if [ -f "$(PYTHON_OUT)/actuator_service_pb2.py" ]; then \
		echo "actuator_service_pb2.py gerado"; \
	else \
		echo "actuator_service_pb2.py nao gerado"; \
	fi
	@if [ -f "$(PYTHON_OUT)/actuator_service_pb2_grpc.py" ]; then \
		echo "actuator_service_pb2_grpc.py gerado"; \
	else \
		echo "actuator_service_pb2_grpc.py nao gerado"; \
	fi
	@echo ""
	@echo "JARs Java:"
	@if [ -f "target/temperature-humidity-sensor.jar" ]; then \
		echo "Sensor Java compilado"; \
	else \
		echo "Sensor Java nao compilado"; \
	fi
	@if [ -f "target/relay-actuator.jar" ]; then \
		echo "Atuador Java compilado"; \
	else \
		echo "Atuador Java nao compilado"; \
	fi
	@echo ""
	@echo "Servicos:"
	@if systemctl is-active --quiet rabbitmq-server; then \
		echo "RabbitMQ ativo"; \
	else \
		echo "RabbitMQ inativo"; \
	fi
	@echo ""
	@echo "Para configurar tudo: make setup"
	@echo "================================"

# === TESTE ESP8266 MQTT ===
.PHONY: test-esp8266-mqtt
test-esp8266-mqtt:
ifeq ($(INFRA),1)
	@echo "=== Testando Comandos MQTT ESP8266 (Raspberry Pi 3) ==="
	@bash -c "source venv/bin/activate && python3 test_esp8266_mqtt_commands.py temp_sensor_esp_001"
else
	@echo "Este comando deve ser executado apenas na Raspberry Pi 3 (Infraestrutura)."
	@echo "Use: make test-esp8266-mqtt INFRA=1"
endif

# === COMANDOS DE MONITORAMENTO ===
.PHONY: monitor-actuator
monitor-actuator:
	@echo "=== Monitorando Actuator ==="
	@echo "1. Verificando conexão TCP..."
	timeout 5 nc -zv localhost 12345 || echo "⚠ Actuator não acessível"
	@echo "2. Verificando multicast..."
	timeout 5 bash -c "source venv/bin/activate && python3 -c 'import socket; s=socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.sendto(b\"TEST\", (\"224.0.0.1\", 12346)); print(\"✓ Multicast OK\")'" || echo "⚠ Multicast não acessível"

.PHONY: monitor-system
monitor-system: build-jars install
ifeq ($(INFRA),1)
	@echo "=== Monitorando Sistema (Raspberry Pi 3) ==="
	@echo "1. Verificando processos..."
	@ps aux | grep -E "(gateway|grpc|mqtt)" | grep -v grep || echo "⚠ Nenhum processo encontrado"
	@echo "2. Verificando portas..."
	@netstat -tlnp | grep -E "(1883|50051)" || echo "⚠ Portas não abertas"
	@echo "3. Verificando logs..."
	@tail -n 5 /var/log/syslog | grep -i mqtt || echo "⚠ Sem logs MQTT"
else
	@echo "Este comando deve ser executado apenas na Raspberry Pi 3 (Infraestrutura)."
	@echo "Use: make monitor-system INFRA=1"
endif

# === COMANDOS DE LIMPEZA ===
.PHONY: clean-logs
clean-logs:
	@echo "=== Limpando Logs ==="
	@find . -name "*.log" -delete 2>/dev/null || true
	@find . -name "*.tmp" -delete 2>/dev/null || true
	@echo "Logs limpos!"

.PHONY: clean-all
clean-all: clean clean-logs
	@echo "=== Limpeza Completa ==="
	@rm -rf venv/ 2>/dev/null || true
	@rm -rf target/ 2>/dev/null || true
	@rm -rf src/grpc_server/__pycache__/ 2>/dev/null || true
	@rm -rf src/gateway/__pycache__/ 2>/dev/null || true
	@rm -rf src/client-test/__pycache__/ 2>/dev/null || true
	@find . -name "*.pyc" -delete 2>/dev/null || true
	@find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
	@echo "Limpeza completa realizada!"

# === CONFIGURAÇÃO AUTOMÁTICA ===
.PHONY: setup-complete
setup-complete:
	@echo "=== Configuração Completa do Sistema ==="
	@echo "1. Instalando dependências..."
	$(MAKE) install
	@echo "2. Gerando Protocol Buffers..."
	$(MAKE) proto
	@echo "3. Compilando Java..."
	$(MAKE) java
	@echo "4. Testando configuração..."
	$(MAKE) status
	@echo "✓ Sistema configurado com sucesso!"
	@echo ""
	@echo "Para executar no Raspberry Pi 3:"
	@echo "  make run-mqtt INFRA=1"
	@echo "  make run-grpc INFRA=1"
	@echo "  make run-gateway INFRA=1"
	@echo ""
	@echo "Para executar dispositivos (qualquer máquina):"
	@echo "  make run-temperature-sensor"
	@echo "  make run-relay-actuator"