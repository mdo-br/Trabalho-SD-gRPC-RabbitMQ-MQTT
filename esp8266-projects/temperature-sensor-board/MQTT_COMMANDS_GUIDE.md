# ESP8266 MQTT Commands Implementation Guide

## Overview
This guide shows how to implement **full MQTT communication** for ESP8266 sensors, including both data publishing and command reception. The ESP8266 V3 implementation eliminates TCP communication entirely for sensors.

## Architecture Evolution

### V1 (Original): TCP/UDP
- **Data**: ESP8266 → UDP → Gateway
- **Commands**: Gateway → TCP → ESP8266
- **Discovery**: UDP multicast

### V2 (Hybrid): MQTT + TCP
- **Data**: ESP8266 → MQTT → Gateway
- **Commands**: Gateway → TCP → ESP8266
- **Discovery**: UDP multicast

### V3 (Full MQTT): MQTT Only
- **Data**: ESP8266 → MQTT → Gateway
- **Commands**: Gateway → MQTT → ESP8266
- **Discovery**: UDP multicast (kept for initial discovery)
- **Registration**: TCP (kept for compatibility)

## Implementation Ready

The complete ESP8266 V3 implementation is provided in:
```
esp8266-projects/temperature-sensor-board/temperature-sensor-board-v3.ino
```

## Key Features

### 1. **Complete MQTT Integration**
- Data publishing via MQTT
- Command reception via MQTT
- Response publishing via MQTT
- JSON message format for easy parsing

### 2. **Required Libraries**
```cpp
#include <PubSubClient.h>    // MQTT client library
#include <ArduinoJson.h>     // JSON parsing for commands
#include <ESP8266WiFi.h>     // WiFi connectivity
#include <DHT.h>             // Temperature sensor
```

### 3. **MQTT Topics Structure**
```cpp
// Data publishing
String dataTopic = "smart_city/sensors/temp_sensor_esp_v3_001";

// Command reception
String commandTopic = "smart_city/commands/sensors/temp_sensor_esp_v3_001";

// Response publishing
String responseTopic = "smart_city/commands/sensors/temp_sensor_esp_v3_001/response";
```

### 4. **Supported Commands**
- `TURN_ON`/`TURN_ACTIVE`: Activate sensor data collection
- `TURN_OFF`/`TURN_IDLE`: Stop sensor data collection
- `SET_FREQ`: Change data collection frequency (in milliseconds)
- `GET_STATUS`: Query current sensor status

### 5. **Command Format (JSON)**
```json
{
  "command_type": "TURN_ON",
  "command_value": "",
  "request_id": "unique_request_id",
  "timestamp": 1640995200000
}
```

### 6. **Response Format (JSON)**
```json
{
  "device_id": "temp_sensor_esp_v3_001",
  "request_id": "unique_request_id",
  "success": true,
  "message": "Sensor activated",
  "status": "ACTIVE",
  "frequency_ms": 5000,
  "temperature": 25.3,
  "humidity": 60.2,
  "timestamp": 1640995200000
}
```

## Hardware Requirements

### Basic Setup
- **ESP8266** (NodeMCU, Wemos D1 Mini, etc.)
- **DHT11 Temperature/Humidity Sensor**
- **Breadboard and jumper wires**

### Connections
```
ESP8266 (NodeMCU)    DHT11
==================   =====
3.3V                 VCC
GND                  GND
D3                   DATA
```

## Software Requirements

### Arduino IDE Libraries
Install these libraries via Library Manager:
```
1. PubSubClient (by Nick O'Leary)
2. ArduinoJson (by Benoit Blanchon)
3. DHT sensor library (by Adafruit)
4. ESP8266WiFi (built-in)
```

### PlatformIO Dependencies
Add to `platformio.ini`:
```ini
[env:nodemcuv2]
platform = espressif8266
board = nodemcuv2
framework = arduino
lib_deps = 
    knolleary/PubSubClient@^2.8
    bblanchon/ArduinoJson@^6.19.4
    adafruit/DHT sensor library@^1.4.3
    adafruit/Adafruit Unified Sensor@^1.1.7
```

## Configuration

### WiFi Settings
```cpp
const char* ssid = "YOUR_WIFI_SSID";
const char* password = "YOUR_WIFI_PASSWORD";
```

### MQTT Settings
```cpp
const char* mqtt_server = "192.168.3.129";  // RabbitMQ broker IP
const int mqtt_port = 1883;
const char* device_id = "temp_sensor_esp_v3_001";  // Unique device ID
```

### Device ID Convention
Use unique device IDs to avoid conflicts:
- `temp_sensor_esp_v3_001`
- `temp_sensor_esp_v3_002`
- `temp_sensor_esp_v3_kitchen`
- `temp_sensor_esp_v3_bedroom`

## Key Implementation Details

### 1. **MQTT Client Setup**
```cpp
WiFiClient wifiClient;
PubSubClient mqttClient(wifiClient);

void setup() {
    // ... WiFi connection ...
    
    mqttClient.setServer(mqtt_server, mqtt_port);
    mqttClient.setCallback(onMqttMessage);
    connectToMQTT();
}
```

### 2. **Command Processing**
```cpp
void onMqttMessage(char* topic, byte* payload, unsigned int length) {
    String message = "";
    for (int i = 0; i < length; i++) {
        message += (char)payload[i];
    }
    
    if (String(topic) == commandTopic) {
        processCommand(message);
    }
}
```

### 3. **Auto-Discovery Integration**
The ESP8266 still uses UDP multicast for initial gateway discovery and TCP for registration, but indicates MQTT V3 capability:
```cpp
// In registration message
message.device_info.capabilities[0].key = "communication";
message.device_info.capabilities[0].value = "mqtt_v3";
```

### 4. **Data Publishing**
```cpp
void sendSensorDataMQTT() {
    StaticJsonDocument<300> doc;
    doc["device_id"] = device_id;
    doc["temperature"] = lastTemperature;
    doc["humidity"] = lastHumidity;
    doc["status"] = getStatusString();
    doc["frequency_ms"] = captureIntervalMs;
    doc["timestamp"] = millis();
    doc["version"] = "mqtt_v3";
    
    String jsonString;
    serializeJson(doc, jsonString);
    
    mqttClient.publish(dataTopic.c_str(), jsonString.c_str());
}
```

## Testing

### 1. **Upload Code**
1. Configure WiFi credentials
2. Set unique device ID
3. Upload to ESP8266
4. Monitor Serial output

### 2. **Test Commands**
```bash
# Test with Python script
python3 test_esp8266_mqtt_commands.py temp_sensor_esp_v3_001

# Test with mosquitto
mosquitto_pub -h 192.168.3.129 -t "smart_city/commands/sensors/temp_sensor_esp_v3_001" \
  -m '{"command_type":"TURN_ON","request_id":"test123","timestamp":1640995200000}'
```

### 3. **Monitor Data**
```bash
# Monitor sensor data
mosquitto_sub -h 192.168.3.129 -t "smart_city/sensors/+"

# Monitor command responses
mosquitto_sub -h 192.168.3.129 -t "smart_city/commands/sensors/+/response"
```

## Advantages of ESP8266 MQTT V3

### 1. **Unified Communication**
- All sensor communication via MQTT
- No TCP connections required
- Consistent protocol across all operations

### 2. **Reliability**
- MQTT QoS levels ensure message delivery
- Automatic reconnection on network issues
- Built-in keep-alive mechanism

### 3. **Scalability**
- Easy to add multiple sensors
- Efficient publish/subscribe model
- Minimal network overhead

### 4. **Real-time Responses**
- Immediate command acknowledgment
- Status updates with sensor data
- Correlation via request IDs

### 5. **ESP8266 Friendly**
- Native MQTT support
- Low memory footprint
- Efficient JSON parsing

## Troubleshooting

### Common Issues

#### 1. **WiFi Connection**
```cpp
// Add connection status check
if (WiFi.status() != WL_CONNECTED) {
    Serial.println("WiFi disconnected, reconnecting...");
    WiFi.begin(ssid, password);
}
```

#### 2. **MQTT Connection**
```cpp
// Check MQTT connection in loop
if (!mqttClient.connected()) {
    connectToMQTT();
}
mqttClient.loop();  // Process MQTT messages
```

#### 3. **JSON Memory Issues**
```cpp
// Use StaticJsonDocument for known size
StaticJsonDocument<400> doc;  // Adjust size as needed

// Or use DynamicJsonDocument for variable size
DynamicJsonDocument doc(1024);
```

#### 4. **Sensor Reading Issues**
```cpp
// Add sensor validation
float temperature = dht.readTemperature();
float humidity = dht.readHumidity();

if (isnan(temperature) || isnan(humidity)) {
    Serial.println("Failed to read from DHT sensor!");
    return;
}
```

### Serial Monitor Debug
Look for these messages:
```
✅ WiFi connected!
✅ MQTT connected!
✅ Subscribed to command topic
✅ Gateway found and registered
✅ Sensor data sent
✅ Command received and processed
```

## Integration with Gateway V3

The ESP8266 V3 automatically integrates with Gateway V3:

1. **Discovery**: ESP8266 finds gateway via UDP multicast
2. **Registration**: ESP8266 registers with MQTT V3 capabilities
3. **Detection**: Gateway detects MQTT V3 support
4. **Commands**: Gateway sends commands via MQTT instead of TCP

## Performance Considerations

### 1. **Memory Management**
- Use StaticJsonDocument for fixed-size messages
- Limit string buffer sizes
- Clean up unused variables

### 2. **Network Efficiency**
- Use appropriate QoS levels (0 for data, 1 for commands)
- Implement reasonable data publishing intervals
- Avoid excessive debug output

### 3. **Power Optimization**
- Use deep sleep between readings (if battery powered)
- Implement WiFi power management
- Optimize sensor reading frequency

## Migration from V2 to V3

### For Existing V2 ESP8266 Sensors:
1. Update code to V3 version
2. Add ArduinoJson library
3. Update device ID to V3 format
4. Test command functionality
5. Deploy gradually

### Compatibility:
- Gateway V3 supports both V2 and V3 sensors
- V2 sensors continue working with TCP commands
- V3 sensors use MQTT commands exclusively

## Conclusion

The ESP8266 MQTT V3 implementation provides a complete, unified communication solution for smart city sensors. The combination of MQTT's reliability, ESP8266's native support, and JSON's simplicity creates an efficient and scalable sensor platform.

### Next Steps:
1. Deploy ESP8266 V3 firmware
2. Test with multiple sensors
3. Monitor performance metrics
4. Consider additional sensor types
5. Implement advanced features (OTA updates, configuration management)

This implementation represents the evolution from mixed protocols to a unified, modern IoT communication architecture.
