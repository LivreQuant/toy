import { Observable } from 'rxjs';
import { TokenManager } from '@trading-app/auth';
import { ConnectionStatus } from '@trading-app/state';
import { Disposable } from '@trading-app/utils';
import { SocketClientOptions, ConfigService } from '../types/connection-types';
export declare class SocketClient implements Disposable {
    private tokenManager;
    private configService;
    private logger;
    private socket;
    private status$;
    private events;
    private options;
    constructor(tokenManager: TokenManager, configService: ConfigService, options?: Partial<SocketClientOptions>);
    getStatus(): Observable<ConnectionStatus>;
    getCurrentStatus(): ConnectionStatus;
    connect(): Promise<boolean>;
    private extractHostname;
    private extractPort;
    disconnect(reason?: string): void;
    send(data: any): boolean;
    private getReadyStateText;
    on<T extends keyof typeof this.events.events>(event: T, callback: (data: typeof this.events.events[T]) => void): {
        unsubscribe: () => void;
    };
    private handleMessage;
    private handleClose;
    private cleanup;
    dispose(): void;
}
