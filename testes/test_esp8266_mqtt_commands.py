#!/usr/bin/env python3
# test_esp8266_mqtt_commands.py - Teste específico para comandos MQTT de sensores ESP8266

import json
import time
import paho.mqtt.client as mqtt
import logging
import sys

# Configuração de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configurações
MQTT_BROKER_HOST = "192.168.1.102"  # <--- Altere aqui para o IP do seu broker MQTT
MQTT_BROKER_PORT = 1883
MQTT_USERNAME = "smartcity"  # <--- Preencha aqui
MQTT_PASSWORD = "smartcity123"    # <--- Preencha aqui

# O device_id pode ser passado por argumento ou definido aqui
import sys
if len(sys.argv) > 1:
    DEVICE_ID = sys.argv[1]
else:
    DEVICE_ID = "temp_sensor_esp_001"

COMMAND_TOPIC = f"smart_city/commands/sensors/{DEVICE_ID}"
RESPONSE_TOPIC = f"smart_city/commands/sensors/{DEVICE_ID}/response"
DATA_TOPIC = f"smart_city/sensors/{DEVICE_ID}"

class ESP8266MQTTTester:
    def __init__(self, device_id):
        self.device_id = device_id
        self.command_topic = COMMAND_TOPIC
        self.response_topic = RESPONSE_TOPIC
        self.data_topic = DATA_TOPIC
        
        self.client = mqtt.Client(f"esp8266_tester_{int(time.time())}")
        self.client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)  # <--- Autenticação
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        
        self.responses = []
        self.sensor_data = []
        
    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            logger.info(f"Conectado ao broker MQTT")
            client.subscribe(self.response_topic)
            client.subscribe(self.data_topic)
            logger.info(f"Inscrito nos topicos:")
            logger.info(f"   - Respostas: {self.response_topic}")
            logger.info(f"   - Dados: {self.data_topic}")
        else:
            logger.error(f"Falha ao conectar: {rc}")
    
    def on_message(self, client, userdata, msg):
        logger.info(f"[MQTT] Mensagem recebida no tópico: {msg.topic}")
        logger.info(f"[MQTT] Payload: {msg.payload.decode('utf-8')}")
        if msg.topic == self.response_topic:
            self.responses.append(msg.payload.decode('utf-8'))
        elif msg.topic == self.data_topic:
            self.sensor_data.append(msg.payload.decode('utf-8'))
    
    def handle_command_response(self, data):
        logger.info(f"Resposta de comando recebida:")
        logger.info(f"   Request ID: {data.get('request_id')}")
        logger.info(f"   Sucesso: {data.get('success')}")
        logger.info(f"   Mensagem: {data.get('message')}")
        logger.info(f"   Status: {data.get('status')}")
        logger.info(f"   Frequencia: {data.get('frequency_ms')}ms")
        
        if 'temperature' in data:
            logger.info(f"   Dados: Temp={data['temperature']:.1f}C, Hum={data['humidity']:.1f}%")
        
        self.responses.append(data)
        
        if data.get('success'):
            logger.info("Comando executado com sucesso!")
        else:
            logger.error("Comando falhou!")
    
    def handle_sensor_data(self, data):
        logger.info(f"Dados do sensor recebidos:")
        logger.info(f"   Device ID: {data.get('device_id')}")
        logger.info(f"   Temp: {data.get('temperature', 'N/A'):.1f}C")
        logger.info(f"   Hum: {data.get('humidity', 'N/A'):.1f}%")
        logger.info(f"   Status: {data.get('status')}")
        logger.info(f"   Versao: {data.get('version', 'N/A')}")
        
        self.sensor_data.append(data)
    
    def send_command(self, command_type, command_value=""):
        """Envia comando para sensor ESP8266 via MQTT"""
        request_id = f"esp8266_test_{int(time.time() * 1000)}"
        
        command = {
            "command_type": command_type,
            "command_value": command_value,
            "request_id": request_id,
            "timestamp": int(time.time() * 1000)
        }
        
        logger.info(f"Enviando comando: {command_type} {command_value}")
        
        result = self.client.publish(self.command_topic, json.dumps(command), qos=1)
        
        if result.rc == mqtt.MQTT_ERR_SUCCESS:
            logger.info(f"Comando enviado com sucesso (Request ID: {request_id})")
        else:
            logger.error(f"Erro ao enviar comando: {result.rc}")
        
        return request_id
    
    def connect(self):
        """Conecta ao broker MQTT"""
        try:
            self.client.connect(MQTT_BROKER_HOST, MQTT_BROKER_PORT, 60)
            self.client.loop_start()
            time.sleep(2)  # Aguardar conexão
            return True
        except Exception as e:
            logger.error(f"Erro ao conectar: {e}")
            return False
    
    def disconnect(self):
        """Desconecta do broker MQTT"""
        self.client.loop_stop()
        self.client.disconnect()
    
    def run_tests(self):
        """Executa sequência completa de testes"""
        logger.info("Iniciando testes do ESP8266 MQTT V3...")
        
        if not self.connect():
            logger.error("Nao foi possivel conectar ao broker MQTT")
            return False
        
        try:
            # Teste 1: Consultar status
            logger.info("\n=== 1. CONSULTAR STATUS ===")
            self.send_command("GET_STATUS")
            time.sleep(3)
            
            # Teste 2: Ativar sensor
            logger.info("\n=== 2. ATIVAR SENSOR ===")
            self.send_command("TURN_ON")
            time.sleep(5)  # Aguardar dados
            
            # Teste 3: Alterar frequência para 2 segundos
            logger.info("\n=== 3. FREQUENCIA 2 SEGUNDOS ===")
            self.send_command("SET_FREQ", "2000")
            time.sleep(6)  # Aguardar dados na nova frequência
            
            # Teste 4: Alterar frequência para 1 segundo
            logger.info("\n=== 4. FREQUENCIA 1 SEGUNDO ===")
            self.send_command("SET_FREQ", "1000")
            time.sleep(4)  # Aguardar dados na nova frequência
            
            # Teste 5: Colocar em idle
            logger.info("\n=== 5. MODO IDLE ===")
            self.send_command("TURN_IDLE")
            time.sleep(3)
            
            # Teste 6: Reativar
            logger.info("\n=== 6. REATIVAR SENSOR ===")
            self.send_command("TURN_ACTIVE")
            time.sleep(4)
            
            # Teste 7: Comando inválido
            logger.info("\n=== 7. COMANDO INVALIDO ===")
            self.send_command("INVALID_COMMAND")
            time.sleep(3)
            
            # Teste 8: Frequência inválida
            logger.info("\n=== 8. FREQUENCIA INVALIDA ===")
            self.send_command("SET_FREQ", "invalid")
            time.sleep(3)
            
            # Relatório final
            self.print_test_report()
            
        except KeyboardInterrupt:
            logger.info("\nTestes interrompidos pelo usuario")
        except Exception as e:
            logger.error(f"Erro durante os testes: {e}")
        finally:
            self.disconnect()
    
    def print_test_report(self):
        """Imprime relatório dos testes"""
        logger.info("\nRELATORIO DE TESTES")
        logger.info("=" * 50)
        
        logger.info(f"Device ID testado: {self.device_id}")
        logger.info(f"Respostas de comando recebidas: {len(self.responses)}")
        logger.info(f"Dados de sensor recebidos: {len(self.sensor_data)}")
        
        if self.responses:
            successful_commands = sum(1 for r in self.responses if r.get('success', False))
            logger.info(f"Comandos bem-sucedidos: {successful_commands}/{len(self.responses)}")
        
        if self.sensor_data:
            logger.info("\nUltimos dados do sensor:")
            latest_data = self.sensor_data[-1]
            logger.info(f"   Temperatura: {latest_data.get('temperature', 'N/A'):.1f}C")
            logger.info(f"   Umidade: {latest_data.get('humidity', 'N/A'):.1f}%")
            logger.info(f"   Status: {latest_data.get('status')}")
            logger.info(f"   Frequencia: {latest_data.get('frequency_ms')}ms")
        
        logger.info("\nTestes concluidos!")

def main():
    print("ESP8266 MQTT Commands Tester")
    print("=" * 50)
    
    # Permitir especificar device ID via argumento
    device_id = sys.argv[1] if len(sys.argv) > 1 else DEVICE_ID
    
    print(f"Device ID: {device_id}")
    print(f"Broker MQTT: {MQTT_BROKER_HOST}:{MQTT_BROKER_PORT}")
    print()
    
    tester = ESP8266MQTTTester(device_id)
    tester.run_tests()

if __name__ == "__main__":
    main()
