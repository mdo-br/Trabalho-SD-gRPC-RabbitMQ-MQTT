package com.smartcity.actuators;

// Arquivo renomeado de AlarmActuator para RelayActuator
import smartcity_devices.SmartCity;
import com.google.protobuf.ByteString;

import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.*;
import java.util.Enumeration;
import java.util.UUID;
import java.util.logging.Level;
import java.util.logging.Logger;

public class RelayActuator {

    private static final Logger LOGGER = Logger.getLogger(RelayActuator.class.getName());

    private static final String MULTICAST_GROUP = "224.1.1.1";
    private static final int MULTICAST_PORT = 5007;
    private static final int ACTUATOR_TCP_PORT = 6002;

    private String deviceId;
    private SmartCity.DeviceStatus currentStatus;
    private String gatewayIp;
    private int gatewayTcpPort;
    private int gatewayUdpPort;

    private ServerSocket tcpServerSocket;

    public RelayActuator(String id) {
        this.deviceId = id;
        this.currentStatus = SmartCity.DeviceStatus.OFF;
        LOGGER.info("Relé Atuador " + deviceId + " inicializado com estado: " + currentStatus);
    }

    public void start() {
        try {
            tcpServerSocket = new ServerSocket(ACTUATOR_TCP_PORT);

            new Thread(this::listenForDiscoveryRequests, "DiscoveryListener-" + deviceId).start();
            new Thread(this::listenForTcpCommands, "CommandListener-" + deviceId).start();
            startStatusScheduler();

        } catch (IOException e) {
            LOGGER.log(Level.SEVERE, "Erro ao iniciar o relé atuador " + deviceId + ": " + e.getMessage(), e);
        }
    }

    private void listenForDiscoveryRequests() {
        try (MulticastSocket multicastSocket = new MulticastSocket(MULTICAST_PORT)) {
            InetAddress group = InetAddress.getByName(MULTICAST_GROUP);
            multicastSocket.joinGroup(group);
            LOGGER.info("Relé Atuador " + deviceId + " aguardando requisições de descoberta multicast...");

            byte[] buffer = new byte[1024];
            DatagramPacket packet = new DatagramPacket(buffer, buffer.length);

            while (true) {
                multicastSocket.receive(packet);
                SmartCity.DiscoveryRequest discoveryRequest = SmartCity.DiscoveryRequest.parseFrom(
                    ByteString.copyFrom(packet.getData(), 0, packet.getLength())
                );

                this.gatewayIp = discoveryRequest.getGatewayIp();
                this.gatewayTcpPort = discoveryRequest.getGatewayTcpPort();
                this.gatewayUdpPort = discoveryRequest.getGatewayUdpPort();

                sendDeviceInfo(gatewayIp, gatewayTcpPort);
            }
        } catch (IOException e) {
            LOGGER.log(Level.SEVERE, "Erro no listener de descoberta multicast: " + e.getMessage(), e);
        }
    }

    private void sendDeviceInfo(String gatewayHost, int gatewayPort) {
        try (Socket socket = new Socket(gatewayHost, gatewayPort)) {
            OutputStream output = socket.getOutputStream();
            SmartCity.DeviceInfo deviceInfo = SmartCity.DeviceInfo.newBuilder()
                    .setDeviceId(deviceId)
                    .setType(SmartCity.DeviceType.RELAY)
                    .setIpAddress(getLocalIpAddress())
                    .setPort(ACTUATOR_TCP_PORT)
                    .setInitialState(currentStatus)
                    .setIsActuator(true)
                    .setIsSensor(false)
                    .build();
            SmartCity.SmartCityMessage envelope = SmartCity.SmartCityMessage.newBuilder()
                    .setMessageType(SmartCity.MessageType.DEVICE_INFO)
                    .setDeviceInfo(deviceInfo)
                    .build();
            envelope.writeDelimitedTo(output);
            output.flush();
            LOGGER.info("Relé Atuador " + deviceId + " enviou DeviceInfo (envelope) para o Gateway em " + gatewayHost + ":" + gatewayPort);
        } catch (IOException e) {
            LOGGER.log(Level.WARNING, "Erro ao enviar DeviceInfo: " + e.getMessage(), e);
        }
    }

    private void listenForTcpCommands() {
        try {
            LOGGER.info("Relé Atuador aguardando comandos TCP...");
            while (true) {
                Socket clientSocket = tcpServerSocket.accept();
                new Thread(() -> handleTcpCommand(clientSocket)).start();
            }
        } catch (IOException e) {
            LOGGER.log(Level.SEVERE, "Erro no listener TCP: " + e.getMessage(), e);
        }
    }

    private void handleTcpCommand(Socket clientSocket) {
        try (InputStream input = clientSocket.getInputStream()) {
            SmartCity.SmartCityMessage envelope = SmartCity.SmartCityMessage.parseDelimitedFrom(input);
            if (envelope != null && envelope.hasClientRequest() && envelope.getClientRequest().hasCommand()) {
                SmartCity.DeviceCommand command = envelope.getClientRequest().getCommand();
                LOGGER.info("Relé Atuador " + deviceId + " recebeu comando TCP: " + command.getCommandType());
                SmartCity.DeviceStatus oldStatus = currentStatus;
                if (command.getCommandType().equals("TURN_ON") && currentStatus == SmartCity.DeviceStatus.OFF) {
                    currentStatus = SmartCity.DeviceStatus.ON;
                    LOGGER.info("RELÉ " + deviceId + " LIGADO!");
                } else if (command.getCommandType().equals("TURN_OFF") && currentStatus == SmartCity.DeviceStatus.ON) {
                    currentStatus = SmartCity.DeviceStatus.OFF;
                    LOGGER.info("RELÉ " + deviceId + " DESLIGADO.");
                }
                if (currentStatus != oldStatus) {
                    sendStatusUpdate();
                }
            } else {
                LOGGER.warning("Envelope SmartCityMessage inválido ou sem comando recebido para o relé atuador " + deviceId);
            }
        } catch (IOException e) {
            LOGGER.log(Level.WARNING, "Erro ao lidar com comando TCP: " + e.getMessage(), e);
        } finally {
            try {
                clientSocket.close();
            } catch (IOException ignored) {}
        }
    }

    private void sendStatusUpdate() {
        if (gatewayIp == null) {
            LOGGER.fine("Relé Atuador " + deviceId + ": Gateway ainda não descoberto, não enviando status.");
            return;
        }
        SmartCity.DeviceUpdate statusUpdate = SmartCity.DeviceUpdate.newBuilder()
                .setDeviceId(deviceId)
                .setType(SmartCity.DeviceType.RELAY)
                .setCurrentStatus(currentStatus)
                .build();
        SmartCity.SmartCityMessage envelope = SmartCity.SmartCityMessage.newBuilder()
                .setMessageType(SmartCity.MessageType.DEVICE_UPDATE)
                .setDeviceUpdate(statusUpdate)
                .build();
        try (DatagramSocket udpSocket = new DatagramSocket()) {
            byte[] data = envelope.toByteArray();
            DatagramPacket packet = new DatagramPacket(data, data.length, InetAddress.getByName(gatewayIp), gatewayUdpPort);
            udpSocket.send(packet);
            LOGGER.info("Relé Atuador " + deviceId + " enviou DeviceUpdate UDP (envelope) para o Gateway.");
        } catch (IOException e) {
            LOGGER.log(Level.WARNING, "Erro ao enviar DeviceUpdate via UDP: " + e.getMessage(), e);
        }
    }

    private void startStatusScheduler() {
        new Thread(() -> {
            while (true) {
                try {
                    Thread.sleep(30000); // 30 segundos
                    sendStatusUpdate();
                } catch (InterruptedException e) {
                    break;
                }
            }
        }, "StatusScheduler-" + deviceId).start();
    }

    private String getLocalIpAddress() {
        try {
            Enumeration<NetworkInterface> interfaces = NetworkInterface.getNetworkInterfaces();
            while (interfaces.hasMoreElements()) {
                NetworkInterface ni = interfaces.nextElement();
                if (ni.isLoopback() || !ni.isUp()) continue;
                Enumeration<InetAddress> addresses = ni.getInetAddresses();
                while (addresses.hasMoreElements()) {
                    InetAddress addr = addresses.nextElement();
                    if (addr instanceof Inet4Address && !addr.isLoopbackAddress()) {
                        return addr.getHostAddress();
                    }
                }
            }
            return InetAddress.getLocalHost().getHostAddress();
        } catch (Exception e) {
            LOGGER.warning("Erro ao obter IP local: " + e.getMessage());
            return "127.0.0.1";
        }
    }

    public static void main(String[] args) {
        String actuatorId = args.length > 0 ? args[0] : UUID.randomUUID().toString();
        RelayActuator actuator = new RelayActuator(actuatorId);
        actuator.start();

        try {
            Thread.sleep(Long.MAX_VALUE);
        } catch (InterruptedException ignored) {}
    }
}