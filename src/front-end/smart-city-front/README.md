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
- Nos atuadores temos o botão ligar, que liga a lâmpada. Com a lâmpada ligada aparecer o botão desligar, que a desliga.
- Nos sensores, temos as seguintes opções:
Atualizar a frequência de envio definindo o intervalo e em seguida atualizar frequência. 
Pausar o envio de dados de um sensor, e quando estiver pausado é possível reativar.
Mostrar detalhes, que retorna a temperatura, umidade, frequência e o status.







---

