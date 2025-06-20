from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, Any
import time
from src.proto import smart_city_pb2
import logging
from src.gateway.smart_city_gateway import send_tcp_command

logger = logging.getLogger("api_server")
logging.basicConfig(level=logging.INFO)

# Importa o estado dos dispositivos do gateway
from src.gateway.state import connected_devices, device_lock

app = FastAPI(title="Smart City Gateway API")

# Modelos de resposta
class DeviceInfo(BaseModel):
    id: str
    ip: str
    port: int
    type: str
    status: str
    is_sensor: bool
    is_actuator: bool
    sensor_data: Dict[str, Any]
    last_seen_seconds: float

class ChangeIdRequest(BaseModel):
    new_id: str


class ChangeStatusRequest(BaseModel):
    new_status: str  # Deve ser 'ACTIVE' ou 'OFF'


class ChangeCaptureSpeedRequest(BaseModel):
    interval_seconds: float  # Novo intervalo em segundos



@app.get("/devices/info", response_model=Dict[str, DeviceInfo])
def list_devices():
    """Retorna todos os dispositivos conectados."""
    with device_lock:
        result = {}
        current_time = time.time()
        for dev_id, dev in connected_devices.items():
            result[dev_id] = DeviceInfo(
                id=dev_id,
                ip=dev['ip'],
                port=dev['port'],
                type=smart_city_pb2.DeviceType.Name(dev['type']),
                status=smart_city_pb2.DeviceStatus.Name(dev['status']),
                is_sensor=dev['is_sensor'],
                is_actuator=dev['is_actuator'],
                sensor_data=dev.get('sensor_data', {}), 
                last_seen_seconds=current_time - dev['last_seen']
            )
        return result


@app.get("/device/info", response_model=DeviceInfo)
def get_device(device_id: str):
    """Obtém informações de um dispositivo específico."""
    with device_lock:
        if device_id not in connected_devices:
            raise HTTPException(status_code=404, detail="Dispositivo não encontrado")

        dev = connected_devices[device_id]
        return DeviceInfo(
            id=device_id,
            ip=dev['ip'],
            port=dev['port'],
            type=smart_city_pb2.DeviceType.Name(dev['type']),
            status=smart_city_pb2.DeviceStatus.Name(dev['status']),
            is_sensor=dev['is_sensor'],
            is_actuator=dev['is_actuator'],
            sensor_data=dev.get('sensor_data', {}),
            last_seen_seconds=time.time() - dev['last_seen']
        )

@app.post("/device/set-id")
def change_device_id(device_id: str, request: ChangeIdRequest):
    with device_lock:
        if device_id not in connected_devices:
            raise HTTPException(status_code=404, detail="Dispositivo não encontrado")
        
        if request.new_id in connected_devices:
            raise HTTPException(status_code=400, detail="Novo ID já está em uso")

        dev = connected_devices[device_id]
        success = send_tcp_command(
            dev['ip'],
            dev['port'],
            "SET_DEVICE_ID",
            request.new_id
        )

        if not success:
            raise HTTPException(status_code=500, detail="Falha ao enviar comando para alterar ID")

        # Atualiza localmente
        connected_devices[request.new_id] = dev.copy()
        connected_devices[request.new_id]['device_id'] = request.new_id
        del connected_devices[device_id]

        return {"message": f"ID alterado de {device_id} para {request.new_id}"}


    
@app.post("/device/change-status")
def change_device_status(device_id: str, request: ChangeStatusRequest):
    with device_lock:
        if device_id not in connected_devices:
            raise HTTPException(status_code=404, detail="Dispositivo não encontrado")
        
        status_map = {
            "ACTIVE": smart_city_pb2.DeviceStatus.ACTIVE,
            "OFF": smart_city_pb2.DeviceStatus.OFF,
        }

        command_map = {
            "ACTIVE": "TURN_ON",
            "OFF": "TURN_OFF",
        }

        if request.new_status not in status_map:
            raise HTTPException(status_code=400, detail="Status inválido. Use 'ACTIVE' ou 'OFF'.")

        dev = connected_devices[device_id]
        success = send_tcp_command(
            dev['ip'],
            dev['port'],
            command_map[request.new_status],
            request.new_status
        )

        if not success:
            raise HTTPException(status_code=500, detail="Falha ao enviar comando TCP para o dispositivo")

        dev['status'] = status_map[request.new_status]
        return {"message": f"Status do dispositivo {device_id} alterado para {request.new_status}"}

    
@app.post("/device/change-capture-speed")
def change_capture_speed(device_id: str, request: ChangeCaptureSpeedRequest):
    with device_lock:
        if device_id not in connected_devices:
            raise HTTPException(status_code=404, detail="Dispositivo não encontrado")

        device = connected_devices[device_id]

        if not device['is_sensor']:
            raise HTTPException(status_code=400, detail="Dispositivo não é um sensor.")

        # Envia comando TCP para o sensor alterar o intervalo
        success = send_tcp_command(
            device_ip=device['ip'],
            device_port=device['port'],
            command_type="SET_SAMPLING_RATE",
            command_value=str(int(request.interval_seconds))
        )

        if not success:
            raise HTTPException(status_code=500, detail="Falha ao enviar comando para o dispositivo.")

        # Atualiza também no banco local da API (opcional)
        device['sensor_data']['capture_interval'] = request.interval_seconds

        return {"message": f"Velocidade de captura do sensor {device_id} alterada para {request.interval_seconds} segundos"}
