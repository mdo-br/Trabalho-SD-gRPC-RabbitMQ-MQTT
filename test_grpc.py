#!/usr/bin/env python3
"""
Teste simples para verificar se o gRPC funciona
"""

try:
    import grpc
    print("gRPC importado com sucesso")
    
    import sys
    sys.path.append('src/proto')
    
    from src.proto import actuator_service_pb2_grpc
    from src.proto import actuator_service_pb2
    print("Modulos protobuf importados com sucesso")
    
    print("Todas as dependencias funcionando!")
    
except ImportError as e:
    print(f"✗ Erro de importação: {e}")
except Exception as e:
    print(f"✗ Erro geral: {e}")
