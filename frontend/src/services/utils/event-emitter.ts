// src/utils/event-emitter.ts

export class EventEmitter {
    private events: Map<string, Set<Function>> = new Map();
    
    public on(event: string, listener: Function): void {
      if (!this.events.has(event)) {
        this.events.set(event, new Set());
      }
      
      this.events.get(event)!.add(listener);
    }
    
    public off(event: string, listener: Function): void {
      const listeners = this.events.get(event);
      if (listeners) {
        listeners.delete(listener);
        
        if (listeners.size === 0) {
          this.events.delete(event);
        }
      }
    }
    
    public once(event: string, listener: Function): void {
      const onceWrapper = (...args: any[]) => {
        listener(...args);
        this.off(event, onceWrapper);
      };
      
      this.on(event, onceWrapper);
    }
    
    public emit(event: string, ...args: any[]): void {
      const listeners = this.events.get(event);
      if (listeners) {
        [...listeners].forEach(listener => {
          try {
            listener(...args);
          } catch (error) {
            console.error(`Error in event listener for ${event}:`, error);
          }
        });
      }
      
      // Also emit to wildcard listeners
      const wildcardListeners = this.events.get('*');
      if (wildcardListeners) {
        [...wildcardListeners].forEach(listener => {
          try {
            listener(event, ...args);
          } catch (error) {
            console.error(`Error in wildcard event listener for ${event}:`, error);
          }
        });
      }
    }
    
    public removeAllListeners(event?: string): void {
      if (event) {
        this.events.delete(event);
      } else {
        this.events.clear();
      }
    }
    
    public listenerCount(event: string): number {
      const listeners = this.events.get(event);
      return listeners ? listeners.size : 0;
    }
  }