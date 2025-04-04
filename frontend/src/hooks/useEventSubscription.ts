// src/hooks/useEventSubscription.ts
import { useEffect, useRef } from 'react';
import { EventEmitter } from '../utils/event-emitter';

/**
 * A hook to safely subscribe to events with automatic cleanup
 */
export function useEventSubscription(
  emitter: EventEmitter | null | undefined,
  event: string,
  handler: Function
) {
  // Use a ref to maintain handler identity across renders
  const handlerRef = useRef(handler);
  
  // Update ref whenever handler changes
  useEffect(() => {
    handlerRef.current = handler;
  }, [handler]);
  
  useEffect(() => {
    if (!emitter) return;
    
    // Create a stable handler that calls current ref
    const stableHandler = (...args: any[]) => handlerRef.current(...args);
    
    // Subscribe to the event
    emitter.on(event, stableHandler);
    
    // Clean up on unmount
    return () => {
      emitter.off(event, stableHandler);
    };
  }, [emitter, event]);
}

/**
 * A hook to safely subscribe to multiple events with automatic cleanup
 */
export function useEventSubscriptions(
  emitter: EventEmitter | null | undefined,
  subscriptions: Record<string, Function>
) {
  useEffect(() => {
    if (!emitter) return;
    
    // Create stable handlers for each subscription
    const handlers = new Map<string, Function>();
    
    // Subscribe to all events
    for (const [event, handler] of Object.entries(subscriptions)) {
      const stableHandler = (...args: any[]) => handler(...args);
      handlers.set(event, stableHandler);
      emitter.on(event, stableHandler);
    }
    
    // Clean up on unmount
    return () => {
      for (const [event, handler] of handlers.entries()) {
        emitter.off(event, handler);
      }
    };
  }, [emitter, subscriptions]);
}