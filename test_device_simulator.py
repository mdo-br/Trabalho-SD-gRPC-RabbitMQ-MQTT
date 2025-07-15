#!/usr/bin/env python3
"""
Simulador de Dispositivo para Teste gRPC

Este script simula um dispositivo atuador que responde aos comandos TCP
enviados pelo servidor gRPC actuator_bridge_server.py
"""

import socket
import threading
import sys
import os
import time

# Adicionar diretório proto ao path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src', 'proto'))

import smart_city_pb2

class DeviceSimulator:
    def __init__(self, device_id, device_type, ip="127.0.0.1", port=8080):
        self.device_id = device_id
        self.device_type = device_type
        self.ip = ip
        self.port = port
        self.status = smart_city_pb2.DeviceStatus.OFF
        self.running = False
        
    def encode_varint(self, value):
        """Codifica um inteiro como varint (formato Protocol Buffers)"""
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
    
    def read_varint(self, stream):
        """Lê um varint do stream"""
        shift = 0
        result = 0
        while True:
            b = stream.read(1)
            if not b:
                raise EOFError("Stream fechado")
            b = b[0]
            result |= (b & 0x7f) << shift
            if not (b & 0x80):
                return result
            shift += 7
    
    def handle_command(self, command):
        """Processa um comando recebido"""
        print(f"Dispositivo {self.device_id} recebeu comando: {command.command_type}")
        
        if command.command_type == "TURN_ON":
            self.status = smart_city_pb2.DeviceStatus.ON
            print(f"Dispositivo {self.device_id} LIGADO")
        elif command.command_type == "TURN_OFF":
            self.status = smart_city_pb2.DeviceStatus.OFF
            print(f"Dispositivo {self.device_id} DESLIGADO")
        elif command.command_type == "GET_STATUS":
            print(f"Dispositivo {self.device_id} - Status atual: {smart_city_pb2.DeviceStatus.Name(self.status)}")
        
        # Criar resposta
        response = smart_city_pb2.SmartCityMessage()
        response.message_type = smart_city_pb2.MessageType.DEVICE_UPDATE
        
        device_update = smart_city_pb2.DeviceUpdate()
        device_update.device_id = self.device_id
        device_update.type = self.device_type
        device_update.current_status = self.status
        
        response.device_update.CopyFrom(device_update)
        return response
    
    def handle_client(self, client_socket, client_address):
        """Manipula uma conexão de cliente"""
        print(f"Conexao aceita de {client_address}")
        
        try:
            client_file = client_socket.makefile('rb')
            
            while True:
                # Ler tamanho da mensagem (varint)
                try:
                    message_size = self.read_varint(client_file)
                except EOFError:
                    print(f"Cliente {client_address} desconectou")
                    break
                
                # Ler mensagem
                message_data = client_file.read(message_size)
                if len(message_data) != message_size:
                    print(f"Mensagem incompleta de {client_address}")
                    break
                
                # Decodificar mensagem
                envelope = smart_city_pb2.SmartCityMessage()
                envelope.ParseFromString(message_data)
                
                print(f"Mensagem recebida de {client_address}: {envelope.message_type}")
                
                # Processar comando
                if envelope.message_type == smart_city_pb2.MessageType.CLIENT_REQUEST:
                    if envelope.client_request.type == smart_city_pb2.ClientRequest.RequestType.SEND_DEVICE_COMMAND:
                        response = self.handle_command(envelope.client_request.command)
                        
                        # Enviar resposta
                        response_data = response.SerializeToString()
                        client_socket.sendall(self.encode_varint(len(response_data)) + response_data)
                        print(f"Resposta enviada para {client_address}")
                
        except Exception as e:
            print(f"Erro ao manipular cliente {client_address}: {e}")
        finally:
            client_socket.close()
    
    def start(self):
        """Inicia o servidor do dispositivo"""
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        try:
            server_socket.bind((self.ip, self.port))
            server_socket.listen(5)
            self.running = True
            
            print(f"Dispositivo {self.device_id} iniciado em {self.ip}:{self.port}")
            print(f"Tipo: {smart_city_pb2.DeviceType.Name(self.device_type)}")
            print(f"Status inicial: {smart_city_pb2.DeviceStatus.Name(self.status)}")
            print("Aguardando comandos...")
            
            while self.running:
                try:
                    client_socket, client_address = server_socket.accept()
                    client_thread = threading.Thread(
                        target=self.handle_client,
                        args=(client_socket, client_address)
                    )
                    client_thread.daemon = True
                    client_thread.start()
                except KeyboardInterrupt:
                    print("\nParando dispositivo...")
                    break
                    
        except Exception as e:
            print(f"Erro ao iniciar dispositivo: {e}")
        finally:
            server_socket.close()

if __name__ == "__main__":
    print("=== Simulador de Dispositivo gRPC ===")
    
    # Criar dispositivo simulado
    device = DeviceSimulator(
        device_id="relay_001",
        device_type=smart_city_pb2.DeviceType.RELAY,
        ip="127.0.0.1",
        port=8080
    )
    
    try:
        device.start()
    except KeyboardInterrupt:
        print("\nSimulador parado pelo usuario") 