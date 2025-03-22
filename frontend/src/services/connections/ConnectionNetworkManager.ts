// src/services/connections/ConnectionNetworkManager.ts
import { ConnectionState } from './ConnectionTypes';
import { getServiceConfig, isEksIngress } from '../config/ServiceConfig';

// Helper class to handle network specifics
export class ConnectionNetworkManager {
  // Check if the error is an EKS/ALB connection reset
  public static isEksConnectionReset(error: any): boolean {
    if (!error) return false;
    
    if (error.code === 'ECONNRESET') return true;
    if (typeof error.message === 'string') {
      return error.message.includes('Connection reset by peer') || 
             error.message.includes('WebSocket was closed before the connection was established') ||
             error.message.includes('GOAWAY') ||
             error.message.includes('503 Service Temporarily Unavailable');
    }
    return false;
  }
  
  // Detect connection type
  public static detectConnectionType(): string {
    // Use Network Information API if available
    if ('connection' in navigator) {
      const conn = (navigator as any).connection;
      if (conn) {
        if (conn.type) {
          return conn.type;
        }
        
        // Fall back to effective type (slow-2g, 2g, 3g, 4g)
        if (conn.effectiveType) {
          return conn.effectiveType;
        }
      }
    }
    
    // Default if Network Information API is not available
    return 'unknown';
  }
  
  // Get appropriate fetch options based on environment
  public static getFetchOptions(options: RequestInit = {}): RequestInit {
    const defaultOptions: RequestInit = {
      credentials: 'same-origin',
      headers: {
        'Content-Type': 'application/json',
      },
    };
    
    // For local Kubernetes testing, add CORS headers
    if (getServiceConfig().isLocalK8s) {
      defaultOptions.credentials = 'include';
      defaultOptions.headers = {
        ...defaultOptions.headers,
        'X-Requested-With': 'XMLHttpRequest',
      };
    }
    
    // Merge with provided options
    return {
      ...defaultOptions,
      ...options,
      headers: {
        ...defaultOptions.headers,
        ...options.headers,
      }
    };
  }
  
  public static isStreamError(error: any): boolean {
    if (!error) return false;
    
    // Check error codes
    if (error.code === 'ECONNRESET' || 
        error.code === 'ETIMEDOUT' ||
        error.code === 'ERR_HTTP2_STREAM_ERROR') {
      return true;
    }
    
    // Check error messages
    if (typeof error.message === 'string') {
      return error.message.includes('Stream closed') || 
             error.message.includes('ERR_NGROK_') ||  
             error.message.includes('network timeout') ||
             error.message.includes('HTTP/2 stream') ||
             error.message.includes('GOAWAY');
    }
    
    return false;
  }
  
  // Create URL based on service configuration
  public static createServiceUrl(service: string, endpoint: string): string {
    const config = getServiceConfig();
    
    // Remove leading slash if present in endpoint
    const cleanEndpoint = endpoint.startsWith('/') ? endpoint.substring(1) : endpoint;
    
    if (service === 'auth') {
      return `${config.authService}/${cleanEndpoint}`;
    } else if (service === 'session') {
      return `${config.sessionService}/${cleanEndpoint}`;
    }
    
    return endpoint; // Fallback to raw endpoint
  }
}