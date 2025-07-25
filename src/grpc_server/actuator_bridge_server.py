#!/usr/bin/env python3
"""
Servidor gRPC para Controle de Atuadores - Raspberry Pi 3

Este servidor atua como ponte entre o Gateway (cliente gRPC) e os dispositivos
atuadores (ESP8266 e Java). Ele recebe chamadas gRPC e as traduz para comandos
TCP que são enviados diretamente aos dispositivos.

Funcionalidades:
- Recebe chamadas gRPC do Gateway
- Traduz comandos gRPC para mensagens Protocol Buffers
- Estabelece conexões TCP com atuadores
- Retorna status das operações

Arquitetura:
Gateway (gRPC Client) -> Servidor gRPC (Raspberry Pi) -> Atuadores TCP

Uso:
    python3 grpc_actuator_server.py
"""

import grpc
from concurrent import futures
import socket
import logging
import sys
import os
import time
import threading
from typing import Dict, Any

# Adicionar diretório do projeto ao path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

# Importar Protocol Buffers
try:
    # Adicionar diretório proto ao path
    proto_path = os.path.join(os.path.dirname(__file__), '..', 'proto')
    sys.path.insert(0, proto_path)
    
    import smart_city_pb2
    import actuator_service_pb2
    import actuator_service_pb2_grpc
except ImportError as e:
    print(f"Erro ao importar proto files: {e}")
    print("Execute: ")
    print("  protoc --python_out=src/proto/ --grpc_python_out=src/proto/ src/proto/actuator_service.proto")
    print("  protoc --python_out=src/proto/ src/proto/smart_city.proto")
    sys.exit(1)

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# Configurações do servidor
GRPC_PORT = 50051
TIMEOUT_TCP = 5  # Timeout para conexões TCP com dispositivos

# Cache de dispositivos descobertos (pode ser populado via discovery)
device_cache: Dict[str, Dict[str, Any]] = {}

def encode_varint(value: int) -> bytes:
    """Codifica um inteiro como varint (formato Protocol Buffers)"""
    result = b""
    while True:
        bits = value & 0x7F
        value >>= 7
        if value:
            result += bytes([bits | 0x80])
        else:
            result += bytes([bits])
            break
    return result

def send_tcp_command_to_device(device_ip: str, device_port: int, command: smart_city_pb2.DeviceCommand) -> smart_city_pb2.DeviceUpdate:
    """
    Envia um comando TCP para um dispositivo atuador e aguarda resposta
    
    Args:
        device_ip: IP do dispositivo
        device_port: Porta TCP do dispositivo
        command: Comando a ser enviado
        
    Returns:
        DeviceUpdate com o status atualizado
        
    Raises:
        Exception: Se houver erro na comunicação
    """
    try:
        logger.info(f"Conectando ao dispositivo {device_ip}:{device_port} para comando {command.command_type}")
        
        with socket.create_connection((device_ip, device_port), timeout=TIMEOUT_TCP) as sock:
            # Criar envelope SmartCityMessage
            envelope = smart_city_pb2.SmartCityMessage()
            envelope.message_type = smart_city_pb2.MessageType.CLIENT_REQUEST
            
            # Criar ClientRequest com o comando
            client_request = smart_city_pb2.ClientRequest()
            client_request.type = smart_city_pb2.ClientRequest.RequestType.SEND_DEVICE_COMMAND
            client_request.target_device_id = command.device_id
            client_request.command.CopyFrom(command)
            
            envelope.client_request.CopyFrom(client_request)
            
            # Enviar mensagem com delimitador varint
            data = envelope.SerializeToString()
            sock.sendall(encode_varint(len(data)) + data)
            
            logger.info(f"Comando enviado para {device_ip}:{device_port}")
            
            # Ler resposta
            sock_file = sock.makefile('rb')
            
            # Ler tamanho da resposta (varint)
            def read_varint(stream):
                shift = 0
                result = 0
                while True:
                    b = stream.read(1)
                    if not b:
                        raise EOFError("Stream fechado")
                    b = b[0]
                    result |= (b & 0x7f) << shift
                    if not (b & 0x80):
                        return result
                    shift += 7
            
            response_size = read_varint(sock_file)
            response_data = sock_file.read(response_size)
            
            if len(response_data) != response_size:
                raise Exception("Resposta TCP incompleta")
            
            # Decodificar resposta
            response_envelope = smart_city_pb2.SmartCityMessage()
            response_envelope.ParseFromString(response_data)
            
            if response_envelope.message_type == smart_city_pb2.MessageType.DEVICE_UPDATE:
                logger.info(f"Status recebido do dispositivo {command.device_id}: {smart_city_pb2.DeviceStatus.Name(response_envelope.device_update.current_status)}")
                return response_envelope.device_update
            else:
                raise Exception(f"Tipo de resposta inesperado: {response_envelope.message_type}")
                
    except Exception as e:
        logger.error(f"Erro ao comunicar com dispositivo {device_ip}:{device_port}: {e}")
        raise


class ActuatorServiceServicer(actuator_service_pb2_grpc.ActuatorServiceServicer):
    """Implementação do serviço gRPC para controle de atuadores (novo .proto)"""

    def LigarDispositivo(self, request, context):
        device_id = request.device_id
        logger.info(f"[gRPC] Comando LIGAR para dispositivo {device_id}")
        ip = request.ip
        port = request.port
        try:
            command = smart_city_pb2.DeviceCommand()
            command.device_id = device_id
            command.command_type = "TURN_ON"
            command.command_value = ""
            device_update = send_tcp_command_to_device(ip, port, command)
            return actuator_service_pb2.Response(
                status="ON",
                message=f"Dispositivo {device_id} ligado com sucesso. Status: {smart_city_pb2.DeviceStatus.Name(device_update.current_status)}"
            )
        except Exception as e:
            logger.error(f"Erro ao ligar dispositivo {device_id}: {e}")
            return actuator_service_pb2.Response(
                status="ERROR",
                message=f"Erro ao ligar dispositivo: {str(e)}"
            )

    def DesligarDispositivo(self, request, context):
        device_id = request.device_id
        logger.info(f"[gRPC] Comando DESLIGAR para dispositivo {device_id}")
        ip = request.ip
        port = request.port
        try:
            command = smart_city_pb2.DeviceCommand()
            command.device_id = device_id
            command.command_type = "TURN_OFF"
            command.command_value = ""
            device_update = send_tcp_command_to_device(ip, port, command)
            return actuator_service_pb2.Response(
                status="OFF",
                message=f"Dispositivo {device_id} desligado com sucesso. Status: {smart_city_pb2.DeviceStatus.Name(device_update.current_status)}"
            )
        except Exception as e:
            logger.error(f"Erro ao desligar dispositivo {device_id}: {e}")
            return actuator_service_pb2.Response(
                status="ERROR",
                message=f"Erro ao desligar dispositivo: {str(e)}"
            )

    def ConsultarEstado(self, request, context):
        device_id = request.device_id
        logger.info(f"[gRPC] Consulta de estado para dispositivo {device_id}")
        ip = request.ip
        port = request.port
        try:
            command = smart_city_pb2.DeviceCommand()
            command.device_id = device_id
            command.command_type = "GET_STATUS"
            command.command_value = ""
            device_update = send_tcp_command_to_device(ip, port, command)
            # Para GET_STATUS, retornar o status real do dispositivo no campo status
            device_status_name = smart_city_pb2.DeviceStatus.Name(device_update.current_status)
            return actuator_service_pb2.Response(
                status=device_status_name,  # Usar o status real do dispositivo
                message=f"Status do dispositivo {device_id}: {device_status_name}"
            )
        except Exception as e:
            logger.error(f"Erro ao consultar estado do dispositivo {device_id}: {e}")
            return actuator_service_pb2.Response(
                status="ERROR",
                message=f"Erro ao consultar estado: {str(e)}"
            )

def serve():
    """Inicia o servidor gRPC"""
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    actuator_service_pb2_grpc.add_ActuatorServiceServicer_to_server(ActuatorServiceServicer(), server)
    listen_addr = f'[::]:{GRPC_PORT}'
    server.add_insecure_port(listen_addr)
    logger.info(f"Servidor gRPC iniciado na porta {GRPC_PORT}")
    logger.info("Aguardando chamadas gRPC do Gateway...")
    server.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Servidor gRPC encerrado por Ctrl+C")
        server.stop(0)

if __name__ == '__main__':
    serve()
