# Trading Simulator Frontend Documentation

## Overview

This project is a modern, resilient frontend for a trading simulator application. It's designed to handle complex connectivity requirements in a Kubernetes environment, with features for session management, authentication, real-time market data processing, and order submission.

The codebase follows a structured architecture that separates concerns while providing a unified user experience. It's currently undergoing a migration from gRPC to a more web-friendly communication approach using REST APIs, WebSockets, and Server-Sent Events (SSE).

## Architecture

The application is structured around several key components:

### Core Infrastructure

1. **Authentication System**: Token-based auth with automatic refresh capabilities
2. **Connection Management**: Handles WebSocket and SSE connections with sophisticated retry logic
3. **Session Management**: Persistent sessions with cross-tab synchronization
4. **Error Handling**: Circuit breaker pattern and comprehensive error recovery

### Communication Protocols

1. **REST APIs**: Used for stateless operations like authentication and order submission
2. **WebSockets**: Manages session state and connection monitoring
3. **SSE (Server-Sent Events)**: Streams market data and order updates

### UI Components

1. **Pages**: Main views (Login, Home, Simulator)
2. **Common Components**: Reusable UI elements (ConnectionStatus, LoadingScreen, ErrorBoundary)
3. **Simulator Components**: Trading-specific UI components

## Core Services

### Authentication (AuthContext)

The authentication system is built around a `TokenManager` that handles token storage, refresh, and validation. It's integrated with a React context (`AuthContext`) to provide application-wide authentication state.

Key features:
- JWT token management with automatic refresh
- Persistent authentication across page reloads
- Integration with connection management for auto-disconnect on auth failure

### Connection Management (ConnectionContext)

A sophisticated connection management system that handles WebSocket and SSE connections with resilience features:
- Automatic reconnection with exponential backoff
- Circuit breaker pattern to prevent excessive reconnection attempts
- Connection quality monitoring
- Recovery strategies for network interruptions

### Session Management

Sessions are persisted in local storage and coordinated across browser tabs:
- Session ID management and storage
- Activity tracking
- Cross-tab session synchronization
- Reconnection attempt tracking

## UI Structure

### Pages

1. **LoginPage**: Authentication entry point
2. **HomePage**: Dashboard with system status and quick actions
3. **SimulatorPage**: Main trading interface with market data and order entry

### Common Components

1. **ConnectionStatus**: Visual indicator of connection state
2. **ConnectionRecoveryDialog**: User interface for manual reconnection
3. **ErrorBoundary**: Global error handling
4. **LoadingScreen**: Loading indicators

## Data Flow

1. **Authentication**: User logs in → tokens stored → connection initiated
2. **Session Creation**: Session created/retrieved → WebSocket connection established
3. **Market Data**: SSE connection streams real-time data → UI updates
4. **Order Submission**: User submits order → REST API call → confirmation

## Resilience Features

The application includes several mechanisms to handle network issues and service disruptions:

1. **Circuit Breaker**: Prevents repeated connection attempts when services are down
2. **Connection Recovery**: Automatic and manual recovery options for lost connections
3. **Token Refresh**: Seamless authentication token refresh
4. **Health Monitoring**: Connection quality tracking
5. **Graceful Degradation**: UI adjusts based on connection state

## Configuration

The application uses environment-specific configuration with sensible defaults:

- API endpoints for different environments (development, production, test)
- Connection parameters (timeout values, retry limits)
- Feature flags

## Key Components in Detail

### HttpClient

A wrapper around the Fetch API with enhanced features:
- Automatic authentication header injection
- Token refresh on 401 responses
- Retry logic for network failures and server errors
- Consistent error handling

### WebSocketManager

Manages WebSocket connections with:
- Automatic reconnection logic
- Heartbeat mechanism
- Circuit breaker implementation
- Event-based communication

### MarketDataStream

Handles Server-Sent Events (SSE) for real-time data:
- Automatic reconnection
- Data parsing and normalization
- Cached data management

### RecoveryManager

Implements recovery strategies for connection failures:
- Graduated recovery attempts
- Exponential backoff
- Recovery coordination

## Future Development Areas

Based on the codebase analysis, these areas could benefit from further work:

1. **Enhanced Error Handling**: More granular error states and user feedback
2. **Performance Optimization**: Memoization and render optimization
3. **State Management Refinement**: Potential Redux integration for complex state
4. **Testing Infrastructure**: Comprehensive test coverage
5. **Documentation**: Inline documentation improvements
6. **Accessibility**: ARIA compliance and keyboard navigation

## Project Structure

```
frontend/
├── src/
│   ├── api/                  # API client implementations
│   ├── components/           # React components
│   │   ├── Auth/             # Authentication components
│   │   ├── Common/           # Shared UI components
│   │   └── Simulator/        # Trading-specific components
│   ├── contexts/             # React contexts for state management
│   ├── pages/                # Page components
│   ├── services/             # Core services
│   │   ├── auth/             # Authentication services
│   │   ├── connection/       # Connection management
│   │   ├── session/          # Session management
│   │   ├── sse/              # Server-Sent Events handling
│   │   └── websocket/        # WebSocket management
│   ├── utils/                # Utility functions and classes
│   ├── App.tsx               # Main application component
│   └── index.tsx             # Application entry point
```

## Technical Highlights

1. **React Router Integration**: Clean routing with authentication protection
2. **Context API Usage**: Sophisticated state management without Redux
3. **TypeScript Implementation**: Strong typing throughout the application
4. **Event-Based Architecture**: Decoupled components communicating via events
5. **Resilient Network Layer**: Graceful handling of connectivity issues

## Conclusion

The Trading Simulator frontend is a well-structured React application with sophisticated state management and network resilience features. It handles the complex requirements of a real-time trading application while providing a responsive user experience across different network conditions.


# docker build -t trading-platform-frontend .
# sudo apt-get update
#  sudo apt-get install pass
#  gpg --full-generate-key
#  pass init sergio.daniel.marques.amaral@gmail.com
# sudo docker login registry.digitalocean.com
# docker tag trading-platform-frontend registry.digitalocean.com/ff-frontend/trading-platform-frontend:latest
# docker push registry.digitalocean.com/ff-frontend/trading-platform-frontend:latest
