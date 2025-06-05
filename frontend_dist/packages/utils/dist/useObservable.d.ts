import { Observable } from 'rxjs';
/**
 * Hook to subscribe to an observable and update state when it emits
 */
export declare function useObservable<T>(observable: Observable<T>, initialState: T): T;
