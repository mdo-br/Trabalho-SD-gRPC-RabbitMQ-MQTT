# Trabalho-SD
A simple network sensor simulator with Java, Python, and Protocol Buffers, using TCP, UDP, and multicast communication.

# Projeto Cidade Inteligente

[cite_start]Este projeto simula uma sistema de cidade inteligente  [cite_start]composto por um Gateway central, dispositivos inteligentes (sensores e atuadores) e um Cliente para controle e observação dos dispositivos. [cite_start]A comunicação entre os componentes utiliza sockets TCP e UDP, além de Protocol Buffers para serialização de mensagens. [cite_start]A descoberta de dispositivos é realizada via multicast UDP.

## Estrutura do Projeto

A estrutura de diretórios do projeto é organizada da seguinte forma:
```
.
├── src
│   ├── api                 # Abstrações de comunicação (se houver)
│   ├── devices             # Implementações de dispositivos
│   │   ├── atuadores       # Atuadores (Java)
│   │   └── sensors         # Sensores (Java)
│   │       └── TemperatureHumiditySensor.java
│   ├── front-end           # Cliente (ainda a ser definido)
│   ├── gateway             # Gateway (Python)
│   │   ├── src             # Código gerado pelo Protobuf para Python
│   │   │   └── proto
│   │   │       └── smart_city_pb2.py
│   │   └── smart_city_gateway.py
│   └── proto               # Definições de mensagens Protocol Buffers (.proto)
│       └── smart_city.proto
├── pom.xml                 # Configuração do Maven para componentes Java
├── requirements.txt        # Dependências Python
└── .gitignore              # Arquivos e diretórios a serem ignorados pelo Git
```

## Requisitos

Para executar os componentes atuais do projeto, você precisará ter instalado:

* **Java Development Kit (JDK) 21 LTS**
* **Apache Maven 3.9.10** (ou versão compatível)
* **Python 3.x**
* **Git**

## Configuração do Ambiente

### 1. Configurar Variáveis de Ambiente Java (Windows)

1.  **JDK 21.0.7 (Eclipse Adoptium):**
    * Abra as "Variáveis de Ambiente do Sistema".
    * Na seção "Variáveis do sistema", clique em "Novo...".
    * **Nome da variável:** `JAVA_HOME`
    * **Valor da variável:** `C:\Program Files\Eclipse Adoptium\jdk-21.0.7.6-hotspot` (ou o caminho exato da sua instalação).
    * Clique em "OK".
    * Na seção "Variáveis do sistema", encontre `Path`, selecione-o e clique em "Editar...".
    * Clique em "Novo" e adicione `%JAVA_HOME%\bin`.
    * Mova esta entrada para a **primeira posição** na lista usando os botões "Mover para Cima".
    * Clique em "OK" em todas as janelas.

### 2. Configurar Variáveis de Ambiente Maven (Windows)

1.  **Baixar Apache Maven:**
    * Acesse [https://maven.apache.org/download.cgi](https://maven.apache.org/download.cgi) e baixe a versão binária (`.zip`) do Apache Maven (e.g., `apache-maven-3.9.10-bin.zip`).
    * Descompacte o arquivo em um diretório como `C:\Program Files\Apache\apache-maven-3.9.10`.
2.  **Configurar Variáveis de Ambiente:**
    * Volte às "Variáveis de Ambiente do Sistema".
    * Na seção "Variáveis do sistema", clique em "Novo...".
    * **Nome da variável:** `M2_HOME`
    * **Valor da variável:** `C:\Program Files\Apache\apache-maven-3.9.10` (ou o caminho exato da sua instalação).
    * Clique em "OK".
    * Na seção "Variáveis do sistema", encontre `Path`, selecione-o e clique em "Editar...".
    * Clique em "Novo" e adicione `%M2_HOME%\bin`.
    * Clique em "OK" em todas as janelas.

### 3. Verificar Instalação

* Abra um **NOVO** Prompt de Comando (ou PowerShell).
* Verifique o Java:
    ```bash
    java -version
    javac -version
    echo %JAVA_HOME%
    ```
    Você deve ver as informações do JDK 21.0.7.
* Verifique o Maven:
    ```bash
    mvn -version
    ```
    Você deve ver as informações do Maven 3.9.10 e o JDK 21.0.7.

## Executando os Componentes

### 1. Configurar o Projeto Localmente

É **altamente recomendado** mover o projeto de diretórios de sincronização de nuvem (como Google Drive) para um diretório local padrão (ex: `C:\Projetos\Trabalho-SD`) para evitar problemas de sincronização e performance durante o desenvolvimento.

1.  Feche o VS Code e quaisquer terminais abertos no projeto.
2.  Mova a pasta `Trabalho-SD` (contendo todo o projeto) do Google Drive para o novo local (ex: `C:\Projetos\`).
3.  Abra o VS Code e o projeto a partir do **novo local** (`File > Open Folder...`).

### 2. Preparação dos Componentes Java (Sensores/Atuadores)

1.  **Certifique-se de que o arquivo `.gitignore` está configurado corretamente** na raiz do projeto para ignorar pastas geradas e arquivos de IDE, incluindo `.vscode/`, `/target/`, `/venv/`, `/src/gateway/src/`.
2.  Na raiz do seu projeto (onde o `pom.xml` está), abra um terminal (VS Code Terminal ou Prompt de Comando).
3.  Execute o Maven para gerar as classes Protocol Buffers para Java, compilar o código Java e empacotar o sensor:
    ```bash
    mvn clean install -U
    ```
    Este comando irá:
    * Baixar o compilador `protoc` (versão 3.25.1).
    * Gerar as classes Java do Protocol Buffers em `target/generated-sources/protobuf/java/smartcity/`.
    * Compilar o código Java (incluindo o gerado) e empacotar o sensor de temperatura em um JAR executável (`smart-city-java-components-1.0-SNAPSHOT-temperature-humidity-sensor.jar`) na pasta `target/`.

### 3. Preparação dos Componentes Python (Gateway)

1.  **Crie e ative um ambiente virtual Python (`venv`):**
    * Na raiz do seu projeto, no terminal, execute:
        ```bash
        python -m venv venv
        ```
    * Ative o ambiente virtual:
        ```bash
        .\venv\Scripts\activate
        ```
2.  **Crie o arquivo `requirements.txt`** na raiz do seu projeto com o seguinte conteúdo:
    ```
    protobuf==6.31.1
    ```
3.  **Instale as dependências Python** (com o ambiente virtual ativado):
    ```bash
    pip install -r requirements.txt
    ```
4.  **Gere as classes Protocol Buffers para Python:**
    * Na raiz do seu projeto, com o ambiente virtual ativado, execute o `protoc` para gerar as classes Python a partir do seu `.proto`. **A pasta de saída é `src/gateway/src/proto/`**:
        ```bash
        protoc --python_out=src/gateway/src/proto/ src/proto/smart_city.proto
        ```
        Isso criará o arquivo `smart_city_pb2.py` (e possivelmente `smart_city_pb2.pyi`) dentro de `src/gateway/src/proto/`.

## Instruções de Execução

Após a preparação de ambos os lados, você pode executar o Gateway e o Sensor.

1.  **Abra DOIS terminais separados.**

2.  **No PRIMEIRO Terminal (Para o Gateway Python):**
    * Navegue até a raiz do seu projeto.
    * Ative o ambiente virtual:
        ```bash
        .\venv\Scripts\activate
        ```
    * Execute o Gateway:
        ```bash
        python src/gateway/smart_city_gateway.py
        ```
    * O Gateway começará a logar suas ações, incluindo o envio de mensagens multicast para descobrir dispositivos e escutar conexões.

3.  **No SEGUNDO Terminal (Para o Sensor Java):**
    * Navegue até a pasta `target/` do seu projeto.
    * Execute o sensor usando o JAR com dependências. Você pode adicionar um ID para o sensor (opcional):
        ```bash
        java -jar smart-city-java-components-1.0-SNAPSHOT-jar-with-dependencies.jar MeuSensor01
        ```
    * O sensor começará a logar suas ações, como aguardar requisições de descoberta, enviar DeviceInfo para o Gateway (via TCP) e, em seguida, enviar dados periódicos (via UDP).

**Interação Observada:**

* No terminal do **Gateway (Python)**, você deverá ver logs indicando a descoberta do sensor (após a requisição multicast), o registro via TCP (recebendo o DeviceInfo) e, posteriormente, o recebimento dos dados sensoriados periodicamente (via UDP).
* No terminal do **Sensor (Java)**, você verá logs de que ele recebeu a requisição de descoberta do Gateway, enviou suas informações e está enviando dados periódicos.