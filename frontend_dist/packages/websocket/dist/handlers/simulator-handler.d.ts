import { SocketClient } from '../client/socket-client';
import { ServerSimulatorStartedResponse, ServerSimulatorStoppedResponse } from '../types/message-types';
export declare class SimulatorHandler {
    private client;
    private logger;
    private responseTimeoutMs;
    constructor(client: SocketClient);
    startSimulator(): Promise<ServerSimulatorStartedResponse>;
    stopSimulator(): Promise<ServerSimulatorStoppedResponse>;
    private sendRequest;
}
