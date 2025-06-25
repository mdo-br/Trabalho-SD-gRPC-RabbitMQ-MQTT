# Script PowerShell para o projeto SmartCity
# Equivalente ao Makefile para Windows

param(
    [Parameter(Position=0)]
    [string]$Command = "help"
)

# Variáveis
$PROTO_DIR = "src/proto"
$PROTO_FILE = "$PROTO_DIR/smart_city.proto"
$PYTHON_OUT = $PROTO_DIR

function Show-Help {
    Write-Host "Comandos disponíveis:" -ForegroundColor Green
    Write-Host "  proto     - Gera código Python a partir do arquivo .proto"
    Write-Host "  clean     - Remove arquivos gerados"
    Write-Host "  install   - Instala dependências Python"
    Write-Host "  test      - Executa testes (se existirem)"
    Write-Host "  run-client - Executa o cliente de teste"
    Write-Host "  run-gateway - Executa o gateway"
    Write-Host "  run-api   - Executa a API server"
    Write-Host "  dev-client - Gera proto e executa cliente"
    Write-Host "  dev-gateway - Gera proto e executa gateway"
    Write-Host "  dev-api   - Gera proto e executa API"
    Write-Host "  status    - Mostra status do projeto"
}

function Generate-Proto {
    Write-Host "Gerando código Python a partir de $PROTO_FILE..." -ForegroundColor Yellow
    protoc --proto_path=$PROTO_DIR --python_out=$PYTHON_OUT $PROTO_FILE
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Código gerado com sucesso em $PYTHON_OUT/smart_city_pb2.py" -ForegroundColor Green
    } else {
        Write-Host "Erro ao gerar código Python" -ForegroundColor Red
    }
}

function Clean-Files {
    Write-Host "Removendo arquivos gerados..." -ForegroundColor Yellow
    if (Test-Path "$PROTO_DIR/smart_city_pb2.py") {
        Remove-Item "$PROTO_DIR/smart_city_pb2.py" -Force
    }
    if (Test-Path "$PROTO_DIR/src/proto/smart_city_pb2.py") {
        Remove-Item "$PROTO_DIR/src/proto/smart_city_pb2.py" -Force
    }
    if (Test-Path "$PROTO_DIR/__pycache__") {
        Remove-Item "$PROTO_DIR/__pycache__" -Recurse -Force
    }
    Write-Host "Limpeza concluída" -ForegroundColor Green
}

function Install-Dependencies {
    Write-Host "Instalando dependências Python..." -ForegroundColor Yellow
    pip install -r requirements.txt
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Dependências instaladas" -ForegroundColor Green
    } else {
        Write-Host "Erro ao instalar dependências" -ForegroundColor Red
    }
}

function Run-Client {
    Write-Host "Executando cliente de teste..." -ForegroundColor Yellow
    Set-Location "src/client-test"
    python smart_city_client.py
    Set-Location "../.."
}

function Run-Gateway {
    Write-Host "Executando gateway..." -ForegroundColor Yellow
    Set-Location "src/gateway"
    python smart_city_gateway.py
    Set-Location "../.."
}

function Run-API {
    Write-Host "Executando API server..." -ForegroundColor Yellow
    Set-Location "src/api"
    python api_server.py
    Set-Location "../.."
}

function Run-Tests {
    Write-Host "Executando testes..." -ForegroundColor Yellow
    if (Test-Path "tests") {
        python -m pytest tests/ -v
    } else {
        Write-Host "Nenhum teste encontrado" -ForegroundColor Yellow
    }
}

function Show-Status {
    Write-Host "=== Status do Projeto SmartCity ===" -ForegroundColor Cyan
    Write-Host "Arquivo .proto: $PROTO_FILE"
    
    if (Test-Path $PROTO_FILE) {
        Write-Host "✓ Arquivo .proto encontrado" -ForegroundColor Green
    } else {
        Write-Host "✗ Arquivo .proto não encontrado" -ForegroundColor Red
    }
    
    if (Test-Path "$PYTHON_OUT/smart_city_pb2.py") {
        Write-Host "✓ Código Python gerado" -ForegroundColor Green
    } else {
        Write-Host "✗ Código Python não gerado (execute './build.ps1 proto')" -ForegroundColor Red
    }
    
    if (Test-Path "requirements.txt") {
        Write-Host "✓ requirements.txt encontrado" -ForegroundColor Green
    } else {
        Write-Host "✗ requirements.txt não encontrado" -ForegroundColor Red
    }
    
    Write-Host "================================" -ForegroundColor Cyan
}

# Execução principal
switch ($Command.ToLower()) {
    "help" { Show-Help }
    "proto" { Generate-Proto }
    "clean" { Clean-Files }
    "install" { Install-Dependencies }
    "test" { Run-Tests }
    "run-client" { Run-Client }
    "run-gateway" { Run-Gateway }
    "run-api" { Run-API }
    "dev-client" { Generate-Proto; Run-Client }
    "dev-gateway" { Generate-Proto; Run-Gateway }
    "dev-api" { Generate-Proto; Run-API }
    "status" { Show-Status }
    default {
        Write-Host "Comando '$Command' não reconhecido." -ForegroundColor Red
        Show-Help
    }
} 