import socket
import threading
import time
import struct
import logging
import sys
from src.gateway.state import connected_devices, device_lock

# Importar as classes geradas do Protocol Buffers
from src.proto import smart_city_pb2

# --- Configurações ---
MULTICAST_GROUP = '224.1.1.1'
MULTICAST_PORT = 5007
GATEWAY_TCP_PORT = 12345
GATEWAY_UDP_PORT = 12346
ESP8266_UDP_PORT = 8888  # Porta para receber dados do ESP8266
API_TCP_PORT = 12347


# Configuração de Logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# --- Dados Globais do Gateway ---
connected_devices = {}
device_lock = threading.Lock()
# connected_devices = {}
# device_lock = threading.Lock() # Para proteger o acesso a connected_devices

# --- Funções Auxiliares ---
def get_local_ip():
    """Tenta obter o endereço IP local da máquina."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

def _read_varint(stream):
    """Lê um varint (tamanho da mensagem) de um stream."""
    shift = 0
    result = 0
    while True:
        b = stream.read(1)
        if not b:
            raise EOFError("Stream fechado inesperadamente ou dados insuficientes ao ler varint.")
        b = ord(b)
        result |= (b & 0x7f) << shift
        if not (b & 0x80):
            return result
        shift += 7
        if shift >= 64:
            raise ValueError("Varint muito longo (provável corrupção de dados).")


def log_device_info_periodic():
    """Loga periodicamente as informações dos dispositivos conectados."""
    while True:
        time.sleep(30)
        with device_lock:
            if connected_devices:
                logger.info("--- Status Atual dos Dispositivos Conectados ---")
                for dev_id, dev_info in connected_devices.items():
                    device_type_name = smart_city_pb2.DeviceType.Name(dev_info['type'])
                    device_status_name = smart_city_pb2.DeviceStatus.Name(dev_info['status'])
                    logger.info(f"  ID: {dev_id} (Tipo: {device_type_name}), "
                                f"IP: {dev_info['ip']}:{dev_info['port']}, "
                                f"Status: {device_status_name}, "
                                f"Sensor Data: {dev_info.get('sensor_data', 'N/A')}, "
                                f"Última Vista: {time.time() - dev_info['last_seen']:.2f}s atrás")
                logger.info("---------------------------------------------")
            else:
                logger.info("Nenhum dispositivo conectado ainda.")

# --- Lógica do Gateway ---

def discover_devices():
    """Envia mensagens multicast UDP para descoberta de dispositivos e escuta respostas."""
    multicast_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    multicast_socket.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
    multicast_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    multicast_socket.bind(('', MULTICAST_PORT))
    mreq = struct.pack("4sl", socket.inet_aton(MULTICAST_GROUP), socket.INADDR_ANY)
    multicast_socket.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

    logger.info(f"Gateway enviando mensagens de descoberta multicast para {MULTICAST_GROUP}:{MULTICAST_PORT}...")

    discovery_request = smart_city_pb2.DiscoveryRequest(
        gateway_ip=get_local_ip(),
        gateway_tcp_port=GATEWAY_TCP_PORT,
        gateway_udp_port=GATEWAY_UDP_PORT
    )
    discovery_bytes = discovery_request.SerializeToString()

    def send_periodic_discovery():
        while True:
            try:
                multicast_socket.sendto(discovery_bytes, (MULTICAST_GROUP, MULTICAST_PORT))
                logger.debug("Enviado requisição de descoberta.")
            except Exception as e:
                logger.error(f"Erro ao enviar multicast discovery: {e}")
            time.sleep(10)

    threading.Thread(target=send_periodic_discovery, daemon=True).start()

    logger.info("Gateway escutando por respostas (UDP) de descoberta de dispositivos (não registro principal)...")
    while True:
        try:
            data, addr = multicast_socket.recvfrom(4096)
            logger.debug(f"Recebida mensagem UDP na porta multicast de {addr}. Ignorando para registro, esperando TCP.")
        except Exception as e:
            logger.error(f"Erro ao processar mensagem na porta multicast: {e}")


def handle_device_registration(device_info, addr):
    logger.info(f"Recebida DeviceInfo de {addr}: ID={device_info.device_id}, Tipo={smart_city_pb2.DeviceType.Name(device_info.type)}")
    with device_lock:
        previous = connected_devices.get(device_info.device_id, {})
        connected_devices[device_info.device_id] = {
            'ip': device_info.ip_address,
            'port': device_info.port,
            'type': device_info.type,
            'status': device_info.initial_state,
            'is_actuator': device_info.is_actuator,
            'is_sensor': device_info.is_sensor,
            'last_seen': time.time(),
            'sensor_data': previous.get('sensor_data', {}) if device_info.is_sensor else 'N/A'
        }
        logger.info(f"Dispositivo {device_info.device_id} ({smart_city_pb2.DeviceType.Name(device_info.type)}) registrado/atualizado via TCP.")


def write_delimited_message(conn, message):
    data = message.SerializeToString()
    conn.sendall(encode_varint(len(data)) + data)

def read_delimited_message_bytes(reader):
    length = _read_varint(reader)
    data = reader.read(length)
    if len(data) != length:
        raise EOFError("Stream fechado inesperadamente ou dados insuficientes ao ler mensagem.")
    return data

def handle_client_request(client_request, conn, addr):
    logger.info(f"Recebida ClientRequest de {addr}: tipo={client_request.type}")
    print(f"[DEBUG] ClientRequest recebida: {client_request}")
    if client_request.type == smart_city_pb2.ClientRequest.RequestType.LIST_DEVICES:
        logger.info("Processando LIST_DEVICES para o cliente.")
        response = smart_city_pb2.GatewayResponse()
        response.type = smart_city_pb2.GatewayResponse.ResponseType.DEVICE_LIST
        with device_lock:
            for dev_id, dev_info in connected_devices.items():
                device = smart_city_pb2.DeviceInfo(
                    device_id=dev_id,
                    type=dev_info['type'],
                    ip_address=dev_info['ip'],
                    port=dev_info['port'],
                    initial_state=dev_info['status'],
                    is_actuator=dev_info['is_actuator'],
                    is_sensor=dev_info['is_sensor']
                )
                response.devices.append(device)
        print(f"[DEBUG] GatewayResponse montada: {response}")
        write_delimited_message(conn, response)
        logger.info("Resposta LIST_DEVICES enviada ao cliente.")

    elif client_request.type == smart_city_pb2.ClientRequest.RequestType.SEND_DEVICE_COMMAND:
        logger.info("Processando SEND_DEVICE_COMMAND para o cliente.")
        response = smart_city_pb2.GatewayResponse()
        response.type = smart_city_pb2.GatewayResponse.ResponseType.COMMAND_ACK

        device_id = client_request.target_device_id
        with device_lock:
            dev_info = connected_devices.get(device_id)
        if dev_info:
            try:
                # Abre conexão TCP com o atuador
                with socket.create_connection((dev_info['ip'], dev_info['port']), timeout=5) as sock:
                    # Envia o comando usando o mesmo protocolo (varint + payload)
                    write_delimited_message(sock, client_request.command)
                response.command_status = "SUCCESS"
                response.message = "Comando enviado ao dispositivo com sucesso."
            except Exception as e:
                response.command_status = "FAILED"
                response.message = f"Erro ao enviar comando ao dispositivo: {e}"
        else:
            response.command_status = "FAILED"
            response.message = f"Dispositivo '{device_id}' não encontrado no gateway."

        print(f"[DEBUG] GatewayResponse COMMAND_ACK: {response}")
        write_delimited_message(conn, response)
        logger.info("Resposta COMMAND_ACK enviada ao cliente.")
    elif client_request.type == smart_city_pb2.ClientRequest.RequestType.GET_DEVICE_STATUS:
        logger.info("Processando GET_DEVICE_STATUS para o cliente.")
        response = smart_city_pb2.GatewayResponse()
        response.type = smart_city_pb2.GatewayResponse.ResponseType.DEVICE_STATUS_UPDATE

        device_id = client_request.target_device_id
        with device_lock:
            dev_info = connected_devices.get(device_id)
        if dev_info:
            # Monta um DeviceUpdate com o status atual do dispositivo
            device_update = smart_city_pb2.DeviceUpdate(
                device_id=device_id,
                type=dev_info['type'],
                current_status=dev_info['status'],
            )
            # Só preenche campos de sensor se for sensor
            if dev_info['is_sensor'] and isinstance(dev_info.get('sensor_data'), dict):
                if dev_info['type'] == smart_city_pb2.DeviceType.TEMPERATURE_SENSOR:
                    device_update.temperature_humidity.temperature = dev_info['sensor_data'].get('temperature', 0.0)
                    device_update.temperature_humidity.humidity = dev_info['sensor_data'].get('humidity', 0.0)
                elif dev_info['type'] == smart_city_pb2.DeviceType.CURRENT_SENSOR:
                    device_update.current_sensor.current = dev_info['sensor_data'].get('current', 0.0)
                    device_update.current_sensor.voltage = dev_info['sensor_data'].get('voltage', 0.0)
                    device_update.current_sensor.power = dev_info['sensor_data'].get('power', 0.0)
                    # Adicione outros tipos conforme necessário
                    device_update.custom_config_status = dev_info['sensor_data'].get('custom_config_status', "")
            response.device_status.CopyFrom(device_update)
            response.message = "Status do dispositivo retornado com sucesso."
        else:
            response.message = f"Dispositivo '{device_id}' não encontrado no gateway."
        print(f"[DEBUG] GatewayResponse DEVICE_STATUS_UPDATE: {response}")
        write_delimited_message(conn, response)
        logger.info("Resposta DEVICE_STATUS_UPDATE enviada ao cliente.")
    else:
        logger.warning(f"Tipo de ClientRequest não suportado: {client_request.type}")


def handle_tcp_connection(conn, addr):
    logger.info(f"Conexão TCP recebida de {addr}")
    reader = None
    try:
        reader = conn.makefile('rb')
        print(f"[DEBUG] Aguardando mensagem do cliente/dispositivo...")
        
        # Lê os bytes da mensagem delimitada uma única vez
        message_bytes = read_delimited_message_bytes(reader)
        print(f"[DEBUG] Mensagem recebida: {len(message_bytes)} bytes")
        print(f"[DEBUG] Primeiros 10 bytes: {message_bytes[:10].hex()}")
        
        # Tenta decodificar como DeviceInfo
        try:
            device_info = smart_city_pb2.DeviceInfo()
            device_info.ParseFromString(message_bytes)
            if device_info.device_id:
                handle_device_registration(device_info, addr)
                return
        except Exception as e:
            print(f"[DEBUG] Não é DeviceInfo: {e}")
            print(f"[DEBUG] Erro detalhado: {type(e).__name__}: {str(e)}")
            
        # Tenta decodificar como ClientRequest
        try:
            client_request = smart_city_pb2.ClientRequest()
            client_request.ParseFromString(message_bytes)
            handle_client_request(client_request, conn, addr)
            return
        except Exception as e:
            print(f"[DEBUG] Não é ClientRequest: {e}")
            print(f"[DEBUG] Erro detalhado: {type(e).__name__}: {str(e)}")
            
        logger.warning("Mensagem recebida não é DeviceInfo nem ClientRequest válida.")
    except Exception as e:
        print(f"[DEBUG] Exceção em handle_tcp_connection: {e}")
        logger.error(f"Erro genérico ao processar conexão TCP de {addr}: {e}", exc_info=True)
    finally:
        if reader:
            reader.close()
        conn.close()
        logger.info(f"Conexão TCP de {addr} fechada.")


def listen_tcp_connections():
    """Escuta por conexões TCP de clientes ou para registro de dispositivos."""
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind(('', GATEWAY_TCP_PORT))
    server_socket.listen(5)
    logger.info(f"Gateway escutando por conexões TCP na porta {GATEWAY_TCP_PORT} (para registro/cliente)...")

    while True:
        conn, addr = server_socket.accept()
        threading.Thread(target=handle_tcp_connection, args=(conn, addr)).start()


def listen_udp_sensored_data():
    """Escuta por dados sensoriados UDP de dispositivos."""
    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    udp_socket.bind(('', GATEWAY_UDP_PORT))
    logger.info(f"Gateway escutando por dados sensoriados UDP na porta {GATEWAY_UDP_PORT}...")
    while True:
        try:
            data, addr = udp_socket.recvfrom(4096)
            device_update = smart_city_pb2.DeviceUpdate()
            device_update.ParseFromString(data)

            logger.debug(f"Recebida atualização UDP de {addr}: Device ID={device_update.device_id}, Status={smart_city_pb2.DeviceStatus.Name(device_update.current_status)}")

            with device_lock:
                if device_update.device_id in connected_devices:
                    dev_info = connected_devices[device_update.device_id]
                    dev_info['status'] = device_update.current_status
                    dev_info['last_seen'] = time.time()
                    if dev_info['is_sensor']:
                        # Atualiza dados sensoriados conforme o tipo
                        if device_update.HasField("temperature_humidity"):
                            dev_info['sensor_data']['temperature'] = device_update.temperature_humidity.temperature
                            dev_info['sensor_data']['humidity'] = device_update.temperature_humidity.humidity
                        if device_update.HasField("current_sensor"):
                            dev_info['sensor_data']['current'] = device_update.current_sensor.current
                            dev_info['sensor_data']['voltage'] = device_update.current_sensor.voltage
                            dev_info['sensor_data']['power'] = device_update.current_sensor.power
                        # Adicione outros tipos conforme necessário
                        dev_info['sensor_data']['custom_config_status'] = device_update.custom_config_status
                    logger.info(f"Dados sensoriados de {device_update.device_id} atualizados: {dev_info['sensor_data']}")
                else:
                    logger.warning(f"Dados UDP de dispositivo desconhecido recebidos de {addr}: ID={device_update.device_id}. Ignorando.")
        except Exception as e:
            logger.error(f"Erro ao processar dados sensoriados UDP de {addr}: {e}", exc_info=True)

def encode_varint(value: int) -> bytes:
    """Codifica um inteiro no formato varint (compatível com Protobuf)."""
    result = b""
    while True:
        bits = value & 0x7F
        value >>= 7
        if value:
            result += struct.pack("B", bits | 0x80)
        else:
            result += struct.pack("B", bits)
            break
    return result


def send_tcp_command(device_ip: str, device_port: int, command_type: str, command_value: str) -> bool:
    try:
        with socket.create_connection((device_ip, device_port), timeout=5) as sock:
            cmd = smart_city_pb2.DeviceCommand(
                command_type=command_type,
                command_value=command_value
            )
            data = cmd.SerializeToString()
            varint = encode_varint(len(data))
            sock.sendall(varint + data)

            logger.info(f"Comando {command_type} enviado para {device_ip}:{device_port} com valor {command_value}")
            return True
    except Exception as e:
        logger.error(f"Erro ao enviar comando TCP para {device_ip}:{device_port} -> {e}")
        return False
    
def listen_api():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(('', API_TCP_PORT))
    s.listen(5)
    logger.info(f"Gateway escutando por conexões da API TCP na porta {API_TCP_PORT}...")
    while True:
        conn, addr = s.accept()
        threading.Thread(target=handle_tcp_connection, args=(conn, addr)).start()

def main():
    threading.Thread(target=discover_devices, daemon=True).start()
    threading.Thread(target=listen_tcp_connections, daemon=True).start()
    threading.Thread(target=listen_udp_sensored_data, daemon=True).start()
    threading.Thread(target=log_device_info_periodic, daemon=True).start()
    threading.Thread(target=listen_api, daemon=True).start() 

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Gateway encerrado por Ctrl+C.")
    except Exception as e:
        logger.critical(f"Erro crítico no Gateway: {e}", exc_info=True)

if __name__ == "__main__":
    main()