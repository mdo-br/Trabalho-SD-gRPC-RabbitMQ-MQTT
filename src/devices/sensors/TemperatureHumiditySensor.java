// src/devices/sensors/TemperatureHumiditySensor.java
package com.smartcity.sensors;

// Importar smartcity.devices.SmartCity
import smartcity_devices.SmartCity;
import com.google.protobuf.ByteString;

import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
// NOVO: Para identificar endereços IPv4
// NOVO: Para iterar sobre interfaces de rede
import java.net.*; // Contém DatagramSocket, ServerSocket, Socket, InetAddress, UnknownHostException
import java.util.Enumeration; // Para iterar sobre NetworkInterface e InetAddress
import java.util.Random;
import java.util.UUID;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;
import java.util.logging.Level;
import java.util.logging.Logger;

public class TemperatureHumiditySensor {

    private static final Logger LOGGER = Logger.getLogger(TemperatureHumiditySensor.class.getName());

    // --- Configurações de Comunicação ---
    private static final String MULTICAST_GROUP = "224.1.1.1";
    private static final int MULTICAST_PORT = 5007; // Porta para descoberta multicast UDP 
    private static final int SENSOR_TCP_PORT = 6001; // Porta TCP específica para este sensor para receber comandos
    private int captureIntervalSeconds = 15; // variável de instância

    private String deviceId;
    private SmartCity.DeviceStatus currentStatus;
    private String gatewayIp;       // IP do Gateway, descoberto via multicast
    private int gatewayUdpPort;     // Porta UDP do Gateway para envio de dados sensoriados
    private int gatewayTcpPort;     // Porta TCP do Gateway para envio de DeviceInfo e possivelmente outros controles

    private DatagramSocket udpSocket; // Socket para envio de dados sensoriados via UDP 
    private ServerSocket tcpServerSocket; // ServerSocket para receber comandos TCP do Gateway 
    private ScheduledExecutorService scheduler; // Para agendar o envio periódico de dados
    private Random random = new Random(); // Para simular leituras de sensor

    public TemperatureHumiditySensor(String id) {
        this.deviceId = id;
        this.currentStatus = SmartCity.DeviceStatus.ACTIVE; // Estado inicial do sensor
        LOGGER.info("Sensor " + deviceId + " inicializado com estado: " + currentStatus);
    }

    public void start() {
        try {
            // Inicializa os sockets de comunicação
            udpSocket = new DatagramSocket(); // Socket para enviar dados UDP
            tcpServerSocket = new ServerSocket(SENSOR_TCP_PORT); // ServerSocket para receber comandos TCP

            // Inicia threads para lidar com diferentes tipos de comunicação
            // Escuta requisições de descoberta multicast do Gateway 
            new Thread(this::listenForDiscoveryRequests, "DiscoveryListener-" + deviceId).start();
            // Escuta comandos TCP do Gateway 
            new Thread(this::listenForTcpCommands, "CommandListener-" + deviceId).start();

            // Agenda o envio periódico de dados sensoriados se o sensor estiver ativo 
            startSensorDataScheduler();

        } catch (IOException e) {
            LOGGER.log(Level.SEVERE, "Erro ao iniciar o sensor " + deviceId + ": " + e.getMessage(), e);
        }
    }

    private void startSensorDataScheduler() {
        if (scheduler != null && !scheduler.isShutdown()) {
            scheduler.shutdownNow(); // Garante que qualquer scheduler anterior seja parado
        }
        scheduler = Executors.newSingleThreadScheduledExecutor();
        // Agenda o envio periódico de dados sensoriados, começando imediatamente
        scheduler.scheduleAtFixedRate(this::sendSensorData, 0, captureIntervalSeconds, TimeUnit.SECONDS);
        LOGGER.info("Envio periódico de dados do sensor " + deviceId + " agendado a cada " + captureIntervalSeconds + " segundos.");
    }

    private void listenForDiscoveryRequests() {
        try (MulticastSocket multicastSocket = new MulticastSocket(MULTICAST_PORT)) {
            InetAddress group = InetAddress.getByName(MULTICAST_GROUP);
            multicastSocket.joinGroup(group); // Junta-se ao grupo multicast para receber mensagens 
            LOGGER.info("Sensor " + deviceId + " aguardando requisições de descoberta multicast em " + MULTICAST_GROUP + ":" + MULTICAST_PORT + "...");

            byte[] buffer = new byte[1024];
            DatagramPacket packet = new DatagramPacket(buffer, buffer.length);

            while (true) {
                multicastSocket.receive(packet); // Recebe uma mensagem multicast 

                // CORREÇÃO AQUI: Usando ByteString.copyFrom para desserialização
                SmartCity.DiscoveryRequest discoveryRequest = SmartCity.DiscoveryRequest.parseFrom(
                    ByteString.copyFrom(packet.getData(), 0, packet.getLength())
                );
                LOGGER.info("Sensor " + deviceId + " recebeu requisição de descoberta do Gateway em " + discoveryRequest.getGatewayIp() + ":" + discoveryRequest.getGatewayTcpPort());

                // Armazena as informações do Gateway para comunicação futura
                this.gatewayIp = discoveryRequest.getGatewayIp();
                this.gatewayTcpPort = discoveryRequest.getGatewayTcpPort();
                this.gatewayUdpPort = discoveryRequest.getGatewayUdpPort();

                // Responde ao Gateway com as informações do próprio dispositivo 
                sendDeviceInfo(gatewayIp, gatewayTcpPort);
            }
        } catch (IOException e) {
            LOGGER.log(Level.SEVERE, "Erro no listener de descoberta multicast para o sensor " + deviceId + ": " + e.getMessage(), e);
        }
    }

    private void sendDeviceInfo(String gatewayHost, int gatewayPort) {
        try (Socket socket = new Socket(gatewayHost, gatewayPort)) {
            OutputStream output = socket.getOutputStream();
            SmartCity.DeviceInfo deviceInfo = SmartCity.DeviceInfo.newBuilder()
                    .setDeviceId(deviceId)
                    .setType(SmartCity.DeviceType.TEMPERATURE_SENSOR)
                    .setIpAddress(getLocalIpAddress())
                    .setPort(SENSOR_TCP_PORT)
                    .setInitialState(currentStatus)
                    .setIsActuator(false)
                    .setIsSensor(true)
                    .build();
            SmartCity.SmartCityMessage envelope = SmartCity.SmartCityMessage.newBuilder()
                    .setMessageType(SmartCity.MessageType.DEVICE_INFO)
                    .setDeviceInfo(deviceInfo)
                    .build();
            envelope.writeDelimitedTo(output);
            output.flush();
            LOGGER.info("Sensor " + deviceId + " enviou DeviceInfo (envelope) para o Gateway em " + gatewayHost + ":" + gatewayPort);
        } catch (IOException e) {
            LOGGER.log(Level.WARNING, "Erro ao enviar DeviceInfo para o Gateway (" + gatewayHost + ":" + gatewayPort + "): " + e.getMessage(), e);
        }
    }

    private void listenForTcpCommands() {
        try {
            LOGGER.info("Sensor " + deviceId + " aguardando comandos TCP na porta " + SENSOR_TCP_PORT + "...");
            while (true) {
                Socket clientSocket = tcpServerSocket.accept(); // Aceita uma nova conexão TCP
                // Lida com cada comando TCP em uma nova thread
                new Thread(() -> handleTcpCommand(clientSocket), "TCPHandler-" + deviceId + "-" + clientSocket.getInetAddress().getHostAddress()).start();
            }
        } catch (IOException e) {
            LOGGER.log(Level.SEVERE, "Erro no listener TCP do sensor " + deviceId + ": " + e.getMessage(), e);
        } finally {
            if (tcpServerSocket != null && !tcpServerSocket.isClosed()) {
                try {
                    tcpServerSocket.close();
                } catch (IOException e) {
                    LOGGER.log(Level.WARNING, "Erro ao fechar ServerSocket TCP: " + e.getMessage(), e);
                }
            }
        }
    }

    private void handleTcpCommand(Socket clientSocket) {
        try (InputStream input = clientSocket.getInputStream()) {
            SmartCity.SmartCityMessage envelope = SmartCity.SmartCityMessage.parseDelimitedFrom(input);
            if (envelope != null && envelope.hasClientRequest() && envelope.getClientRequest().hasCommand()) {
                SmartCity.DeviceCommand command = envelope.getClientRequest().getCommand();
                LOGGER.info("Sensor " + deviceId + " recebeu comando TCP: " + command.getCommandType() + " com valor " + command.getCommandValue());
                if (command.getCommandType().equals("TURN_OFF") || command.getCommandType().equals("TURN_IDLE")) {
                    currentStatus = SmartCity.DeviceStatus.IDLE;
                    LOGGER.info("Sensor " + deviceId + " em modo IDLE por comando.");
                    if (scheduler != null && !scheduler.isShutdown()) {
                        scheduler.shutdownNow();
                        LOGGER.info("Envio de dados do sensor " + deviceId + " interrompido.");
                    }
                } else if (command.getCommandType().equals("TURN_ON") || command.getCommandType().equals("TURN_ACTIVE")) {
                    currentStatus = SmartCity.DeviceStatus.ACTIVE;
                    LOGGER.info("Sensor " + deviceId + " em modo ACTIVE por comando.");
                    startSensorDataScheduler();
                } else if (command.getCommandType().equals("SET_DEVICE_ID")) {
                    String oldId = this.deviceId;
                    this.deviceId = command.getCommandValue();
                    LOGGER.info("Sensor alterou ID de " + oldId + " para " + this.deviceId);
                    sendDeviceInfo(gatewayIp, gatewayTcpPort);
                } else if (command.getCommandType().equals("SET_SAMPLING_RATE") || command.getCommandType().equals("SET_FREQ")) {
                    try {
                        int newInterval = Integer.parseInt(command.getCommandValue());
                        captureIntervalSeconds = newInterval / 1000;
                        LOGGER.info("Sensor " + deviceId + " alterou frequência de envio para " + newInterval + " ms.");
                        startSensorDataScheduler();
                    } catch (NumberFormatException e) {
                        LOGGER.warning("Valor inválido para SET_SAMPLING_RATE: " + command.getCommandValue());
                    }
                } else {
                    LOGGER.warning("Comando desconhecido recebido para o sensor " + deviceId + ": " + command.getCommandType());
                }
            } else {
                LOGGER.warning("Envelope SmartCityMessage inválido ou sem comando recebido para o sensor " + deviceId);
            }
        } catch (IOException e) {
            LOGGER.log(Level.WARNING, "Erro ao lidar com comando TCP para o sensor " + deviceId + ": " + e.getMessage(), e);
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

    private void sendSensorData() {
        if (gatewayIp == null || currentStatus == SmartCity.DeviceStatus.IDLE) {
            if (gatewayIp == null) {
                LOGGER.fine("Sensor " + deviceId + ": Gateway ainda não descoberto, não enviando dados.");
            } else {
                LOGGER.fine("Sensor " + deviceId + ": Em modo IDLE, não enviando dados.");
            }
            return;
        }
        double temperature = 20.0 + random.nextGaussian() * 5.0;
        double humidity = 50.0 + random.nextGaussian() * 10.0;
        SmartCity.DeviceUpdate sensorUpdate = SmartCity.DeviceUpdate.newBuilder()
                .setDeviceId(deviceId)
                .setType(SmartCity.DeviceType.TEMPERATURE_SENSOR)
                .setCurrentStatus(currentStatus)
                .setTemperatureHumidity(
                    SmartCity.TemperatureHumidityData.newBuilder()
                        .setTemperature(temperature)
                        .setHumidity(humidity)
                        .build()
                )
                .build();
        SmartCity.SmartCityMessage envelope = SmartCity.SmartCityMessage.newBuilder()
                .setMessageType(SmartCity.MessageType.DEVICE_UPDATE)
                .setDeviceUpdate(sensorUpdate)
                .build();
        try {
            byte[] data = envelope.toByteArray();
            DatagramPacket packet = new DatagramPacket(data, data.length, InetAddress.getByName(gatewayIp), gatewayUdpPort);
            udpSocket.send(packet);
            LOGGER.info(String.format("Sensor %s enviou DeviceUpdate UDP (envelope): Temp=%.2f°C, Hum=%.2f%%", deviceId, temperature, humidity));
        } catch (IOException e) {
            LOGGER.log(Level.WARNING, "Erro ao enviar DeviceUpdate via UDP para " + gatewayIp + ":" + gatewayUdpPort + ": " + e.getMessage(), e);
        }
    }

    // CORREÇÃO AQUI: Método getLocalIpAddress refatorado para usar laço while
    private String getLocalIpAddress() {
        try {
            Enumeration<NetworkInterface> networkInterfaces = NetworkInterface.getNetworkInterfaces();
            while (networkInterfaces.hasMoreElements()) {
                NetworkInterface ni = networkInterfaces.nextElement();
                // Ignora interfaces de loopback (como 127.0.0.1) e as que não estão ativas
                if (ni.isLoopback() || !ni.isUp()) {
                    continue;
                }

                // Obtém todos os endereços IP para esta interface
                Enumeration<InetAddress> addresses = ni.getInetAddresses();
                while (addresses.hasMoreElements()) {
                    InetAddress addr = addresses.nextElement();
                    // Verifica se é um IPv4 e não é um endereço de loopback
                    if (addr instanceof Inet4Address && !addr.isLoopbackAddress()) {
                        return addr.getHostAddress(); // Retorna o primeiro IP válido encontrado
                    }
                }
            }
            // Fallback se nenhum IP não-loopback IPv4 for encontrado, retorna o IP do localhost
            LOGGER.log(Level.WARNING, "Não foi possível encontrar um IP de rede não-loopback IPv4. Usando IP do localhost.");
            return InetAddress.getLocalHost().getHostAddress();
        } catch (SocketException | UnknownHostException e) {
            LOGGER.log(Level.WARNING, "Erro ao tentar obter o IP local: " + e.getMessage(), e);
            return "127.0.0.1"; // Retorna localhost como fallback em caso de erro
        }
    }

    public static void main(String[] args) {
        String sensorId = args.length > 0 ? args[0] : UUID.randomUUID().toString();
        // Cria uma instância do sensor com o ID exatamente igual ao argumento
        TemperatureHumiditySensor sensor = new TemperatureHumiditySensor(sensorId);
        sensor.start();

        // Mantém o thread principal vivo para que os threads de comunicação continuem executando
        try {
            Thread.sleep(Long.MAX_VALUE);
        } catch (InterruptedException e) {
            LOGGER.log(Level.WARNING, "Thread principal do sensor foi interrompida.", e);
            Thread.currentThread().interrupt(); // Restaura o status de interrupção
        } finally {
            // Garante o desligamento limpo dos recursos ao sair
            if (sensor.scheduler != null && !sensor.scheduler.isShutdown()) {
                sensor.scheduler.shutdown();
                try {
                    if (!sensor.scheduler.awaitTermination(5, TimeUnit.SECONDS)) {
                        sensor.scheduler.shutdownNow();
                    }
                } catch (InterruptedException e) {
                    sensor.scheduler.shutdownNow();
                    Thread.currentThread().interrupt();
                }
            }
            if (sensor.udpSocket != null && !sensor.udpSocket.isClosed()) {
                sensor.udpSocket.close();
            }
            if (sensor.tcpServerSocket != null && !sensor.tcpServerSocket.isClosed()) {
                try {
                    sensor.tcpServerSocket.close();
                } catch (IOException e) {
                    LOGGER.log(Level.WARNING, "Erro ao fechar ServerSocket TCP no encerramento: " + e.getMessage(), e);
                }
            }
            LOGGER.info("Sensor " + sensor.deviceId + " desligado.");
        }
    }
}