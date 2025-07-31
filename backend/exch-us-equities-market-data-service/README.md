# Market Data Service - PostgreSQL Edition

A controlled market data service that generates predictable test data and stores it directly in PostgreSQL.

## Overview

The Market Data Service generates controlled, predictable market data based on JSON configuration files. All data is stored directly in PostgreSQL using the `exch_us_equity` schema - no CSV files are generated.

## Features

- **Controlled Data Generation**: Generates predictable market data from JSON configuration
- **PostgreSQL Storage**: Stores all data directly in `exch_us_equity.equity_data` and `exch_us_equity.fx_data` tables
- **Real-time Streaming**: Streams data to Exchange Simulator subscribers via gRPC
- **Timezone Support**: Handles different market timezones properly
- **Health Monitoring**: Provides health checks, stats, and metrics endpoints
- **Database Metrics**: Tracks successful saves and errors

## Configuration

The service loads configuration from JSON files. Key parameters:

| Field | Description | Example |
|-------|-------------|---------|
| config_name | Human-readable config name | "PostgreSQL Test" |
| timezone | Market timezone | "America/New_York" |
| start_time | Simulation start time | "2024-01-01T09:30:00" |
| time_increment_minutes | Minutes between updates | 1 |
| server_port | gRPC server port | 50060 |
| equity | Array of equity configurations | See example below |
| fx | Array of FX rate configurations | See example below |

### Example JSON Configuration

```json
{
    "config_name": "Basic PostgreSQL Test",
    "timezone": "America/New_York",
    "start_time": "2024-01-01T09:30:00", 
    "time_increment_minutes": 1,
    "server_port": 50060,
    "equity": [
        {
            "symbol": "AAPL",
            "starting_price": 190.00,
            "price_change_per_minute": 0.01,
            "base_volume": 10000,
            "trade_count": 100,
            "currency": "USD",
            "vwas": 0.0050,
            "vwav": 0.0050,
            "exchange": "NASDAQ"
        }
    ],
    "fx": [
        {
            "from_currency": "USD",
            "to_currency": "EUR",
            "starting_rate": 0.8500,
            "rate_change_per_minute": 0.0001
        }
    ]
}

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| CONFIG_FILE | JSON configuration file | test_0.json |
| API_HOST | gRPC server host | 0.0.0.0 |
| API_PORT | gRPC server port | 50060 |
| DB_HOST | PostgreSQL host | postgres |
| DB_PORT | PostgreSQL port | 5432 |
| DB_NAME | Database name | opentp |
| DB_USER | Database user | opentp |
| DB_PASSWORD | Database password | samaral |
| LOG_LEVEL | Logging level | INFO |

## Database Schema

The service automatically creates the required schema and tables:

### exch_us_equity.equity_data
- equity_id (UUID, Primary Key)
- timestamp (TIMESTAMP WITH TIME ZONE)
- symbol (VARCHAR(20))
- currency (VARCHAR(3))
- open, high, low, close (DECIMAL(12,4))
- vwap, vwas, vwav (DECIMAL(12,4))
- volume (BIGINT)
- count (INTEGER)

### exch_us_equity.fx_data
- fx_id (UUID, Primary Key)
- timestamp (TIMESTAMP WITH TIME ZONE)
- from_currency, to_currency (VARCHAR(3))
- rate (DECIMAL(12,6))

## API Endpoints

### gRPC Service
- **SubscribeMarketData**: Stream market data to subscribers

### HTTP Health Checks
- **GET /health**: Service health status
- **GET /stats**: Detailed service statistics
- **GET /metrics**: Prometheus-style metrics

## Running the Service

### Docker
```bash
docker build -t market-data-service .
docker run -e CONFIG_FILE=test_0.json \
           -e DB_HOST=postgres \
           -e DB_USER=opentp \
           -e DB_PASSWORD=samaral \
           -p 50060:50060 \
           -p 50061:50061 \
           market-data-service