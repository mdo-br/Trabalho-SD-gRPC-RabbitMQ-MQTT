#!/bin/bash

# Script to generate protobuf files correctly

echo "Generating protobuf files..."

# Clean the output directory
rm -rf target/generated-sources/protobuf/java/*
mkdir -p target/generated-sources/protobuf/java

# Generate Java classes from proto files
echo "Generating Java classes..."
protoc --java_out=target/generated-sources/protobuf/java --proto_path=src/proto src/proto/smart_city.proto
protoc --java_out=target/generated-sources/protobuf/java --proto_path=src/proto src/proto/actuator_service.proto

# Generate gRPC service files
echo "Generating gRPC service files..."
if [ -f "target/protoc-plugins/protoc-gen-grpc-java-1.58.0-linux-x86_64.exe" ]; then
    protoc --plugin=protoc-gen-grpc-java=target/protoc-plugins/protoc-gen-grpc-java-1.58.0-linux-x86_64.exe --grpc-java_out=target/generated-sources/protobuf/java --proto_path=src/proto src/proto/actuator_service.proto
else
    echo "Plugin gRPC Java não encontrado. Execute 'make install-grpc-plugin' ou 'make setup-local INFRA=1' para instalar."
    echo "Pulando geração de arquivos gRPC Java..."
fi

echo "Files generated successfully!"
echo "Generated files:"
find target/generated-sources/protobuf/java -name "*.java" -type f
