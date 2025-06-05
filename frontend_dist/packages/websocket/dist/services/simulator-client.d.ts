import { SocketClient } from '../client/socket-client';
import { StateManager } from '../types/connection-types';
export declare class SimulatorClient {
    private stateManager;
    private logger;
    private socketClient;
    private simulatorHandler;
    constructor(socketClient: SocketClient, stateManager: StateManager);
    startSimulator(): Promise<{
        success: boolean;
        status?: string;
        error?: string;
    }>;
    stopSimulator(): Promise<{
        success: boolean;
        status?: string;
        error?: string;
    }>;
}
