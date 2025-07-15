#!/bin/bash

# Script to generate protobuf files correctly

echo "Generating protobuf files..."

# Clean the output directory
rm -rf target/generated-sources/protobuf/java/*
mkdir -p target/generated-sources/protobuf/java

# Generate Java classes from proto files
echo "Generating Java classes..."
protoc --java_out=target/generated-sources/protobuf/java --proto_path=src/proto src/proto/smart_city.proto
#protoc --java_out=target/generated-sources/protobuf/java --proto_path=src/proto src/proto/actuator_service.proto

# Generate gRPC service files
echo "Generating gRPC service files..."
protoc --plugin=protoc-gen-grpc-java=/home/mdo/Projetos/Trabalho-SD-RabbitMQ-MQTT-gRPC/target/protoc-plugins/protoc-gen-grpc-java-1.58.0-linux-x86_64.exe --grpc-java_out=target/generated-sources/protobuf/java --proto_path=src/proto src/proto/actuator_service.proto

echo "Files generated successfully!"
echo "Generated files:"
find target/generated-sources/protobuf/java -name "*.java" -type f
