from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, Any
import threading
import time
import google.protobuf.message
from src.proto import smart_city_pb2

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


@app.get("/")
def root():
    return {"message": "Smart City Gateway API Online"}


@app.get("/devices", response_model=Dict[str, DeviceInfo])
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


@app.get("/devices/{device_id}", response_model=DeviceInfo)
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
