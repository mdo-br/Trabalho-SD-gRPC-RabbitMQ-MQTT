from status import sensor_state

# ---------- Função para ligar/desligar sensor ----------
def power_on():
    sensor_state["status"] = "ativo"
    return {"message": "Sensor ligado"}

def power_off():
    sensor_state["status"] = "inativo"
    return {"message": "Sensor desligado"}  