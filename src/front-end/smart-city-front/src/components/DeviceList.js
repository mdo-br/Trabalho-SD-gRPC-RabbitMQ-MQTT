import React from 'react';
import DeviceStatus from './DeviceStatus';
import Button from '@mui/material/Button';

function getFriendlyName(device) {
  const relayMap = {
    "relay_board_001001001": "Lâmpada 1",
    "relay_board_001001002": "Lâmpada 2",
  };

  const sensorMap = {
    "temp_board_001001001": "Sensor 1",
    "temp_board_001001002": "Sensor 2",
    "temp_java_001": "Sensor 3",
    "temp_sensor_esp_001": "Sensor ESP 1",
    "temp_sensor_esp_002": "Sensor ESP 2",
    "sensor_java_test_001": "Sensor Java",
  };

  if (device.type === "RELAY") {
    return relayMap[device.id] || "Lâmpada";
  }

  if (device.type === "TEMPERATURE_SENSOR") {
    return sensorMap[device.id] || "Sensor";
  }

  return device.id;
}

function getFriendlyType(type) {
  switch (type) {
    case "RELAY":
      return "Atuador";
    case "TEMPERATURE_SENSOR":
      return "Sensor";
    default:
      return type;
  }
}

function getFriendlyStatus(status) {
  switch (status) {
    case "ON":
      return "Ligado";
    case "OFF":
      return "Desligado";
    case "ACTIVE":
      return "Ativo";
    case "IDLE":
      return "Pausado";
    default:
      return status;
  }
}

function getDeviceOrigin(device) {
  if (device.id.includes("java")) {
    return "Simulado";
  }
  if (device.id.includes("esp")) {
    return "Real";
  }
  return "";
}

export default function DevicesList({ devices, onStatusChange }) {
  if (!devices.length) return <p>Nenhum dispositivo conectado.</p>;

  const handleTurnOnAll = () => {
    devices
      .filter(device => device.type === "RELAY" && device.status !== "ON" && device._toggleRelay)
      .forEach(device => device._toggleRelay());
  };

  const handleTurnOffAll = () => {
    devices
      .filter(device => device.type === "RELAY" && device.status !== "OFF" && device._toggleRelay)
      .forEach(device => device._toggleRelay());
  };

  return (
    <div>
      <div style={{ marginBottom: 16 }}>
        <Button
          variant="contained"
          color="success"
          onClick={handleTurnOnAll}
          sx={{ marginRight: 2 }}
        >
          Ligar Todas as Lâmpadas
        </Button>

        <Button
          variant="contained"
          color="error"
          onClick={handleTurnOffAll}
        >
          Desligar Todas as Lâmpadas
        </Button>
      </div>

      <ul style={{ listStyleType: 'none', padding: 0 }}>
        {devices.map(device => (
          <li key={device.id} style={{
            backgroundColor: '#f0f0f0',
            marginBottom: 8,
            padding: 12,
            borderRadius: 6,
            boxShadow: '0 1px 3px rgba(0,0,0,0.1)'
          }}>
            <strong>Dispositivo:</strong> {getFriendlyName(device)} <br />
            <strong>Tipo:</strong> {getFriendlyType(device.type)} {getDeviceOrigin(device) && `(${getDeviceOrigin(device)})`} <br />
            <strong>Status:</strong> {getFriendlyStatus(device.status)} <br />
            <DeviceStatus device={device} onStatusChange={onStatusChange} />
          </li>
        ))}
      </ul>
    </div>
  );
}
