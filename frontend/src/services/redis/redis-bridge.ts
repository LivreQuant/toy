// src/services/redis/redis-bridge.ts

import Redis from 'ioredis';

export interface RedisConfig {
  host: string;
  port: number;
  password?: string;
  db?: number;
  keyPrefix?: string;
}

export class RedisBridge {
  private client: Redis;
  private subscriber: Redis;
  private eventHandlers: Map<string, Set<(data: any) => void>> = new Map();
  
  constructor(config: RedisConfig) {
    // Create main Redis client
    this.client = new Redis({
      host: config.host,
      port: config.port,
      password: config.password,
      db: config.db || 0,
      keyPrefix: config.keyPrefix || 'trading-platform:',
      // Reconnection settings
      retryStrategy: (times) => {
        const delay = Math.min(times * 100, 3000);
        return delay;
      }
    });
    
    // Create separate client for pub/sub (as per Redis best practices)
    this.subscriber = new Redis({
      host: config.host,
      port: config.port,
      password: config.password,
      db: config.db || 0
    });
    
    // Set up message handler
    this.subscriber.on('message', (channel, message) => {
      try {
        const data = JSON.parse(message);
        const handlers = this.eventHandlers.get(channel);
        
        if (handlers) {
          handlers.forEach(handler => handler(data));
        }
      } catch (error) {
        console.error(`Error handling Redis message on channel ${channel}:`, error);
      }
    });
  }
  
  // Store session data in Redis
  public async storeSessionData(sessionId: string, data: any, expirySeconds = 3600): Promise<boolean> {
    try {
      const key = `session:${sessionId}`;
      await this.client.set(key, JSON.stringify(data), 'EX', expirySeconds);
      return true;
    } catch (error) {
      console.error('Error storing session data in Redis:', error);
      return false;
    }
  }
  
  // Get session data from Redis
  public async getSessionData(sessionId: string): Promise<any | null> {
    try {
      const key = `session:${sessionId}`;
      const data = await this.client.get(key);
      
      if (!data) return null;
      
      return JSON.parse(data);
    } catch (error) {
      console.error('Error getting session data from Redis:', error);
      return null;
    }
  }
  
  // Update session TTL
  public async updateSessionTTL(sessionId: string, expirySeconds = 3600): Promise<boolean> {
    try {
      const key = `session:${sessionId}`;
      const result = await this.client.expire(key, expirySeconds);
      return result === 1;
    } catch (error) {
      console.error('Error updating session TTL in Redis:', error);
      return false;
    }
  }
  
  // Store connection metrics
  public async storeConnectionMetrics(sessionId: string, metrics: any): Promise<boolean> {
    try {
      const key = `connection:${sessionId}:metrics`;
      await this.client.set(key, JSON.stringify(metrics), 'EX', 300); // 5 minute expiry
      return true;
    } catch (error) {
      console.error('Error storing connection metrics in Redis:', error);
      return false;
    }
  }
  
  // Subscribe to a channel
  public async subscribe(channel: string, handler: (data: any) => void): Promise<boolean> {
    try {
      // Add handler to map
      if (!this.eventHandlers.has(channel)) {
        this.eventHandlers.set(channel, new Set());
      }
      
      this.eventHandlers.get(channel)!.add(handler);
      
      // Subscribe to Redis channel
      await this.subscriber.subscribe(channel);
      return true;
    } catch (error) {
      console.error(`Error subscribing to Redis channel ${channel}:`, error);
      return false;
    }
  }
  
  // Unsubscribe from a channel
  public async unsubscribe(channel: string, handler?: (data: any) => void): Promise<boolean> {
    try {
      if (handler && this.eventHandlers.has(channel)) {
        // Remove specific handler
        this.eventHandlers.get(channel)!.delete(handler);
        
        // If no more handlers, unsubscribe
        if (this.eventHandlers.get(channel)!.size === 0) {
          await this.subscriber.unsubscribe(channel);
          this.eventHandlers.delete(channel);
        }
      } else {
        // Remove all handlers for this channel
        await this.subscriber.unsubscribe(channel);
        this.eventHandlers.delete(channel);
      }
      
      return true;
    } catch (error) {
      console.error(`Error unsubscribing from Redis channel ${channel}:`, error);
      return false;
    }
  }
  
  // Publish a message to a channel
  public async publish(channel: string, data: any): Promise<boolean> {
    try {
      const message = typeof data === 'string' ? data : JSON.stringify(data);
      await this.client.publish(channel, message);
      return true;
    } catch (error) {
      console.error(`Error publishing to Redis channel ${channel}:`, error);
      return false;
    }
  }
  
  // Track user connection to a specific pod
  public async trackPodConnection(sessionId: string, podId: string): Promise<boolean> {
    try {
      // Store mapping of session to pod
      await this.client.set(`session:${sessionId}:pod`, podId, 'EX', 3600);
      
      // Add session to pod's set of active sessions
      await this.client.sadd(`pod:${podId}:sessions`, sessionId);
      
      return true;
    } catch (error) {
      console.error('Error tracking pod connection in Redis:', error);
      return false;
    }
  }
  
  // Get pod ID for a session
  public async getSessionPod(sessionId: string): Promise<string | null> {
    try {
      return await this.client.get(`session:${sessionId}:pod`);
    } catch (error) {
      console.error('Error getting session pod from Redis:', error);
      return null;
    }
  }
  
  // Close Redis connections
  public async close(): Promise<void> {
    await this.client.quit();
    await this.subscriber.quit();
  }
}