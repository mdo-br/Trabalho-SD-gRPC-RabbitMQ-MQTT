# Frontend React para Controle de Dispositivos 

## Requisitos

- Node.js (versão 16 ou superior recomendada)  
- npm (gerenciador de pacotes do Node.js)


## Instalar dependências

```bash
 npm install
```

## Executar o backend
```bash
uvicorn src.api.src.api_server:app --reload --host 192.168.3.83 --port 8000 # mesmo IP que vai no frontend
```

## Executar o frontend
```bash
npm start
```

O app abrirá no navegador em: http://localhost:3000

## Funcionalidades
- Ligar/desligar dispositivos (botão ON/OFF)
- Alterar intervalo de captura dos sensores (campo numérico)
- Mostrar detalhes do sensor (temperatura, umidade, status customizado)
- Para alarmes, mostra som "BEEP, BEEP, BEEP..." somente quando ligado




---

