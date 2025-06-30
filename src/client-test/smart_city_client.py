"""
Smart City Client - Cliente de Teste para Sistema IoT

Este módulo implementa um cliente de teste que se comunica com o Smart City Gateway
para realizar operações de controle e monitoramento de dispositivos IoT.

Funcionalidades:
- Listar dispositivos conectados ao gateway
- Enviar comandos para atuadores (ligar/desligar alarmes)
- Consultar status de dispositivos (sensores e atuadores)
- Interface de menu interativo para testes

Protocolo:
- Comunicação TCP com o gateway
- Mensagens Protocol Buffers com delimitador de tamanho (varint)
- Formato: [varint_tamanho][dados_protobuf]

Uso:
    python3 src/client-test/smart_city_client.py
"""

import socket
import sys
import logging
import google.protobuf.message
import os

# Adicionar o diretório raiz do projeto ao path para importações
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

# --- Configuração de Logging ---
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# Importar as classes geradas do Protocol Buffers
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

# --- Configurações de Conexão com o Gateway ---
GATEWAY_IP = '192.168.0.20'  # IP do gateway - altere conforme necessário
GATEWAY_TCP_PORT = 12345     # Porta TCP do gateway

def _read_varint(sock):
    """
    Lê um varint (inteiro variável) de um socket.
    
    Varint é o formato usado pelo Protocol Buffers para codificar o tamanho
    das mensagens. Cada byte contém 7 bits de dados e 1 bit indicando se há mais bytes.
    
    Args:
        sock: Socket para leitura
        
    Returns:
        int: Valor do varint lido
        
    Raises:
        EOFError: Se o socket for fechado inesperadamente
        ValueError: Se o varint for muito longo (corrupção de dados)
    """
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
            result += bytes([bits | 0x80])
        else:
            result += bytes([bits])
            break
    return result

def write_delimited_message(sock, message):
    """
    Envia uma mensagem Protocol Buffers com delimitador de tamanho.
    
    Protocol Buffers usa um formato onde o tamanho da mensagem é codificado
    como varint seguido pelos dados da mensagem.
    
    Args:
        sock: Socket para envio
        message: Objeto Protocol Buffers para serializar
    """
    data = message.SerializeToString()
    sock.sendall(_encode_varint(len(data)) + data)

def read_delimited_message(sock, message_type):
    """
    Lê uma mensagem Protocol Buffers com delimitador de tamanho.
    
    Primeiro lê o varint com o tamanho da mensagem, depois lê os dados
    correspondentes e deserializa para o tipo especificado.
    
    Args:
        sock: Socket para leitura
        message_type: Classe do tipo de mensagem Protocol Buffers
        
    Returns:
        Objeto do tipo message_type deserializado
        
    Raises:
        EOFError: Se o socket for fechado inesperadamente
    """
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
    """
    Cliente para comunicação com o Smart City Gateway.
    
    Esta classe encapsula toda a comunicação com o gateway, incluindo
    envio de requisições, recebimento de respostas e tratamento de erros.
    
    Attributes:
        gateway_ip (str): Endereço IP do gateway
        gateway_port (int): Porta TCP do gateway
    """
    
    def __init__(self, gateway_ip, gateway_port):
        """
        Inicializa o cliente SmartCity.
        
        Args:
            gateway_ip (str): Endereço IP do gateway
            gateway_port (int): Porta TCP do gateway
        """
        self.gateway_ip = gateway_ip
        self.gateway_port = gateway_port
        logger.info(f"Cliente SmartCity inicializado. Conectando a {gateway_ip}:{gateway_port}")

    def send_request(self, request_proto):
        """
        Envia uma requisição Protocol Buffers para o Gateway e retorna a resposta.
        
        Estabelece uma conexão TCP com o gateway, envia a requisição e aguarda
        a resposta. Trata erros de rede e decodificação.
        
        Args:
            request_proto: Objeto Protocol Buffers da requisição
            
        Returns:
            Objeto GatewayResponse ou None em caso de erro
        """
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                # Conecta ao gateway
                sock.connect((self.gateway_ip, self.gateway_port))
                
                # Envia a requisição
                write_delimited_message(sock, request_proto)
                logger.debug(f"Requisição enviada: {request_proto.DESCRIPTOR.full_name}")
                
                # Recebe a resposta
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
        """
        Solicita ao Gateway a lista de dispositivos conectados.
        
        Envia uma requisição LIST_DEVICES e exibe informações sobre todos
        os dispositivos registrados no gateway, incluindo tipo, status,
        endereço IP e se são sensores ou atuadores.
        """
        # Cria requisição para listar dispositivos
        request = smart_city_pb2.ClientRequest(
            type=smart_city_pb2.ClientRequest.RequestType.LIST_DEVICES
        )
        logger.info("Solicitando lista de dispositivos ao Gateway...")
        response = self.send_request(request)

        # Processa a resposta
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
        """
        Envia um comando para um dispositivo específico.
        
        Cria uma requisição SEND_DEVICE_COMMAND com um DeviceCommand
        e envia para o gateway, que repassa o comando para o dispositivo.
        
        Args:
            device_id (str): ID do dispositivo alvo
            command_type (str): Tipo do comando (ex: "TURN_ON", "TURN_OFF")
            command_value (str): Valor adicional do comando (opcional)
        """
        # Cria o comando do dispositivo
        command_proto = smart_city_pb2.DeviceCommand(
            device_id=device_id,
            command_type=command_type,
            command_value=command_value
        )
        
        # Cria a requisição para enviar o comando
        request = smart_city_pb2.ClientRequest(
            type=smart_city_pb2.ClientRequest.RequestType.SEND_DEVICE_COMMAND,
            target_device_id=device_id,
            command=command_proto
        )
        
        logger.info(f"Enviando comando '{command_type}' para dispositivo '{device_id}'...")
        response = self.send_request(request)

        # Processa a resposta
        if response and response.type == smart_city_pb2.GatewayResponse.ResponseType.COMMAND_ACK:
            logger.info(f"Comando enviado com sucesso para '{device_id}': Status={response.command_status}, Mensagem: {response.message}")
        elif response:
            logger.error(f"Falha ao enviar comando para '{device_id}': Status={response.command_status}, Mensagem: {response.message}")
        else:
            logger.error("Falha na comunicação ao enviar comando.")

    def get_device_status(self, device_id):
        """
        Solicita ao Gateway o status de um dispositivo específico.
        
        Envia uma requisição GET_DEVICE_STATUS e exibe informações detalhadas
        sobre o dispositivo, incluindo dados de sensor se disponíveis.
        
        Args:
            device_id (str): ID do dispositivo para consultar
        """
        # Cria requisição para obter status do dispositivo
        request = smart_city_pb2.ClientRequest(
            type=smart_city_pb2.ClientRequest.RequestType.GET_DEVICE_STATUS,
            target_device_id=device_id
        )
        
        logger.info(f"Solicitando status do dispositivo '{device_id}' ao Gateway...")
        response = self.send_request(request)

        # Processa a resposta
        if response and response.type == smart_city_pb2.GatewayResponse.ResponseType.DEVICE_STATUS_UPDATE:
            dev_status = response.device_status
            device_type_name = smart_city_pb2.DeviceType.Name(dev_status.type)
            device_status_name = smart_city_pb2.DeviceStatus.Name(dev_status.current_status)
            
            # Exibe informações básicas do dispositivo
            logger.info(f"--- Status de '{dev_status.device_id}' ---")
            logger.info(f"  Tipo: {device_type_name}")
            logger.info(f"  Status Atual: {device_status_name}")
            
            # Exibe dados de sensor se disponíveis
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
    """
    Exibe o menu interativo do cliente.
    
    Cria uma instância do SmartCityClient e apresenta um menu de opções
    para testar as funcionalidades do sistema. Permite ao usuário:
    - Listar dispositivos conectados
    - Ligar/desligar alarmes
    - Consultar status de dispositivos
    """
    # Inicializa o cliente
    client = SmartCityClient(GATEWAY_IP, GATEWAY_TCP_PORT)

    # Loop principal do menu
    while True:
        print("\n--- Menu do Cliente SmartCity ---")
        print("1. Listar Dispositivos")
        print("2. Ligar Alarme (TURN_ON)")
        print("3. Desligar Alarme (TURN_OFF)")
        print("4. Consultar Status de um Dispositivo")
        print("0. Sair")
        
        choice = input("Escolha uma opção: ").strip()

        # Processa a escolha do usuário
        if choice == '1':
            # Lista todos os dispositivos conectados
            client.list_devices()
        elif choice == '2':
            # Liga um alarme específico
            alarm_id = input("ID do Alarme a Ligar (ex: alarm_xxxx): ").strip()
            if alarm_id:
                client.send_device_command(alarm_id, "TURN_ON")
            else:
                logger.warning("ID do alarme não pode ser vazio.")
        elif choice == '3':
            # Desliga um alarme específico
            alarm_id = input("ID do Alarme a Desligar (ex: alarm_xxxx): ").strip()
            if alarm_id:
                client.send_device_command(alarm_id, "TURN_OFF")
            else:
                logger.warning("ID do alarme não pode ser vazio.")
        elif choice == '4':
            # Consulta status de um dispositivo específico
            device_id = input("ID do Dispositivo para Consultar Status (ex: temp_hum_sensor_xxxx ou alarm_xxxx): ").strip()
            if device_id:
                client.get_device_status(device_id)
            else:
                logger.warning("ID do dispositivo não pode ser vazio.")
        elif choice == '0':
            # Sai do programa
            logger.info("Saindo do cliente SmartCity.")
            break
        else:
            logger.warning("Opção inválida. Tente novamente.")

if __name__ == "__main__":
    main_menu()