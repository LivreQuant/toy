// frontend_dist/packages/websocket/src/utils/debug-utils.ts
import { getLogger } from '@trading-app/logging';

const logger = getLogger('WebSocketDebug');

export function debugConnectionManagerInstances(connectionManager: any): void {
  logger.info('🔍 CONNECTION MANAGER INSTANCE DEBUG');
  
  console.group('🔍 CONNECTION MANAGER DEBUG');
  
  // Main ConnectionManager info
  console.log('ConnectionManager:', {
    instance: connectionManager,
    isDisposed: connectionManager.isDisposed,
    desiredState: connectionManager.desiredState
  });
  
  // SocketClient instances
  const mainSocketClient = connectionManager.socketClient || connectionManager.getSocketClient?.();
  const heartbeatClient = connectionManager.heartbeat?.client;
  const sessionClient = connectionManager.sessionHandler?.client;
  const simulatorSocketClient = connectionManager.simulatorClient?.socketClient || connectionManager.simulatorClient?.getSocketClient?.();
  
  // 🚨 FIXED: Use public getters instead of private properties
  console.log('SocketClient Instances:', {
    main: {
      instance: mainSocketClient,
      instanceId: mainSocketClient?.getInstanceId?.(),
      socketInfo: mainSocketClient?.getSocketInfo?.(), // ✅ Use public getter
      status: mainSocketClient?.getCurrentStatus?.()
    },
    heartbeat: {
      instance: heartbeatClient,
      instanceId: heartbeatClient?.getInstanceId?.(),
      socketInfo: heartbeatClient?.getSocketInfo?.(), // ✅ Use public getter
      status: heartbeatClient?.getCurrentStatus?.()
    },
    session: {
      instance: sessionClient,
      instanceId: sessionClient?.getInstanceId?.(),
      socketInfo: sessionClient?.getSocketInfo?.(), // ✅ Use public getter
      status: sessionClient?.getCurrentStatus?.()
    },
    simulator: {
      instance: simulatorSocketClient,
      instanceId: simulatorSocketClient?.getInstanceId?.(),
      socketInfo: simulatorSocketClient?.getSocketInfo?.(), // ✅ Use public getter
      status: simulatorSocketClient?.getCurrentStatus?.()
    }
  });
  
  // Instance equality check
  const instancesMatch = {
    mainVsHeartbeat: mainSocketClient === heartbeatClient,
    mainVsSession: mainSocketClient === sessionClient,
    mainVsSimulator: mainSocketClient === simulatorSocketClient,
    allMatch: (
      mainSocketClient === heartbeatClient &&
      mainSocketClient === sessionClient &&
      mainSocketClient === simulatorSocketClient
    )
  };
  
  console.log('Instance Equality:', instancesMatch);
  
  // 🚨 FIXED: Use public getters for socket state
  console.log('Socket States:', {
    mainHasSocket: mainSocketClient?.getSocketInfo?.()?.hasSocket,
    heartbeatHasSocket: heartbeatClient?.getSocketInfo?.()?.hasSocket,
    sessionHasSocket: sessionClient?.getSocketInfo?.()?.hasSocket,
    simulatorHasSocket: simulatorSocketClient?.getSocketInfo?.()?.hasSocket
  });
  
  if (!instancesMatch.allMatch) {
    console.error('🚨 CRITICAL: Not all services are using the same SocketClient instance!');
  } else {
    console.log('✅ SUCCESS: All services are using the same SocketClient instance');
  }
  
  console.groupEnd();
}

// Global function for browser console debugging
if (typeof window !== 'undefined') {
  (window as any).debugWebSocketInstances = (connectionManager: any) => {
    debugConnectionManagerInstances(connectionManager);
  };
}