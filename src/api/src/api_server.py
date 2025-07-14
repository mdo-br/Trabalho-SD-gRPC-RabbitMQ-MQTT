from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import socket
import struct
from src.proto import smart_city_pb2

app = FastAPI()

# Configuração do CORS para acesso a API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

GATEWAY_HOST = "192.168.3.129"
GATEWAY_API_PORT = 12347

# Utilitários de serialização varint (delimited Protobuf)
# Encapsular mensagens Protobuf em tamanhos prefixadoss de forma a garantir 
# que o receptor saiba o tamanho da mensagem antes de tentar ler os dados.

def encode_varint(value: int) -> bytes:
    result = b""
    while True:
        bits = value & 0x7F
        value >>= 7
        if value:
            result += struct.pack("B", bits | 0x80)
        else:
            result += struct.pack("B", bits)
            break
    return result

def read_varint(stream):
    shift = 0
    result = 0
    while True:
        b = stream.read(1)
        if not b:
            raise EOFError("Stream fechado inesperadamente ao ler varint.")
        b = ord(b)
        result |= (b & 0x7f) << shift
        if not (b & 0x80):
            return result
        shift += 7
        if shift >= 64:
            raise ValueError("Varint muito longo.")

def write_delimited_message(sock, message):
    data = message.SerializeToString()
    sock.sendall(encode_varint(len(data)) + data)

def read_delimited_message(sock):
    reader = sock.makefile('rb')
    size = read_varint(reader)
    
    return reader.read(size)

# Envia uma mensagem Protobuf para o gateway e espera uma resposta, tuda a comunicação é feita por essa função.
def send_protobuf_request(request_msg: smart_city_pb2.ClientRequest) -> smart_city_pb2.GatewayResponse | smart_city_pb2.DeviceUpdate:
    try:
        envelope = smart_city_pb2.SmartCityMessage(
            message_type=smart_city_pb2.MessageType.CLIENT_REQUEST,
            client_request=request_msg
        )
        with socket.create_connection((GATEWAY_HOST, GATEWAY_API_PORT), timeout=5) as sock:
            write_delimited_message(sock, envelope)
            data = read_delimited_message(sock)

            response_envelope = smart_city_pb2.SmartCityMessage()
            response_envelope.ParseFromString(data)
            print(f"Recebido envelope: {response_envelope}")

            if response_envelope.message_type == smart_city_pb2.MessageType.GATEWAY_RESPONSE:
                return response_envelope.gateway_response
            
            #elif response_envelope.message_type == smart_city_pb2.MessageType.DEVICE_UPDATE:
                #return response_envelope.device_update
            
            else:
                raise HTTPException(status_code=500, detail=f"Tipo de mensagem inesperado: {response_envelope.message_type}")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro na comunicação com o gateway: {e}")


@app.get("/devices")
def list_devices():
    req = smart_city_pb2.ClientRequest(type=smart_city_pb2.ClientRequest.LIST_DEVICES)
    res = send_protobuf_request(req)
    return [
        {
            "id": d.device_id,
            "type": smart_city_pb2.DeviceType.Name(d.type),
            "ip": d.ip_address,
            "port": d.port,
            "status": smart_city_pb2.DeviceStatus.Name(d.initial_state),
            "is_sensor": d.is_sensor,
            "is_actuator": d.is_actuator
        }
        for d in res.devices
    ]

@app.get("/device/data")
def get_device_status(device_id: str):
    req = smart_city_pb2.ClientRequest(
        type=smart_city_pb2.ClientRequest.GET_DEVICE_STATUS,
        target_device_id=device_id
    )
    res = send_protobuf_request(req)

    print(res.device_status)

    if res.type == smart_city_pb2.GatewayResponse.DEVICE_STATUS_UPDATE:
        d = res.device_status
        response = {
            "id": d.device_id,
            "type": smart_city_pb2.DeviceType.Name(d.type),
            "status": smart_city_pb2.DeviceStatus.Name(d.current_status),
            "custom_config_status": d.custom_config_status,
        }

        if d.HasField("temperature_humidity"):
            response["temperature"] = d.temperature_humidity.temperature
            response["humidity"] = d.temperature_humidity.humidity

        if hasattr(d, "frequency_ms") and d.frequency_ms > 0:
            response["frequency_ms"] = d.frequency_ms

        return response

    raise HTTPException(status_code=404, detail=res.message or "Dispositivo não encontrado")


@app.put("/device/relay")
def control_relay(device_id: str, action: str):
    if action not in ["TURN_ON", "TURN_OFF"]:
        raise HTTPException(status_code=400, detail="Inválido. Use TURN_ON ou TURN_OFF.")
    
    cmd = smart_city_pb2.DeviceCommand(device_id=device_id, command_type=action)
    req = smart_city_pb2.ClientRequest(
        type=smart_city_pb2.ClientRequest.SEND_DEVICE_COMMAND,
        target_device_id=device_id,
        command=cmd
    )
    res = send_protobuf_request(req)
    return {"status": res.command_status, "message": res.message}

@app.put("/device/sensor/state")
def change_sensor_state(device_id: str, state: str):
    if state not in ["TURN_ACTIVE", "TURN_IDLE"]:
        raise HTTPException(status_code=400, detail="Inválido. Use TURN_ACTIVE ou TURN_IDLE.")
    
    cmd = smart_city_pb2.DeviceCommand(device_id=device_id, command_type=state)
    req = smart_city_pb2.ClientRequest(
        type=smart_city_pb2.ClientRequest.SEND_DEVICE_COMMAND,
        target_device_id=device_id,
        command=cmd
    )
    res = send_protobuf_request(req)
    return {"status": res.command_status, "message": res.message}

@app.put("/device/sensor/frequency")
def set_sensor_frequency(device_id: str, frequency: int):
    if frequency < 1000 or frequency > 60000:
        raise HTTPException(status_code=400, detail="Frequência incorreto.")
    
    cmd = smart_city_pb2.DeviceCommand(device_id=device_id, command_type="SET_FREQ", command_value=str(frequency))
    req = smart_city_pb2.ClientRequest(
        type=smart_city_pb2.ClientRequest.SEND_DEVICE_COMMAND,
        target_device_id=device_id,
        command=cmd
    )
    res = send_protobuf_request(req)
    return {"status": res.command_status, "message": res.message}
