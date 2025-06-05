// src/hooks/useObservable.ts
import { useState, useEffect } from 'react';
/**
 * Hook to subscribe to an observable and update state when it emits
 */
export function useObservable(observable, initialState) {
    const [state, setState] = useState(initialState);
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
