import React from 'react';
import Button from '@mui/material/Button';
import TextField from '@mui/material/TextField';
import axios from 'axios';

const IP = '192.168.3.83'; // ou substitua pelo IP real da API

export default function DeviceStatus({ device, onStatusChange, onIntervalChange }) {
  const [loading, setLoading] = React.useState(false);
  const [interval, setInterval] = React.useState('');
  const [sensorData, setSensorData] = React.useState(null);
  const [showDetails, setShowDetails] = React.useState(false);
  const [sensorState, setSensorState] = React.useState(device.status); // ACTIVE ou IDLE

  const fetchSensorData = async () => {
    try {
      const res = await axios.get(`http://${IP}:8000/device/data`, {
        params: { device_id: device.id },
      });

      console.log("Dados recebidos do sensor:", res.data); // DEBUG

      setSensorData(res.data);

      if (res.data.frequency_ms) {
        setInterval((res.data.frequency_ms / 1000).toString());
      }

      if (res.data.status) {
        setSensorState(res.data.status);
      }
    } catch (err) {
      console.error('Erro ao buscar dados do sensor', err);
    }
  };

  React.useEffect(() => {
    if (device.is_sensor) {
      fetchSensorData();
    }
  }, [device.id, device.is_sensor]);

  const toggleSensorState = async () => {
    setLoading(true);
    try {
      const newState = sensorState === 'ACTIVE' ? 'TURN_IDLE' : 'TURN_ACTIVE';
      await axios.put(`http://${IP}:8000/device/sensor/state`, null, {
        params: {
          device_id: device.id,
          state: newState,
        },
      });
      setSensorState(newState === 'TURN_ACTIVE' ? 'ACTIVE' : 'IDLE');
      onStatusChange(device.id, newState === 'TURN_ACTIVE' ? 'ACTIVE' : 'IDLE');
      await fetchSensorData(); // Atualiza dados após troca de estado
    } catch (err) {
      alert('Erro ao alterar estado do sensor.');
    } finally {
      setLoading(false);
    }
  };

  const updateFrequency = async () => {
    const freqMs = parseInt(interval, 10) * 1000;
    if (isNaN(freqMs) || freqMs < 1000 || freqMs > 60000) {
      alert('Intervalo inválido (deve estar entre 1 e 60 segundos)');
      return;
    }
    setLoading(true);
    try {
      await axios.put(`http://${IP}:8000/device/sensor/frequency`, null, {
        params: {
          device_id: device.id,
          frequency: freqMs,
        },
      });
      onIntervalChange(device.id, freqMs);
      setInterval((freqMs / 1000).toString());
      await fetchSensorData(); // Recarrega dados do sensor após mudança
    } catch (err) {
      console.error('Erro ao atualizar frequência:', err);
    } finally {
      setLoading(false);
    }
  };

  const toggleRelay = async () => {
    const newAction = device.status === 'ON' ? 'TURN_OFF' : 'TURN_ON';
    setLoading(true);
    try {
      await axios.put(`http://${IP}:8000/device/relay`, null, {
        params: {
          device_id: device.id,
          action: newAction,
        },
      });
      onStatusChange(device.id, newAction === 'TURN_ON' ? 'ON' : 'OFF');
    } catch (err) {
      alert('Erro ao enviar comando para a lâmpada.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      {device.type === 'RELAY' && (
        <Button
          variant="contained"
          color={device.status === 'ON' ? 'error' : 'success'}
          onClick={toggleRelay}
          disabled={loading}
          sx={{ mr: 2 }}
        >
          {loading ? 'Aguarde...' : device.status === 'ON' ? 'Desligar' : 'Ligar'}
        </Button>
      )}

      {device.is_sensor && (
        <>
          <div style={{ marginBottom: 8 }}>
            <TextField
              label="Intervalo (s)"
              type="number"
              value={interval}
              onChange={(e) => setInterval(e.target.value)}
              size="small"
              sx={{ width: 120, mr: 1 }}
              disabled={loading}
            />
            <Button
              variant="outlined"
              onClick={updateFrequency}
              disabled={loading || !interval}
              sx={{ mr: 2 }}
            >
              Atualizar Frequência
            </Button>

            <Button
              variant="contained"
              color={sensorState === 'ACTIVE' ? 'error' : 'success'}
              onClick={toggleSensorState}
              disabled={loading}
            >
              {loading
                ? 'Aguarde...'
                : sensorState === 'ACTIVE'
                ? 'Pausar Sensor'
                : 'Ativar Sensor'}
            </Button>
          </div>

          <Button variant="text" onClick={() => setShowDetails(!showDetails)}>
            {showDetails ? 'Esconder Detalhes' : 'Mostrar Detalhes'}
          </Button>

          {showDetails && sensorData && (
            <div style={{ marginTop: 10 }}>
              <div><strong>Temperatura:</strong> {sensorData.temperature?.toFixed(2)} °C</div>
              <div><strong>Umidade:</strong> {sensorData.humidity?.toFixed(2)} %</div>
              <div><strong>Frequência:</strong> {(sensorData.frequency_ms ? (sensorData.frequency_ms / 1000).toFixed(0) : 'N/A')} s</div>
              <div><strong>Estado:</strong> {sensorState}</div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
