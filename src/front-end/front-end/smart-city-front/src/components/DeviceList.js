import React from 'react';
import DeviceStatus from './DeviceStatus';

function getFriendlyName(device) {
  const relayMap = {
    "relay_board_001001001": "Lâmpada 1",
    "relay_board_001001002": "Lâmpada 2",
  };
  const sensorMap = {
    "temp_board_001001002": "Sensor 1",
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
      return type;}
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
      return status;}
}


export default function DevicesList({ devices, onStatusChange }) {
  if (!devices.length) return <p>Nenhum dispositivo conectado.</p>;

  return (
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
          <strong>Tipo:</strong> {getFriendlyType(device.type)} <br />
          <strong>Status:</strong> {getFriendlyStatus(device.status)} <br />
          <DeviceStatus device={device} onStatusChange={onStatusChange} />
        </li>
      ))}
    </ul>
  );
}
