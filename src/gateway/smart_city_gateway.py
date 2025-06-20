import socket
import threading
import time
import struct
import logging
import sys
import io
import google.protobuf.message

# Importar as classes geradas do Protocol Buffers
from src.proto import smart_city_pb2

# --- Configurações ---
MULTICAST_GROUP = '224.1.1.1'
MULTICAST_PORT = 5007
GATEWAY_TCP_PORT = 12345
GATEWAY_UDP_PORT = 12346

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


def handle_device_registration_tcp(conn, addr):
    """
    Lida com conexões TCP de dispositivos para o registro inicial (DeviceInfo).
    O sensor Java usa .writeDelimitedTo(), então o Python deve ler o prefixo varint.
    """
    logger.info(f"Conexão TCP para registro recebida de {addr}")
    reader = None
    try:
        reader = conn.makefile('rb')
        device_info = smart_city_pb2.DeviceInfo()

        message_length = _read_varint(reader)
        
        if message_length > 8192:
            raise ValueError(f"Mensagem Protobuf muito grande ({message_length} bytes) de {addr}. Limite de buffer excedido.")

        message_bytes = reader.read(message_length)
        
        if len(message_bytes) != message_length:
            raise EOFError("Stream fechado inesperadamente ou dados insuficientes ao ler a mensagem Protobuf.")

        device_info.ParseFromString(message_bytes)

        logger.info(f"Recebida DeviceInfo de {addr}: ID={device_info.device_id}, Tipo={smart_city_pb2.DeviceType.Name(device_info.type)}")

        with device_lock:
            connected_devices[device_info.device_id] = {
                'ip': device_info.ip_address,
                'port': device_info.port,
                'type': device_info.type,
                'status': device_info.initial_state,
                'is_actuator': device_info.is_actuator,
                'is_sensor': device_info.is_sensor,
                'last_seen': time.time(),
                'sensor_data': {} if device_info.is_sensor else 'N/A'
            }
            logger.info(f"Dispositivo {device_info.device_id} ({smart_city_pb2.DeviceType.Name(device_info.type)}) registrado/atualizado via TCP.")

    except google.protobuf.message.DecodeError as e:
        logger.error(f"Erro de decodificação Protobuf (DecodeError) ao ler DeviceInfo de {addr}: {e}")
    except EOFError as e:
        logger.error(f"Conexão fechada inesperadamente (EOFError) ao ler DeviceInfo de {addr}: {e}")
    except ValueError as e:
        logger.error(f"Erro de valor (ValueError) ao processar DeviceInfo de {addr}: {e}")
    except Exception as e:
        logger.error(f"Erro genérico ao processar registro TCP de dispositivo {addr}: {e}", exc_info=True)
    finally:
        if reader:
            reader.close()
        conn.close()
        logger.info(f"Conexão TCP de registro de {addr} fechada.")


def listen_tcp_connections():
    """Escuta por conexões TCP de clientes ou para registro de dispositivos."""
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind(('', GATEWAY_TCP_PORT))
    server_socket.listen(5)
    logger.info(f"Gateway escutando por conexões TCP na porta {GATEWAY_TCP_PORT} (para registro/cliente)...")

    while True:
        conn, addr = server_socket.accept()
        threading.Thread(target=handle_device_registration_tcp, args=(conn, addr)).start()


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
                        dev_info['sensor_data']['temperature_value'] = device_update.temperature_value
                        dev_info['sensor_data']['air_quality_index'] = device_update.air_quality_index
                        dev_info['sensor_data']['custom_config_status'] = device_update.custom_config_status
                    logger.info(f"Dados sensoriados de {device_update.device_id} atualizados: {dev_info['sensor_data']}")
                else:
                    logger.warning(f"Dados UDP de dispositivo desconhecido recebidos de {addr}: ID={device_update.device_id}. Ignorando.")
        except Exception as e:
            logger.error(f"Erro ao processar dados sensoriados UDP de {addr}: {e}", exc_info=True)


def main():
    logger.info("Iniciando Gateway da Cidade Inteligente - Versão de Teste...")

    threading.Thread(target=discover_devices, daemon=True).start()
    threading.Thread(target=listen_tcp_connections, daemon=True).start()
    threading.Thread(target=listen_udp_sensored_data, daemon=True).start()
    threading.Thread(target=log_device_info_periodic, daemon=True).start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Gateway encerrado por Ctrl+C.")
    except Exception as e:
        logger.critical(f"Erro crítico no Gateway: {e}", exc_info=True)

if __name__ == "__main__":
    main()