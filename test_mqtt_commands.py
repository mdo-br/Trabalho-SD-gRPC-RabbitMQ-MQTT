#!/usr/bin/env python3
# test_mqtt_commands.py - Teste de comandos MQTT para sensores

import json
import time
import paho.mqtt.client as mqtt
import logging

# Configuração de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configurações
MQTT_BROKER_HOST = "192.168.1.102"
MQTT_BROKER_PORT = 1883
MQTT_USERNAME = "smartcity"  # <--- Preencha aqui
MQTT_PASSWORD = "smartcity123"    # <--- Preencha aqui
DEVICE_ID = "temp_sensor_mqtt_001"
COMMAND_TOPIC = f"smart_city/commands/sensors/{DEVICE_ID}"
RESPONSE_TOPIC = f"smart_city/commands/sensors/{DEVICE_ID}/response"

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        logger.info(f"Cliente teste conectado ao broker MQTT")
        client.subscribe(RESPONSE_TOPIC)
        logger.info(f"Inscrito no tópico de resposta: {RESPONSE_TOPIC}")
    else:
        logger.error(f"Falha ao conectar: {rc}")

def on_message(client, userdata, msg):
    topic = msg.topic
    payload = msg.payload.decode('utf-8')
    logger.info(f"Resposta recebida de {topic}: {payload}")
    
    try:
        data = json.loads(payload)
        if data.get('success', False):
            logger.info(f"[OK] Comando executado com sucesso: {data.get('message')}")
            logger.info(f"   Status: {data.get('status')}")
            logger.info(f"   Frequência: {data.get('frequency_ms')}ms")
            if 'temperature' in data:
                logger.info(f"   Dados: Temp={data['temperature']:.1f}°C, Hum={data['humidity']:.1f}%")
        else:
            logger.error(f"[FALHA] Comando falhou: {data.get('message')}")
    except json.JSONDecodeError:
        logger.error(f"Erro ao decodificar resposta: {payload}")

def send_command(client, command_type, command_value=""):
    """Envia comando para sensor via MQTT"""
    command = {
        "command_type": command_type,
        "command_value": command_value,
        "request_id": f"test_{int(time.time() * 1000)}",
        "timestamp": int(time.time() * 1000)
    }
    
    logger.info(f"Enviando comando: {command_type} {command_value}")
    result = client.publish(COMMAND_TOPIC, json.dumps(command), qos=1)
    
    if result.rc == mqtt.MQTT_ERR_SUCCESS:
        logger.info(f"Comando enviado com sucesso")
    else:
        logger.error(f"Erro ao enviar comando: {result.rc}")

def main():
    print("=== TESTE DE COMANDOS MQTT PARA SENSORES V3 ===")
    print(f"Sensor alvo: {DEVICE_ID}")
    print(f"Broker MQTT: {MQTT_BROKER_HOST}:{MQTT_BROKER_PORT}")
    print()
    
    # Configurar cliente MQTT
    client = mqtt.Client(f"test_client_{int(time.time())}")
    client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)  # <--- Adicionado para autenticação
    client.on_connect = on_connect
    client.on_message = on_message
    
    try:
        # Conectar
        client.connect(MQTT_BROKER_HOST, MQTT_BROKER_PORT, 60)
        client.loop_start()
        
        # Aguardar conexão
        time.sleep(2)
        
        # Testes de comandos
        print("=== SEQUÊNCIA DE TESTES ===")
        
        # 1. Consultar status
        print("\n1. Consultando status atual...")
        send_command(client, "GET_STATUS")
        time.sleep(3)
        
        # 2. Ativar sensor
        print("\n2. Ativando sensor...")
        send_command(client, "TURN_ON")
        time.sleep(3)
        
        # 3. Alterar frequência
        print("\n3. Alterando frequência para 3 segundos...")
        send_command(client, "SET_FREQ", "3000")
        time.sleep(5)
        
        # 4. Alterar frequência novamente
        print("\n4. Alterando frequência para 2 segundos...")
        send_command(client, "SET_FREQ", "2000")
        time.sleep(5)
        
        # 5. Colocar em idle
        print("\n5. Colocando sensor em IDLE...")
        send_command(client, "TURN_IDLE")
        time.sleep(3)
        
        # 6. Reativar
        print("\n6. Reativando sensor...")
        send_command(client, "TURN_ACTIVE")
        time.sleep(5)
        
        # 7. Comando inválido
        print("\n7. Testando comando inválido...")
        send_command(client, "INVALID_COMMAND")
        time.sleep(3)
        
        print("\n=== TESTES CONCLUÍDOS ===")
        
    except KeyboardInterrupt:
        print("\nTeste interrompido pelo usuário")
    except Exception as e:
        logger.error(f"Erro no teste: {e}")
    finally:
        client.loop_stop()
        client.disconnect()
        print("Cliente desconectado")

if __name__ == "__main__":
    main()
