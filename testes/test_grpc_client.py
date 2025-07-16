#!/usr/bin/env python3
"""
Cliente de teste gRPC para o servidor de atuadores

Este script testa a comunicação gRPC com o servidor actuator_bridge_server.py
"""

import grpc
import sys
import os

# Adicionar diretório proto ao path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src', 'proto'))

import actuator_service_pb2
import actuator_service_pb2_grpc

def test_grpc_connection():
    """Testa a conexão com o servidor gRPC"""
    print("Testando conexao gRPC com servidor de atuadores...")
    
    try:
        # Criar canal gRPC
        with grpc.insecure_channel('localhost:50051') as channel:
            # Criar stub do cliente
            stub = actuator_service_pb2_grpc.AtuadorServiceStub(channel)
            
            # Testar consulta de estado
            print("\n1. Testando ConsultarEstado...")
            request = actuator_service_pb2.DeviceRequest(
                device_id="relay_board_001001002",
                ip="192.168.1.103",
                port=8891
            )
            
            try:
                response = stub.ConsultarEstado(request, timeout=5)
                print(f"Resposta: {response.status} - {response.message}")
            except grpc.RpcError as e:
                print(f"Erro na consulta: {e}")
            
            # Testar ligar dispositivo
            print("\n2. Testando LigarDispositivo...")
            try:
                response = stub.LigarDispositivo(request, timeout=5)
                print(f"Resposta: {response.status} - {response.message}")
            except grpc.RpcError as e:
                print(f"Erro ao ligar: {e}")
            
            # Testar desligar dispositivo
            print("\n3. Testando DesligarDispositivo...")
            try:
                response = stub.DesligarDispositivo(request, timeout=5)
                print(f"Resposta: {response.status} - {response.message}")
            except grpc.RpcError as e:
                print(f"Erro ao desligar: {e}")
                
    except Exception as e:
        print(f"Erro ao conectar com servidor gRPC: {e}")
        return False
    
    return True

if __name__ == "__main__":
    print("=== Teste Cliente gRPC ===")
    success = test_grpc_connection()
    
    if success:
        print("\nTeste concluido com sucesso!")
    else:
        print("\nTeste falhou!")
        sys.exit(1) 