# Smart City Gateway API

API para gerenciamento de sensores e atuadores em uma cidade inteligente.  
Permite listar dispositivos, obter dados de sensores, controlar atuadores (relés) e ajustar a frequência de coleta dos sensores.

---

## Sobre a API

- **Framework:** FastAPI  
- **Protocolo:** HTTP (REST)  
- **Backend:** Comunicação via TCP com o Gateway usando Protobuf  
- **Funcionalidades:**
  - Listagem de dispositivos conectados
  - Consulta de status e dados sensoriais
  - Controle de relés (ligar/desligar)
  - Alteração de estado de sensores (ativo/inativo)
  - Ajuste da frequência de coleta dos sensores

---

## Endpoints

| Método | Endpoint                      | Descrição                                                        |
|--------|-------------------------------|------------------------------------------------------------------|
| GET    | `/devices`                    | Lista todos os dispositivos conectados ao gateway                |
| GET    | `/device/data`                | Retorna dados e status de um dispositivo                         |
| PUT    | `/device/relay`               | Liga ou desliga um relé (atuador)                                |
| PUT    | `/device/sensor/state`        | Ativa ou desativa um sensor                                      |
| PUT    | `/device/sensor/frequency`    | Define o intervalo de coleta de dados para um sensor (em ms)     |

---

## Modelos de Dados

### Resposta geral dos Dispositivos (Exemplo de descoberta)

```json
{
  "id": "sensor01",
  "type": "SENSOR",
  "ip": "192.168.3.45",
  "port": 9001,
  "status": "ACTIVE",
  "is_sensor": true,
  "is_actuator": false
}
```

### Dados do Sensor

```json
{
  "id": "sensor01",
  "type": "SENSOR",
  "status": "ACTIVE",
  "custom_config_status": "default",
  "temperature": 23.1,
  "humidity": 55.0,
  "frequency_ms": 5000
}
```

## Exemplos com curl

```bash
curl -X GET "http://127.0.0.1:8000/devices"
```

```bash
curl -X GET "http://127.0.0.1:8000/device/data?device_id=sensor01"
```

```bash
curl -X PUT "http://localhost:8000/device/relay?device_id=relay01&action=TURN_ON"
```

```bash
curl -X PUT "http://localhost:8000/device/relay?device_id=relay01&action=TURN_OFF"
```

```bash
curl -X PUT "http://localhost:8000/device/sensor/state?device_id=sensor01&state=TURN_IDLE"
```

## Como Usar

1. Inicie a API:

```bash
uvicorn src.api.src.api_server:app --reload
```

2. Acesse a documentação interativa no navegador:

```
http://127.0.0.1:8000/docs
```
