import { SocketClient } from '../client/socket-client';
import { StateManager } from '../types/connection-types';
export declare class ExchangeDataHandler {
    private client;
    private stateManager;
    private logger;
    constructor(client: SocketClient, stateManager: StateManager);
    private setupListeners;
    private handleExchangeData;
}
