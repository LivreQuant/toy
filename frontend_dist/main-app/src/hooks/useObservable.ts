// src/hooks/useObservable.ts
import { useState, useEffect } from 'react';
import { Observable } from 'rxjs';

/**
 * Hook to subscribe to an observable and update state when it emits
 */
export function useObservable<T>(observable: Observable<T>, initialState: T): T {
  const [state, setState] = useState<T>(initialState);
  
  useEffect(() => {
    const subscription = observable.subscribe(value => {
      setState(value);
    });
    
    return () => {
      subscription.unsubscribe();
    };
  }, [observable]);
  
  return state;
}