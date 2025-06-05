// --- Type Guards ---
export function isHeartbeatAckMessage(msg) {
    return msg.type === 'heartbeat_ack';
}
export function isReconnectResultMessage(msg) {
    return msg.type === 'reconnect_result';
}
export function isExchangeDataMessage(msg) {
    return msg.type === 'exchange_data';
}
export function isSessionInfoResponse(msg) {
    return msg.type === 'session_info';
}
export function isSessionStoppedResponse(msg) {
    return msg.type === 'session_stopped';
}
export function isSimulatorStartedResponse(msg) {
    return msg.type === 'simulator_started';
}
export function isSimulatorStoppedResponse(msg) {
    return msg.type === 'simulator_stopped';
}
