// src/services/sse/sse-client.ts
import { TokenManager } from '../auth/token-manager';
import { BackoffStrategy } from '../websocket/backoff-strategy';

export interface SSEOptions {
  reconnectMaxAttempts?: number;
  initialReconnectDelayMs?: number;
  maxReconnectDelayMs?: number;
  reconnectOnError?: boolean;
}

export class SSEClient {
  private url: string;
  private tokenManager: TokenManager;
  private eventSource: EventSource | null = null;
  private backoffStrategy: BackoffStrategy;
  private isConnecting: boolean = false;
  private reconnectTimer: number | null = null;
  private sessionId: string | null = null;
  private eventHandlers: Map<string, Set<Function>> = new Map();
  private reconnectAttempt: number = 0;
  private maxReconnectAttempts: number;
  private reconnectOnError: boolean;
  private lastEventId: string | null = null;
  private params: Record<string, string> = {};
  
  constructor(url: string, tokenManager: TokenManager, options: SSEOptions = {}) {
    this.url = url;
    this.tokenManager = tokenManager;
    this.backoffStrategy = new BackoffStrategy(
      options.initialReconnectDelayMs || 1000,
      options.maxReconnectDelayMs || 30000
    );
    this.maxReconnectAttempts = options.reconnectMaxAttempts || 10;
    this.reconnectOnError = options.reconnectOnError !== false;
  }
  
  public async connect(sessionId: string, params: Record<string, string> = {}): Promise<boolean> {
    if (this.eventSource && this.eventSource.readyState === EventSource.OPEN) {
      return true;
    }
    
    if (this.isConnecting) {
      return new Promise<boolean>(resolve => {
        this.once('open', () => resolve(true));
        this.once('error', () => resolve(false));
      });
    }
    
    this.isConnecting = true;
    this.sessionId = sessionId;
    this.params = { ...params };
    
    try {
      // Close existing connection if any
      this.close();
      
      const token = await this.tokenManager.getAccessToken();
      if (!token) {
        this.isConnecting = false;
        return false;
      }
      
      // Add session ID, token and other params to the URL
      let sseUrl = `${this.url}?sessionId=${sessionId}&token=${token}`;
      
      // Add any additional parameters
      Object.entries(params).forEach(([key, value]) => {
        sseUrl += `&${key}=${encodeURIComponent(value)}`;
      });
      
      // Add last event ID if available for resuming stream
      if (this.lastEventId) {
        sseUrl += `&lastEventId=${this.lastEventId}`;
      }
      
      // Create SSE connection
      this.eventSource = new EventSource(sseUrl);
      
      return new Promise<boolean>((resolve) => {
        if (!this.eventSource) {
          this.isConnecting = false;
          resolve(false);
          return;
        }
        
        // Handle SSE events
        this.eventSource.onopen = () => {
          this.isConnecting = false;
          this.reconnectAttempt = 0;
          this.backoffStrategy.reset();
          this.emit('open', { connected: true });
          resolve(true);
        };
        
        this.eventSource.onerror = (error) => {
          console.error('SSE error:', error);
          this.emit('error', { error });
          
          if (this.isConnecting) {
            this.isConnecting = false;
            resolve(false);
          }
          
          // Handle reconnection on error
          if (this.reconnectOnError) {
            this.handleDisconnect();
          }
        };
        
        // Add message event listener
        this.eventSource.addEventListener('message', (event: MessageEvent) => {
          this.handleMessage(event);
        });
        
        // Add custom event listeners
        ['market-data', 'order-update', 'portfolio-update', 'connection', 'error'].forEach(eventType => {
          this.eventSource?.addEventListener(eventType, (event: MessageEvent) => {
            this.handleEvent(eventType, event);
          });
        });
      });
    } catch (error) {
      console.error('SSE connection error:', error);
      this.isConnecting = false;
      return false;
    }
  }
  
  public close(): void {
    this.stopReconnectTimer();
    
    if (this.eventSource) {
      this.eventSource.close();
      this.eventSource = null;
    }
    
    this.emit('close', { reason: 'user_disconnect' });
  }
  
  public on(event: string, callback: Function): void {
    if (!this.eventHandlers.has(event)) {
      this.eventHandlers.set(event, new Set());
    }
    
    this.eventHandlers.get(event)?.add(callback);
  }
  
  public off(event: string, callback: Function): void {
    const callbacks = this.eventHandlers.get(event);
    if (callbacks) {
      callbacks.delete(callback);
    }
  }
  
  public once(event: string, callback: Function): void {
    const onceCallback = (...args: any[]) => {
      this.off(event, onceCallback);
      callback(...args);
    };
    
    this.on(event, onceCallback);
  }
  
  private emit(event: string, data: any): void {
    const callbacks = this.eventHandlers.get(event);
    if (callbacks) {
      callbacks.forEach(callback => {
        try {
          callback(data);
        } catch (error) {
          console.error(`Error in SSE event handler for ${event}:`, error);
        }
      });
    }
    
    // Also emit to wildcard listeners
    const wildcardCallbacks = this.eventHandlers.get('*');
    if (wildcardCallbacks) {
      wildcardCallbacks.forEach(callback => {
        try {
          callback(event, data);
        } catch (error) {


// src/services/sse/sse-client.ts (continued)
private handleMessage(event: MessageEvent): void {
    try {
      // Store last event ID for resuming stream if available
      if (event.lastEventId) {
        this.lastEventId = event.lastEventId;
      }
      
      // Parse message data if it's a string
      let data = event.data;
      if (typeof data === 'string') {
        try {
          data = JSON.parse(data);
        } catch {
          // Keep as string if not valid JSON
        }
      }
      
      // Emit the message event
      this.emit('message', data);
    } catch (error) {
      console.error('Error handling SSE message:', error);
    }
  }
  
  private handleEvent(eventType: string, event: MessageEvent): void {
    try {
      // Store last event ID for resuming stream if available
      if (event.lastEventId) {
        this.lastEventId = event.lastEventId;
      }
      
      // Parse event data if it's a string
      let data = event.data;
      if (typeof data === 'string') {
        try {
          data = JSON.parse(data);
        } catch {
          // Keep as string if not valid JSON
        }
      }
      
      // Emit the specific event type
      this.emit(eventType, data);
    } catch (error) {
      console.error(`Error handling SSE event ${eventType}:`, error);
    }
  }
  
  private handleDisconnect(): void {
    if (this.eventSource) {
      this.eventSource.close();
      this.eventSource = null;
    }
    
    this.emit('close', { reason: 'error' });
    
    // Attempt to reconnect
    this.attemptReconnect();
  }
  
  private attemptReconnect(): void {
    if (this.reconnectTimer !== null) {
      return; // Already trying to reconnect
    }
    
    if (this.reconnectAttempt >= this.maxReconnectAttempts) {
      this.emit('max_reconnect_attempts', { attempts: this.reconnectAttempt });
      return;
    }
    
    this.reconnectAttempt++;
    
    const delay = this.backoffStrategy.nextBackoffTime();
    
    this.emit('reconnecting', { 
      attempt: this.reconnectAttempt, 
      maxAttempts: this.maxReconnectAttempts,
      delay
    });
    
    this.reconnectTimer = window.setTimeout(async () => {
      this.reconnectTimer = null;
      
      if (this.sessionId) {
        const connected = await this.connect(this.sessionId, this.params);
        
        if (!connected) {
          // If connection failed, try again
          this.attemptReconnect();
        }
      }
    }, delay);
  }
  
  private stopReconnectTimer(): void {
    if (this.reconnectTimer !== null) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
  }
}