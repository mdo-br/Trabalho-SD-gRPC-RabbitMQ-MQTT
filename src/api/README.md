
# 🌆 Smart City Gateway API

API para gerenciamento de dispositivos IoT em uma cidade inteligente. Permite listar dispositivos, obter informações, alterar ID, modificar status (ligar/desligar) e ajustar a frequência de captura dos sensores.

---

## 🚀 Sobre a API

- **Framework:** FastAPI
- **Protocolo:** HTTP (REST)
- **Descrição:** Permite controle e monitoramento de sensores e atuadores conectados no gateway.

---

## 🔌 Endpoints

| Método | Endpoint                               | Descrição                                       |
|--------|-----------------------------------------|-------------------------------------------------|
| GET    | `/devices/info`                        | Lista todos os dispositivos conectados          |
| GET    | `/device/info`                          | Retorna informações de um dispositivo específico|
| POST   | `/device/set-id`                        | Altera o ID de um dispositivo                  |
| POST   | `/device/change-status`                 | Altera o status (ligado/desligado) do dispositivo|
| POST   | `/device/change-capture-speed`          | Altera a frequência de captura de um sensor     |

---

## 📄 Modelos de Dados

### 🔍 DeviceInfo

| Campo             | Tipo           | Descrição                              |
|-------------------|----------------|-----------------------------------------|
| id                | string         | ID do dispositivo                      |
| ip                | string         | Endereço IP                            |
| port              | integer        | Porta TCP                               |
| type              | string         | Tipo (ex.: SENSOR, ACTUATOR)            |
| status            | string         | Status (ex.: ACTIVE, OFF)               |
| is_sensor         | boolean        | Se é um sensor                          |
| is_actuator       | boolean        | Se é um atuador                         |
| sensor_data       | dict           | Dados específicos do sensor              |
| last_seen_seconds | float          | Segundos desde a última comunicação     |

---

### 🔧 ChangeIdRequest

```json
{
  "new_id": "string"
}
```

---

### 🔧 ChangeStatusRequest

```json
{
  "new_status": "ACTIVE" | "OFF"
}
```

---

### 🔧 ChangeCaptureSpeedRequest

```json
{
  "interval_seconds": float
}
```

---

## 🔗 Endpoints Detalhados

---

### 🔹 Listar todos os dispositivos

**GET** `/devices/info`

**Resposta Exemplo:**

```json
{
  "dev001": {
    "id": "dev001",
    "ip": "192.168.0.10",
    "port": 9000,
    "type": "SENSOR",
    "status": "ACTIVE",
    "is_sensor": true,
    "is_actuator": false,
    "sensor_data": {
      "temperature": 24.5,
      "humidity": 60
    },
    "last_seen_seconds": 5.23
  }
}
```

---

### 🔹 Obter informações de um dispositivo

**GET** `/device/info?device_id=dev001`

**Resposta Exemplo:**

```json
{
  "id": "dev001",
  "ip": "192.168.0.10",
  "port": 9000,
  "type": "SENSOR",
  "status": "ACTIVE",
  "is_sensor": true,
  "is_actuator": false,
  "sensor_data": {
    "temperature": 24.5,
    "humidity": 60
  },
  "last_seen_seconds": 3.12
}
```

---

### 🔹 Alterar o ID do dispositivo

**POST** `/device/set-id?device_id=dev001`

**Body:**

```json
{
  "new_id": "dev100"
}
```

**Resposta:**

```json
{
  "message": "ID alterado de dev001 para dev100"
}
```

---

### 🔹 Alterar status (ligar/desligar)

**POST** `/device/change-status?device_id=dev100`

**Body:**

```json
{
  "new_status": "OFF"
}
```

**Resposta:**

```json
{
  "message": "Status do dispositivo dev100 alterado para OFF"
}
```

**Valores permitidos para `new_status`:**
- `ACTIVE`
- `OFF`

---

### 🔹 Alterar frequência de captura do sensor

**POST** `/device/change-capture-speed?device_id=dev100`

**Body:**

```json
{
  "interval_seconds": 10
}
```

**Resposta:**

```json
{
  "message": "Velocidade de captura do sensor dev100 alterada para 10 segundos"
}
```

---

## 🛠️ Como Usar

1. Inicie a API:

```bash
uvicorn src.api.api_server:app --reload
```

2. Acesse a documentação interativa no navegador:

```
http://127.0.0.1:8000/docs
```

3. Utilize qualquer cliente HTTP, como `curl`, Postman, Insomnia, ou diretamente no Python com `requests`.

---

## 💡 Exemplos de chamadas usando `curl`

- **Listar dispositivos:**

```bash
curl -X GET "http://127.0.0.1:8000/devices/info"
```

- **Obter informações de um dispositivo:**

```bash
curl -X GET "http://127.0.0.1:8000/device/info?device_id=dev001"
```

- **Alterar ID:**

```bash
curl -X POST "http://127.0.0.1:8000/device/set-id?device_id=dev001" \
-H "Content-Type: application/json" \
-d '{"new_id": "dev100"}'
```

- **Alterar status:**

```bash
curl -X POST "http://127.0.0.1:8000/device/change-status?device_id=dev100" \
-H "Content-Type: application/json" \
-d '{"new_status": "ACTIVE"}'
```

- **Alterar frequência de captura:**

```bash
curl -X POST "http://127.0.0.1:8000/device/change-capture-speed?device_id=dev100" \
-H "Content-Type: application/json" \
-d '{"interval_seconds": 5}'
```

---

## 🚧 Observações

- O backend mantém o estado dos dispositivos em memória (`connected_devices`).
- As alterações são feitas tanto localmente quanto remotamente via comandos TCP, utilizando `send_tcp_command`.
- Se o servidor for reiniciado, os dispositivos precisam ser detectados novamente (a persistência não é implementada).
