import socket
import sys
import logging
import google.protobuf.message
import os

# Adicionar o diretório raiz do projeto ao path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

# Importar as classes geradas do Protocol Buffers
# A importação assume que o diretório que contém smart_city_pb2.py
# (src/protobuf_gen_py/smartcity/devices/) foi adicionado ao PYTHONPATH no terminal antes da execução.
# --- Configuração de Logging ---
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

try:
    from src.proto import smart_city_pb2
except ImportError as e:
    # Mensagem de erro aprimorada para ajudar o usuário a depurar a importação
    logger.error(f"Erro ao importar smart_city_pb2: {e}. Verifique:")
    logger.error("1. Ambiente virtual Python ativado.")
    logger.error("2. Classes Protobuf Python geradas (execute 'protoc --python_out=src/protobuf_gen_py/ src/proto/smart_city.proto' na raiz do projeto).")
    logger.error("3. PYTHONPATH configurado corretamente no terminal (ex: 'export PYTHONPATH=$PYTHONPATH:src/protobuf_gen_py' ou '$env:PYTHONPATH += \";src/protobuf_gen_py\"').")
    logger.error(f"Caminhos de busca Python (sys.path): {sys.path}")
    sys.exit(1)


# --- Configuração de Logging ---
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# --- Configurações de Conexão com o Gateway ---
GATEWAY_IP = '192.168.0.20' # Mude para o IP do seu Gateway se não for localhost
GATEWAY_TCP_PORT = 12345

def _read_varint(sock):
    shift = 0
    result = 0
    while True:
        b = sock.recv(1)
        if not b:
            raise EOFError("Socket fechado inesperadamente ao ler varint.")
        b = b[0]
        result |= (b & 0x7f) << shift
        if not (b & 0x80):
            return result
        shift += 7
        if shift >= 64:
            raise ValueError("Varint muito longo (provável corrupção de dados).")

def _encode_varint(value):
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

def write_delimited_message(sock, message):
    data = message.SerializeToString()
    sock.sendall(_encode_varint(len(data)) + data)

def read_delimited_message(sock, message_type):
    length = _read_varint(sock)
    data = b''
    while len(data) < length:
        chunk = sock.recv(length - len(data))
        if not chunk:
            raise EOFError("Socket fechado inesperadamente ao ler mensagem.")
        data += chunk
    msg = message_type()
    msg.ParseFromString(data)
    return msg

class SmartCityClient:
    def __init__(self, gateway_ip, gateway_port):
        self.gateway_ip = gateway_ip
        self.gateway_port = gateway_port
        logger.info(f"Cliente SmartCity inicializado. Conectando a {gateway_ip}:{gateway_port}")

    def send_request(self, request_proto):
        """Envia uma requisição Protocol Buffers para o Gateway e retorna a resposta."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.connect((self.gateway_ip, self.gateway_port))
                write_delimited_message(sock, request_proto)
                logger.debug(f"Requisição enviada: {request_proto.DESCRIPTOR.full_name}")
                response_proto = read_delimited_message(sock, smart_city_pb2.GatewayResponse)
                logger.debug(f"Resposta recebida: {response_proto.DESCRIPTOR.full_name}")
                return response_proto
        except socket.error as e:
            logger.error(f"Erro de socket ao comunicar com o Gateway: {e}")
            return None
        except google.protobuf.message.DecodeError as e:
            logger.error(f"Erro de decodificação Protobuf na resposta do Gateway: {e}")
            return None
        except Exception as e:
            logger.error(f"Erro inesperado ao enviar requisição: {e}", exc_info=True)
            return None

    def list_devices(self):
        """Solicita ao Gateway a lista de dispositivos conectados."""
        request = smart_city_pb2.ClientRequest(
            type=smart_city_pb2.ClientRequest.RequestType.LIST_DEVICES
        )
        logger.info("Solicitando lista de dispositivos ao Gateway...")
        response = self.send_request(request)

        if response and response.type == smart_city_pb2.GatewayResponse.ResponseType.DEVICE_LIST:
            logger.info("--- Dispositivos Conectados ---")
            if response.devices:
                for dev in response.devices:
                    device_type_name = smart_city_pb2.DeviceType.Name(dev.type)
                    device_status_name = smart_city_pb2.DeviceStatus.Name(dev.initial_state)
                    logger.info(f"  ID: {dev.device_id}, Tipo: {device_type_name}, "
                                f"IP: {dev.ip_address}:{dev.port}, Status: {device_status_name}, "
                                f"Atuador: {dev.is_actuator}, Sensor: {dev.is_sensor}")
            else:
                logger.info("Nenhum dispositivo encontrado.")
            logger.info("-----------------------------")
        elif response:
            logger.error(f"Erro ao listar dispositivos: {response.message}")
        else:
            logger.error("Falha na comunicação ao listar dispositivos.")

    def send_device_command(self, device_id, command_type, command_value=""):
        """Envia um comando para um dispositivo específico."""
        command_proto = smart_city_pb2.DeviceCommand(
            device_id=device_id,
            command_type=command_type,
            command_value=command_value
        )
        request = smart_city_pb2.ClientRequest(
            type=smart_city_pb2.ClientRequest.RequestType.SEND_DEVICE_COMMAND,
            target_device_id=device_id,
            command=command_proto
        )
        logger.info(f"Enviando comando '{command_type}' para dispositivo '{device_id}'...")
        response = self.send_request(request)

        if response and response.type == smart_city_pb2.GatewayResponse.ResponseType.COMMAND_ACK:
            logger.info(f"Comando enviado com sucesso para '{device_id}': Status={response.command_status}, Mensagem: {response.message}")
        elif response:
            logger.error(f"Falha ao enviar comando para '{device_id}': Status={response.command_status}, Mensagem: {response.message}")
        else:
            logger.error("Falha na comunicação ao enviar comando.")

    def get_device_status(self, device_id):
        """Solicita ao Gateway o status de um dispositivo específico."""
        request = smart_city_pb2.ClientRequest(
            type=smart_city_pb2.ClientRequest.RequestType.GET_DEVICE_STATUS,
            target_device_id=device_id
        )
        logger.info(f"Solicitando status do dispositivo '{device_id}' ao Gateway...")
        response = self.send_request(request)

        if response and response.type == smart_city_pb2.GatewayResponse.ResponseType.DEVICE_STATUS_UPDATE:
            dev_status = response.device_status
            device_type_name = smart_city_pb2.DeviceType.Name(dev_status.type)
            device_status_name = smart_city_pb2.DeviceStatus.Name(dev_status.current_status)
            logger.info(f"--- Status de '{dev_status.device_id}' ---")
            logger.info(f"  Tipo: {device_type_name}")
            logger.info(f"  Status Atual: {device_status_name}")
            if dev_status.HasField("temperature_humidity"):
                logger.info(f"  Temperatura: {dev_status.temperature_humidity.temperature}°C")
                logger.info(f"  Umidade: {dev_status.temperature_humidity.humidity}%")
            if dev_status.HasField("current_sensor"):
                logger.info(f"  Corrente: {dev_status.current_sensor.current}A")
                logger.info(f"  Tensão: {dev_status.current_sensor.voltage}V")
                logger.info(f"  Potência: {dev_status.current_sensor.power}W")
            logger.info(f"  Configuração: {dev_status.custom_config_status}")
            logger.info("--------------------------------")
        elif response:
            logger.error(f"Erro ao obter status do dispositivo: {response.message}")
        else:
            logger.error("Falha na comunicação ao obter status.")


def main_menu():
    """Exibe o menu interativo do cliente."""
    client = SmartCityClient(GATEWAY_IP, GATEWAY_TCP_PORT)

    while True:
        print("\n--- Menu do Cliente SmartCity ---")
        print("1. Listar Dispositivos")
        print("2. Ligar Alarme (TURN_ON)")
        print("3. Desligar Alarme (TURN_OFF)")
        print("4. Consultar Status de um Dispositivo")
        print("0. Sair")
        
        choice = input("Escolha uma opção: ").strip()

        if choice == '1':
            client.list_devices()
        elif choice == '2':
            alarm_id = input("ID do Alarme a Ligar (ex: alarm_xxxx): ").strip()
            if alarm_id:
                client.send_device_command(alarm_id, "TURN_ON")
            else:
                logger.warning("ID do alarme não pode ser vazio.")
        elif choice == '3':
            alarm_id = input("ID do Alarme a Desligar (ex: alarm_xxxx): ").strip()
            if alarm_id:
                client.send_device_command(alarm_id, "TURN_OFF")
            else:
                logger.warning("ID do alarme não pode ser vazio.")
        elif choice == '4':
            device_id = input("ID do Dispositivo para Consultar Status (ex: temp_hum_sensor_xxxx ou alarm_xxxx): ").strip()
            if device_id:
                client.get_device_status(device_id)
            else:
                logger.warning("ID do dispositivo não pode ser vazio.")
        elif choice == '0':
            logger.info("Saindo do cliente SmartCity.")
            break
        else:
            logger.warning("Opção inválida. Tente novamente.")

if __name__ == "__main__":
    main_menu()