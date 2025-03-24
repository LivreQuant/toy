# Trading Services

This directory contains the Kubernetes configurations for trading execution venues and market simulators.

## Components

### Execution Venues

- IEXG (IEX Global)
  - Market data gateway
  - Order gateway
- XNAS (Nasdaq)
  - Market data gateway
  - Order gateway
- XOSR (Smart Router)
  - Market data gateway
  - Order gateway
- XVWAP (VWAP Strategy)
  - Order gateway

### Market Simulators

- IEXG Simulator
- XNAS Simulator

## Dependencies

- Kafka infrastructure
- PostgreSQL database
- Trading services RBAC configuration

## Notes

- Each venue uses StatefulSets for consistent identity
- Simulators provide FIX protocol connectivity
- All components include monitoring
