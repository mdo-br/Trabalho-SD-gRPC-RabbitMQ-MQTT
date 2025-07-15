#!/usr/bin/env python3
"""
Teste do servidor gRPC para atuadores
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

def test_gateway_communication():
    """Testa comunicação com gateway e comando para atuador"""
    try:
        # Conectar ao gateway
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.connect(('localhost', 12345))
        
        print("✅ Conectado ao gateway na porta 12345")
        
        # 1. Listar dispositivos
        print("\n1. Listando dispositivos conectados...")
        
        request = smart_city_pb2.ClientRequest(
            type=smart_city_pb2.ClientRequest.RequestType.LIST_DEVICES
        )
        
        envelope = smart_city_pb2.SmartCityMessage(
            message_type=smart_city_pb2.MessageType.CLIENT_REQUEST,
            client_request=request
        )
        
        send_delimited_message(client_socket, envelope)
        
        # Ler resposta
        response_envelope = receive_delimited_message(client_socket, smart_city_pb2.SmartCityMessage)
        
        if response_envelope and response_envelope.HasField('gateway_response'):
            response = response_envelope.gateway_response
            print(f"✅ Resposta: {response.message}")
            
            if response.devices:
                print(f"✅ Dispositivos encontrados: {len(response.devices)}")
                for device in response.devices:
                    print(f"  - {device.device_id} ({smart_city_pb2.DeviceType.Name(device.type)}) - {device.ip_address}:{device.port}")
                    
                    # Se encontrar um atuador, enviar comando
                    if device.is_actuator:
                        print(f"\n2. Enviando comando TURN_ON para {device.device_id}...")
                        
                        command = smart_city_pb2.DeviceCommand(
                            command_type="TURN_ON",
                            command_value=""
                        )
                        
                        command_request = smart_city_pb2.ClientRequest(
                            type=smart_city_pb2.ClientRequest.RequestType.SEND_DEVICE_COMMAND,
                            target_device_id=device.device_id,
                            command=command
                        )
                        
                        command_envelope = smart_city_pb2.SmartCityMessage(
                            message_type=smart_city_pb2.MessageType.CLIENT_REQUEST,
                            client_request=command_request
                        )
                        
                        send_delimited_message(client_socket, command_envelope)
                        
                        # Ler resposta do comando
                        command_response_envelope = receive_delimited_message(client_socket, smart_city_pb2.SmartCityMessage)
                        
                        if command_response_envelope and command_response_envelope.HasField('gateway_response'):
                            cmd_response = command_response_envelope.gateway_response
                            print(f"✅ Comando enviado: {cmd_response.message}")
                            print(f"✅ Status: {cmd_response.command_status}")
                            
                            # Aguardar e enviar comando TURN_OFF
                            print(f"\n3. Aguardando 3 segundos...")
                            time.sleep(3)
                            
                            print(f"4. Enviando comando TURN_OFF para {device.device_id}...")
                            
                            off_command = smart_city_pb2.DeviceCommand(
                                command_type="TURN_OFF",
                                command_value=""
                            )
                            
                            off_command_request = smart_city_pb2.ClientRequest(
                                type=smart_city_pb2.ClientRequest.RequestType.SEND_DEVICE_COMMAND,
                                target_device_id=device.device_id,
                                command=off_command
                            )
                            
                            off_command_envelope = smart_city_pb2.SmartCityMessage(
                                message_type=smart_city_pb2.MessageType.CLIENT_REQUEST,
                                client_request=off_command_request
                            )
                            
                            send_delimited_message(client_socket, off_command_envelope)
                            
                            # Ler resposta do comando OFF
                            off_response_envelope = receive_delimited_message(client_socket, smart_city_pb2.SmartCityMessage)
                            
                            if off_response_envelope and off_response_envelope.HasField('gateway_response'):
                                off_response = off_response_envelope.gateway_response
                                print(f"✅ Comando OFF enviado: {off_response.message}")
                                print(f"✅ Status: {off_response.command_status}")
                        
                        break
            else:
                print("❌ Nenhum dispositivo encontrado")
        
        client_socket.close()
        print("\n✅ Teste concluído!")
        
    except Exception as e:
        print(f"❌ Erro: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_gateway_communication()
