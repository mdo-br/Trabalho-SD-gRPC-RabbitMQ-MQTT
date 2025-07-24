#!/usr/bin/env python3
# src/gateway/smart_city_gateway.py - SMART CITY GATEWAY WITH MQTT AND GRPC
# Unified gateway: MQTT for sensors, gRPC for actuators

import socket
import struct
import threading
import time
import json
import logging
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, Optional
import paho.mqtt.client as mqtt
import grpc
from grpc import StatusCode

# Imports dos protocolos
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'proto'))
import smart_city_pb2
import actuator_service_pb2
import actuator_service_pb2_grpc

# Configuração de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# === CONFIGURAÇÕES ===
MULTICAST_GROUP = "224.1.1.1"
MULTICAST_PORT = 5007
GATEWAY_TCP_PORT = 12345       # Porta TCP para registro de dispositivos
GATEWAY_UDP_PORT = 12346       # Porta UDP para dados de sensores (legado)
API_TCP_PORT = 12347           # Porta TCP para API externa
GRPC_SERVER_HOST = "127.0.0.1"  # <--- Substitua pelo IP real do seu servidor gRPC
GRPC_SERVER_PORT = 50051

# Configurações MQTT
MQTT_BROKER_HOST = "127.0.0.1"  # <--- Substitua pelo IP real do seu broker MQTT
MQTT_BROKER_PORT = 1883
MQTT_COMMAND_TOPIC_PREFIX = "smart_city/commands/sensors/"
MQTT_RESPONSE_TOPIC_PREFIX = "smart_city/commands/sensors/"
MQTT_SENSOR_DATA_TOPIC_PREFIX = "smart_city/sensors/"

# === ESTRUTURAS DE DADOS ===
connected_devices: Dict[str, Dict[str, Any]] = {}
device_lock = threading.Lock()
mqtt_client = None
mqtt_responses: Dict[str, Dict[str, Any]] = {}  # request_id -> response_data
mqtt_response_lock = threading.Lock()

# === FUNÇÕES AUXILIARES ===
def encode_varint(value):
    """Codifica um inteiro como varint protobuf"""
    result = b''
    while value >= 0x80:
        result += bytes([value & 0x7F | 0x80])
        value >>= 7
    result += bytes([value])
    return result

def decode_varint(data, offset=0):
    """Decodifica um varint protobuf"""
    result = 0
    shift = 0
    i = offset
    while i < len(data):
        byte = data[i]
        result |= (byte & 0x7F) << shift
        if (byte & 0x80) == 0:
            return result, i + 1
        shift += 7
        i += 1
    raise ValueError("Invalid varint")

def read_delimited_message_bytes(sock_file):
    """Lê uma mensagem protobuf com delimitador de tamanho"""
    # Ler varint byte por byte
    size = 0
    shift = 0
    bytes_read = 0
    
    while True:
        byte_data = sock_file.read(1)
        if not byte_data:
            return None
        
        byte = byte_data[0]
        size |= (byte & 0x7F) << shift
        bytes_read += 1
        
        if (byte & 0x80) == 0:
            break
        
        shift += 7
        if bytes_read > 5:  # Proteção contra loop infinito
            raise ValueError("Varint too long")
    
    # Ler dados da mensagem
    message_data = sock_file.read(size)
    if len(message_data) != size:
        raise ValueError(f"Expected {size} bytes, got {len(message_data)}")
    
    envelope = smart_city_pb2.SmartCityMessage()
    envelope.ParseFromString(message_data)
    return envelope

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip

# === MQTT HANDLERS ===
def setup_mqtt():
    """Configura cliente MQTT"""
    global mqtt_client
    
    client_id = f"gateway_{int(time.time())}"
    mqtt_client = mqtt.Client(client_id)
    
    # Adicionar autenticação MQTT
    mqtt_client.username_pw_set('smartcity', 'smartcity123')  # <--- Substitua pelos dados corretos
    
    def on_connect(client, userdata, flags, rc):
        if rc == 0:
            logger.info(f"Gateway conectado ao broker MQTT: {MQTT_BROKER_HOST}:{MQTT_BROKER_PORT}")
            # Inscrever nos tópicos de dados de sensores
            client.subscribe(f"{MQTT_SENSOR_DATA_TOPIC_PREFIX}+")
            # Inscrever nos tópicos de resposta de comandos
            client.subscribe(f"{MQTT_RESPONSE_TOPIC_PREFIX}+/response")
            logger.info("Inscrito nos tópicos MQTT de sensores e respostas")
        else:
            logger.error(f"Falha ao conectar ao broker MQTT: {rc}")
    
    def on_message(client, userdata, msg):
        topic = msg.topic
        payload = msg.payload.decode('utf-8')
        
        try:
            if "/response" in topic:
                # Resposta de comando
                handle_mqtt_command_response(topic, payload)
            else:
                # Dados de sensor
                handle_mqtt_sensor_data(topic, payload)
        except Exception as e:
            logger.error(f"Erro ao processar mensagem MQTT de {topic}: {e}")
    
    def on_disconnect(client, userdata, rc):
        logger.warning(f"Desconectado do broker MQTT: {rc}")
    
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message
    mqtt_client.on_disconnect = on_disconnect
    
    # Conectar ao broker
    try:
        mqtt_client.connect(MQTT_BROKER_HOST, MQTT_BROKER_PORT, 60)
        mqtt_client.loop_start()
        return True
    except Exception as e:
        logger.error(f"Erro ao conectar ao broker MQTT: {e}")
        return False

def handle_mqtt_sensor_data(topic, payload):
    """Processa dados de sensor recebidos via MQTT"""
    try:
        data = json.loads(payload)
        device_id = data.get('device_id')
        
        if not device_id:
            logger.warning(f"Dados MQTT sem device_id: {payload}")
            return
        
        # Atualizar informações do dispositivo
        with device_lock:
            if device_id in connected_devices:
                device = connected_devices[device_id]
                device['last_seen'] = time.time()
                device['last_data'] = data
                
                # Atualizar status se fornecido
                if 'status' in data:
                    try:
                        status_name = data['status']
                        if hasattr(smart_city_pb2.DeviceStatus, status_name):
                            device['status'] = getattr(smart_city_pb2.DeviceStatus, status_name)
                    except:
                        pass
                
                logger.info(f"Dados MQTT atualizados para {device_id}: Temp={data.get('temperature', 'N/A')}, Hum={data.get('humidity', 'N/A')}")
            else:
                logger.warning(f"Recebidos dados MQTT de dispositivo não registrado: {device_id}")
    
    except json.JSONDecodeError as e:
        logger.error(f"Erro ao decodificar JSON de {topic}: {e}")
    except Exception as e:
        logger.error(f"Erro ao processar dados MQTT: {e}")

def handle_mqtt_command_response(topic, payload):
    """Processa respostas de comandos MQTT"""
    try:
        data = json.loads(payload)
        request_id = data.get('request_id')
        device_id = data.get('device_id')
        
        if request_id:
            with mqtt_response_lock:
                mqtt_responses[request_id] = data
                logger.info(f"Resposta MQTT recebida para request_id {request_id}: {data.get('message', 'N/A')}")
            
            # Atualizar status do dispositivo na lista connected_devices
            if device_id and 'status' in data:
                with device_lock:
                    if device_id in connected_devices:
                        try:
                            status_name = data['status']
                            if hasattr(smart_city_pb2.DeviceStatus, status_name):
                                connected_devices[device_id]['status'] = getattr(smart_city_pb2.DeviceStatus, status_name)
                                connected_devices[device_id]['last_seen'] = time.time()
                                logger.info(f"Status do dispositivo {device_id} atualizado para {status_name}")
                        except Exception as e:
                            logger.warning(f"Erro ao atualizar status do dispositivo {device_id}: {e}")
        else:
            logger.warning(f"Resposta MQTT sem request_id: {payload}")
    
    except json.JSONDecodeError as e:
        logger.error(f"Erro ao decodificar resposta MQTT: {e}")
    except Exception as e:
        logger.error(f"Erro ao processar resposta MQTT: {e}")

def send_mqtt_command(device_id, command_type, command_value="", timeout=10):
    """Envia comando via MQTT para sensor e aguarda resposta"""
    request_id = str(uuid.uuid4())
    
    command_data = {
        "command_type": command_type,
        "command_value": command_value,
        "request_id": request_id,
        "timestamp": int(time.time() * 1000)
    }
    
    topic = f"{MQTT_COMMAND_TOPIC_PREFIX}{device_id}"
    
    try:
        # Enviar comando
        result = mqtt_client.publish(topic, json.dumps(command_data), qos=1)
        
        if result.rc != mqtt.MQTT_ERR_SUCCESS:
            logger.error(f"Erro ao publicar comando MQTT para {device_id}: {result.rc}")
            return None
        
        logger.info(f"Comando MQTT enviado para {device_id}: {command_type} (request_id: {request_id})")
        
        # Aguardar resposta
        start_time = time.time()
        while time.time() - start_time < timeout:
            with mqtt_response_lock:
                if request_id in mqtt_responses:
                    response = mqtt_responses.pop(request_id)
                    return response
            time.sleep(0.1)
        
        logger.warning(f"Timeout aguardando resposta MQTT de {device_id} (request_id: {request_id})")
        return None
        
    except Exception as e:
        logger.error(f"Erro ao enviar comando MQTT para {device_id}: {e}")
        return None

# === MULTICAST DISCOVERY ===
def multicast_discovery():
    """Envia descoberta multicast periodicamente"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    # Configurar multicast
    ttl = struct.pack('b', 1)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, ttl)
    
    local_ip = get_local_ip()
    
    discovery_request = smart_city_pb2.DiscoveryRequest(
        gateway_ip=local_ip,
        gateway_tcp_port=GATEWAY_TCP_PORT,
        gateway_udp_port=GATEWAY_UDP_PORT,
        mqtt_broker_ip=MQTT_BROKER_HOST,
        mqtt_broker_port=MQTT_BROKER_PORT
    )

    logger.info(f"Enviando discovery: gateway_ip={local_ip}, mqtt_broker_ip={MQTT_BROKER_HOST}, tcp_port={GATEWAY_TCP_PORT}, udp_port={GATEWAY_UDP_PORT}")
    logger.info(f"DiscoveryRequest enviado: {discovery_request}")
    envelope = smart_city_pb2.SmartCityMessage(
        message_type=smart_city_pb2.MessageType.DISCOVERY_REQUEST,
        discovery_request=discovery_request
    )

    message = envelope.SerializeToString()

    logger.info(f"Payload discovery (hex): {message.hex()}")
    
    logger.info(f"Iniciando descoberta multicast no grupo {MULTICAST_GROUP}:{MULTICAST_PORT}")
    
    while True:
        try:
            sock.sendto(message, (MULTICAST_GROUP, MULTICAST_PORT))
            logger.debug("Descoberta multicast enviada")
        except Exception as e:
            logger.error(f"Erro no multicast: {e}")
        
        time.sleep(10)  # Enviar a cada 10 segundos

# === REGISTRO DE DISPOSITIVOS ===
def register_device(device_info):
    """Registra ou atualiza um dispositivo"""
    with device_lock:
        # Log extra para debug: mensagem completa
        logger.info(f"[DEBUG] DeviceInfo completo recebido:\n{device_info}")
        device_id = device_info.device_id
        # Log extra para debug
        logger.info(f"[DEBUG] DeviceInfo recebido: device_id={device_info.device_id} type={device_info.type} ip={device_info.ip_address}")
        # Todos os sensores usam MQTT
        is_mqtt_sensor = device_info.is_sensor
        device_data = {
            'id': device_id,
            'type': device_info.type,
            'ip': device_info.ip_address,
            'port': device_info.port,
            'status': device_info.initial_state,
            'is_actuator': device_info.is_actuator,
            'is_sensor': device_info.is_sensor,
            'last_seen': time.time(),
            'capabilities': dict(device_info.capabilities),
            'is_mqtt_sensor': is_mqtt_sensor
        }
        if is_mqtt_sensor:
            device_data['mqtt_command_topic'] = f"{MQTT_COMMAND_TOPIC_PREFIX}{device_id}"
            device_data['mqtt_response_topic'] = f"{MQTT_COMMAND_TOPIC_PREFIX}{device_id}/response"
            logger.info(f"Sensor MQTT registrado: {device_id}")
        connected_devices[device_id] = device_data
        logger.info(f"Dispositivo {device_id} ({smart_city_pb2.DeviceType.Name(device_info.type)}) registrado/atualizado. Status: {smart_city_pb2.DeviceStatus.Name(device_info.initial_state)}")

# === COMANDO PARA DISPOSITIVOS ===
def send_command_to_device(dev_id, command_type, command_value=""):
    """Envia comando para dispositivo (sensor ou atuador)"""
    with device_lock:
        if dev_id not in connected_devices:
            return {"command_status": "FAILED", "message": f"Dispositivo {dev_id} não encontrado"}
        
        dev = connected_devices[dev_id]
    
    # Verificar se é sensor MQTT
    if dev.get('is_sensor', False):
        logger.info(f"[GATEWAY] Enviando comando MQTT para sensor {dev_id}")
        
        response = send_mqtt_command(dev_id, command_type, command_value)
        
        if response:
            if response.get('success', False):
                # Atualizar estado do dispositivo
                with device_lock:
                    if dev_id in connected_devices:
                        device = connected_devices[dev_id]
                        device['last_seen'] = time.time()
                        
                        # Atualizar status se fornecido
                        if 'status' in response:
                            try:
                                status_name = response['status']
                                if hasattr(smart_city_pb2.DeviceStatus, status_name):
                                    device['status'] = getattr(smart_city_pb2.DeviceStatus, status_name)
                            except:
                                pass
                
                return {
                    "command_status": "SUCCESS",
                    "message": f"Comando MQTT enviado para sensor: {response.get('message', 'OK')}"
                }
            else:
                return {
                    "command_status": "FAILED", 
                    "message": f"Erro no sensor: {response.get('message', 'Unknown error')}"
                }
        else:
            return {"command_status": "FAILED", "message": "Timeout ou erro na comunicação MQTT"}
    
    # Lógica para atuadores gRPC
    elif dev.get('is_actuator', False):
        # ATUADOR: Usar gRPC
        logger.info(f"[GATEWAY] Enviando comando gRPC para atuador {dev_id}")
        return send_grpc_command(dev_id, command_type, command_value)
    
    else:
        return {"command_status": "FAILED", "message": f"Tipo de dispositivo não suportado: {dev_id}"}

def send_grpc_command(dev_id, command_type, command_value=""):
    """Envia comando via gRPC para atuador"""
    try:
        with grpc.insecure_channel(f'{GRPC_SERVER_HOST}:{GRPC_SERVER_PORT}') as channel:
            stub = actuator_service_pb2_grpc.ActuatorServiceStub(channel)
            # Buscar ip e port do dispositivo
            with device_lock:
                dev = connected_devices.get(dev_id)
                ip = dev['ip'] if dev else ''
                port = dev['port'] if dev else 0
            request = actuator_service_pb2.DeviceId(device_id=dev_id, ip=ip, port=port)

            # Mapeamento do comando para o método correto
            if command_type.upper() in ["LIGAR", "TURN_ON", "ON"]:
                response = stub.LigarDispositivo(request)
            elif command_type.upper() in ["DESLIGAR", "TURN_OFF", "OFF"]:
                response = stub.DesligarDispositivo(request)
            elif command_type.upper() in ["CONSULTAR", "STATUS", "GET_STATUS"]:
                response = stub.ConsultarEstado(request)
            else:
                return {"command_status": "FAILED", "message": f"Comando gRPC desconhecido: {command_type}"}

            if response.status.upper() in ["ON", "OFF", "OK"]:
                with device_lock:
                    if dev_id in connected_devices:
                        connected_devices[dev_id]['last_seen'] = time.time()
                        connected_devices[dev_id]['status'] = response.status
                return {
                    "command_status": "SUCCESS",
                    "message": f"Comando gRPC enviado para atuador: {response.message}",
                    "status": response.status  # Adicionar o status no resultado
                }
            else:
                return {
                    "command_status": "FAILED",
                    "message": f"Erro no atuador: {response.message}"
                }
    except grpc.RpcError as e:
        logger.error(f"Erro gRPC ao enviar comando para {dev_id}: {e}")
        return {"command_status": "FAILED", "message": f"Erro gRPC: {e.details()}"}
    except Exception as e:
        logger.error(f"Erro ao enviar comando gRPC: {e}")
        return {"command_status": "FAILED", "message": f"Erro interno: {str(e)}"}

# === HANDLERS TCP ===
def handle_tcp_connection(conn, addr):
    """Gerencia uma conexão TCP individual"""
    logger.info(f"Conexão TCP de {addr}")
    
    try:
        with conn:
            sock_file = conn.makefile('rb')
            envelope = read_delimited_message_bytes(sock_file)
            
            if envelope:
                if envelope.message_type == smart_city_pb2.MessageType.DEVICE_INFO:
                    register_device(envelope.device_info)
                    
                elif envelope.message_type == smart_city_pb2.MessageType.CLIENT_REQUEST:
                    response = handle_client_request(envelope.client_request)
                    
                    resp_envelope = smart_city_pb2.SmartCityMessage(
                        message_type=smart_city_pb2.MessageType.GATEWAY_RESPONSE,
                        gateway_response=response
                    )
                    
                    data = resp_envelope.SerializeToString()
                    conn.sendall(encode_varint(len(data)) + data)
                    
    except Exception as e:
        logger.error(f"Erro na conexão TCP de {addr}: {e}")

def handle_client_request(req):
    if req.type == smart_city_pb2.ClientRequest.RequestType.LIST_DEVICES:
        with device_lock:
            devices = []
            for dev_id, dev_data in connected_devices.items():
                device_info = smart_city_pb2.DeviceInfo(
                    device_id=dev_id,
                    type=dev_data['type'],
                    ip_address=dev_data['ip'],
                    port=dev_data['port'],
                    initial_state=dev_data['status'],
                    is_actuator=dev_data['is_actuator'],
                    is_sensor=dev_data['is_sensor']
                )
                devices.append(device_info)
            
        return smart_city_pb2.GatewayResponse(
            type=smart_city_pb2.GatewayResponse.ResponseType.DEVICE_LIST,
            message=f"Lista de {len(devices)} dispositivos",
            devices=devices
        )
    
    elif req.type == smart_city_pb2.ClientRequest.RequestType.SEND_DEVICE_COMMAND:
        result = send_command_to_device(req.target_device_id, req.command.command_type, req.command.command_value)
        
        return smart_city_pb2.GatewayResponse(
            type=smart_city_pb2.GatewayResponse.ResponseType.COMMAND_ACK,
            message=result["message"],
            command_status=result["command_status"]
        )
    
    elif req.type == smart_city_pb2.ClientRequest.RequestType.GET_DEVICE_STATUS:
        dev_id = req.target_device_id
        with device_lock:
            dev = connected_devices.get(dev_id)
        if not dev:
            return smart_city_pb2.GatewayResponse(
                type=smart_city_pb2.GatewayResponse.ResponseType.ERROR,
                message="Dispositivo não encontrado."
            )

        # SENSOR: responder com último dado recebido via MQTT
        if dev.get('is_sensor', False):
            logger.info(f"[GATEWAY] Respondendo status do sensor {dev_id} com último dado MQTT recebido")
            last_data = dev.get('last_data', {})
            logger.info(f"[DEBUG] last_data recebido via MQTT: {last_data}")
            status_str = last_data.get('status')
            if status_str and hasattr(smart_city_pb2.DeviceStatus, status_str):
                status_enum = getattr(smart_city_pb2.DeviceStatus, status_str)
            else:
                status_enum = smart_city_pb2.DeviceStatus.IDLE  # Valor padrão seguro
            update = smart_city_pb2.DeviceUpdate(
                device_id=dev_id,
                type=dev['type'],
                current_status=status_enum,
            )
            if 'temperature' in last_data and 'humidity' in last_data:
                update.temperature_humidity.temperature = float(last_data['temperature'])
                update.temperature_humidity.humidity = float(last_data['humidity'])
            return smart_city_pb2.GatewayResponse(
                type=smart_city_pb2.GatewayResponse.ResponseType.DEVICE_STATUS_UPDATE,
                device_status=update,
                message="Status retornado do sensor (último dado MQTT recebido)."
            )

        # ATUADOR: obter status via gRPC (mantém igual)
        elif dev.get('is_actuator', False):
            logger.info(f"[GATEWAY] Consultando status do atuador {dev_id} via gRPC")
            grpc_result = send_grpc_command(dev_id, "GET_STATUS")
            logger.info(f"[DEBUG] grpc_result completo: {grpc_result}")
            if grpc_result["command_status"] == "SUCCESS":
                status_from_grpc = grpc_result.get('status', 'UNKNOWN_STATUS')
                logger.info(f"[DEBUG] status_from_grpc: {status_from_grpc}")
                
                # Tentar obter o enum do status
                try:
                    status_enum = getattr(smart_city_pb2.DeviceStatus, status_from_grpc)
                    logger.info(f"[DEBUG] status_enum convertido: {status_enum}")
                except AttributeError:
                    logger.warning(f"[DEBUG] Status '{status_from_grpc}' não encontrado no enum, usando UNKNOWN_STATUS")
                    status_enum = smart_city_pb2.DeviceStatus.UNKNOWN_STATUS
                
                update = smart_city_pb2.DeviceUpdate(
                    device_id=dev_id,
                    type=dev['type'],
                    current_status=status_enum,
                )
                return smart_city_pb2.GatewayResponse(
                    type=smart_city_pb2.GatewayResponse.ResponseType.DEVICE_STATUS_UPDATE,
                    device_status=update,
                    message="Status retornado do atuador via gRPC."
                )
            else:
                return smart_city_pb2.GatewayResponse(
                    type=smart_city_pb2.GatewayResponse.ResponseType.ERROR,
                    message=f"Falha ao obter status do atuador {dev_id} via gRPC: {grpc_result['message']}"
                )

        else:
            return smart_city_pb2.GatewayResponse(
                type=smart_city_pb2.GatewayResponse.ResponseType.ERROR,
                message=f"Tipo de dispositivo não suportado para consulta de status: {dev_id}"
            )
    
    return smart_city_pb2.GatewayResponse(
        type=smart_city_pb2.GatewayResponse.ResponseType.ERROR,
        message="Tipo de requisição não suportada"
    )

def listen_tcp_connections():
    """Thread que escuta por conexões TCP"""
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind(('0.0.0.0', GATEWAY_TCP_PORT))
    server_socket.listen(5)
    
    logger.info(f"Gateway TCP ouvindo na porta {GATEWAY_TCP_PORT}")
    
    while True:
        try:
            conn, addr = server_socket.accept()
            threading.Thread(target=handle_tcp_connection, args=(conn, addr), daemon=True).start()
        except Exception as e:
            logger.error(f"Erro ao aceitar conexão TCP: {e}")

# === MAIN ===
def main():
    logger.info("=== SMART CITY GATEWAY (MQTT + gRPC) ===")
    
    # Configurar MQTT
    if not setup_mqtt():
        logger.error("Falha ao configurar MQTT, terminando...")
        return
    
    # Iniciar threads
    multicast_thread = threading.Thread(target=multicast_discovery, daemon=True)
    tcp_thread = threading.Thread(target=listen_tcp_connections, daemon=True)
    
    multicast_thread.start()
    tcp_thread.start()
    
    logger.info("Gateway iniciado com sucesso!")
    logger.info(f"- Descoberta multicast: {MULTICAST_GROUP}:{MULTICAST_PORT}")
    logger.info(f"- Registro TCP: porta {GATEWAY_TCP_PORT}")
    logger.info(f"- MQTT Broker: {MQTT_BROKER_HOST}:{MQTT_BROKER_PORT}")
    logger.info("- Comandos para sensores: MQTT")
    logger.info("- Comandos para atuadores: gRPC")
    
    try:
        while True:
            time.sleep(1)
            
            # Limpeza periódica de dispositivos offline
            current_time = time.time()
            with device_lock:
                offline_devices = [
                    dev_id for dev_id, dev_data in connected_devices.items()
                    if current_time - dev_data['last_seen'] > 15  # 15 segundos
                ]
                
                for dev_id in offline_devices:
                    logger.info(f"Removendo dispositivo offline: {dev_id}")
                    del connected_devices[dev_id]
            
            # Limpeza de respostas MQTT antigas
            with mqtt_response_lock:
                old_responses = [
                    req_id for req_id, resp_data in mqtt_responses.items()
                    if current_time - resp_data.get('timestamp', 0) / 1000 > 15  # 15 segundos
                ]
                
                for req_id in old_responses:
                    del mqtt_responses[req_id]
    
    except KeyboardInterrupt:
        logger.info("Gateway interrompido pelo usuário")
    except Exception as e:
        logger.error(f"Erro no Gateway: {e}")
    finally:
        if mqtt_client:
            mqtt_client.loop_stop()
            mqtt_client.disconnect()
        logger.info("Gateway finalizado")

if __name__ == "__main__":
    main()
