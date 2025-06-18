import socket
import asyncio
import json
from devices_dict import DEVICES

def get_device_info(device_id: int):
    device = DEVICES.get(device_id)
    if not device:
        raise ValueError(f"Dispositivo '{device_id}' não encontrado.")
    return device

def get_devices_list():
    return [{"id": device_id, "ip": device["ip"], "port": device["port"], "type": device["type"]} for device_id, device in DEVICES.items()]


# ----------- Comunicação com Sensores (UDP) -----------



# ----------- Comunicação com Atuadores (TCP) -----------
