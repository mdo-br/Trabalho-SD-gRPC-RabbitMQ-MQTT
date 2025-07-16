#!/usr/bin/env python3
"""
Teste específico para comandos gRPC de atuador
"""
import sys
import os
import socket
import time

# Adicionar diretório do projeto ao path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src', 'proto'))

import smart_city_pb2

def encode_varint(value):
    """Codifica um inteiro como varint protobuf"""
    result = b''
    while value >= 0x80:
        result += bytes([value & 0x7F | 0x80])
        value >>= 7
    result += bytes([value])
    return result

def send_delimited_message(socket, message):
    """Envia uma mensagem protobuf com delimitador de tamanho"""
    data = message.SerializeToString()
    size = len(data)
    size_bytes = encode_varint(size)
    socket.send(size_bytes + data)

def decode_varint(data, offset=0):
    """Decodifica um varint protobuf"""
    result = 0
    shift = 0
    i = offset
    while i < len(data):
        byte = data[i]
        result |= (byte & 0x7F) << shift
        if (byte & 0x80) == 0:
            return result, i + 1
        shift += 7
        i += 1
    raise ValueError("Invalid varint")

def receive_delimited_message(socket, message_type):
    """Recebe uma mensagem protobuf com delimitador de tamanho"""
    # Ler o tamanho
    size_bytes = socket.recv(1)
    if not size_bytes:
        return None
    
    size = size_bytes[0]
    if size & 0x80:
        # Varint de múltiplos bytes
        additional_bytes = socket.recv(4)
        size_data = size_bytes + additional_bytes
        size, _ = decode_varint(size_data)
    
    # Ler os dados
    data = socket.recv(size)
    if len(data) != size:
        raise ValueError(f"Expected {size} bytes, got {len(data)}")
    
    # Parse da mensagem
    message = message_type()
    message.ParseFromString(data)
    return message

def test_actuator_command():
    """Testa comando específico para atuador"""
    try:
        # Conectar ao gateway
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.connect(('localhost', 12345))
        
        print("Conectado ao gateway na porta 12345")
        
        # Enviar comando TURN_ON
        print("\nEnviando comando TURN_ON para relay_final_test...")
        
        command = smart_city_pb2.DeviceCommand(
            command_type="TURN_ON",
            command_value=""
        )
        
        command_request = smart_city_pb2.ClientRequest(
            type=smart_city_pb2.ClientRequest.RequestType.SEND_DEVICE_COMMAND,
            target_device_id="relay_final_test",
            command=command
        )
        
        command_envelope = smart_city_pb2.SmartCityMessage(
            message_type=smart_city_pb2.MessageType.CLIENT_REQUEST,
            client_request=command_request
        )
        
        send_delimited_message(client_socket, command_envelope)
        
        # Ler resposta do comando
        print("Aguardando resposta do comando...")
        command_response_envelope = receive_delimited_message(client_socket, smart_city_pb2.SmartCityMessage)
        
        if command_response_envelope and command_response_envelope.HasField('gateway_response'):
            cmd_response = command_response_envelope.gateway_response
            print(f"Resposta recebida: {cmd_response.message}")
            print(f"Status do comando: {cmd_response.command_status}")
            
            if cmd_response.command_status == "SUCCESS":
                print("Comando executado com sucesso!")
                
                # Aguardar um pouco
                print("\nAguardando 2 segundos...")
                time.sleep(2)
                
                # Enviar comando TURN_OFF
                print("\nEnviando comando TURN_OFF para relay_final_test...")
                
                off_command = smart_city_pb2.DeviceCommand(
                    command_type="TURN_OFF",
                    command_value=""
                )
                
                off_command_request = smart_city_pb2.ClientRequest(
                    type=smart_city_pb2.ClientRequest.RequestType.SEND_DEVICE_COMMAND,
                    target_device_id="relay_final_test",
                    command=off_command
                )
                
                off_command_envelope = smart_city_pb2.SmartCityMessage(
                    message_type=smart_city_pb2.MessageType.CLIENT_REQUEST,
                    client_request=off_command_request
                )
                
                send_delimited_message(client_socket, off_command_envelope)
                
                # Ler resposta do comando OFF
                print("Aguardando resposta do comando OFF...")
                off_response_envelope = receive_delimited_message(client_socket, smart_city_pb2.SmartCityMessage)
                
                if off_response_envelope and off_response_envelope.HasField('gateway_response'):
                    off_response = off_response_envelope.gateway_response
                    print(f"Resposta OFF recebida: {off_response.message}")
                    print(f"Status do comando OFF: {off_response.command_status}")
                    
                    if off_response.command_status == "SUCCESS":
                        print("Comando OFF executado com sucesso!")
            else:
                print(f"Comando falhou: {cmd_response.message}")
        else:
            print("Resposta inválida do gateway")
        
        client_socket.close()
        print("\nTeste concluído!")
        
    except Exception as e:
        print(f"Erro: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_actuator_command()
