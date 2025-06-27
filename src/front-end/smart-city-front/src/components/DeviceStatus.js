import axios from 'axios';
import React from 'react';
import Button from '@mui/material/Button';
import TextField from '@mui/material/TextField';

export default function DeviceStatus({ device, onStatusChange, onIntervalChange }) {
  const [loading, setLoading] = React.useState(false);
  const [interval, setInterval] = React.useState(device.sampling_interval?.toString() || '');
  const [showDetails, setShowDetails] = React.useState(false);
  const [sensorData, setSensorData] = React.useState(null);

  React.useEffect(() => {
    async function fetchSensorData() {
      try {
        const res = await axios.get('http://localhost:8000/device/data', {
          params: { device_id: device.id }
        });
        setSensorData({
          temperature: res.data.temperature,
          humidity: res.data.humidity,
          customConfigStatus: res.data.custom_config_status || '',
          status: res.data.status || '',
        });
      } catch (error) {
        console.error('Erro ao buscar dados sensoriais:', error);
        setSensorData(null);
      }
    }

    if (device.is_sensor || device.type === 'ALARM') {
      fetchSensorData();
    }
  }, [device.id, device.is_sensor, device.type]);

  const toggleStatus = async () => {
    const newStatus = device.status === 'ON' ? 'OFF' : 'ON';
    setLoading(true);
    try {
      await axios.put('http://localhost:8000/devices/config', null, {
        params: {
          device_id: device.id,
          new_status: newStatus
        }
      });
      onStatusChange(device.id, newStatus);
    } catch (error) {
      alert('Falha ao alterar status do dispositivo.');
    } finally {
      setLoading(false);
    }
  };

  const changeInterval = async () => {
    const newInterval = parseInt(interval, 10);
    if (isNaN(newInterval) || newInterval <= 0) {
      alert('Intervalo inválido');
      return;
    }
    setLoading(true);
    try {
      await axios.put('http://localhost:8000/devices/config', null, {
        params: {
          device_id: device.id,
          new_interval: newInterval
        }
      });
      onIntervalChange(device.id, newInterval);
    } catch (error) {

    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <Button
        variant="contained"
        color={device.status === 'ON' ? 'error' : 'success'}
        onClick={toggleStatus}
        disabled={loading}
        sx={{ mr: 2 }}
      >
        {loading ? 'Aguarde...' : (device.status === 'ON' ? 'Desligar' : 'Ligar')}
      </Button>

      {(device.is_sensor || device.type === 'ALARM') && (
        <>
          {device.is_sensor && (
            <>
              <TextField
                type="number"
                label="Intervalo (s)"
                value={interval}
                onChange={(e) => setInterval(e.target.value)}
                variant="outlined"
                size="small"
                sx={{ width: 120, mr: 1 }}
              />
              <Button
                variant="outlined"
                onClick={changeInterval}
                disabled={loading || !interval}
                sx={{ mr: 2 }}
              >
                Atualizar
              </Button>
            </>
          )}

          <Button
            variant="text"
            onClick={() => setShowDetails(!showDetails)}
          >
            {showDetails ? 'Esconder Detalhes' : 'Mostrar Detalhes'}
          </Button>

          {showDetails && sensorData && (
            <div style={{ marginTop: 12 }}>
              {device.type === 'TEMPERATURE_SENSOR' && (
                <>
                  <div><strong>Temperatura:</strong> {sensorData.temperature.toFixed(2)} °C</div>
                  <div><strong>Umidade:</strong> {sensorData.humidity.toFixed(2)} %</div>
                </>
              )}

              {device.type === 'ALARM' && device.status === 'ON' && (
                <div style={{ color: 'red', fontWeight: 'bold' }}>
                  Som do alarme: BEEP, BEEP, BEEP...
                </div>
              )}

            </div>
          )}
        </>
      )}
    </div>
  );
}
