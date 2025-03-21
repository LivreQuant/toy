# OpenTP Database Setup

This repository contains the PostgreSQL database initialization scripts for OpenTP (Open Trading Platform).

## Structure

```
.
├── Dockerfile
├── init/
│   └── 00-init.sql          # Initial database and role setup
├── schemas/
│   ├── clientconfig.sql     # Client configuration schema
│   ├── referencedata.sql    # Reference data schema
│   └── users.sql            # Users schema
└── data/
    ├── clientconfig.sql     # Client configuration data
    ├── referencedata.sql    # Reference data (instruments, markets, listings)
    └── users.sql            # User data
```

## Description

- `init/00-init.sql`: Creates the opentp role and database, sets up permissions
- `schemas/`: Contains schema definitions for three main components:
  - Client configuration
  - Reference data (instruments, markets, listings)
  - Users
- `data/`: Contains the initial data for each schema

## Setup

1. Build the Docker image:

```bash
docker build -t opentp-db .
```

2. Run the container:

```bash
docker run -d \
  --name opentp-db \
  -p 5432:5432 \
  -e POSTGRES_PASSWORD=password \
  opentp-db
```

## Database Schema

The database consists of three main schemas:

1. `clientconfig`: Stores user interface configurations
2. `referencedata`: Stores financial instruments, markets, and listings
3. `users`: Stores user information and permissions

## Development

To modify the database:

1. Update relevant schema files in `schemas/`
2. Update corresponding data files in `data/`
3. Rebuild and run the container

## Notes

- Based on Bitnami PostgreSQL 11.8.0
- Initialization scripts run in alphabetical order
- All schemas are owned by the opentp role

## Original Source

This is derived from the original `opentp.db` file, split into maintainable components.

## Access DB

docker exec -it $(docker ps -q -f name=postgres) psql -U opentp -d opentp

clientconfig
fx
marketdata
orders
users
