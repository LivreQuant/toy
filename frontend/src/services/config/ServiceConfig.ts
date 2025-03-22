// src/services/config/ServiceConfig.ts

export interface ServiceConfig {
    authService: string;
    sessionService: string;
    maxReconnectAttempts: number;
    heartbeatIntervalMs: number;
    initialBackoffMs: number;
    maxBackoffMs: number;
    connectionTimeoutMs: number;
    isLocalK8s: boolean;
  }
  
  export function getServiceConfig(): ServiceConfig {
    // Check if we're in local Kubernetes mode
    const isLocalK8s = window.location.hostname.endsWith('.local');
    
    // Common configuration
    const commonConfig = {
      maxReconnectAttempts: 15,
      heartbeatIntervalMs: 10000,
      initialBackoffMs: 1000,
      maxBackoffMs: 30000,
      connectionTimeoutMs: 30000,
      isLocalK8s,
      useHttps: process.env.NODE_ENV === 'production' || window.location.protocol === 'https:'
    };
    
    const protocol = commonConfig.useHttps ? 'https' : 'http';
    
    // Environment-specific configurations
    if (isLocalK8s) {
      // Local Kubernetes configuration
      return {
        ...commonConfig,
        authService: `${protocol}://auth-api.local`,
        sessionService: `${protocol}://session-api.local`,
      };
    } else if (process.env.NODE_ENV === 'development') {
      // Development configuration
      return {
        ...commonConfig,
        authService: `${protocol}://localhost:3001/api/auth`,
        sessionService: `${protocol}://localhost:3001/api/session`,
      };
    } else {
      // Production configuration
      return {
        ...commonConfig,
        authService: '/api/auth',
        sessionService: '/api/session',
      };
    }
  }
  
  // Helper function to detect EKS ingress
  export function isEksIngress(): boolean {
    const hostname = window.location.hostname;
    return (
      hostname.includes('eks') ||
      hostname.endsWith('.elb.amazonaws.com') ||
      hostname.endsWith('.eks.amazonaws.com') ||
      !!sessionStorage.getItem('eks-environment')
    );
  }