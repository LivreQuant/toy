import { SocketClient } from '../client/socket-client';
import { ServerSessionInfoResponse, ServerStopSessionResponse } from '../types/message-types';
export declare class SessionHandler {
    private client;
    private logger;
    private responseTimeoutMs;
    constructor(client: SocketClient);
    requestSessionInfo(): Promise<ServerSessionInfoResponse>;
    stopSession(): Promise<ServerStopSessionResponse>;
    private sendRequest;
}
