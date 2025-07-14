#!/bin/bash

# Script para configurar RabbitMQ com plugin MQTT

echo "Configurando RabbitMQ com plugin MQTT..."

# Verificar se RabbitMQ está instalado
if ! command -v rabbitmq-server &> /dev/null; then
    echo "RabbitMQ não está instalado. Instalando..."
    
    # Instalar RabbitMQ no Ubuntu/Debian
    if command -v apt-get &> /dev/null; then
        sudo apt-get update
        sudo apt-get install -y rabbitmq-server
    # Instalar RabbitMQ no CentOS/RHEL
    elif command -v yum &> /dev/null; then
        sudo yum install -y rabbitmq-server
    # Instalar RabbitMQ no Fedora
    elif command -v dnf &> /dev/null; then
        sudo dnf install -y rabbitmq-server
    else
        echo "Sistema operacional não suportado. Instale o RabbitMQ manualmente."
        exit 1
    fi
fi

# Iniciar RabbitMQ
echo "Iniciando RabbitMQ..."
sudo -n systemctl start rabbitmq-server
sudo -n systemctl enable rabbitmq-server

# Verificar status (sem pager)
sudo -n systemctl status rabbitmq-server --no-pager

# Habilitar plugin MQTT
echo "Habilitando plugin MQTT..."
sudo -n rabbitmq-plugins enable rabbitmq_mqtt

# Habilitar plugin de gerenciamento (opcional, para interface web)
echo "Habilitando plugin de gerenciamento..."
sudo -n rabbitmq-plugins enable rabbitmq_management

# Criar usuário para MQTT (opcional, só se não existir)
echo "Criando usuário MQTT..."
if ! sudo -n rabbitmqctl list_users | grep -q smartcity; then
  sudo -n rabbitmqctl add_user smartcity smartcity123
  sudo -n rabbitmqctl set_permissions -p / smartcity ".*" ".*" ".*"
else
  echo "Usuário smartcity já existe."
fi

# Reiniciar RabbitMQ para aplicar mudanças
echo "Reiniciando RabbitMQ..."
sudo -n systemctl restart rabbitmq-server

echo ""
echo "Configuração concluída!"
echo ""
echo "Informações de conexão:"
echo "- MQTT Broker: localhost:1883"
echo "- Web Management: http://localhost:15672"
echo "- Usuário: smartcity"
echo "- Senha: smartcity123"
echo ""
echo "Para verificar tópicos MQTT:"
echo "sudo rabbitmqctl list_queues"
echo ""
echo "Para monitorar logs:"
echo "sudo journalctl -u rabbitmq-server -f"
