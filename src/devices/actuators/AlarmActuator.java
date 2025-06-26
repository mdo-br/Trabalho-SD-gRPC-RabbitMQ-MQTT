// src/devices/actuators/AlarmActuator.java
// ATUALIZADO: Nome do pacote
package com.smartcity.actuators;

// CORRIGIDO: Importar smartcity.devices.SmartCity
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

public class AlarmActuator {

    private static final Logger LOGGER = Logger.getLogger(AlarmActuator.class.getName());

    // --- Configurações de Comunicação ---
    private static final String MULTICAST_GROUP = "224.1.1.1";
    private static final int MULTICAST_PORT = 5007;
    private static final int ACTUATOR_TCP_PORT = 6002; // Porta TCP específica para este atuador (diferente do sensor)

    private String deviceId;
    private SmartCity.DeviceStatus currentStatus; // ON ou OFF
    private String gatewayIp;
    private int gatewayTcpPort;
    private int gatewayUdpPort; // Mantém a porta UDP do Gateway, mesmo que o atuador não envie dados UDP periodicamente

    private ServerSocket tcpServerSocket; // Para receber comandos TCP do Gateway

    public AlarmActuator(String id) {
        this.deviceId = id;
        this.currentStatus = SmartCity.DeviceStatus.OFF; // Alarme inicia DESLIGADO
        LOGGER.info("Atuador de Alarme " + deviceId + " inicializado com estado: " + currentStatus);
    }

    public void start() {
        try {
            tcpServerSocket = new ServerSocket(ACTUATOR_TCP_PORT);

            new Thread(this::listenForDiscoveryRequests, "DiscoveryListener-" + deviceId).start();
            new Thread(this::listenForTcpCommands, "CommandListener-" + deviceId).start();

        } catch (IOException e) {
            LOGGER.log(Level.SEVERE, "Erro ao iniciar o atuador de alarme " + deviceId + ": " + e.getMessage(), e);
        }
    }

    private void listenForDiscoveryRequests() {
        try (MulticastSocket multicastSocket = new MulticastSocket(MULTICAST_PORT)) {
            InetAddress group = InetAddress.getByName(MULTICAST_GROUP);
            multicastSocket.joinGroup(group);
            LOGGER.info("Atuador de Alarme " + deviceId + " aguardando requisições de descoberta multicast em " + MULTICAST_GROUP + ":" + MULTICAST_PORT + "...");

            byte[] buffer = new byte[1024];
            DatagramPacket packet = new DatagramPacket(buffer, buffer.length);

            while (true) {
                multicastSocket.receive(packet);
                SmartCity.DiscoveryRequest discoveryRequest = SmartCity.DiscoveryRequest.parseFrom(
                    ByteString.copyFrom(packet.getData(), 0, packet.getLength())
                );
                LOGGER.info("Atuador de Alarme " + deviceId + " recebeu requisição de descoberta do Gateway em " + discoveryRequest.getGatewayIp() + ":" + discoveryRequest.getGatewayTcpPort());

                this.gatewayIp = discoveryRequest.getGatewayIp();
                this.gatewayTcpPort = discoveryRequest.getGatewayTcpPort();
                this.gatewayUdpPort = discoveryRequest.getGatewayUdpPort();

                sendDeviceInfo(gatewayIp, gatewayTcpPort);
            }
        } catch (IOException e) {
            LOGGER.log(Level.SEVERE, "Erro no listener de descoberta multicast para o atuador " + deviceId + ": " + e.getMessage(), e);
        }
    }

    private void sendDeviceInfo(String gatewayHost, int gatewayPort) {
        try (Socket socket = new Socket(gatewayHost, gatewayPort)) {
            OutputStream output = socket.getOutputStream();

            SmartCity.DeviceInfo deviceInfo = SmartCity.DeviceInfo.newBuilder()
                    .setDeviceId(deviceId)
                    .setType(SmartCity.DeviceType.ALARM)
                    .setIpAddress(getLocalIpAddress())
                    .setPort(ACTUATOR_TCP_PORT)
                    .setInitialState(currentStatus)
                    .setIsActuator(true)
                    .setIsSensor(false)
                    .build();

            deviceInfo.writeDelimitedTo(output);
            output.flush();
            LOGGER.info("Atuador de Alarme " + deviceId + " enviou DeviceInfo para o Gateway em " + gatewayHost + ":" + gatewayPort);
        } catch (IOException e) {
            LOGGER.log(Level.WARNING, "Erro ao enviar DeviceInfo para o Gateway (" + gatewayHost + ":" + gatewayPort + "): " + e.getMessage(), e);
        }
    }

    private void listenForTcpCommands() {
        try {
            LOGGER.info("Atuador de Alarme " + deviceId + " aguardando comandos TCP na porta " + ACTUATOR_TCP_PORT + "...");
            while (true) {
                Socket clientSocket = tcpServerSocket.accept();
                new Thread(() -> handleTcpCommand(clientSocket), "TCPHandler-" + deviceId + "-" + clientSocket.getInetAddress().getHostAddress()).start();
            }
        } catch (IOException e) {
            LOGGER.log(Level.SEVERE, "Erro no listener TCP do atuador de alarme: " + e.getMessage(), e);
        } finally {
            if (tcpServerSocket != null && !tcpServerSocket.isClosed()) {
                try {
                    tcpServerSocket.close();
                } catch (IOException e) {
                    LOGGER.log(Level.WARNING, "Erro ao fechar ServerSocket TCP do atuador: " + e.getMessage(), e);
                }
            }
        }
    }

    private void handleTcpCommand(Socket clientSocket) {
        try (InputStream input = clientSocket.getInputStream()) {
            SmartCity.DeviceCommand command = SmartCity.DeviceCommand.parseDelimitedFrom(input);
            if (command != null) {
                LOGGER.info("Atuador de Alarme " + deviceId + " recebeu comando TCP: " + command.getCommandType() + " com valor " + command.getCommandValue());

                SmartCity.DeviceStatus oldStatus = currentStatus;

                if (command.getCommandType().equals("TURN_ON") && currentStatus == SmartCity.DeviceStatus.OFF) {
                    currentStatus = SmartCity.DeviceStatus.ON;
                    LOGGER.info("ALARME " + deviceId + " LIGADO! Som: [BEEP-BEEP-BEEP]");
                } else if (command.getCommandType().equals("TURN_OFF") && currentStatus == SmartCity.DeviceStatus.ON) {
                    currentStatus = SmartCity.DeviceStatus.OFF;
                    LOGGER.info("ALARME " + deviceId + " DESLIGADO.");
                } else {
                    LOGGER.warning("Comando '" + command.getCommandType() + "' recebido para o alarme " + deviceId + ", mas não resultou em mudança de estado.");
                }

                if (currentStatus != oldStatus) {
                    reportStatusToGateway();
                }
            }

        } catch (IOException e) {
            LOGGER.log(Level.WARNING, "Erro ao lidar com comando TCP para o atuador " + deviceId + ": " + e.getMessage(), e);
        } finally {
            try {
                if (clientSocket != null) {
                    clientSocket.close();
                }
            } catch (IOException e) {
                LOGGER.log(Level.WARNING, "Erro ao fechar socket TCP do comando: " + e.getMessage(), e);
            }
        }
    }

    private void reportStatusToGateway() {
        if (gatewayIp == null || gatewayTcpPort == 0) {
            LOGGER.warning("Gateway não descoberto. Não foi possível reportar o estado do alarme.");
            return;
        }

        try (Socket socket = new Socket(gatewayIp, gatewayTcpPort)) {
            OutputStream output = socket.getOutputStream();

            SmartCity.DeviceUpdate statusUpdate = SmartCity.DeviceUpdate.newBuilder()
                    .setDeviceId(deviceId)
                    .setType(SmartCity.DeviceType.ALARM)
                    .setCurrentStatus(currentStatus)
                    // Não há dados sensoriados para o alarme, mas se no futuro houver, adicione aqui
                    .build();

            statusUpdate.writeDelimitedTo(output);
            output.flush();
            LOGGER.info("Atuador de Alarme " + deviceId + " reportou estado '" + currentStatus.name() + "' ao Gateway.");
        } catch (IOException e) {
            LOGGER.log(Level.WARNING, "Erro ao reportar estado do alarme ao Gateway: " + e.getMessage(), e);
        }
    }

    private String getLocalIpAddress() {
        try {
            Enumeration<NetworkInterface> networkInterfaces = NetworkInterface.getNetworkInterfaces();
            while (networkInterfaces.hasMoreElements()) {
                NetworkInterface ni = networkInterfaces.nextElement();
                if (ni.isLoopback() || !ni.isUp()) {
                    continue;
                }
                // CORRIGIDO: Chamada correta a getInetAddresses() em ni
                Enumeration<InetAddress> addresses = ni.getInetAddresses();
                while (addresses.hasMoreElements()) {
                    InetAddress addr = addresses.nextElement();
                    if (addr instanceof Inet4Address && !addr.isLoopbackAddress()) {
                        return addr.getHostAddress();
                    }
                }
            }
            LOGGER.log(Level.WARNING, "Não foi possível encontrar um IP de rede não-loopback IPv4. Usando IP do localhost.");
            return InetAddress.getLocalHost().getHostAddress();
        } catch (SocketException | UnknownHostException e) {
            LOGGER.log(Level.WARNING, "Erro ao tentar obter o IP local para o atuador: " + e.getMessage(), e);
            return "127.0.0.1";
        }
    }

    public static void main(String[] args) {
        String actuatorId = args.length > 0 ? args[0] : UUID.randomUUID().toString();
        AlarmActuator actuator = new AlarmActuator(actuatorId);
        actuator.start();

        try {
            Thread.sleep(Long.MAX_VALUE);
        } catch (InterruptedException e) {
            LOGGER.log(Level.WARNING, "Thread principal do atuador foi interrompida.", e);
            Thread.currentThread().interrupt();
        } finally {
            LOGGER.info("Atuador de Alarme " + actuator.deviceId + " desligado.");
        }
    }
}