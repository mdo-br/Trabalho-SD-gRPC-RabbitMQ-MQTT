#!/usr/bin/env python3
"""
Test script para verificar o sistema completo do Smart City
"""
import json
import time
import paho.mqtt.client as mqtt
import socket
import threading

# Configurações
MQTT_BROKER = "localhost"
MQTT_PORT = 1883
GATEWAY_HOST = "localhost"
GATEWAY_PORT = 12345

def test_mqtt_connection():
    """Testa conectividade MQTT"""
    print("🔄 Testando conexão MQTT...")
    
    client = mqtt.Client()
    try:
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        print("[OK] Conexão MQTT estabelecida")
        
        # Publicar mensagem de teste
        test_message = {
            "device_id": "test_sensor_001",
            "temperature": 23.5,
            "humidity": 65.0,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        
        client.publish("smart_city/sensors/test_sensor_001", json.dumps(test_message))
        print(f"[OK] Mensagem MQTT publicada: {test_message}")
        
        client.disconnect()
        return True
    except Exception as e:
        print(f"[FALHA] Erro na conexão MQTT: {e}")
        return False

def test_gateway_connection():
    """Testa conectividade TCP com o gateway"""
    print("Testando conexão TCP com gateway...")
    
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex((GATEWAY_HOST, GATEWAY_PORT))
        
        if result == 0:
            print("[OK] Conexão TCP com gateway estabelecida")
            
            # Testar comando simples
            command = "LIST_DEVICES"
            sock.sendall(command.encode())
            
            response = sock.recv(1024).decode()
            print(f"[OK] Resposta do gateway: {response}")
            
            sock.close()
            return True
        else:
            print(f"[FALHA] Não foi possível conectar ao gateway na porta {GATEWAY_PORT}")
            return False
            
    except Exception as e:
        print(f"[FALHA] Erro na conexão TCP: {e}")
        return False

def test_grpc_server():
    """Testa se o servidor gRPC está rodando"""
    print("Testando servidor gRPC...")
    
    try:
        import grpc
        channel = grpc.insecure_channel('localhost:50051')
        grpc.channel_ready_future(channel).result(timeout=5)
        print("[OK] Servidor gRPC acessível")
        channel.close()
        return True
    except Exception as e:
        print(f"[FALHA] Erro no servidor gRPC: {e}")
        return False

def main():
    """Executa todos os testes"""
    print("Iniciando teste completo do sistema Smart City")
    print("=" * 50)
    
    results = []
    
    # Teste 1: MQTT
    results.append(test_mqtt_connection())
    print()
    
    # Teste 2: Gateway TCP
    results.append(test_gateway_connection())
    print()
    
    # Teste 3: Servidor gRPC
    results.append(test_grpc_server())
    print()
    
    # Resumo
    print("=" * 50)
    print("📊 RESUMO DOS TESTES:")
    print(f"MQTT: {'OK' if results[0] else 'FALHA'}")
    print(f"Gateway TCP: {'OK' if results[1] else 'FALHA'}")
    print(f"Servidor gRPC: {'OK' if results[2] else 'FALHA'}")
    
    success_rate = sum(results) / len(results) * 100
    print(f"\nTaxa de sucesso: {success_rate:.1f}%")
    
    if all(results):
        print("Todos os testes passaram! Sistema funcionando corretamente.")
        return 0
    else:
        print("Alguns testes falharam. Verifique os componentes.")
        return 1

if __name__ == "__main__":
    exit(main())
