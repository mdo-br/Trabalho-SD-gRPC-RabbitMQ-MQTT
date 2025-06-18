import socket
import json
import threading
import random
from status import sensor_state
from power import power_on, power_off

# ---------- Configurações ----------
SENSOR_IP = "0.0.0.0"
SENSOR_PORT = 5005
SENSOR_ID = "1"

# ---------- Função para gerar dados ----------
def generate_sensor_data():
    return {
        "sensor_id": SENSOR_ID,
        "temperature": round(random.uniform(20, 30), 2),
        "humidity": round(random.uniform(40, 60), 2),
        "pressure": round(random.uniform(950, 1050), 2),
        "status": sensor_state["status"]
    }


# ---------- Processamento dos comandos ----------
def process_command(command):
    cmd = command.get("command")

    if cmd == "get_data":
        return generate_sensor_data()

    elif cmd == "get_status":
        return {
            "sensor_id": SENSOR_ID,
            "status": sensor_state["status"]
        }

    elif cmd == "power_off":
        power_off()
        return {"message": "Sensor desligado"}

    elif cmd == "power_on":
        power_on()
        return {"message": "Sensor ligado"}

    else:
        return {"error": "Comando desconhecido"}


# ---------- Servidor UDP ----------
def start_sensor_server():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((SENSOR_IP, SENSOR_PORT))

    print(f"Sensor {SENSOR_ID} ouvindo em {SENSOR_IP}:{SENSOR_PORT}...")

    while True:
        data, addr = sock.recvfrom(1024)
        print(f"\nRecebido de {addr}: {data.decode()}")

        try:
            command = json.loads(data.decode())
            response = process_command(command)
        except Exception as e:
            response = {"error": str(e)}

        resp_str = json.dumps(response).encode()
        sock.sendto(resp_str, addr)
        print(f"Resposta enviada para {addr}: {resp_str.decode()}")


# ---------- Inicialização ----------
if __name__ == "__main__":
    start_sensor_server()
