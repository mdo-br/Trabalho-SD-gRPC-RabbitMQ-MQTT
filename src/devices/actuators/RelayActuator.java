package com.smartcity.actuators;

// Arquivo renomeado de AlarmActuator para RelayActuator
import smartcity.devices.SmartCity;
import com.google.protobuf.ByteString;

import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.*;
import java.util.Enumeration;
import java.util.UUID;
import java.util.logging.Level;
import java.util.logging.Logger;
import java.util.Arrays;
// import actuator.ActuatorService;
// import actuator.AtuadorServiceGrpc;

public class RelayActuator {

    private static final Logger LOGGER = Logger.getLogger(RelayActuator.class.getName());

    private static final String MULTICAST_GROUP = "224.1.1.1";
    private static final int MULTICAST_PORT = 5007;

    private String deviceId;
    private SmartCity.DeviceStatus currentStatus;
    private String gatewayIp;
    private int gatewayTcpPort;
    private int gatewayUdpPort;

    private int tcpPort; // Porta TCP do próprio relé (atuador)
    private ServerSocket tcpServerSocket;

    public RelayActuator(String id, int tcpPort) {
        this.deviceId = id;
        this.currentStatus = SmartCity.DeviceStatus.OFF;
        this.tcpPort = tcpPort;
        LOGGER.info("Relé Atuador " + deviceId + " inicializado com estado: " + currentStatus + " | TCP Port: " + tcpPort);
    }

    // Mantenha o construtor antigo para compatibilidade:
    public RelayActuator(String id) {
        this(id, 6002);
    }

    public void start() {
        try {
            tcpServerSocket = new ServerSocket(tcpPort);

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
                LOGGER.info("Pacote recebido: tamanho=" + packet.getLength() + ", bytes=" + bytesToHex(Arrays.copyOf(packet.getData(), packet.getLength())));
                SmartCity.DiscoveryRequest discoveryRequest = SmartCity.DiscoveryRequest.parseFrom(
                    ByteString.copyFrom(packet.getData(), 0, packet.getLength())
                );

                this.gatewayIp = discoveryRequest.getGatewayIp();
                this.gatewayTcpPort = discoveryRequest.getGatewayTcpPort();
                this.gatewayUdpPort = discoveryRequest.getGatewayUdpPort();
                LOGGER.info("Discovery recebido: gatewayIp=" + gatewayIp + ", gatewayTcpPort=" + gatewayTcpPort + ", gatewayUdpPort=" + gatewayUdpPort);

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
                    .setPort(tcpPort) // Corrigido: usa a porta configurada do relé
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
        try (InputStream input = clientSocket.getInputStream();
             OutputStream output = clientSocket.getOutputStream()) {
            SmartCity.SmartCityMessage envelope = SmartCity.SmartCityMessage.parseDelimitedFrom(input);
            boolean responded = false;
            if (envelope != null && envelope.hasClientRequest()) {
                SmartCity.ClientRequest req = envelope.getClientRequest();
                if (req.hasCommand()) {
                    SmartCity.DeviceCommand command = req.getCommand();
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
                    responded = true;
                }
                // Sempre responde com DeviceUpdate, seja comando ou GET_DEVICE_STATUS
                if (responded || req.getType() == SmartCity.ClientRequest.RequestType.GET_DEVICE_STATUS) {
                    SmartCity.DeviceUpdate statusUpdate = SmartCity.DeviceUpdate.newBuilder()
                            .setDeviceId(deviceId)
                            .setType(SmartCity.DeviceType.RELAY)
                            .setCurrentStatus(currentStatus)
                            .build();
                    SmartCity.SmartCityMessage responseEnvelope = SmartCity.SmartCityMessage.newBuilder()
                            .setMessageType(SmartCity.MessageType.DEVICE_UPDATE)
                            .setDeviceUpdate(statusUpdate)
                            .build();
                    responseEnvelope.writeDelimitedTo(output);
                    output.flush();
                    LOGGER.info("Relé Atuador " + deviceId + " respondeu status via TCP.");
                }
            } else {
                LOGGER.warning("Envelope SmartCityMessage inválido ou sem client request recebido para o relé " + deviceId);
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
                    Thread.sleep(5000); // 30 segundos
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

    private static String bytesToHex(byte[] bytes) {
        StringBuilder sb = new StringBuilder();
        for (byte b : bytes) {
            sb.append(String.format("%02X", b));
        }
        return sb.toString();
    }

    public static void main(String[] args) {
        String actuatorId = args.length > 0 ? args[0] : UUID.randomUUID().toString();
        int tcpPort = 6002; // padrão

        if (args.length > 1) {
            try {
                tcpPort = Integer.parseInt(args[1]);
            } catch (NumberFormatException e) {
                System.err.println("Porta TCP inválida, usando padrão 6002.");
            }
        }

        RelayActuator actuator = new RelayActuator(actuatorId, tcpPort);
        actuator.start();

        try {
            Thread.sleep(Long.MAX_VALUE);
        } catch (InterruptedException ignored) {}
    }
}