// src/services/connections/ConnectionHeartbeat.ts
import { EnhancedConnectionManager } from './EnhancedConnectionManager';
import { ConnectionNetworkManager } from './ConnectionNetworkManager';
import { SessionStore } from '../session/SessionStore';

export class ConnectionHeartbeat {
  private manager: EnhancedConnectionManager;
  private config: any;
  
  // Heartbeat tracking
  private lastHeartbeatResponse: number = Date.now();
  private heartbeatLatency: number | null = null;
  private heartbeatInterval: NodeJS.Timeout | null = null;
  private consecutiveHeartbeatMisses: number = 0;
  private maxHeartbeatMisses: number = 3;
  
  constructor(manager: EnhancedConnectionManager, config: any) {
    this.manager = manager;
    this.config = config;
  }
  
  public startHeartbeats(): void {
    this.clearIntervals();
    
    // Start more frequent heartbeats
    this.heartbeatInterval = setInterval(() => {
      this.sendHeartbeat();
    }, this.config.heartbeatIntervalMs || 5000); // Default to 5 seconds
  }
  
  public clearIntervals(): void {
    if (this.heartbeatInterval) {
      clearInterval(this.heartbeatInterval);
      this.heartbeatInterval = null;
    }
  }
  
  private async sendHeartbeat(): Promise<void> {
    const session = SessionStore.getSession();
    if (!session || !session.token || !session.sessionId) {
      return;
    }
    
    try {
      // Record time before heartbeat
      const heartbeatSentTime = Date.now();
      
      // Send heartbeat
      const url = ConnectionNetworkManager.createServiceUrl('session', 'keep-alive');
      const response = await fetch(url, {
        method: 'POST',
        ...ConnectionNetworkManager.getFetchOptions({
          headers: {
            'Authorization': `Bearer ${session.token}`
          },
          body: JSON.stringify({
            sessionId: session.sessionId,
            timestamp: Date.now()
          })
        })
      });
      
      if (response.ok) {
        // Update last successful heartbeat time
        this.lastHeartbeatResponse = Date.now();
        this.consecutiveHeartbeatMisses = 0;
        
        // Calculate latency for monitoring
        this.heartbeatLatency = this.lastHeartbeatResponse - heartbeatSentTime;
        
        // Emit heartbeat event with latency info
        this.manager.emit('heartbeat', { 
          success: true, 
          latency: this.heartbeatLatency,
          timestamp: this.lastHeartbeatResponse
        });
        
        // Update session activity
        SessionStore.updateActivity();
      } else {
        this.handleHeartbeatFailure('server_rejected');
      }
    } catch (error) {
      this.handleHeartbeatFailure('network_error', error);
    }
  }
  
  private handleHeartbeatFailure(reason: string, error?: any): void {
    this.consecutiveHeartbeatMisses++;
    

    // Check for server shutdown signals
    if (error && typeof error.message === 'string' && 
        (error.message.includes('shutting down') || 
        error.message.includes('Service unavailable'))) {
    
        console.warn('Server is shutting down for maintenance');
        this.manager.emit('heartbeat', {
            success: false,
            reason: 'server_maintenance',
            error,
            maintenanceMode: true
        });
        
        // Show maintenance notification to user
        // This could dispatch to your UI notification system
        this.showMaintenanceNotification();
        
        // Use a longer delay before reconnecting to allow deployment to complete
        setTimeout(() => {
            this.manager.reconnectWithBackoff();
        }, 10000); // 10 second delay
        
        return;
    }

    this.manager.emit('heartbeat', {
      success: false,
      reason,
      error,
      consecutiveMisses: this.consecutiveHeartbeatMisses,
      maxMisses: this.maxHeartbeatMisses
    });
    
    // If we've missed too many heartbeats in a row, consider connection lost
    if (this.consecutiveHeartbeatMisses >= this.maxHeartbeatMisses) {
      console.warn(`Missed ${this.consecutiveHeartbeatMisses} heartbeats. Connection considered unstable.`);
      
      if (this.manager.getState() === 'CONNECTED') {
        this.manager.setState('DISCONNECTED');
        this.manager.checkAndReconnect();
      }
    }
  }
  
  // Public getters for state
  public getLastHeartbeatTime(): number {
    return this.lastHeartbeatResponse;
  }
  
  public getHeartbeatLatency(): number | null {
    return this.heartbeatLatency;
  }
  
  public getConsecutiveMisses(): number {
    return this.consecutiveHeartbeatMisses;
  }
}