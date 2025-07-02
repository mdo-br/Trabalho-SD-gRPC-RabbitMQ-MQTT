#!/usr/bin/env python3
"""
Exemplo de Comandos para Sensor de Temperatura

Este script demonstra como usar o cliente SmartCity para enviar comandos
para o sensor de temperatura ESP8266, incluindo:

- SET_FREQ: Alterar frequência de envio de dados
- TURN_IDLE: Pausar envio de dados sensoriados
- TURN_ACTIVE: Ativar envio de dados sensoriados

Uso:
    python3 src/client-test/temperature_sensor_commands.py
"""

import sys
import os
import logging

# Adicionar o diretório raiz do projeto ao path para importações
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

# Importar o cliente
from smart_city_client import SmartCityClient

# Configuração de logging
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# Configurações do Gateway
GATEWAY_IP = '127.0.0.1'  # IP do gateway - CONFIGURAR COM O IP CORRETO
GATEWAY_TCP_PORT = 12345     # Porta TCP do gateway

def main():
    """
    Função principal que demonstra os comandos do sensor de temperatura.
    """
    # Inicializa o cliente
    client = SmartCityClient(GATEWAY_IP, GATEWAY_TCP_PORT)
    
    # ID do sensor de temperatura (ajuste conforme necessário)
    sensor_id = "temp_board_001001001"
    
    print("=== Comandos para Sensor de Temperatura ===")
    print(f"Sensor ID: {sensor_id}")
    print(f"Gateway: {GATEWAY_IP}:{GATEWAY_TCP_PORT}")
    print()
    
    # 1. Lista dispositivos para verificar se o sensor está conectado
    print("1. Verificando dispositivos conectados...")
    client.list_devices()
    print()
    
    # 2. Consulta status atual do sensor
    print("2. Consultando status atual do sensor...")
    client.get_device_status(sensor_id)
    print()
    
    # 3. Define frequência de envio para 10 segundos
    print("3. Alterando frequência de envio para 10 segundos...")
    client.send_device_command(sensor_id, "SET_FREQ", "10000")
    print()
    
    # 4. Pausa o envio de dados (TURN_IDLE)
    print("4. Pausando envio de dados sensoriados...")
    client.send_device_command(sensor_id, "TURN_IDLE")
    print()
    
    # 5. Consulta status após pausar
    print("5. Consultando status após pausar...")
    client.get_device_status(sensor_id)
    print()
    
    # 6. Reativa o envio de dados (TURN_ACTIVE)
    print("6. Reativando envio de dados sensoriados...")
    client.send_device_command(sensor_id, "TURN_ACTIVE")
    print()
    
    # 7. Define frequência de envio para 2 segundos (mais rápido)
    print("7. Alterando frequência de envio para 2 segundos...")
    client.send_device_command(sensor_id, "SET_FREQ", "2000")
    print()
    
    # 8. Consulta status final
    print("8. Consultando status final...")
    client.get_device_status(sensor_id)
    print()
    
    print("=== Demonstração Concluída ===")
    print("Comandos disponíveis para o sensor de temperatura:")
    print("- SET_FREQ <valor_ms>: Define frequência de envio (1000-60000 ms)")
    print("- TURN_IDLE: Pausa envio de dados sensoriados")
    print("- TURN_ACTIVE: Ativa envio de dados sensoriados")

if __name__ == "__main__":
    main() 