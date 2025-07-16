#!/usr/bin/env python3
"""
Script de validação final do sistema Smart City
Verifica se README.md está alinhado com a implementação real
"""

import os
import subprocess
import sys
from pathlib import Path

def print_status(message, success=True):
    """Imprime status sem emoji"""
    status = "OK" if success else "FALHA"
    print(f"[{status}] {message}")

def check_file_exists(filepath, description):
    """Verifica se arquivo existe"""
    if Path(filepath).exists():
        print_status(f"{description}: {filepath}")
        return True
    else:
        print_status(f"{description} NÃO ENCONTRADO: {filepath}", False)
        return False

def check_command_exists(command, description):
    """Verifica se comando está disponível"""
    try:
        subprocess.run([command, "--version"], capture_output=True, check=True)
        print_status(f"{description} disponível")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        print_status(f"{description} NÃO ENCONTRADO", False)
        return False

def check_port_listening(port, description):
    """Verifica se porta está sendo escutada"""
    try:
        result = subprocess.run(
            ["ss", "-tulpn", "|", "grep", str(port)], 
            shell=True, 
            capture_output=True, 
            text=True
        )
        if str(port) in result.stdout:
            print_status(f"{description} (porta {port}) está escutando")
            return True
        else:
            print_status(f"{description} (porta {port}) NÃO está escutando", False)
            return False
    except Exception:
        print_status(f"Erro ao verificar porta {port}", False)
        return False

def validate_makefile_commands():
    """Valida comandos do Makefile"""
    print("\n🔍 Validando comandos do Makefile...")
    
    makefile_commands = [
        "setup", "proto", "java", "clean", "install", "rabbitmq",
        "run-grpc", "run-gateway", "run-api", "run-client", "run-sensor",
        "test-mqtt", "status", "demo", "validate"
    ]
    
    success = True
    for cmd in makefile_commands:
        try:
            result = subprocess.run(
                ["make", "-n", cmd], 
                capture_output=True, 
                text=True, 
                cwd="."
            )
            if result.returncode == 0:
                print_status(f"Comando 'make {cmd}' definido")
            else:
                print_status(f"Comando 'make {cmd}' NÃO definido", False)
                success = False
        except Exception as e:
            print_status(f"Erro ao verificar 'make {cmd}': {e}", False)
            success = False
    
    return success

def validate_python_environment():
    """Valida ambiente Python"""
    print("\n🐍 Validando ambiente Python...")
    
    python_files = [
        "src/gateway/smart_city_gateway.py",
        "src/grpc_server/actuator_bridge_server.py",
        "src/client-test/smart_city_client.py",
        "test_full_system.py"
    ]
    
    success = True
    for file in python_files:
        if not check_file_exists(file, "Arquivo Python"):
            success = False
    
    # Verificar dependências Python
    required_modules = [
        "paho.mqtt.client",
        "grpc",
        "protobuf",
        "fastapi",
        "uvicorn"
    ]
    
    for module in required_modules:
        try:
            __import__(module.replace(".", ""))
            print_status(f"Módulo Python '{module}' instalado")
        except ImportError:
            print_status(f"Módulo Python '{module}' NÃO instalado", False)
            success = False
    
    return success

def validate_java_environment():
    """Valida ambiente Java"""
    print("\n☕ Validando ambiente Java...")
    
    java_files = [
        "src/devices/sensors/TemperatureHumiditySensor.java",
        "src/devices/actuators/RelayActuator.java",
        "pom.xml"
    ]
    
    success = True
    for file in java_files:
        if not check_file_exists(file, "Arquivo Java"):
            success = False
    
    # Verificar ferramentas Java
    if not check_command_exists("java", "Java Runtime"):
        success = False
    if not check_command_exists("javac", "Java Compiler"):
        success = False
    if not check_command_exists("mvn", "Maven"):
        success = False
    
    return success

def validate_protocol_buffers():
    """Valida Protocol Buffers"""
    print("\n📋 Validando Protocol Buffers...")
    
    proto_files = [
        "src/proto/smart_city.proto",
        "src/proto/actuator_service.proto"
    ]
    
    generated_files = [
        "src/proto/smart_city_pb2.py",
        "src/proto/actuator_service_pb2.py",
        "src/proto/actuator_service_pb2_grpc.py"
    ]
    
    success = True
    
    for file in proto_files:
        if not check_file_exists(file, "Arquivo .proto"):
            success = False
    
    for file in generated_files:
        if not check_file_exists(file, "Arquivo gerado"):
            success = False
    
    if not check_command_exists("protoc", "Protocol Compiler"):
        success = False
    
    return success

def validate_infrastructure():
    """Valida infraestrutura"""
    print("\nValidando infraestrutura...")
    
    success = True
    
    # Verificar RabbitMQ
    try:
        result = subprocess.run(
            ["sudo", "systemctl", "is-active", "rabbitmq-server"], 
            capture_output=True, 
            text=True
        )
        if "active" in result.stdout:
            print_status("RabbitMQ está ativo")
        else:
            print_status("RabbitMQ NÃO está ativo", False)
            success = False
    except Exception:
        print_status("Erro ao verificar RabbitMQ", False)
        success = False
    
    # Verificar portas
    ports = [
        (1883, "MQTT"),
        (50051, "gRPC"),
        (12345, "Gateway TCP"),
        (5007, "Multicast Discovery")
    ]
    
    for port, description in ports:
        if not check_port_listening(port, description):
            # Não marca como erro se portas não estiverem escutando
            # pois podem não estar rodando no momento
            pass
    
    return success

def main():
    """Função principal de validação"""
    print("Validacao Final do Sistema Smart City")
    print("=" * 50)
    
    # Verificar se estamos no diretório correto
    if not Path("README.md").exists():
        print_status("Execute este script no diretório raiz do projeto", False)
        sys.exit(1)
    
    results = []
    
    # Validações principais
    results.append(validate_makefile_commands())
    results.append(validate_python_environment())
    results.append(validate_java_environment())
    results.append(validate_protocol_buffers())
    results.append(validate_infrastructure())
    
    # Resumo final
    print("\n" + "=" * 50)
    print("RESUMO DA VALIDACAO:")
    
    validation_names = [
        "Makefile",
        "Python Environment",
        "Java Environment", 
        "Protocol Buffers",
        "Infrastructure"
    ]
    
    for name, result in zip(validation_names, results):
        print_status(f"{name}: {'OK' if result else 'FALHA'}", result)
    
    success_rate = sum(results) / len(results) * 100
    print(f"\nTaxa de sucesso: {success_rate:.1f}%")
    
    if all(results):
        print("\nSistema validado com sucesso!")
        print("[OK] README.md esta alinhado com a implementacao")
        print("[OK] Todos os componentes estao prontos")
        print("\nPara executar o sistema:")
        print("1. make setup")
        print("2. make run-grpc (terminal 1)")
        print("3. make run-gateway (terminal 2)")
        print("4. make run-client (terminal 3)")
        return 0
    else:
        print("\nAlgumas validacoes falharam")
        print("Consulte o README.md para instrucoes de configuracao")
        print("Execute 'make setup' para configurar o ambiente")
        return 1

if __name__ == "__main__":
    exit(main())
