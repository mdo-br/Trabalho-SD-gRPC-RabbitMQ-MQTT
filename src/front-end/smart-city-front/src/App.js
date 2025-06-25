import React, {useEffect, useState} from "react";
import {Container, Typography} from "@mui/material";
import DeviceCard from "./components/DeviceCard";

function App() {
  const [devices, setDevices] = useState([]);

  useEffect(() => {
    fetch("http://localhost:8000/devices/info")
      .then((res) => res.json())
      .then((data) => {
        const adaptado = Object.values(data).map((dev) => ({
          id: dev.id,
          name: dev.type,
          status: dev.status === "ACTIVE" ? "Ativo" : "Inativo",
          config: dev.sensor_data?.capture_interval || "",
        }));
        setDevices(adaptado);
      })
      .catch((err) => {
        console.error("Erro ao buscar dispositivos:", err);
      });
  }, []);

  const toggleDevice = (id) => {
    const device = devices.find((d) => d.id === id);
    const novoStatus = device.status === "Ativo" ? "OFF" : "ACTIVE";

    fetch(`http://localhost:8000/device/change-status?device_id=${id}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ new_status: novoStatus }),
    })
      .then((res) => {
        if (!res.ok) throw new Error("Erro ao mudar status");
        setDevices(devices.map((dev) =>
          dev.id === id
            ? { ...dev, status: dev.status === "Ativo" ? "Inativo" : "Ativo" }
            : dev
        ));
      })
      .catch((err) => console.error("Erro ao enviar comando:", err));
  };

  const updateConfig = (id, newValue) => {
    fetch(`http://localhost:8000/device/change-capture-speed?device_id=${id}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ interval_seconds: parseFloat(newValue) }),
    })
      .then((res) => {
        if (!res.ok) throw new Error("Erro ao atualizar configuração");
        setDevices(devices.map((dev) =>
          dev.id === id ? { ...dev, config: newValue } : dev
        ));
      })
      .catch((err) => console.error("Erro ao atualizar configuração:", err));
  };

  return (
    <Container maxWidth="md" sx={{ mt: 4 }}>
      <Typography variant="h4" gutterBottom>
        Dispositivos Conectados
      </Typography>

      {devices.length === 0 ? (
        <Typography variant="body1">Nenhum dispositivo conectado.</Typography>
      ) : (
        devices.map((device) => (
          <DeviceCard
            key={device.id}
            device={device}
            onToggle={toggleDevice}
            onConfigChange={updateConfig}
          />
        ))
      )}
    </Container>
  );
}

export default App;
