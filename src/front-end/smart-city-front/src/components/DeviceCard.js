import React from "react";
import {
  Card,
  CardContent,
  Typography,
  Button,
  Slider,
  TextField,
  Box,
} from "@mui/material";

const DeviceCard = ({ device, onToggle, onConfigChange }) => {
  return (
    <Card sx={{ marginBottom: 2, boxShadow: 2 }}>
      <CardContent>
        <Typography variant="h6">{device.name} ({device.type})</Typography>
        <Typography variant="body2" color="text.secondary" sx={{ marginBottom: 1 }}>
          Status: <strong>{device.status}</strong>
        </Typography>

        <Button
          variant={device.status === "Ativo" ? "contained" : "outlined"}
          color={device.status === "Ativo" ? "error" : "primary"}
          onClick={() => onToggle(device.id)}
        >
          {device.status === "Ativo" ? "Desligar" : "Ligar"}
        </Button>

        {device.type === "Temperatura" && (
          <Box mt={2}>
            <TextField
              label="Temperatura (°C)"
              type="number"
              value={device.config}
              onChange={(e) => onConfigChange(device.id, parseInt(e.target.value))}
              fullWidth
            />
          </Box>
        )}

        {device.type === "Iluminação" && (
          <Box mt={2}>
            <Typography gutterBottom>Intensidade</Typography>
            <Slider
              value={device.config}
              onChange={(e, val) => onConfigChange(device.id, val)}
              step={1}
              min={0}
              max={100}
              valueLabelDisplay="auto"
            />
          </Box>
        )}
      </CardContent>
    </Card>
  );
};

export default DeviceCard;
