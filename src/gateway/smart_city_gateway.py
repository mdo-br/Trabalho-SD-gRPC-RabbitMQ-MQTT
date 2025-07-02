"""
Smart City Gateway - Sistema de Gerenciamento de Dispositivos IoT

Este módulo implementa o gateway central que gerencia a comunicação entre dispositivos IoT
(sensores e atuadores) e clientes. O gateway suporta:

- Descoberta automática de dispositivos via multicast UDP
- Registro de dispositivos via TCP
- Recebimento de dados sensoriados via UDP
- Processamento de comandos de clientes
- API para consultas e controle

Protocolos utilizados:
- Protocol Buffers para serialização de mensagens
- TCP para registro de dispositivos e comandos
- UDP para dados sensoriados e descoberta multicast
"""

import socket
import threading
import time
import struct
import logging
import sys
from src.gateway.state import connected_devices, device_lock
from src.proto import smart_city_pb2

# --- Configurações de Rede ---
MULTICAST_GROUP = '224.1.1.1'  # Endereço multicast para descoberta de dispositivos
MULTICAST_PORT = 5007          # Porta multicast para descoberta
GATEWAY_TCP_PORT = 12345       # Porta TCP para registro de dispositivos e comandos
GATEWAY_UDP_PORT = 12346       # Porta UDP para recebimento de dados sensoriados
API_TCP_PORT = 12347           # Porta TCP para API externa

# --- Configuração de Logging ---
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# --- Variáveis Globais ---
connected_devices = {}  # Dicionário com dispositivos conectados: {device_id: device_info}
device_lock = threading.Lock()  # Lock para acesso thread-safe aos dispositivos

def get_local_ip():
    """
    Obtém o endereço IP local da máquina.
    
    Tenta conectar a um endereço externo para determinar o IP local.
    Se falhar, retorna localhost (127.0.0.1).
    
    Returns:
        str: Endereço IP local da máquina
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 80))  # Conecta ao Google DNS
        IP = s.getsockname()[0]
    except Exception:
        try:
            s.connect(('10.255.255.255', 1))
            IP = s.getsockname()[0]
        except Exception:
            IP = '127.0.0.1'
    finally:
        s.close()
    return IP

def _read_varint(stream):
    """
    Lê um varint (inteiro variável) de um stream.
    
    Varint é o formato usado pelo Protocol Buffers para codificar inteiros.
    Cada byte contém 7 bits de dados e 1 bit indicando se há mais bytes.
    
    Args:
        stream: Stream de bytes para leitura
        
    Returns:
        int: Valor do varint lido
        
    Raises:
        EOFError: Se o stream for fechado inesperadamente
        ValueError: Se o varint for muito longo (corrupção de dados)
    """
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
    """
    Thread que loga periodicamente o status dos dispositivos conectados.
    
    Executa a cada 30 segundos e mostra informações sobre todos os dispositivos
    registrados no gateway, incluindo tipo, status, dados de sensor e última atividade.
    """
    while True:
        time.sleep(30)
        with device_lock:
            if connected_devices:
                logger.info("--- Status Atual dos Dispositivos Conectados ---")
                for dev_id, dev_info in connected_devices.items():
                    type_name = smart_city_pb2.DeviceType.Name(dev_info['type'])
                    status_name = smart_city_pb2.DeviceStatus.Name(dev_info['status'])
                    # Exibe dados de sensor e frequência, se disponíveis
                    sensor_data = dev_info.get('sensor_data', {})
                    freq_str = ''
                    if 'frequency_ms' in sensor_data:
                        freq_str = f", Freq: {sensor_data['frequency_ms']}ms"
                    logger.info(f"  ID: {dev_id} (Tipo: {type_name}), IP: {dev_info['ip']}:{dev_info['port']}, Status: {status_name}, Sensor Data: {sensor_data}{freq_str}, Última Vista: {time.time() - dev_info['last_seen']:.2f}s atrás")
                logger.info("---------------------------------------------")
            else:
                logger.info("Nenhum dispositivo conectado ainda.")

def discover_devices():
    """
    Thread responsável pela descoberta de dispositivos via multicast UDP.
    
    Configura um socket multicast e envia periodicamente mensagens de descoberta
    para que dispositivos na rede possam encontrar o gateway. As respostas UDP
    são ignoradas, pois o registro real acontece via TCP.
    """
    # Configuração do socket multicast
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(('', MULTICAST_PORT))
    mreq = struct.pack("4sl", socket.inet_aton(MULTICAST_GROUP), socket.INADDR_ANY)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

    logger.info(f"Gateway enviando mensagens de descoberta multicast para {MULTICAST_GROUP}:{MULTICAST_PORT}...")
    
    # Criação da mensagem de descoberta
    request = smart_city_pb2.DiscoveryRequest(
        gateway_ip=get_local_ip(),
        gateway_tcp_port=GATEWAY_TCP_PORT,
        gateway_udp_port=GATEWAY_UDP_PORT
    )
    payload = request.SerializeToString()

    def periodic_discovery():
        """Envia mensagens de descoberta a cada 10 segundos"""
        while True:
            try:
                local_ip = get_local_ip()
                logger.info(f"[DISCOVERY] Enviando pacote multicast: IP local={local_ip}, grupo={MULTICAST_GROUP}, porta={MULTICAST_PORT}, tamanho={len(payload)} bytes")
                sock.sendto(payload, (MULTICAST_GROUP, MULTICAST_PORT))
                logger.info(f"[DISCOVERY] Pacote multicast enviado para {MULTICAST_GROUP}:{MULTICAST_PORT} em {time.strftime('%H:%M:%S')}")
            except Exception as e:
                logger.error(f"[DISCOVERY][ERRO] Falha ao enviar multicast: {e}")
            time.sleep(10)

    threading.Thread(target=periodic_discovery, daemon=True).start()

    # Loop principal - escuta por respostas (debug)
    local_ip = get_local_ip()
    while True:
        try:
            data, addr = sock.recvfrom(4096)
            if addr[0] != local_ip:
                logger.info(f"[DISCOVERY][RECV] Pacote UDP recebido na porta {MULTICAST_PORT} de {addr[0]}:{addr[1]}, tamanho={len(data)} bytes")
        except Exception as e:
            logger.error(f"[DISCOVERY][ERRO] Falha ao receber UDP: {e}")

def handle_device_registration(device_info, addr):
    """
    Processa o registro de um dispositivo no gateway.
    
    Quando um dispositivo se conecta via TCP e envia uma mensagem DeviceInfo,
    esta função registra ou atualiza as informações do dispositivo no dicionário
    de dispositivos conectados.
    
    Args:
        device_info: Objeto DeviceInfo do Protocol Buffers
        addr: Endereço (IP, porta) do dispositivo
    """
    logger.info(f"Recebida DeviceInfo de {addr}: ID={device_info.device_id}, Tipo={smart_city_pb2.DeviceType.Name(device_info.type)}")
    with device_lock:
        # Preserva dados existentes se o dispositivo já estiver registrado
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
    """
    Envia uma mensagem Protocol Buffers com delimitador de tamanho, agora usando SmartCityMessage como envelope.
    """
    envelope = smart_city_pb2.SmartCityMessage()
    # Detecta o tipo da mensagem e encapsula
    if isinstance(message, smart_city_pb2.ClientRequest):
        envelope.message_type = smart_city_pb2.MessageType.CLIENT_REQUEST
        envelope.client_request.CopyFrom(message)
    elif isinstance(message, smart_city_pb2.DeviceUpdate):
        envelope.message_type = smart_city_pb2.MessageType.DEVICE_UPDATE
        envelope.device_update.CopyFrom(message)
    elif isinstance(message, smart_city_pb2.GatewayResponse):
        envelope.message_type = smart_city_pb2.MessageType.GATEWAY_RESPONSE
        envelope.gateway_response.CopyFrom(message)
    elif isinstance(message, smart_city_pb2.DeviceInfo):
        envelope.message_type = smart_city_pb2.MessageType.DEVICE_INFO
        envelope.device_info.CopyFrom(message)
    elif isinstance(message, smart_city_pb2.DiscoveryRequest):
        envelope.message_type = smart_city_pb2.MessageType.DISCOVERY_REQUEST
        envelope.discovery_request.CopyFrom(message)
    else:
        raise ValueError("Tipo de mensagem não suportado para envelope!")
    data = envelope.SerializeToString()
    conn.sendall(encode_varint(len(data)) + data)

def read_delimited_message_bytes(reader):
    """
    Lê uma mensagem Protocol Buffers com delimitador de tamanho, agora esperando sempre SmartCityMessage.
    """
    length = _read_varint(reader)
    data = reader.read(length)
    if len(data) != length:
        raise EOFError("Stream fechado inesperadamente.")
    envelope = smart_city_pb2.SmartCityMessage()
    envelope.ParseFromString(data)
    return envelope

def handle_client_request(req, conn, addr):
    """
    Processa requisições de clientes.
    
    Clientes podem solicitar:
    - LIST_DEVICES: Lista todos os dispositivos conectados
    - SEND_DEVICE_COMMAND: Envia comando para um dispositivo específico
    - GET_DEVICE_STATUS: Obtém status atual de um dispositivo
    
    Args:
        req: Objeto ClientRequest do Protocol Buffers
        conn: Conexão socket com o cliente
        addr: Endereço do cliente
    """
    logger.info(f"Recebida ClientRequest de {addr}: tipo={req.type}")
    
    # Lista todos os dispositivos conectados
    if req.type == smart_city_pb2.ClientRequest.RequestType.LIST_DEVICES:
        resp = smart_city_pb2.GatewayResponse(type=smart_city_pb2.GatewayResponse.ResponseType.DEVICE_LIST)
        with device_lock:
            for dev_id, dev in connected_devices.items():
                info = smart_city_pb2.DeviceInfo(
                    device_id=dev_id, type=dev['type'], ip_address=dev['ip'],
                    port=dev['port'], initial_state=dev['status'],
                    is_actuator=dev['is_actuator'], is_sensor=dev['is_sensor']
                )
                resp.devices.append(info)
        write_delimited_message(conn, resp)

    # Envia comando para um dispositivo específico
    elif req.type == smart_city_pb2.ClientRequest.RequestType.SEND_DEVICE_COMMAND:
        dev_id = req.target_device_id
        resp = smart_city_pb2.GatewayResponse(type=smart_city_pb2.GatewayResponse.ResponseType.COMMAND_ACK)
        with device_lock:
            dev = connected_devices.get(dev_id)
        if dev:
            try:
                # Conecta ao dispositivo e envia o comando como envelope
                with socket.create_connection((dev['ip'], dev['port']), timeout=5) as sock:
                    envelope = smart_city_pb2.SmartCityMessage()
                    envelope.message_type = smart_city_pb2.MessageType.CLIENT_REQUEST
                    envelope.client_request.CopyFrom(req)
                    data = envelope.SerializeToString()
                    sock.sendall(encode_varint(len(data)) + data)
                    # --- Lê resposta TCP (DeviceUpdate) ---
                    sock_file = sock.makefile('rb')
                    resp_envelope = read_delimited_message_bytes(sock_file)
                    if resp_envelope.message_type == smart_city_pb2.MessageType.DEVICE_UPDATE:
                        update = resp_envelope.device_update
                        logger.info(f"[GATEWAY] Status atualizado recebido do dispositivo: {update.device_id} -> {smart_city_pb2.DeviceStatus.Name(update.current_status)}")
                        with device_lock:
                            if update.device_id in connected_devices:
                                dev2 = connected_devices[update.device_id]
                                dev2['status'] = update.current_status
                                dev2['last_seen'] = time.time()
                                # Armazena frequência se presente (dentro do oneof data)
                                try:
                                    if update.HasField('frequency_ms'):
                                        dev2['sensor_data']['frequency_ms'] = update.frequency_ms
                                        logger.info(f"[GATEWAY] Frequência armazenada: {update.frequency_ms} ms")
                                except Exception as e:
                                    logger.error(f"[GATEWAY] Erro ao processar frequência: {e}")
                        resp.command_status = "SUCCESS"
                        resp.message = f"Comando enviado e status atualizado: {smart_city_pb2.DeviceStatus.Name(update.current_status)}"
                    else:
                        logger.warning(f"[GATEWAY] Envelope inesperado na resposta TCP: {resp_envelope.message_type}")
                        resp.command_status = "FAILED"
                        resp.message = "Resposta inesperada do dispositivo."
            except Exception as e:
                resp.command_status = "FAILED"
                resp.message = str(e)
        else:
            resp.command_status = "FAILED"
            resp.message = "Dispositivo não encontrado."
        write_delimited_message(conn, resp)

    # Obtém status de um dispositivo específico
    elif req.type == smart_city_pb2.ClientRequest.RequestType.GET_DEVICE_STATUS:
        resp = smart_city_pb2.GatewayResponse(type=smart_city_pb2.GatewayResponse.ResponseType.DEVICE_STATUS_UPDATE)
        dev_id = req.target_device_id
        with device_lock:
            dev = connected_devices.get(dev_id)
        if dev:
            # Cria DeviceUpdate com status atual
            update = smart_city_pb2.DeviceUpdate(
                device_id=dev_id, type=dev['type'], current_status=dev['status']
            )
            # Adiciona dados de sensor se disponíveis
            if dev['is_sensor'] and isinstance(dev.get('sensor_data'), dict):
                logger.info(f"[DEBUG] Sensor Data de {dev_id}: {dev['sensor_data']}")
                update.temperature_humidity.temperature = dev['sensor_data'].get('temperature', 0.0)
                update.temperature_humidity.humidity = dev['sensor_data'].get('humidity', 0.0)
                # Adiciona frequência se disponível
                if 'frequency_ms' in dev['sensor_data']:
                    update.frequency_ms = dev['sensor_data']['frequency_ms']
                    logger.info(f"[DEBUG] Frequência adicionada ao DeviceUpdate: {dev['sensor_data']['frequency_ms']} ms")
                else:
                    logger.info(f"[DEBUG] Frequência NÃO encontrada em sensor_data para {dev_id}")
            resp.device_status.CopyFrom(update)
            resp.message = "Status retornado."
        else:
            resp.message = "Dispositivo não encontrado."
        write_delimited_message(conn, resp)

def handle_tcp_connection(conn, addr):
    """
    Gerencia uma conexão TCP individual.
    Agora espera sempre SmartCityMessage como envelope.
    """
    logger.info(f"Conexão TCP de {addr}")
    try:
        reader = conn.makefile('rb')
        envelope = read_delimited_message_bytes(reader)
        # Desempacota e trata conforme o tipo
        if envelope.message_type == smart_city_pb2.MessageType.CLIENT_REQUEST:
            req = envelope.client_request
            handle_client_request(req, conn, addr)
        elif envelope.message_type == smart_city_pb2.MessageType.DEVICE_INFO:
            info = envelope.device_info
            if info.device_id:
                handle_device_registration(info, addr)
        else:
            logger.warning("Mensagem desconhecida recebida no envelope.")
    finally:
        conn.close()

def listen_tcp_connections():
    """
    Thread que escuta por conexões TCP.
    
    Aceita conexões TCP na porta GATEWAY_TCP_PORT e cria uma thread
    para cada conexão para processar mensagens de registro de dispositivos
    e requisições de clientes.
    """
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(('', GATEWAY_TCP_PORT))
    server.listen(5)
    logger.info(f"Gateway ouvindo TCP na porta {GATEWAY_TCP_PORT}...")
    while True:
        conn, addr = server.accept()
        threading.Thread(target=handle_tcp_connection, args=(conn, addr)).start()

def listen_udp_sensored_data():
    """
    Thread que escuta por dados sensoriados via UDP.
    Recebe mensagens DeviceUpdate de sensores via UDP na porta GATEWAY_UDP_PORT.
    Atualiza o status e dados dos sensores no dicionário de dispositivos conectados.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(('', GATEWAY_UDP_PORT))
    logger.info(f"Gateway ouvindo UDP na porta {GATEWAY_UDP_PORT}...")
    while True:
        try:
            data, addr = sock.recvfrom(4096)
            logger.info(f"[UDP] Pacote recebido de {addr}, {len(data)} bytes")
            update = smart_city_pb2.DeviceUpdate()
            update.ParseFromString(data)
            logger.info(f"[UDP] DeviceUpdate: device_id={update.device_id}, type={update.type}, current_status={update.current_status}")
            with device_lock:
                if update.device_id in connected_devices:
                    dev = connected_devices[update.device_id]
                    dev['status'] = update.current_status
                    dev['last_seen'] = time.time()
                    # Atualiza dados de sensor se disponíveis
                    if dev['is_sensor']:
                        if update.HasField("temperature_humidity"):
                            dev['sensor_data']['temperature'] = update.temperature_humidity.temperature
                            dev['sensor_data']['humidity'] = update.temperature_humidity.humidity
                        # Armazena frequência se presente (dentro do oneof data)
                        if update.HasField('frequency_ms'):
                            dev['sensor_data']['frequency_ms'] = update.frequency_ms
                            logger.info(f"[UDP] Frequência armazenada para {update.device_id}: {update.frequency_ms} ms")
                        else:
                            logger.info(f"[UDP] Frequência NÃO encontrada no DeviceUpdate UDP para {update.device_id}")
                    logger.info(f"Atualização de status de {update.device_id}: {smart_city_pb2.DeviceStatus.Name(update.current_status)} (armazenado em dev['status'])")
                else:
                    logger.warning(f"Atualização UDP ignorada. Dispositivo desconhecido: {update.device_id}")
        except Exception as e:
            logger.error(f"Erro no recebimento UDP: {e}")

def encode_varint(value):
    """
    Codifica um inteiro como varint (formato Protocol Buffers).
    
    Varint é um formato de codificação de inteiros onde cada byte contém
    7 bits de dados e 1 bit indicando se há mais bytes.
    
    Args:
        value: Inteiro a ser codificado
        
    Returns:
        bytes: Representação varint do inteiro
    """
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
    """
    Thread que escuta por conexões da API externa.
    
    Funciona de forma similar ao listen_tcp_connections(), mas na porta API_TCP_PORT.
    Permite que aplicações externas se conectem ao gateway para consultas e controle.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(('', API_TCP_PORT))
    sock.listen(5)
    logger.info(f"Gateway ouvindo API TCP na porta {API_TCP_PORT}...")
    while True:
        conn, addr = sock.accept()
        threading.Thread(target=handle_tcp_connection, args=(conn, addr)).start()

def main():
    """
    Função principal do gateway.
    
    Inicia todas as threads necessárias para o funcionamento do gateway:
    - Descoberta de dispositivos via multicast
    - Escuta de conexões TCP (registro e comandos)
    - Escuta de dados UDP (dados sensoriados)
    - Log periódico de status
    - API externa
    
    O gateway roda indefinidamente até ser interrompido por Ctrl+C.
    """
    # Determina e exibe o IP do gateway
    gateway_ip = get_local_ip()
    logger.info(f"Gateway iniciado com IP: {gateway_ip}")
    logger.info(f"Portas: TCP={GATEWAY_TCP_PORT}, UDP={GATEWAY_UDP_PORT}, API={API_TCP_PORT}")
    logger.info("=" * 50)
    
    # Inicia todas as threads de serviço
    threading.Thread(target=discover_devices, daemon=True).start()
    threading.Thread(target=listen_tcp_connections, daemon=True).start()
    threading.Thread(target=listen_udp_sensored_data, daemon=True).start()
    threading.Thread(target=log_device_info_periodic, daemon=True).start()
    threading.Thread(target=listen_api, daemon=True).start()
    
    # Loop principal - mantém o programa rodando
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Gateway encerrado por Ctrl+C")

if __name__ == "__main__":
    main()