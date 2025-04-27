# Market Data Distributor Service

A service that generates and distributes market data to exchange simulator instances.

## Overview

The Market Data Distributor Service simulates a real-time market data feed by:
1. Generating realistic market data for configured symbols
2. Distributing this data to registered Exchange Simulator instances
3. Providing an API for Exchange Simulators to register and unregister

## Features

- **Realistic Market Data Generation**: Produces minute bar data with bid/ask prices, sizes, and other market metrics
- **Scheduled Operation**: Runs during configured market hours (default: 3AM-8PM)
- **Self-registration API**: Exchange Simulators can register themselves to receive data
- **Fault Tolerance**: Detects and removes failed Exchange Simulator instances
- **Health Monitoring**: Provides health check and status endpoints

## Configuration

The service is configured via environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| API_HOST | Host to bind the API server | 0.0.0.0 |
| API_PORT | Port for the API server | 50060 |
| SYMBOLS | Comma-separated list of ticker symbols | AAPL,GOOGL,MSFT,AMZN,TSLA,FB |
| UPDATE_INTERVAL | Interval in seconds between market data updates | 60 |
| STARTUP_HOUR | Hour of day to start operations (24h format) | 3 |
| SHUTDOWN_HOUR | Hour of day to stop operations (24h format) | 20 |
| LOG_LEVEL | Logging level | INFO |
| EXCHANGE_SERVICE_NAME | Kubernetes service name for Exchange Simulators | exchange-simulator |
| EXCHANGE_SERVICE_PORT | gRPC port for Exchange Simulators | 50055 |

## API Endpoints

### Register Exchange Simulator