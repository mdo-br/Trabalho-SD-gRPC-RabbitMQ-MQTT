# Guia Completo: Instalar Gateway no Raspberry Pi via SSH

## Passos para Instalação

### **1. Conectar via SSH**
```bash
ssh pi@ip_do_raspberry
```

### **2. Clonar o Repositório**
```bash
git clone https://github.com/JoaoAndrade18/Trabalho-SD.git
cd Trabalho-SD
```

### **3. Instalar Dependências**
```bash
# Criar ambiente virtual
python3 -m venv venv
source venv/bin/activate

# Instalar dependências Python
pip install -r requirements.txt
```

### **4. Instalar Protocol Buffers**
```bash
sudo apt update
sudo apt install protobuf-compiler
```

### **5. Gerar Arquivos Protobuf (Versão Gateway)**
```bash
cd src/proto

# Gerar arquivo Python para gateway (versão simplificada sem nanopb)
protoc --python_out=. smart_city.proto

# Verificar se foi gerado
ls -la smart_city_pb2.py

cd ../..
```

### **6. Configurar PYTHONPATH**
```bash
export PYTHONPATH=$PYTHONPATH:$(pwd)/src/proto
```

### **7. Rodar o Gateway**
```bash
# Ativar ambiente virtual (se não estiver ativo)
source venv/bin/activate

# Executar gateway
python3 -m src.gateway.smart_city_gateway
```

## Comandos Úteis

### **Para Rodar em Background**
```bash
# Usando nohup
nohup python3 -m src.gateway.smart_city_gateway > gateway.log 2>&1 &

# Usando screen
screen -S gateway
python3 -m src.gateway.smart_city_gateway
# Ctrl+A, D para sair do screen
```

### **Para Verificar se Está Rodando**
```bash
# Verificar processos
ps aux | grep smart_city_gateway

# Verificar portas
netstat -tlnp | grep :12345
netstat -tlnp | grep :12346
```

### **Para Parar o Gateway**
```bash
# Se rodando em foreground: Ctrl+C
# Se rodando em background:
pkill -f smart_city_gateway
```

## Portas Utilizadas
- **TCP 12345** - Comandos e registro de dispositivos
- **UDP 12346** - Dados sensoriados dos dispositivos
- **UDP 5007** - Multicast para descoberta de dispositivos

## Verificação de Sucesso
O gateway está funcionando quando você vê logs como:
```
[INFO] Gateway iniciado com IP: 192.168.1.100
[INFO] Gateway ouvindo TCP na porta 12345...
[INFO] Gateway ouvindo UDP na porta 12346...
[DISCOVERY] Enviando pacote multicast...
```

## Estrutura de Arquivos .proto

### **Para Gateway/Cliente (Python)**
- **Arquivo:** `src/proto/smart_city.proto`
- **Comando:** `protoc --python_out=. smart_city.proto`
- **Gera:** `smart_city_pb2.py`
- **Características:** Versão simplificada sem nanopb

### **Para Dispositivos ESP8266 (C/C++)**
- **Arquivo:** `src/proto/smart_city_devices.proto`
- **Comando:** `protoc -I. -I../../nanopb-0.4.9.1-linux-x86/generator/proto --nanopb_out=. smart_city_devices.proto`
- **Gera:** `smart_city_devices.pb.h` e `smart_city_devices.pb.c`
- **Características:** Versão completa com nanopb e opções de tamanho

## Resumo dos Comandos em Sequência
```bash
ssh pi@ip_do_raspberry
git clone https://github.com/JoaoAndrade18/Trabalho-SD.git
cd Trabalho-SD
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
sudo apt install protobuf-compiler
cd src/proto
protoc --python_out=. smart_city.proto
cd ../..
export PYTHONPATH=$PYTHONPATH:$(pwd)/src/proto
python3 -m src.gateway.smart_city_gateway
```

## Atualizações Futuras
Se o protocolo for atualizado, execute apenas:
```bash
cd src/proto
protoc --python_out=. smart_city.proto
cd ../..
python3 -m src.gateway.smart_city_gateway
```

**Pronto! Guarde este guia para futuras instalações! 🎉** 