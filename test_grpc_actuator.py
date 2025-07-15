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
        
        envelope.writeDelimitedTo(client_socket)
        
        # Ler resposta
        response_envelope = smart_city_pb2.SmartCityMessage()
        response_envelope.ParseDelimitedFrom(client_socket)
        
        if response_envelope.HasField('gateway_response'):
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
                        
                        command_envelope.writeDelimitedTo(client_socket)
                        
                        # Ler resposta do comando
                        command_response_envelope = smart_city_pb2.SmartCityMessage()
                        command_response_envelope.ParseDelimitedFrom(client_socket)
                        
                        if command_response_envelope.HasField('gateway_response'):
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
                            
                            off_command_envelope.writeDelimitedTo(client_socket)
                            
                            # Ler resposta do comando OFF
                            off_response_envelope = smart_city_pb2.SmartCityMessage()
                            off_response_envelope.ParseDelimitedFrom(client_socket)
                            
                            if off_response_envelope.HasField('gateway_response'):
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
