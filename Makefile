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
	@echo "  make setup         - Configura ambiente completo (deps + proto + rabbitmq)"
	@echo "  make proto         - Gera código Python/gRPC a partir dos arquivos .proto"
	@echo "  make java          - Compila dispositivos Java com Maven"
	@echo "  make clean         - Remove arquivos gerados"
	@echo "  make install       - Instala dependências Python"
	@echo "  make rabbitmq      - Configura RabbitMQ com plugin MQTT"
	@echo "  make run-grpc      - Executa servidor ponte gRPC"
	@echo "  make run-gateway   - Executa gateway"
	@echo "  make run-api       - Executa API server"
	@echo "  make run-client    - Executa cliente de teste"
	@echo "  make run-sensor    - Executa sensor Java (MQTT)"
	@echo "  make test-mqtt     - Testa conexão MQTT"
	@echo "  make status        - Mostra status do projeto"
	@echo "  make test-mqtt-commands - Testa comandos MQTT"
	@echo "  make demo          - Inicia demo completa"
	@echo "  make validate      - Valida sistema"

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
	@echo "Próximos passos:"
	@echo "1. make run-grpc    (servidor ponte gRPC - em um terminal)"
	@echo "2. make run-gateway (em outro terminal)"
	@echo "3. make run-sensor  (em outro terminal)"
	@echo "4. make run-client  (para testar)"

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

# Compila dispositivos Java (sem limpar)
.PHONY: java
java: java-proto
	@echo "Compilando dispositivos Java..."
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
run-grpc:
ifeq ($(INFRA),1)
	@echo "Executando servidor ponte gRPC (Raspberry Pi 3)..."
	@bash -c "source venv/bin/activate && python3 src/grpc_server/actuator_bridge_server.py"
else
	@echo "Este comando deve ser executado apenas na Raspberry Pi 3 (Infraestrutura)."
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
run-sensor: java
	@echo "Executando sensor Java..."
	mvn exec:java -Dexec.mainClass="com.smartcity.sensors.TemperatureHumiditySensor"

# Executa atuador Java (RelayActuator)
.PHONY: run-actuator
ACTUATOR_ID ?= relay_001
ACTUATOR_PORT ?= 6002
run-actuator: java
	@echo "Executando atuador Java com ID $(ACTUATOR_ID) e porta $(ACTUATOR_PORT)..."
	mvn exec:java -Dexec.mainClass="com.smartcity.actuators.RelayActuator" -Dexec.args="$(ACTUATOR_ID) $(ACTUATOR_PORT)"

# Testa conexão MQTT
.PHONY: test-mqtt
test-mqtt:
	@echo "Testando conexão MQTT..."
	@echo "Publicando mensagem de teste..."
	mosquitto_pub -h localhost -t "smart_city/sensors/test" -m '{"device_id":"test","temperature":25.0,"humidity":60.0}'
	@echo "Escutando mensagens (Ctrl+C para parar)..."
	mosquitto_sub -h localhost -t "smart_city/sensors/+"

# === TESTE COMANDOS MQTT ===
.PHONY: test-mqtt-commands
test-mqtt-commands: install-python-deps
	@echo "=== Testando Comandos MQTT ==="
	python3 test_mqtt_commands.py

# === VALIDAÇÃO FINAL ===
.PHONY: validate
validate:
	@echo "=== Validando Sistema Smart City ==="
	python3 validate_system.py

# === DEMO COMPLETA ===
.PHONY: demo
demo: compile install-python-deps
	@echo "=== Iniciando Demo Smart City ==="
	@echo "Iniciando componentes em background..."
	cd $(SRC_DIR) && python3 grpc_server/actuator_bridge_server.py &
	sleep 3
	cd $(SRC_DIR) && python3 gateway/smart_city_gateway.py &
	sleep 3
	cd $(SRC_DIR) && java -cp ".:$(CLASSPATH)" sensors.TemperatureHumiditySensor temp_001 &
	cd $(SRC_DIR) && java -cp ".:$(CLASSPATH)" sensors.TemperatureHumiditySensor temp_002 &
	@echo "Demo iniciada! Pressione Ctrl+C para parar."
	@echo "Aguardando 5 segundos para estabilizar..."
	sleep 5
	@echo "Testando comandos MQTT..."
	python3 test_mqtt_commands.py
	@echo "Demo V3 concluída!"

# === COMANDOS DE VALIDAÇÃO V3 ===
.PHONY: validate-v3
validate-v3: compile install-python-deps
	@echo "=== Validando Sistema V3 ==="
	@echo "1. Verificando dependências..."
	@python3 -c "import paho.mqtt.client; print('✓ paho-mqtt OK')"
	@python3 -c "import grpc; print('✓ grpc OK')"
	@java -version
	@echo "2. Compilando código Java..."
	$(MAKE) compile
	@echo "3. Testando conexão MQTT..."
	timeout 5 python3 -c "import paho.mqtt.client as mqtt; c=mqtt.Client(); c.connect('$(MQTT_BROKER)', 1883); print('✓ MQTT OK')" || echo "⚠ MQTT não acessível"
	@echo "4. Testando gRPC..."
	timeout 5 python3 -c "import grpc; grpc.insecure_channel('localhost:50051'); print('✓ gRPC OK')" || echo "⚠ gRPC não acessível"
	@echo "Validação concluída!"

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
test-esp8266-mqtt: install-python-deps
	@echo "=== Testando Comandos MQTT ESP8266 ==="
	python3 test_esp8266_mqtt_commands.py temp_sensor_esp_001