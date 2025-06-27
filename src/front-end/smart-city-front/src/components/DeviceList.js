import React from 'react';
import DeviceStatus from './DeviceStatus'; 

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
          <strong>ID:</strong> {device.id} <br />
          <strong>Tipo:</strong> {device.type} <br />
          <strong>Status:</strong> {device.status} <br />
          <DeviceStatus device={device} onStatusChange={onStatusChange} />
        </li>
      ))}
    </ul>
  );
}
