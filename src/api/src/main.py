from fastapi import FastAPI, HTTPException
import asyncio
from device_client import send_udp_command, send_tcp_command, get_device_info, get_devices_list

app = FastAPI()

@app.get("/devices-list")
def devices_list():
    response = get_devices_list()
    return response

@app.get("/device-info")
def get_sensor_info(device_id: int):
    try:
        response = get_device_info(device_id)
        return response
    except ValueError as e:
        return {"error": str(e)}
