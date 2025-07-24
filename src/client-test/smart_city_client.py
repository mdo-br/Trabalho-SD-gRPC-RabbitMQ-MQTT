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

import requests
import sys
import logging

API_URL = "http://127.0.0.1:8000"  # Ajuste conforme necessário

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

class SmartCityRestClient:
    def __init__(self, api_url):
        self.api_url = api_url

    def list_devices(self):
        try:
            resp = requests.get(f"{self.api_url}/devices")
            resp.raise_for_status()
            devices = resp.json()
            print("\n" + "="*94)
            print("    DISPOSITIVOS CONECTADOS AO GATEWAY")
            print("="*94)
            print(f"{'ID':<25} {'TIPO':<20} {'IP:PORTA':<20} {'STATUS':<10}")
            print("-"*94)
            for d in devices:
                print(f"{d['id']:<25} {d['type']:<20} {d['ip']}:{d['port']:<7} {d['status']:<10}")
            print("="*94)
            logger.info(f"Total de dispositivos: {len(devices)}")
        except Exception as e:
            logger.error(f"Erro ao listar dispositivos: {e}")

    def send_device_command(self, device_id, command_type, command_value=""):
        try:
            # Seleciona endpoint correto conforme comando
            if command_type in ["TURN_ON", "TURN_OFF"]:
                resp = requests.put(
                    f"{self.api_url}/device/relay",
                    params={"device_id": device_id, "action": command_type}
                )
            elif command_type in ["TURN_ACTIVE", "TURN_IDLE"]:
                resp = requests.put(
                    f"{self.api_url}/device/sensor/state",
                    params={"device_id": device_id, "state": command_type}
                )
            elif command_type == "SET_FREQ":
                resp = requests.put(
                    f"{self.api_url}/device/sensor/frequency",
                    params={"device_id": device_id, "frequency": int(command_value)}
                )
            else:
                logger.error("Tipo de comando não suportado.")
                return False

            resp.raise_for_status()
            result = resp.json()
            logger.info(f"Resposta: {result}")
            return result.get("status", "") == "SUCCESS"
        except Exception as e:
            logger.error(f"Erro ao enviar comando: {e}")
            return False

    def get_device_status(self, device_id):
        try:
            resp = requests.get(f"{self.api_url}/device/data", params={"device_id": device_id})
            resp.raise_for_status()
            status = resp.json()
            print(f"Status do dispositivo {device_id}: {status}")
        except Exception as e:
            logger.error(f"Erro ao consultar status: {e}")

def relay_menu(client):
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
            relay_id = input("ID do Relé/Atuador (ex: relay_001001001): ").strip()
            if relay_id:
                client.get_device_status(relay_id)
            else:
                logger.warning("ID do relé não pode ser vazio.")
        elif choice == '4':
            try:
                resp = requests.get(f"{API_URL}/devices")
                resp.raise_for_status()
                devices = resp.json()
                relays = [d for d in devices if d['type'] == "RELAY"]
                if not relays:
                    logger.info("Nenhum atuador do tipo RELAY encontrado.")
                else:
                    for relay in relays:
                        logger.info(f"Enviando TURN_ON para {relay['id']}...")
                        client.send_device_command(relay['id'], "TURN_ON")
                    logger.info(f"Comando TURN_ON enviado para {len(relays)} atuadores.")
            except Exception as e:
                logger.error("Não foi possível obter a lista de dispositivos.")
        elif choice == '5':
            try:
                resp = requests.get(f"{API_URL}/devices")
                resp.raise_for_status()
                devices = resp.json()
                relays = [d for d in devices if d['type'] == "RELAY"]
                if not relays:
                    logger.info("Nenhum atuador do tipo RELAY encontrado.")
                else:
                    for relay in relays:
                        logger.info(f"Enviando TURN_OFF para {relay['id']}...")
                        client.send_device_command(relay['id'], "TURN_OFF")
                    logger.info(f"Comando TURN_OFF enviado para {len(relays)} atuadores.")
            except Exception as e:
                logger.error("Não foi possível obter a lista de dispositivos.")
        elif choice == '6':
            break
        else:
            logger.warning("Opção inválida. Tente novamente.")

def temperature_sensor_menu(client):
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
            sensor_id = input("ID do Sensor de Temperatura (ex: temp_board_001001001): ").strip()
            if sensor_id:
                client.get_device_status(sensor_id)
            else:
                logger.warning("ID do sensor não pode ser vazio.")
        elif choice == '5':
            break
        else:
            logger.warning("Opção inválida. Tente novamente.")

def main_menu():
    client = SmartCityRestClient(API_URL)
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
        if choice == '1':
            client.list_devices()
        elif choice == '2':
            relay_menu(client)
        elif choice == '3':
            temperature_sensor_menu(client)
        elif choice == '4':
            device_id = input("ID do Dispositivo para Consultar Status: ").strip()
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