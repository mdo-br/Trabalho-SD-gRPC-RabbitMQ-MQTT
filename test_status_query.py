#!/usr/bin/env python3
"""
Teste específico para consulta de status
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

def test_status_query():
    """Testa consulta de status específica"""
    try:
        # Conectar ao gateway
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.connect(('localhost', 12345))
        
        print("✅ Conectado ao gateway na porta 12345")
        
        # Consultar status
        print("\n🔍 Consultando status do relay_final_test...")
        
        status_request = smart_city_pb2.ClientRequest(
            type=smart_city_pb2.ClientRequest.RequestType.GET_DEVICE_STATUS,
            target_device_id="relay_final_test"
        )
        
        status_envelope = smart_city_pb2.SmartCityMessage(
            message_type=smart_city_pb2.MessageType.CLIENT_REQUEST,
            client_request=status_request
        )
        
        send_delimited_message(client_socket, status_envelope)
        
        # Ler resposta
        print("📥 Aguardando resposta do status...")
        response_envelope = receive_delimited_message(client_socket, smart_city_pb2.SmartCityMessage)
        
        if response_envelope and response_envelope.HasField('gateway_response'):
            response = response_envelope.gateway_response
            print(f"✅ Resposta recebida: {response.message}")
            
            if response.HasField('device_status'):
                device_status = response.device_status
                print(f"📊 Status do dispositivo:")
                print(f"  - Device ID: {device_status.device_id}")
                print(f"  - Type: {smart_city_pb2.DeviceType.Name(device_status.type)}")
                print(f"  - Current Status: {smart_city_pb2.DeviceStatus.Name(device_status.current_status)}")
                print("🎉 Consulta de status bem-sucedida!")
            else:
                print("❌ Resposta não contém status do dispositivo")
        else:
            print("❌ Resposta inválida do gateway")
        
        client_socket.close()
        print("\n✅ Teste concluído!")
        
    except Exception as e:
        print(f"❌ Erro: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_status_query()
