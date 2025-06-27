import React from 'react';

export default function DeviceDetails({ sensorData, device }) {
  if (!device) return null;

  return (
    <div style={{ border: '1px solid #ccc', padding: 10, marginTop: 10 }}>
      <p><strong>ID:</strong> {device.id}</p>
      <p><strong>Tipo:</strong> {device.type || 'Desconhecido'}</p>
      <p><strong>Status:</strong> {device.status || 'Desconhecido'}</p>

      {device.is_sensor && sensorData && (
        <>
          {sensorData.temperature !== undefined && (
            <p><strong>Temperatura:</strong> {sensorData.temperature.toFixed(2)} °C</p>
          )}
          {sensorData.humidity !== undefined && (
            <p><strong>Umidade:</strong> {sensorData.humidity.toFixed(2)} %</p>
          )}
          {/* Coloque outros dados sensoriais aqui */}
        </>
      )}

      {!sensorData && <p>Sem dados sensoriais disponíveis.</p>}
    </div>
  );
}
