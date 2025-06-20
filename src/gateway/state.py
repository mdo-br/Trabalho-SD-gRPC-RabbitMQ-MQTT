import threading

# Estado global dos dispositivos
connected_devices = {}
device_lock = threading.Lock()
