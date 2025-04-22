// Create src/state/app-state-adapter.ts
import { connectionState, ConnectionStatus, ConnectionQuality } from './connection-state';
import { authState } from './auth-state';

// Re-export the needed types
export { ConnectionStatus, ConnectionQuality };

// Create adapter functions that components can use temporarily
export const appStateAdapter = {
  // Get the connection slice
  getConnectionState: () => connectionState.getState(),
  
  // Get the auth slice
  getAuthState: () => authState.getState(),
  
  // Update connection state
  updateConnectionState: (changes: Partial<ReturnType<typeof connectionState.getState>>) => {
    connectionState.updateState(changes);
  },
  
  // Update auth state
  updateAuthState: (changes: Partial<ReturnType<typeof authState.getState>>) => {
    authState.updateState(changes);
  }
};

// For components that directly import from app-state.service
export { appStateAdapter as appState };