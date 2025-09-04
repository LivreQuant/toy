# WebSocket Package Migration Guide

## Overview
This guide explains how to migrate from the old websocket and connection services to the new `@trading-app/websocket` package.

## Changes Made

### 1. Dependency Injection
- All services now use constructor injection instead of direct imports
- State management is injected rather than directly imported
- Toast notifications are injected rather than directly imported
- Configuration is injected rather than directly imported

### 2. Package Structure
@trading-app/websocket/
├── types/          # All type definitions
├── client/         # Core connection management
├── handlers/       # Message-specific handlers
├── services/       # Supporting services
└── utils/          # Helper utilities and factories

### 3. Key Benefits
- **Testability**: All dependencies can be mocked
- **Reusability**: Package can be used in different contexts
- **Maintainability**: Clear separation of concerns
- **Type Safety**: Comprehensive TypeScript support

## Migration Steps

### 1. Install the Package
Add to your package.json dependencies:
```json
{
  "dependencies": {
    "@trading-app/websocket": "file:../packages/websocket"
  }
}