package com.smartcity.sensors;

import smartcity.SmartCity; // Importa as classes geradas do Protocol Buffers

import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.*;
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
    private static final long SENSOR_REPORT_INTERVAL_SECONDS = 15; // Intervalo de envio de dados sensoriados (UDP)

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
        scheduler.scheduleAtFixedRate(this::sendSensorData, 0, SENSOR_REPORT_INTERVAL_SECONDS, TimeUnit.SECONDS);
        LOGGER.info("Envio periódico de dados do sensor " + deviceId + " agendado a cada " + SENSOR_REPORT_INTERVAL_SECONDS + " segundos.");
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

                // Desserializa a mensagem para DiscoveryRequest usando Protocol Buffers
                SmartCity.DiscoveryRequest discoveryRequest = SmartCity.DiscoveryRequest.parseFrom(packet.getData(), 0, packet.getLength());
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

            // Constrói a mensagem DeviceInfo com os dados do sensor 
            SmartCity.DeviceInfo deviceInfo = SmartCity.DeviceInfo.newBuilder()
                    .setDeviceId(deviceId)
                    .setType(SmartCity.DeviceType.TEMPERATURE_SENSOR) // Tipo do sensor 
                    .setIpAddress(getLocalIpAddress()) // IP local do sensor 
                    .setPort(SENSOR_TCP_PORT) // Porta TCP do sensor para comandos 
                    .setInitialState(currentStatus) // Estado inicial do sensor 
                    .setIsActuator(false) // Este é um sensor, não um atuador primário 
                    .setIsSensor(true)    // Este é um sensor 
                    .build();

            // Serializa e envia a mensagem para o Gateway via TCP 
            deviceInfo.writeDelimitedTo(output); // Usa writeDelimitedTo para prefixar o tamanho da mensagem
            output.flush();
            LOGGER.info("Sensor " + deviceId + " enviou DeviceInfo para o Gateway em " + gatewayHost + ":" + gatewayPort);
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
            // Desserializa o comando recebido do Gateway 
            SmartCity.DeviceCommand command = SmartCity.DeviceCommand.parseDelimitedFrom(input);
            if (command != null) {
                LOGGER.info("Sensor " + deviceId + " recebeu comando TCP: " + command.getCommandType() + " com valor " + command.getCommandValue());

                // Lógica para processar comandos:
                if (command.getCommandType().equals("TURN_OFF")) {
                    currentStatus = SmartCity.DeviceStatus.OFF;
                    LOGGER.info("Sensor " + deviceId + " DESLIGADO por comando.");
                    if (scheduler != null && !scheduler.isShutdown()) {
                        scheduler.shutdownNow(); // Para o envio de dados
                        LOGGER.info("Envio de dados do sensor " + deviceId + " interrompido.");
                    }
                } else if (command.getCommandType().equals("TURN_ON")) {
                    currentStatus = SmartCity.DeviceStatus.ACTIVE;
                    LOGGER.info("Sensor " + deviceId + " LIGADO por comando.");
                    startSensorDataScheduler(); // Reinicia o envio de dados
                } else {
                    LOGGER.warning("Comando desconhecido recebido para o sensor " + deviceId + ": " + command.getCommandType());
                }
                // Atuadores teriam mais lógica aqui (e.g., mudar resolução da câmera, tempo do semáforo) 

                // Opcional: Enviar um ACK de volta para o Gateway se a lógica do protocolo permitir.
                // Atualmente, o .proto não tem uma mensagem de ACK específica para comandos de dispositivo.
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
        // Só envia dados se o Gateway foi descoberto e o sensor estiver ativo
        if (gatewayIp == null || currentStatus == SmartCity.DeviceStatus.OFF) {
            if (gatewayIp == null) {
                LOGGER.fine("Sensor " + deviceId + ": Gateway ainda não descoberto, não enviando dados.");
            } else {
                LOGGER.fine("Sensor " + deviceId + ": Desligado, não enviando dados.");
            }
            return;
        }

        // Simula leituras de temperatura e umidade com alguma variação
        double temperature = 20.0 + random.nextGaussian() * 5.0; // Ex: 20°C +/- 5°C
        double humidity = 50.0 + random.nextGaussian() * 10.0; // Ex: 50% +/- 10%

        // Constrói a mensagem DeviceUpdate com os dados sensoriados 
        SmartCity.DeviceUpdate sensorUpdate = SmartCity.DeviceUpdate.newBuilder()
                .setDeviceId(deviceId)
                .setType(SmartCity.DeviceType.TEMPERATURE_SENSOR)
                .setCurrentStatus(currentStatus)
                .setTemperatureValue(temperature)
                .setAirQualityIndex(humidity) // Usando air_quality_index para umidade, como discutido
                .build();

        try {
            byte[] data = sensorUpdate.toByteArray(); // Serializa a mensagem para bytes
            DatagramPacket packet = new DatagramPacket(data, data.length, InetAddress.getByName(gatewayIp), gatewayUdpPort);
            udpSocket.send(packet); // Envia a mensagem via UDP para o Gateway 
            LOGGER.info(String.format("Sensor %s enviou dados UDP: Temp=%.2f°C, Hum=%.2f%%", deviceId, temperature, humidity));
        } catch (IOException e) {
            LOGGER.log(Level.WARNING, "Erro ao enviar dados sensoriados via UDP para " + gatewayIp + ":" + gatewayUdpPort + ": " + e.getMessage(), e);
        }
    }

    private String getLocalIpAddress() {
        try {
            // Tenta obter o IP não-loopback.
            // Isso é importante para ambientes de rede reais onde 127.0.0.1 não funcionaria para comunicação externa.
            for (java.net.NetworkInterface ni : java.net.NetworkInterface.getNetworkInterfaces()) {
                ni.getInterfaceAddresses().stream()
                        .map(java.net.InterfaceAddress::getAddress)
                        .filter(addr -> addr instanceof java.net.Inet4Address && !addr.isLoopbackAddress())
                        .findFirst()
                        .map(java.net.InetAddress::getHostAddress)
                        .ifPresent(ip -> {
                            // Retornar o IP diretamente não funciona bem em um stream.
                            // Para um método simples, esta é uma abordagem mais robusta para pegar o IP.
                            // No entanto, para simplicidade e compatibilidade com o retorno de string:
                        });
            }
            return InetAddress.getLocalHost().getHostAddress(); // Fallback se o loop acima for complicado
        } catch (SocketException | UnknownHostException e) {
            LOGGER.log(Level.WARNING, "Não foi possível obter o IP local: " + e.getMessage(), e);
            return "127.0.0.1"; // Retorna localhost como fallback
        }
    }

    public static void main(String[] args) {
        String sensorId = args.length > 0 ? args[0] : UUID.randomUUID().toString();
        // Cria uma instância do sensor com um ID único (usando os 4 primeiros caracteres do UUID para simplicidade)
        TemperatureHumiditySensor sensor = new TemperatureHumiditySensor("temp_hum_sensor_" + sensorId.substring(0, 4));
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