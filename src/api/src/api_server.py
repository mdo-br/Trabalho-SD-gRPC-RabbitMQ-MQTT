from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import socket
import struct
from src.proto import smart_city_pb2

app = FastAPI()

# Configuração do CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Ou especifique ["http://localhost:3000"] para restringir
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

GATEWAY_HOST = "192.168.3.129"
GATEWAY_API_PORT = 12347

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


def send_protobuf_request(request_msg: smart_city_pb2.ClientRequest) -> smart_city_pb2.GatewayResponse:
    try:
        with socket.create_connection((GATEWAY_HOST, GATEWAY_API_PORT), timeout=5) as sock:
            write_delimited_message(sock, request_msg)
            data = read_delimited_message(sock)
            response = smart_city_pb2.GatewayResponse()
            response.ParseFromString(data)
            return response
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
    if res.type == smart_city_pb2.GatewayResponse.DEVICE_STATUS_UPDATE:
        d = res.device_status
        base_response = {
            "id": d.device_id,
            "status": smart_city_pb2.DeviceStatus.Name(d.current_status),
            "custom_config_status": d.custom_config_status,
        }

        if d.HasField("temperature_humidity"):
            base_response["temperature"] = d.temperature_humidity.temperature
            base_response["humidity"] = d.temperature_humidity.humidity

        # Exemplo para ALARM ligado
        if d.type == smart_city_pb2.DeviceType.ALARM and d.current_status == smart_city_pb2.DeviceStatus.ON:
            base_response["sound"] = "Ligado"

        return base_response

    raise HTTPException(status_code=404, detail=res.message or "Dispositivo não encontrado")


@app.put("/devices/config")
def update_device_config(device_id: str, new_interval: int = None, new_status: str = None):
    try:
        commands = []
        if new_interval is not None:
            commands.append(("SET_SAMPLING_RATE", str(new_interval)))
        if new_status:
            commands.append(("TURN_ON" if new_status == "ON" else "TURN_OFF", ""))

        responses = []

        for command_type, value in commands:
            req = smart_city_pb2.ClientRequest(
                type=smart_city_pb2.ClientRequest.SEND_DEVICE_COMMAND,
                target_device_id=device_id,
                command=smart_city_pb2.DeviceCommand(
                    device_id=device_id,
                    command_type=command_type,
                    command_value=value
                )
            )
            res = send_protobuf_request(req)
            responses.append({
                "command": command_type,
                "status": res.command_status,
                "message": res.message
            })

        return {"results": responses}
    except Exception as e:
        return {"error": str(e)}
