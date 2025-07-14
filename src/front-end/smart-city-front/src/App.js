import React from 'react';
import axios from 'axios';
import DevicesList from './components/DeviceList';

const IP = '192.168.3.121'

export default function App() {
  const [devices, setDevices] = React.useState([]);

  React.useEffect(() => {
    fetchDevices();
  }, []);

  async function fetchDevices() {
    try {
      const response = await axios.get(`http://${IP}:8000/devices`);
      setDevices(response.data);
    } catch (error) {
      console.error('Erro ao buscar dispositivos:', error);
      alert('Erro ao buscar dispositivos.');
    }
  }

  const handleStatusChange = (deviceId, newStatus) => {
    setDevices(prevDevices =>
      prevDevices.map(d =>
        d.id === deviceId ? { ...d, status: newStatus } : d
      )
    );
  };

  return (
    <div style={{ maxWidth: 600, margin: '20px auto', fontFamily: 'Arial, sans-serif' }}>
      <h1>Smart City - Dispositivos Conectados</h1>
      <DevicesList devices={devices} onStatusChange={handleStatusChange} />
    </div>
  );
}
