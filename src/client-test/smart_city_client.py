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
GATEWAY_IP = '192.168.3.129'  # IP do gateway - altere conforme necessário
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
    Envia uma mensagem Protocol Buffers com delimitador de tamanho, agora usando SmartCityMessage como envelope.
    """
    envelope = smart_city_pb2.SmartCityMessage()
    if isinstance(message, smart_city_pb2.ClientRequest):
        envelope.message_type = smart_city_pb2.MessageType.CLIENT_REQUEST
        envelope.client_request.CopyFrom(message)
    else:
        raise ValueError("Tipo de mensagem não suportado para envelope!")
    data = envelope.SerializeToString()
    sock.sendall(_encode_varint(len(data)) + data)

def read_delimited_message(sock):
    """
    Lê uma mensagem Protocol Buffers com delimitador de tamanho, esperando sempre SmartCityMessage.
    """
    length = _read_varint(sock)
    data = b''
    while len(data) < length:
        chunk = sock.recv(length - len(data))
        if not chunk:
            raise EOFError("Socket fechado inesperadamente ao ler mensagem.")
        data += chunk
    envelope = smart_city_pb2.SmartCityMessage()
    envelope.ParseFromString(data)
    return envelope

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
        Agora usa SmartCityMessage como envelope.
        """
        try:
            # Usa socket.create_connection com timeout para evitar bloqueio se o gateway estiver offline
            with socket.create_connection((self.gateway_ip, self.gateway_port), timeout=3) as sock:
                sock.settimeout(3)  # timeout para operações de leitura/escrita
                write_delimited_message(sock, request_proto)
                logger.debug(f"Requisição enviada: {request_proto.DESCRIPTOR.full_name}")
                envelope = read_delimited_message(sock)
                # Trata o payload do envelope
                if envelope.message_type == smart_city_pb2.MessageType.GATEWAY_RESPONSE:
                    return envelope.gateway_response
                elif envelope.message_type == smart_city_pb2.MessageType.DEVICE_UPDATE:
                    return envelope.device_update
                else:
                    logger.error(f"Tipo de resposta inesperado: {envelope.message_type}")
                    return None
        except (socket.timeout, ConnectionRefusedError) as e:
            logger.error(f"Gateway offline ou sem resposta: {e}")
            return None
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
        
        Envia uma requisição LIST_DEVICES e exibe informações detalhadas
        sobre cada dispositivo conectado ao gateway.
        """
        # Cria requisição para listar dispositivos
        request = smart_city_pb2.ClientRequest(
            type=smart_city_pb2.ClientRequest.RequestType.LIST_DEVICES
        )
        
        logger.info("Solicitando lista de dispositivos ao Gateway...")
        response = self.send_request(request)

        # Processa a resposta
        if response and response.type == smart_city_pb2.GatewayResponse.ResponseType.DEVICE_LIST:
            devices = response.devices
            if devices:
                print("\n" + "="*94)
                print("    DISPOSITIVOS CONECTADOS AO GATEWAY")
                print("="*94)
                print(f"{'ID':<25} {'TIPO':<20} {'IP:PORTA':<20} {'STATUS':<10} {'ATUADOR':<8} {'SENSOR':<8}")
                print("-"*94)
                
                for device in devices:
                    device_type_name = smart_city_pb2.DeviceType.Name(device.type)
                    device_status_name = smart_city_pb2.DeviceStatus.Name(device.initial_state)
                    
                    print(f"{device.device_id:<25} {device_type_name:<20} {device.ip_address}:{device.port:<7} {device_status_name:<10} {'SIM' if device.is_actuator else 'NAO':<8} {'SIM' if device.is_sensor else 'NAO':<8}")
                
                print("="*94)
                logger.info(f"Total de dispositivos: {len(devices)}")
            else:
                logger.info("Nenhum dispositivo encontrado.")
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
        Returns:
            bool: True se o comando foi aceito (status SUCCESS), False caso contrário.
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
            if response.command_status == "SUCCESS":
                logger.info(f"Comando enviado para '{device_id}': Status={response.command_status}, Mensagem: {response.message}")
                return True
            else:
                logger.error(f"Falha ao enviar comando para '{device_id}': Status={response.command_status}, Mensagem: {response.message}")
                return False
        elif response:
            logger.error(f"Falha ao enviar comando para '{device_id}': Status={getattr(response, 'command_status', 'N/A')}, Mensagem: {response.message}")
            return False
        else:
            logger.error("Falha na comunicação ao enviar comando.")
            return False

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
            # Exibe frequência de envio se presente
            if hasattr(dev_status, 'frequency_ms') and dev_status.frequency_ms > 0:
                logger.info(f"  Frequência de envio: {dev_status.frequency_ms} ms")
            logger.info("--------------------------------")
        elif response and response.type == smart_city_pb2.GatewayResponse.ResponseType.ERROR:
            logger.error(f"Erro ao obter status do dispositivo: {response.message}")
        else:
            logger.error("Falha na comunicação ao obter status.")


def main_menu():
    """
    Exibe o menu interativo do cliente.
    
    Cria uma instância do SmartCityClient e apresenta um menu de opções
    para testar as funcionalidades do sistema. Permite ao usuário:
    - Listar dispositivos conectados
    - Controlar relés/atuadores
    - Controlar sensores de temperatura
    - Consultar status de dispositivos
    """
    # Inicializa o cliente
    client = SmartCityClient(GATEWAY_IP, GATEWAY_TCP_PORT)

    # Loop principal do menu
    while True:
        print("\n" + "="*50)
        print("    CLIENTE SMART CITY - MENU PRINCIPAL")
        print("="*50)
        print("1. Listar Dispositivos Conectados")
        print("2. Comandos do Relé/Atuador")
        print("3. Comandos do Sensor de Temperatura")
        print("4. Consultar Status de Dispositivo")
        print("0. Sair")
        print("-"*50)
        
        choice = input("Escolha uma opção: ").strip()

        # Processa a escolha do usuário
        if choice == '1':
            # Lista todos os dispositivos conectados
            client.list_devices()
        elif choice == '2':
            # Menu específico para comandos do relé/atuador
            relay_menu(client)
        elif choice == '3':
            # Menu específico para comandos do sensor de temperatura
            temperature_sensor_menu(client)
        elif choice == '4':
            # Consulta status de um dispositivo específico
            device_id = input("ID do Dispositivo para Consultar Status: ").strip()
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


def relay_menu(client):
    """
    Menu específico para comandos do relé/atuador.
    
    Permite ao usuário:
    - Ligar/desligar relés
    - Consultar status do relé
    - Testar diferentes comandos
    """
    while True:
        print("\n" + "="*50)
        print("    COMANDOS DO RELÉ/ATUADOR")
        print("="*50)
        print("1. Ligar Relé (TURN_ON)")
        print("2. Desligar Relé (TURN_OFF)")
        print("3. Consultar Status do Relé")
        print("4. Ligar TODOS os Atuadores")
        print("5. Desligar TODOS os Atuadores")
        print("6. Voltar ao Menu Principal")
        print("-"*50)
        
        choice = input("Escolha uma opção: ").strip()

        if choice == '1':
            # Liga o relé
            relay_id = input("ID do Relé/Atuador (ex: relay_001001001): ").strip()
            if relay_id:
                result = client.send_device_command(relay_id, "TURN_ON")
                if result:
                    logger.info("Comando TURN_ON enviado com sucesso.")
                else:
                    logger.error("Falha ao enviar comando TURN_ON.")
            else:
                logger.warning("ID do relé não pode ser vazio.")
                
        elif choice == '2':
            # Desliga o relé
            relay_id = input("ID do Relé/Atuador (ex: relay_001001001): ").strip()
            if relay_id:
                result = client.send_device_command(relay_id, "TURN_OFF")
                if result:
                    logger.info("Comando TURN_OFF enviado com sucesso.")
                else:
                    logger.error("Falha ao enviar comando TURN_OFF.")
            else:
                logger.warning("ID do relé não pode ser vazio.")
                
        elif choice == '3':
            # Consulta status do relé
            relay_id = input("ID do Relé/Atuador (ex: relay_001001001): ").strip()
            if relay_id:
                client.get_device_status(relay_id)
            else:
                logger.warning("ID do relé não pode ser vazio.")

        elif choice == '4':
            # Ligar TODOS os atuadores
            logger.info("Solicitando lista de dispositivos ao Gateway para ligar todos os atuadores...")
            request = smart_city_pb2.ClientRequest(
                type=smart_city_pb2.ClientRequest.RequestType.LIST_DEVICES
            )
            response = client.send_request(request)
            if response and response.type == smart_city_pb2.GatewayResponse.ResponseType.DEVICE_LIST:
                devices = response.devices
                relays = [d for d in devices if d.type == smart_city_pb2.DeviceType.RELAY]
                if not relays:
                    logger.info("Nenhum atuador do tipo RELAY encontrado.")
                else:
                    for relay in relays:
                        logger.info(f"Enviando TURN_ON para {relay.device_id}...")
                        client.send_device_command(relay.device_id, "TURN_ON")
                    logger.info(f"Comando TURN_ON enviado para {len(relays)} atuadores.")
            else:
                logger.error("Não foi possível obter a lista de dispositivos.")

        elif choice == '5':
            # Desligar TODOS os atuadores
            logger.info("Solicitando lista de dispositivos ao Gateway para desligar todos os atuadores...")
            request = smart_city_pb2.ClientRequest(
                type=smart_city_pb2.ClientRequest.RequestType.LIST_DEVICES
            )
            response = client.send_request(request)
            if response and response.type == smart_city_pb2.GatewayResponse.ResponseType.DEVICE_LIST:
                devices = response.devices
                relays = [d for d in devices if d.type == smart_city_pb2.DeviceType.RELAY]
                if not relays:
                    logger.info("Nenhum atuador do tipo RELAY encontrado.")
                else:
                    for relay in relays:
                        logger.info(f"Enviando TURN_OFF para {relay.device_id}...")
                        client.send_device_command(relay.device_id, "TURN_OFF")
                    logger.info(f"Comando TURN_OFF enviado para {len(relays)} atuadores.")
            else:
                logger.error("Não foi possível obter a lista de dispositivos.")

        elif choice == '6':
            # Volta ao menu principal
            break
        else:
            logger.warning("Opção inválida. Tente novamente.")

def temperature_sensor_menu(client):
    """
    Menu específico para comandos do sensor de temperatura.
    
    Permite ao usuário:
    - Ativar/desativar envio de dados
    - Alterar frequência de envio
    - Consultar status do sensor
    """
    while True:
        print("\n" + "="*50)
        print("    COMANDOS DO SENSOR DE TEMPERATURA")
        print("="*50)
        print("1. Ativar Sensor (TURN_ACTIVE)")
        print("2. Pausar Sensor (TURN_IDLE)")
        print("3. Alterar Frequência de Envio (SET_FREQ)")
        print("4. Consultar Status do Sensor")
        print("5. Voltar ao Menu Principal")
        print("-"*50)
        
        choice = input("Escolha uma opção: ").strip()

        if choice == '1':
            # Ativa o sensor
            sensor_id = input("ID do Sensor de Temperatura (ex: temp_board_001001001): ").strip()
            if sensor_id:
                result = client.send_device_command(sensor_id, "TURN_ACTIVE")
                if result:
                    logger.info("Comando TURN_ACTIVE enviado com sucesso.")
                else:
                    logger.error("Falha ao enviar comando TURN_ACTIVE.")
            else:
                logger.warning("ID do sensor não pode ser vazio.")
                
        elif choice == '2':
            # Pausa o sensor
            sensor_id = input("ID do Sensor de Temperatura (ex: temp_board_001001001): ").strip()
            if sensor_id:
                result = client.send_device_command(sensor_id, "TURN_IDLE")
                if result:
                    logger.info("Comando TURN_IDLE enviado com sucesso.")
                else:
                    logger.error("Falha ao enviar comando TURN_IDLE.")
            else:
                logger.warning("ID do sensor não pode ser vazio.")
                
        elif choice == '3':
            # Altera frequência de envio
            sensor_id = input("ID do Sensor de Temperatura (ex: temp_board_001001001): ").strip()
            if sensor_id:
                print("Frequência em milissegundos (1000-60000):")
                print("  - 1000 = 1 segundo")
                print("  - 5000 = 5 segundos (padrão)")
                print("  - 10000 = 10 segundos")
                print("  - 30000 = 30 segundos")
                freq_input = input("Nova frequência (ms): ").strip()
                if freq_input.isdigit():
                    freq_ms = int(freq_input)
                    if 1000 <= freq_ms <= 60000:
                        result = client.send_device_command(sensor_id, "SET_FREQ", str(freq_ms))
                        if result:
                            logger.info(f"Comando SET_FREQ enviado com sucesso para {freq_ms} ms.")
                        else:
                            logger.error("Falha ao enviar comando SET_FREQ.")
                    else:
                        logger.warning("Frequência deve estar entre 1000 e 60000 ms.")
                else:
                    logger.warning("Frequência deve ser um número válido.")
            else:
                logger.warning("ID do sensor não pode ser vazio.")
                
        elif choice == '4':
            # Consulta status do sensor
            sensor_id = input("ID do Sensor de Temperatura (ex: temp_board_001001001): ").strip()
            if sensor_id:
                client.get_device_status(sensor_id)
            else:
                logger.warning("ID do sensor não pode ser vazio.")
                
        elif choice == '5':
            # Volta ao menu principal
            break
        else:
            logger.warning("Opção inválida. Tente novamente.")

if __name__ == "__main__":
    main_menu()