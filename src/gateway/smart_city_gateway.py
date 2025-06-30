import socket
import threading
import time
import struct
import logging
import sys
from src.gateway.state import connected_devices, device_lock
from src.proto import smart_city_pb2

MULTICAST_GROUP = '224.1.1.1'
MULTICAST_PORT = 5007
GATEWAY_TCP_PORT = 12345
GATEWAY_UDP_PORT = 12346
API_TCP_PORT = 12347

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

connected_devices = {}
device_lock = threading.Lock()

def get_local_ip():
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
    shift = 0
    result = 0
    while True:
        b = stream.read(1)
        if not b:
            raise EOFError("Stream fechado inesperadamente ao ler varint.")
        b = ord(b)
        result |= (b & 0x7f) << shift
        if not (b & 0x80):
            return result
        shift += 7
        if shift >= 64:
            raise ValueError("Varint muito longo.")

def log_device_info_periodic():
    while True:
        time.sleep(30)
        with device_lock:
            if connected_devices:
                logger.info("--- Status Atual dos Dispositivos Conectados ---")
                for dev_id, dev_info in connected_devices.items():
                    type_name = smart_city_pb2.DeviceType.Name(dev_info['type'])
                    status_name = smart_city_pb2.DeviceStatus.Name(dev_info['status'])
                    logger.info(f"  ID: {dev_id} (Tipo: {type_name}), IP: {dev_info['ip']}:{dev_info['port']}, Status: {status_name}, Sensor Data: {dev_info.get('sensor_data', 'N/A')}, Última Vista: {time.time() - dev_info['last_seen']:.2f}s atrás")
                logger.info("---------------------------------------------")
            else:
                logger.info("Nenhum dispositivo conectado ainda.")

def discover_devices():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(('', MULTICAST_PORT))
    mreq = struct.pack("4sl", socket.inet_aton(MULTICAST_GROUP), socket.INADDR_ANY)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

    logger.info(f"Gateway enviando mensagens de descoberta multicast para {MULTICAST_GROUP}:{MULTICAST_PORT}...")
    request = smart_city_pb2.DiscoveryRequest(
        gateway_ip=get_local_ip(),
        gateway_tcp_port=GATEWAY_TCP_PORT,
        gateway_udp_port=GATEWAY_UDP_PORT
    )
    payload = request.SerializeToString()

    def periodic_discovery():
        while True:
            try:
                sock.sendto(payload, (MULTICAST_GROUP, MULTICAST_PORT))
            except Exception as e:
                logger.error(f"Erro no multicast discovery: {e}")
            time.sleep(10)

    threading.Thread(target=periodic_discovery, daemon=True).start()

    while True:
        try:
            data, addr = sock.recvfrom(4096)
            logger.debug(f"Ignorando resposta UDP de descoberta de {addr}")
        except Exception as e:
            logger.error(f"Erro na descoberta: {e}")

def handle_device_registration(device_info, addr):
    logger.info(f"Recebida DeviceInfo de {addr}: ID={device_info.device_id}, Tipo={smart_city_pb2.DeviceType.Name(device_info.type)}")
    with device_lock:
        previous = connected_devices.get(device_info.device_id, {})
        connected_devices[device_info.device_id] = {
            'ip': device_info.ip_address,
            'port': device_info.port,
            'type': device_info.type,
            'status': previous.get('status', device_info.initial_state),
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
        raise EOFError("Stream fechado inesperadamente.")
    return data

def handle_client_request(req, conn, addr):
    logger.info(f"Recebida ClientRequest de {addr}: tipo={req.type}")
    if req.type == smart_city_pb2.ClientRequest.RequestType.LIST_DEVICES:
        resp = smart_city_pb2.GatewayResponse(type=smart_city_pb2.GatewayResponse.DEVICE_LIST)
        with device_lock:
            for dev_id, dev in connected_devices.items():
                info = smart_city_pb2.DeviceInfo(
                    device_id=dev_id, type=dev['type'], ip_address=dev['ip'],
                    port=dev['port'], initial_state=dev['status'],
                    is_actuator=dev['is_actuator'], is_sensor=dev['is_sensor']
                )
                resp.devices.append(info)
        write_delimited_message(conn, resp)

    elif req.type == smart_city_pb2.ClientRequest.RequestType.SEND_DEVICE_COMMAND:
        dev_id = req.target_device_id
        resp = smart_city_pb2.GatewayResponse(type=smart_city_pb2.GatewayResponse.COMMAND_ACK)
        with device_lock:
            dev = connected_devices.get(dev_id)
        if dev:
            try:
                with socket.create_connection((dev['ip'], dev['port']), timeout=5) as sock:
                    write_delimited_message(sock, req.command)
                resp.command_status = "SUCCESS"
                resp.message = "Comando enviado com sucesso."
            except Exception as e:
                resp.command_status = "FAILED"
                resp.message = str(e)
        else:
            resp.command_status = "FAILED"
            resp.message = "Dispositivo não encontrado."
        write_delimited_message(conn, resp)

    elif req.type == smart_city_pb2.ClientRequest.RequestType.GET_DEVICE_STATUS:
        resp = smart_city_pb2.GatewayResponse(type=smart_city_pb2.GatewayResponse.DEVICE_STATUS_UPDATE)
        dev_id = req.target_device_id
        with device_lock:
            dev = connected_devices.get(dev_id)
        if dev:
            update = smart_city_pb2.DeviceUpdate(
                device_id=dev_id, type=dev['type'], current_status=dev['status']
            )
            if dev['is_sensor'] and isinstance(dev.get('sensor_data'), dict):
                logger.debug(f"[DEBUG] Sensor Data de {dev_id}: {dev['sensor_data']}")
                update.temperature_humidity.temperature = dev['sensor_data'].get('temperature', 0.0)
                update.temperature_humidity.humidity = dev['sensor_data'].get('humidity', 0.0)
            resp.device_status.CopyFrom(update)
            resp.message = "Status retornado."
        else:
            resp.message = "Dispositivo não encontrado."
        write_delimited_message(conn, resp)

def handle_tcp_connection(conn, addr):
    logger.info(f"Conexão TCP de {addr}")
    try:
        reader = conn.makefile('rb')
        data = read_delimited_message_bytes(reader)
        try:
            info = smart_city_pb2.DeviceInfo()
            info.ParseFromString(data)
            if info.device_id:
                handle_device_registration(info, addr)
                return
        except Exception:
            pass
        try:
            req = smart_city_pb2.ClientRequest()
            req.ParseFromString(data)
            handle_client_request(req, conn, addr)
        except Exception:
            logger.warning("Mensagem desconhecida recebida.")
    finally:
        conn.close()

def listen_tcp_connections():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(('', GATEWAY_TCP_PORT))
    server.listen(5)
    logger.info(f"Gateway ouvindo TCP na porta {GATEWAY_TCP_PORT}...")
    while True:
        conn, addr = server.accept()
        threading.Thread(target=handle_tcp_connection, args=(conn, addr)).start()

def listen_udp_sensored_data():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(('', GATEWAY_UDP_PORT))
    logger.info(f"Gateway ouvindo UDP na porta {GATEWAY_UDP_PORT}...")
    while True:
        try:
            data, addr = sock.recvfrom(4096)
            update = smart_city_pb2.DeviceUpdate()
            update.ParseFromString(data)
            with device_lock:
                if update.device_id in connected_devices:
                    dev = connected_devices[update.device_id]
                    dev['status'] = update.current_status
                    dev['last_seen'] = time.time()
                    if dev['is_sensor']:
                        if update.HasField("temperature_humidity"):
                            dev['sensor_data']['temperature'] = update.temperature_humidity.temperature
                            dev['sensor_data']['humidity'] = update.temperature_humidity.humidity
                    logger.info(f"Atualização de status de {update.device_id}: {smart_city_pb2.DeviceStatus.Name(update.current_status)}")
                else:
                    logger.warning(f"Atualização UDP ignorada. Dispositivo desconhecido: {update.device_id}")
        except Exception as e:
            logger.error(f"Erro no recebimento UDP: {e}")

def encode_varint(value):
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

def listen_api():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(('', API_TCP_PORT))
    sock.listen(5)
    logger.info(f"Gateway ouvindo API TCP na porta {API_TCP_PORT}...")
    while True:
        conn, addr = sock.accept()
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
        logger.info("Gateway encerrado por Ctrl+C")

if __name__ == "__main__":
    main()