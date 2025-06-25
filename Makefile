# Makefile para o projeto SmartCity
# Comandos para gerenciar Protocol Buffers e outras tarefas

# Variáveis
PROTO_DIR = src/proto
PROTO_FILE = $(PROTO_DIR)/smart_city.proto
PYTHON_OUT = $(PROTO_DIR)

# Comando padrão
.PHONY: help
help:
	@echo "Comandos disponíveis:"
	@echo "  make proto     - Gera código Python a partir do arquivo .proto"
	@echo "  make clean     - Remove arquivos gerados"
	@echo "  make install   - Instala dependências Python"
	@echo "  make test      - Executa testes (se existirem)"
	@echo "  make run-client - Executa o cliente de teste"
	@echo "  make run-gateway - Executa o gateway"
	@echo "  make run-api   - Executa a API server"

# Gera código Python a partir do arquivo .proto
.PHONY: proto
proto:
	@echo "Gerando código Python a partir de $(PROTO_FILE)..."
	protoc --proto_path=$(PROTO_DIR) --python_out=$(PYTHON_OUT) $(PROTO_FILE)
	@echo "Código gerado com sucesso em $(PYTHON_OUT)/smart_city_pb2.py"

# Remove arquivos gerados
.PHONY: clean
clean:
	@echo "Removendo arquivos gerados..."
	rm -f $(PROTO_DIR)/smart_city_pb2.py
	rm -f $(PROTO_DIR)/src/proto/smart_city_pb2.py
	rm -rf $(PROTO_DIR)/__pycache__
	@echo "Limpeza concluída"

# Instala dependências Python
.PHONY: install
install:
	@echo "Instalando dependências Python..."
	pip install -r requirements.txt
	@echo "Dependências instaladas"

# Executa o cliente de teste
.PHONY: run-client
run-client:
	@echo "Executando cliente de teste..."
	cd src/client-test && python smart_city_client.py

# Executa o gateway
.PHONY: run-gateway
run-gateway:
	@echo "Executando gateway..."
	cd src/gateway && python smart_city_gateway.py

# Executa a API server
.PHONY: run-api
run-api:
	@echo "Executando API server..."
	cd src/api && python api_server.py

# Executa todos os testes (se existirem)
.PHONY: test
test:
	@echo "Executando testes..."
	@if [ -f "tests" ] || [ -d "tests" ]; then \
		python -m pytest tests/ -v; \
	else \
		echo "Nenhum teste encontrado"; \
	fi

# Comando para desenvolvimento: gera proto e executa cliente
.PHONY: dev-client
dev-client: proto run-client

# Comando para desenvolvimento: gera proto e executa gateway
.PHONY: dev-gateway
dev-gateway: proto run-gateway

# Comando para desenvolvimento: gera proto e executa API
.PHONY: dev-api
dev-api: proto run-api

# Mostra status do projeto
.PHONY: status
status:
	@echo "=== Status do Projeto SmartCity ==="
	@echo "Arquivo .proto: $(PROTO_FILE)"
	@if [ -f "$(PROTO_FILE)" ]; then \
		echo "✓ Arquivo .proto encontrado"; \
	else \
		echo "✗ Arquivo .proto não encontrado"; \
	fi
	@if [ -f "$(PYTHON_OUT)/smart_city_pb2.py" ]; then \
		echo "✓ Código Python gerado"; \
	else \
		echo "✗ Código Python não gerado (execute 'make proto')"; \
	fi
	@if [ -f "requirements.txt" ]; then \
		echo "✓ requirements.txt encontrado"; \
	else \
		echo "✗ requirements.txt não encontrado"; \
	fi
	@echo "================================" 