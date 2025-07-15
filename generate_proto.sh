#!/bin/bash

# Script para gerar código Protocol Buffers e gRPC

echo "Gerando código Protocol Buffers e gRPC..."

# Diretório de saída
OUTPUT_DIR="src/proto"

# Gerar código Python para smart_city.proto (mensagens básicas)
echo "Gerando smart_city_pb2.py..."
python3 -m grpc_tools.protoc --python_out=$OUTPUT_DIR --proto_path=src/proto smart_city.proto

# Gerar código Python e gRPC para actuator_service.proto
echo "Gerando actuator_service_pb2.py e actuator_service_pb2_grpc.py..."
python3 -m grpc_tools.protoc --python_out=$OUTPUT_DIR --grpc_python_out=$OUTPUT_DIR --proto_path=src/proto actuator_service.proto

# Verificar se os arquivos foram gerados
if [ -f "$OUTPUT_DIR/smart_city_pb2.py" ]; then
    echo "✓ smart_city_pb2.py gerado com sucesso"
else
    echo "✗ Erro ao gerar smart_city_pb2.py"
fi

if [ -f "$OUTPUT_DIR/actuator_service_pb2.py" ]; then
    echo "✓ actuator_service_pb2.py gerado com sucesso"
else
    echo "✗ Erro ao gerar actuator_service_pb2.py"
fi

if [ -f "$OUTPUT_DIR/actuator_service_pb2_grpc.py" ]; then
    echo "✓ actuator_service_pb2_grpc.py gerado com sucesso"
else
    echo "✗ Erro ao gerar actuator_service_pb2_grpc.py"
fi

echo "Geração concluída!"
echo ""
echo "Para usar o código gerado, certifique-se de:"
echo "1. Ter as dependências instaladas: pip install -r requirements.txt"
echo "2. Configurar o PYTHONPATH: export PYTHONPATH=\$PYTHONPATH:\$(pwd)"
echo "3. Iniciar o servidor gRPC: python3 src/grpc_server/grpc_actuator_server.py"
echo "4. Iniciar o gateway: python3 src/gateway/smart_city_gateway.py"
