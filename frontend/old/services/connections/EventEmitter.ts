// src/services/connections/EventEmitter.ts
import { ConnectionEventType } from './ConnectionTypes';

export class EventEmitter {
  private listeners: Map<string, Set<Function>> = new Map();
  
  public on(event: ConnectionEventType, callback: Function): void {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, new Set());
    }
    
    this.listeners.get(event)?.add(callback);
  }
  
  public off(event: ConnectionEventType, callback: Function): void {
    if (this.listeners.has(event)) {
      this.listeners.get(event)?.delete(callback);
    }
  }
  
  public emit(event: ConnectionEventType, data: any): void {
    if (this.listeners.has(event)) {
      this.listeners.get(event)?.forEach(callback => {
        try {
          callback(data);
        } catch (error) {
          console.error(`Error in event listener for ${event}:`, error);
        }
      });
    }
    
    // Also emit to 'all' listeners
    if (this.listeners.has('all')) {
      this.listeners.get('all')?.forEach(callback => {
        try {
          callback({
            type: event,
            data: data
          });
        } catch (error) {
          console.error(`Error in 'all' event listener handling ${event}:`, error);
        }
      });
    }
  }
}