package com.smartcity.sensors;

// Update the import to the correct package where SmartCity is defined
import smartcity.devices.SmartCity;
import org.eclipse.paho.client.mqttv3.*;
import org.eclipse.paho.client.mqttv3.persist.MemoryPersistence;
import com.google.gson.Gson;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import com.google.protobuf.InvalidProtocolBufferException;

import java.io.IOException;
import java.io.OutputStream;
import java.net.*;
import java.util.Random;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;
import java.util.logging.Level;
import java.util.logging.Logger;
// import actuator.ActuatorService;
// import actuator.AtuadorServiceGrpc;
import java.util.Arrays;

public class TemperatureHumiditySensor {

    private static final Logger LOGGER = Logger.getLogger(TemperatureHumiditySensor.class.getName());

    // --- Configurações de Comunicação ---
    private static final String MULTICAST_GROUP = "224.1.1.1";
    private static final int MULTICAST_PORT = 5007;
    
    // --- Configurações MQTT ---
    private static final String MQTT_TOPIC_PREFIX = "smart_city/sensors/";
    private static final String MQTT_COMMAND_TOPIC_PREFIX = "smart_city/commands/sensors/";
    private static final int MQTT_QOS = 0;
    private static final int MQTT_COMMAND_QOS = 1; // QoS 1 para garantir entrega de comandos
    
    private int captureIntervalSeconds = 5;
    private String deviceId;
    private SmartCity.DeviceStatus currentStatus;
    private String gatewayIp;
    private int gatewayTcpPort;
    private int tcpPort = 6001; // Mantido apenas para registro inicial
    private String mqttBrokerIp = null;
    private int mqttBrokerPort = 1883; // valor padrão
    
    // MQTT
    private MqttClient mqttClient;
    private String mqttDataTopic;
    private String mqttCommandTopic;
    private String mqttResponseTopic;
    private Gson gson = new Gson();
    // Usar método estático para parse
    
    // Threads e dados
    private ScheduledExecutorService scheduler;
    private Random random = new Random();
    private double ultimaTemperatura = 0.0;
    private double ultimaUmidade = 0.0;

    public TemperatureHumiditySensor(String deviceId) {
        this.deviceId = deviceId;
        this.currentStatus = SmartCity.DeviceStatus.ACTIVE;
        this.mqttDataTopic = MQTT_TOPIC_PREFIX + deviceId;
        this.mqttCommandTopic = MQTT_COMMAND_TOPIC_PREFIX + deviceId;
        this.mqttResponseTopic = MQTT_COMMAND_TOPIC_PREFIX + deviceId + "/response";
        
        LOGGER.info("Sensor MQTT criado: " + deviceId);
        LOGGER.info("Tópico dados: " + mqttDataTopic);
        LOGGER.info("Tópico comandos: " + mqttCommandTopic);
        LOGGER.info("Tópico respostas: " + mqttResponseTopic);
    }

    public void start() {
        try {
            // 1. Descobrir Gateway via multicast
            discoverGateway();
            
            // 2. Conectar ao MQTT
            connectToMQTT();
            
            // 3. Registrar no Gateway (ainda via TCP para compatibilidade)
            registerWithGateway();
            
            // 4. Iniciar coleta de dados
            startSensorDataScheduler();
            
            LOGGER.info("Sensor MQTT " + deviceId + " iniciado com sucesso!");
            
        } catch (Exception e) {
            LOGGER.log(Level.SEVERE, "Erro ao iniciar sensor " + deviceId + ": " + e.getMessage(), e);
        }
    }

    private void discoverGateway() throws IOException {
        LOGGER.info("Sensor " + deviceId + " procurando Gateway via multicast...");
        
        try (MulticastSocket socket = new MulticastSocket(MULTICAST_PORT)) {
            InetAddress group = InetAddress.getByName(MULTICAST_GROUP);
            socket.joinGroup(new InetSocketAddress(group, 0), NetworkInterface.getByInetAddress(InetAddress.getLocalHost()));
            
            byte[] buffer = new byte[1024];
            DatagramPacket packet = new DatagramPacket(buffer, buffer.length);
            
            socket.receive(packet);
            
            // Parse da mensagem protobuf
            SmartCity.SmartCityMessage envelope = SmartCity.SmartCityMessage.parseFrom(Arrays.copyOfRange(packet.getData(), 0, packet.getLength()));
            
            if (envelope.hasDiscoveryRequest()) {
                SmartCity.DiscoveryRequest discoveryRequest = envelope.getDiscoveryRequest();
                gatewayIp = discoveryRequest.getGatewayIp();
                gatewayTcpPort = discoveryRequest.getGatewayTcpPort();
                if (!discoveryRequest.getMqttBrokerIp().isEmpty()) {
                    mqttBrokerIp = discoveryRequest.getMqttBrokerIp();
                }
                if (discoveryRequest.getMqttBrokerPort() != 0) {
                    mqttBrokerPort = discoveryRequest.getMqttBrokerPort();
                }
                
                LOGGER.info("Sensor " + deviceId + " encontrou Gateway: " + gatewayIp + ":" + gatewayTcpPort);
                LOGGER.info("Sensor " + deviceId + " encontrou MQTT broker: " + mqttBrokerIp + ":" + mqttBrokerPort);
            }
            
            socket.leaveGroup(new InetSocketAddress(group, 0), NetworkInterface.getByInetAddress(InetAddress.getLocalHost()));
        }
    }

    private void connectToMQTT() {
        try {
            String broker = "tcp://" + (mqttBrokerIp != null ? mqttBrokerIp : "localhost") + ":" + mqttBrokerPort;
            mqttClient = new MqttClient(broker, deviceId + "_v3", new MemoryPersistence());
            
            MqttConnectOptions options = new MqttConnectOptions();
            options.setAutomaticReconnect(true);
            options.setCleanSession(true);
            options.setConnectionTimeout(10);
            options.setKeepAliveInterval(30);
            options.setUserName("smartcity");
            options.setPassword("smartcity123".toCharArray());
            
            // Configurar callback para receber comandos
            mqttClient.setCallback(new MqttCallback() {
                @Override
                public void connectionLost(Throwable cause) {
                    LOGGER.log(Level.WARNING, "Conexão MQTT perdida para sensor " + deviceId, cause);
                }

                @Override
                public void messageArrived(String topic, MqttMessage message) throws Exception {
                    handleMqttCommand(topic, message);
                }

                @Override
                public void deliveryComplete(IMqttDeliveryToken token) {
                    // Não usado para este sensor
                }
            });
            
            mqttClient.connect(options);
            LOGGER.info("Sensor " + deviceId + " conectado ao MQTT broker: " + broker);
            
            // Inscrever-se no tópico de comandos
            mqttClient.subscribe(mqttCommandTopic, MQTT_COMMAND_QOS);
            LOGGER.info("Sensor " + deviceId + " inscrito no tópico de comandos: " + mqttCommandTopic);
            
        } catch (Exception e) {
            LOGGER.log(Level.SEVERE, "Erro ao conectar MQTT para sensor " + deviceId + ": " + e.getMessage(), e);
        }
    }

    private void handleMqttCommand(String topic, MqttMessage message) {
        try {
            String payload = new String(message.getPayload());
            LOGGER.info("Sensor " + deviceId + " recebeu comando MQTT: " + payload);
            
            // Parse do comando JSON
            JsonObject commandJson = JsonParser.parseString(payload).getAsJsonObject();
            String commandType = commandJson.get("command_type").getAsString();
            String commandValue = commandJson.has("command_value") ? commandJson.get("command_value").getAsString() : "";
            String requestId = commandJson.has("request_id") ? commandJson.get("request_id").getAsString() : "";
            
            // Processar comando
            SmartCity.DeviceStatus newStatus = currentStatus;
            String responseMessage = "";
            boolean success = true;
            
            switch (commandType) {
                case "TURN_OFF":
                case "TURN_IDLE":
                    newStatus = SmartCity.DeviceStatus.IDLE;
                    responseMessage = "Sensor em modo IDLE";
                    if (scheduler != null && !scheduler.isShutdown()) {
                        scheduler.shutdownNow();
                    }
                    break;
                    
                case "TURN_ON":
                case "TURN_ACTIVE":
                    newStatus = SmartCity.DeviceStatus.ACTIVE;
                    responseMessage = "Sensor em modo ACTIVE";
                    startSensorDataScheduler();
                    break;
                    
                case "SET_FREQ":
                    try {
                        int newFreqMs = Integer.parseInt(commandValue);
                        captureIntervalSeconds = newFreqMs / 1000;
                        responseMessage = "Frequência alterada para " + captureIntervalSeconds + " segundos";
                        if (currentStatus == SmartCity.DeviceStatus.ACTIVE) {
                            startSensorDataScheduler();
                        }
                    } catch (NumberFormatException e) {
                        success = false;
                        responseMessage = "Valor de frequência inválido: " + commandValue;
                    }
                    break;
                    
                case "GET_STATUS":
                    responseMessage = "Status atual: " + currentStatus.name();
                    break;
                    
                default:
                    success = false;
                    responseMessage = "Comando não reconhecido: " + commandType;
            }
            
            currentStatus = newStatus;
            
            // Enviar resposta via MQTT
            sendMqttResponse(requestId, success, responseMessage);
            
        } catch (Exception e) {
            LOGGER.log(Level.WARNING, "Erro ao processar comando MQTT: " + e.getMessage(), e);
            try {
                sendMqttResponse("", false, "Erro interno: " + e.getMessage());
            } catch (Exception ex) {
                LOGGER.log(Level.SEVERE, "Erro ao enviar resposta de erro: " + ex.getMessage(), ex);
            }
        }
    }

    private void sendMqttResponse(String requestId, boolean success, String message) throws MqttException {
        JsonObject response = new JsonObject();
        response.addProperty("device_id", deviceId);
        response.addProperty("request_id", requestId);
        response.addProperty("success", success);
        response.addProperty("message", message);
        response.addProperty("status", currentStatus.name());
        response.addProperty("frequency_ms", captureIntervalSeconds * 1000);
        response.addProperty("timestamp", System.currentTimeMillis());
        
        // Adicionar dados atuais se disponíveis
        if (ultimaTemperatura > 0 && ultimaUmidade > 0) {
            response.addProperty("temperature", ultimaTemperatura);
            response.addProperty("humidity", ultimaUmidade);
        }
        
        String jsonResponse = gson.toJson(response);
        
        if (mqttClient.isConnected()) {
            MqttMessage mqttMessage = new MqttMessage(jsonResponse.getBytes());
            mqttMessage.setQos(MQTT_COMMAND_QOS);
            mqttClient.publish(mqttResponseTopic, mqttMessage);
            
            LOGGER.info("Resposta MQTT enviada para " + mqttResponseTopic + ": " + jsonResponse);
        }
    }

    private void registerWithGateway() {
        if (gatewayIp == null || gatewayTcpPort == 0) {
            LOGGER.warning("Gateway não encontrado, não é possível registrar sensor " + deviceId);
            return;
        }
        
        sendDeviceInfo(gatewayIp, gatewayTcpPort);
    }

    private void sendDeviceInfo(String gatewayHost, int gatewayPort) {
        try (Socket socket = new Socket(gatewayHost, gatewayPort)) {
            OutputStream output = socket.getOutputStream();
            SmartCity.DeviceInfo deviceInfo = SmartCity.DeviceInfo.newBuilder()
                    .setDeviceId(deviceId)
                    .setType(SmartCity.DeviceType.TEMPERATURE_SENSOR)
                    .setIpAddress(getLocalIpAddress())
                    .setPort(tcpPort) // Ainda reporta porta TCP para compatibilidade
                    .setInitialState(currentStatus)
                    .setIsActuator(false)
                    .setIsSensor(true)
                    .putCapabilities("communication", "mqtt") // Indica comunicação MQTT
                    .putCapabilities("command_topic", mqttCommandTopic)
                    .putCapabilities("response_topic", mqttResponseTopic)
                    .build();
            SmartCity.SmartCityMessage envelope = SmartCity.SmartCityMessage.newBuilder()
                    .setMessageType(SmartCity.MessageType.DEVICE_INFO)
                    .setDeviceInfo(deviceInfo)
                    .build();
            envelope.writeDelimitedTo(output);
            output.flush();
            LOGGER.info("Sensor " + deviceId + " enviou DeviceInfo MQTT V3 para Gateway " + gatewayHost + ":" + gatewayPort);
        } catch (IOException e) {
            LOGGER.log(Level.WARNING, "Erro ao enviar DeviceInfo para Gateway: " + e.getMessage(), e);
        }
    }

    private void startSensorDataScheduler() {
        if (scheduler != null && !scheduler.isShutdown()) {
            scheduler.shutdownNow();
        }
        scheduler = Executors.newSingleThreadScheduledExecutor();
        scheduler.scheduleAtFixedRate(this::sendSensorDataMQTT, 0, captureIntervalSeconds, TimeUnit.SECONDS);
        LOGGER.info("Envio periódico MQTT do sensor " + deviceId + " agendado a cada " + captureIntervalSeconds + " segundos.");
    }

    private void sendSensorDataMQTT() {
        if (currentStatus != SmartCity.DeviceStatus.ACTIVE) {
            return; // Não envia se não estiver ativo
        }

        try {
            // Simular leitura de sensor
            double temperature = 20.0 + (random.nextDouble() * 15.0); // 20-35°C
            double humidity = 40.0 + (random.nextDouble() * 40.0);    // 40-80%
            
            // Atualizar valores internos
            ultimaTemperatura = temperature;
            ultimaUmidade = humidity;

            // Criar dados JSON para MQTT
            JsonObject jsonData = new JsonObject();
            jsonData.addProperty("device_id", deviceId);
            jsonData.addProperty("temperature", temperature);
            jsonData.addProperty("humidity", humidity);
            jsonData.addProperty("status", currentStatus.name());
            jsonData.addProperty("frequency_ms", captureIntervalSeconds * 1000);
            jsonData.addProperty("timestamp", System.currentTimeMillis());
            jsonData.addProperty("version", "mqtt");

            String jsonPayload = gson.toJson(jsonData);
            
            // Publicar no MQTT
            if (mqttClient.isConnected()) {
                MqttMessage message = new MqttMessage(jsonPayload.getBytes());
                message.setQos(MQTT_QOS);
                mqttClient.publish(mqttDataTopic, message);
                
                LOGGER.info("Dados MQTT enviados para " + mqttDataTopic + ": Temp=" + 
                           String.format("%.1f", temperature) + "°C, Hum=" + 
                           String.format("%.1f", humidity) + "%");
            } else {
                LOGGER.warning("Cliente MQTT desconectado, não foi possível enviar dados do sensor " + deviceId);
            }
            
        } catch (Exception e) {
            LOGGER.log(Level.WARNING, "Erro ao enviar dados MQTT do sensor " + deviceId + ": " + e.getMessage(), e);
        }
    }

    private String getLocalIpAddress() {
        try {
            for (NetworkInterface networkInterface : java.util.Collections.list(NetworkInterface.getNetworkInterfaces())) {
                if (networkInterface.isLoopback() || !networkInterface.isUp()) continue;
                
                for (InetAddress address : java.util.Collections.list(networkInterface.getInetAddresses())) {
                    if (address instanceof java.net.Inet4Address && !address.isLoopbackAddress()) {
                        return address.getHostAddress();
                    }
                }
            }
        } catch (Exception e) {
            LOGGER.log(Level.WARNING, "Erro ao obter IP local: " + e.getMessage(), e);
        }
        return "127.0.0.1";
    }

    public void shutdown() {
        try {
            if (scheduler != null && !scheduler.isShutdown()) {
                scheduler.shutdown();
            }
            if (mqttClient != null && mqttClient.isConnected()) {
                mqttClient.unsubscribe(mqttCommandTopic);
                mqttClient.disconnect();
                mqttClient.close();
            }
            LOGGER.info("Sensor " + deviceId + " desconectado com sucesso.");
        } catch (Exception e) {
            LOGGER.log(Level.WARNING, "Erro ao desconectar sensor " + deviceId + ": " + e.getMessage(), e);
        }
    }

    public static void main(String[] args) {
        String deviceId = args.length > 0 ? args[0] : "temp_sensor_mqtt_001";
        TemperatureHumiditySensor sensor = new TemperatureHumiditySensor(deviceId);
        
        // Configurar shutdown hook
        Runtime.getRuntime().addShutdownHook(new Thread(sensor::shutdown));
        
        sensor.start();
        
        // Manter o sensor rodando
        try {
            Thread.currentThread().join();
        } catch (InterruptedException e) {
            LOGGER.info("Sensor " + deviceId + " interrompido.");
        }
    }
}
