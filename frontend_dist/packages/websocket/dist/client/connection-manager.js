var __assign = (this && this.__assign) || function () {
    __assign = Object.assign || function(t) {
        for (var s, i = 1, n = arguments.length; i < n; i++) {
            s = arguments[i];
            for (var p in s) if (Object.prototype.hasOwnProperty.call(s, p))
                t[p] = s[p];
        }
        return t;
    };
    return __assign.apply(this, arguments);
};
var __awaiter = (this && this.__awaiter) || function (thisArg, _arguments, P, generator) {
    function adopt(value) { return value instanceof P ? value : new P(function (resolve) { resolve(value); }); }
    return new (P || (P = Promise))(function (resolve, reject) {
        function fulfilled(value) { try { step(generator.next(value)); } catch (e) { reject(e); } }
        function rejected(value) { try { step(generator["throw"](value)); } catch (e) { reject(e); } }
        function step(result) { result.done ? resolve(result.value) : adopt(result.value).then(fulfilled, rejected); }
        step((generator = generator.apply(thisArg, _arguments || [])).next());
    });
};
var __generator = (this && this.__generator) || function (thisArg, body) {
    var _ = { label: 0, sent: function() { if (t[0] & 1) throw t[1]; return t[1]; }, trys: [], ops: [] }, f, y, t, g;
    return g = { next: verb(0), "throw": verb(1), "return": verb(2) }, typeof Symbol === "function" && (g[Symbol.iterator] = function() { return this; }), g;
    function verb(n) { return function (v) { return step([n, v]); }; }
    function step(op) {
        if (f) throw new TypeError("Generator is already executing.");
        while (g && (g = 0, op[0] && (_ = 0)), _) try {
            if (f = 1, y && (t = op[0] & 2 ? y["return"] : op[0] ? y["throw"] || ((t = y["return"]) && t.call(y), 0) : y.next) && !(t = t.call(y, op[1])).done) return t;
            if (y = 0, t) op = [op[0] & 2, t.value];
            switch (op[0]) {
                case 0: case 1: t = op; break;
                case 4: _.label++; return { value: op[1], done: false };
                case 5: _.label++; y = op[1]; op = [0]; continue;
                case 7: op = _.ops.pop(); _.trys.pop(); continue;
                default:
                    if (!(t = _.trys, t = t.length > 0 && t[t.length - 1]) && (op[0] === 6 || op[0] === 2)) { _ = 0; continue; }
                    if (op[0] === 3 && (!t || (op[1] > t[0] && op[1] < t[3]))) { _.label = op[1]; break; }
                    if (op[0] === 6 && _.label < t[1]) { _.label = t[1]; t = op; break; }
                    if (t && _.label < t[2]) { _.label = t[2]; _.ops.push(op); break; }
                    if (t[2]) _.ops.pop();
                    _.trys.pop(); continue;
            }
            op = body.call(thisArg, _);
        } catch (e) { op = [6, e]; y = 0; } finally { f = t = 0; }
        if (op[0] & 5) throw op[1]; return { value: op[0] ? op[1] : void 0, done: true };
    }
};
// frontend_dist/packages/websocket/src/client/connection-manager.ts
import { getLogger } from '@trading-app/logging';
import { DeviceIdManager } from '@trading-app/auth';
import { ConnectionStatus } from '@trading-app/state';
import { EventEmitter, handleError } from '@trading-app/utils';
import { SocketClient } from './socket-client';
import { SessionHandler } from '../handlers/session-handler';
import { Heartbeat } from '../services/heartbeat';
import { Resilience, ResilienceState } from '../services/resilience';
import { SimulatorClient } from '../services/simulator-client';
var ConnectionManager = /** @class */ (function () {
    function ConnectionManager(tokenManager, stateManager, toastService, configService, options) {
        if (options === void 0) { options = {}; }
        var _a, _b, _c, _d, _e;
        this.tokenManager = tokenManager;
        this.stateManager = stateManager;
        this.toastService = toastService;
        this.configService = configService;
        this.logger = getLogger('ConnectionManager');
        this.isDisposed = false;
        this.hasAuthInitialized = false; // 🚨 NEW: Track if auth has been properly initialized
        this.desiredState = {
            connected: false,
            simulatorRunning: false
        };
        this.events = new EventEmitter();
        this.logger.info('🔌 CONNECTION: Initializing ConnectionManager');
        var reconnectionConfig = this.configService.getReconnectionConfig();
        var mergedOptions = {
            heartbeatInterval: options.heartbeatInterval || 15000,
            heartbeatTimeout: options.heartbeatTimeout || 5000,
            resilience: {
                initialDelayMs: ((_a = options.resilience) === null || _a === void 0 ? void 0 : _a.initialDelayMs) || reconnectionConfig.initialDelayMs,
                maxDelayMs: ((_b = options.resilience) === null || _b === void 0 ? void 0 : _b.maxDelayMs) || reconnectionConfig.maxDelayMs,
                maxAttempts: ((_c = options.resilience) === null || _c === void 0 ? void 0 : _c.maxAttempts) || reconnectionConfig.maxAttempts,
                jitterFactor: ((_d = options.resilience) === null || _d === void 0 ? void 0 : _d.jitterFactor) || reconnectionConfig.jitterFactor,
                suspensionTimeoutMs: ((_e = options.resilience) === null || _e === void 0 ? void 0 : _e.suspensionTimeoutMs) || 60000,
            }
        };
        this.socketClient = new SocketClient(tokenManager, configService);
        this.heartbeat = new Heartbeat(this.socketClient, this.stateManager, {
            interval: options.heartbeatInterval || 15000,
            timeout: options.heartbeatTimeout || 5000
        });
        this.resilience = new Resilience(tokenManager, toastService, options.resilience);
        this.sessionHandler = new SessionHandler(this.socketClient);
        this.simulatorClient = new SimulatorClient(this.socketClient, this.stateManager);
        this.setupListeners();
        // 🚨 NEW: Wait for auth to initialize before allowing connections
        this.waitForAuthInitialization();
    }
    // 🚨 NEW: Wait for proper auth initialization
    ConnectionManager.prototype.waitForAuthInitialization = function () {
        var _this = this;
        var checkAuthInit = function () {
            var authState = _this.stateManager.getAuthState();
            // Auth is considered initialized when isAuthLoading becomes false
            if (!authState.isAuthLoading) {
                _this.hasAuthInitialized = true;
                _this.logger.info('🔌 CONNECTION: Auth initialization complete, connections now allowed', {
                    isAuthenticated: authState.isAuthenticated,
                    userId: authState.userId
                });
                // Now sync the connection state if needed
                _this.syncConnectionState();
                return;
            }
            _this.logger.debug('🔌 CONNECTION: Waiting for auth initialization...', {
                isAuthLoading: authState.isAuthLoading,
                isAuthenticated: authState.isAuthenticated
            });
            // Check again in 100ms
            setTimeout(checkAuthInit, 100);
        };
        // Start checking
        setTimeout(checkAuthInit, 50);
    };
    ConnectionManager.prototype.setupListeners = function () {
        var _this = this;
        this.socketClient.getStatus().subscribe(function (status) {
            if (_this.isDisposed)
                return;
            _this.stateManager.updateConnectionState({
                webSocketStatus: status
            });
            if (status === ConnectionStatus.CONNECTED) {
                _this.logger.info('WebSocket connected. Not starting heartbeat automatically.');
                _this.resilience.reset();
                _this.syncSimulatorState();
            }
            else if (status === ConnectionStatus.DISCONNECTED) {
                _this.logger.info('WebSocket disconnected. Stopping heartbeat.');
                _this.heartbeat.stop();
                if (_this.desiredState.connected && _this.stateManager.getAuthState().isAuthenticated) {
                    _this.attemptRecovery('ws_disconnect');
                }
            }
        });
        this.heartbeat.on('timeout', function () {
            if (_this.isDisposed)
                return;
            _this.logger.warn('Heartbeat timeout detected. Disconnecting WebSocket.');
            _this.socketClient.disconnect('heartbeat_timeout');
        });
        this.heartbeat.on('response', function (data) {
            if (_this.isDisposed)
                return;
            if (!data.deviceIdValid) {
                _this.logger.warn('Device ID invalidated by heartbeat response');
                _this.handleDeviceIdInvalidation('heartbeat_response');
            }
        });
        this.socketClient.on('message', function (message) {
            if (_this.isDisposed)
                return;
            if (message.type === 'device_id_invalidated') {
                _this.logger.warn("Device ID invalidated: ".concat(message.deviceId));
                _this.handleDeviceIdInvalidation('server_message', message.reason);
            }
        });
    };
    ConnectionManager.prototype.resetState = function () {
        if (this.isDisposed)
            return;
        this.logger.info('Resetting connection manager state');
        this.disconnect('reset');
        this.desiredState = {
            connected: false,
            simulatorRunning: false
        };
        this.resilience.reset();
        this.stateManager.updateConnectionState({
            webSocketStatus: ConnectionStatus.DISCONNECTED,
            overallStatus: ConnectionStatus.DISCONNECTED,
            isRecovering: false,
            recoveryAttempt: 0,
            simulatorStatus: 'UNKNOWN',
            lastConnectionError: null
        });
    };
    ConnectionManager.prototype.setDesiredState = function (state) {
        if (this.isDisposed) {
            this.logger.warn('Cannot set desired state: ConnectionManager is disposed');
            return;
        }
        var oldState = __assign({}, this.desiredState);
        this.desiredState = __assign(__assign({}, this.desiredState), state);
        this.logger.info('🔌 CONNECTION: Desired state updated', {
            oldState: oldState,
            newState: this.desiredState,
            hasAuthInitialized: this.hasAuthInitialized
        });
        // 🚨 CRITICAL: Only sync if auth has been initialized
        if (this.hasAuthInitialized) {
            this.syncConnectionState();
            if (oldState.simulatorRunning !== this.desiredState.simulatorRunning) {
                this.syncSimulatorState();
            }
        }
        else {
            this.logger.info('🔌 CONNECTION: Deferring connection sync until auth initialization completes');
        }
    };
    ConnectionManager.prototype.syncConnectionState = function () {
        var _this = this;
        if (this.isDisposed)
            return;
        // 🚨 CRITICAL: Block all connections until auth is properly initialized
        if (!this.hasAuthInitialized) {
            this.logger.debug('🔌 CONNECTION: Sync blocked - auth not yet initialized');
            return;
        }
        var connState = this.stateManager.getConnectionState();
        var authState = this.stateManager.getAuthState();
        var resilienceState = this.resilience.getState().state;
        this.logger.info('🔌 CONNECTION: Syncing connection state', {
            desiredConnected: this.desiredState.connected,
            isAuthenticated: authState.isAuthenticated,
            isAuthLoading: authState.isAuthLoading,
            currentWebSocketStatus: connState.webSocketStatus,
            isRecovering: connState.isRecovering,
            resilienceState: resilienceState,
            hasAuthInitialized: this.hasAuthInitialized
        });
        if (authState.isAuthLoading) {
            this.logger.debug('🔌 CONNECTION: Sync skipped - auth still loading');
            return;
        }
        if (!authState.isAuthenticated) {
            this.logger.debug('🔌 CONNECTION: Sync skipped - not authenticated');
            return;
        }
        if (resilienceState === ResilienceState.SUSPENDED || resilienceState === ResilienceState.FAILED) {
            this.logger.debug("\uD83D\uDD0C CONNECTION: Sync skipped - resilience state is ".concat(resilienceState));
            return;
        }
        if (this.desiredState.connected &&
            connState.webSocketStatus !== ConnectionStatus.CONNECTED &&
            connState.webSocketStatus !== ConnectionStatus.CONNECTING &&
            !connState.isRecovering) {
            this.logger.info('🔌 CONNECTION: Initiating connection (desired=true, authenticated, not connected)');
            this.connect().catch(function (err) {
                _this.logger.error('Connect promise rejected', {
                    error: err instanceof Error ? err.message : String(err)
                });
            });
        }
        else if (!this.desiredState.connected &&
            (connState.webSocketStatus === ConnectionStatus.CONNECTED ||
                connState.webSocketStatus === ConnectionStatus.CONNECTING ||
                connState.isRecovering)) {
            this.logger.info('🔌 CONNECTION: Disconnecting (desired=false)');
            this.disconnect('desired_state_sync');
        }
    };
    ConnectionManager.prototype.syncSimulatorState = function () {
        return __awaiter(this, void 0, void 0, function () {
            var connState, simStatus, isRunning, isBusy;
            return __generator(this, function (_a) {
                switch (_a.label) {
                    case 0:
                        if (this.isDisposed)
                            return [2 /*return*/];
                        connState = this.stateManager.getConnectionState();
                        if (connState.webSocketStatus !== ConnectionStatus.CONNECTED) {
                            this.logger.debug('Sync simulator state skipped: Not connected');
                            return [2 /*return*/];
                        }
                        simStatus = connState.simulatorStatus;
                        isRunning = simStatus === 'RUNNING';
                        isBusy = simStatus === 'STARTING' || simStatus === 'STOPPING';
                        if (!(this.desiredState.simulatorRunning && !isRunning && !isBusy)) return [3 /*break*/, 2];
                        this.logger.info('Syncing simulator state: Starting simulator');
                        return [4 /*yield*/, this.startSimulator()];
                    case 1:
                        _a.sent();
                        return [3 /*break*/, 4];
                    case 2:
                        if (!(!this.desiredState.simulatorRunning && isRunning && !isBusy)) return [3 /*break*/, 4];
                        this.logger.info('Syncing simulator state: Stopping simulator');
                        return [4 /*yield*/, this.stopSimulator()];
                    case 3:
                        _a.sent();
                        _a.label = 4;
                    case 4: return [2 /*return*/];
                }
            });
        });
    };
    ConnectionManager.prototype.connect = function () {
        return __awaiter(this, void 0, void 0, function () {
            var authState, connState, wsConnected, sessionResponse, sessionSuccess, sessionError_1, error_1, errorMessage;
            return __generator(this, function (_a) {
                switch (_a.label) {
                    case 0:
                        if (this.isDisposed)
                            return [2 /*return*/, false];
                        // 🚨 CRITICAL: Prevent connections until auth is initialized
                        if (!this.hasAuthInitialized) {
                            this.logger.warn('🔌 CONNECTION: Connect blocked - auth not yet initialized');
                            return [2 /*return*/, false];
                        }
                        authState = this.stateManager.getAuthState();
                        if (!authState.isAuthenticated) {
                            this.logger.error('🔌 CONNECTION: Connect failed - not authenticated');
                            return [2 /*return*/, false];
                        }
                        connState = this.stateManager.getConnectionState();
                        if (connState.webSocketStatus === ConnectionStatus.CONNECTED ||
                            connState.webSocketStatus === ConnectionStatus.CONNECTING ||
                            connState.isRecovering) {
                            this.logger.warn("\uD83D\uDD0C CONNECTION: Connect ignored - Status=".concat(connState.webSocketStatus, ", Recovering=").concat(connState.isRecovering));
                            return [2 /*return*/, connState.webSocketStatus === ConnectionStatus.CONNECTED];
                        }
                        this.logger.info('🔌 CONNECTION: Initiating connection process');
                        this.stateManager.updateConnectionState({
                            webSocketStatus: ConnectionStatus.CONNECTING,
                            lastConnectionError: null
                        });
                        _a.label = 1;
                    case 1:
                        _a.trys.push([1, 7, , 8]);
                        return [4 /*yield*/, this.socketClient.connect()];
                    case 2:
                        wsConnected = _a.sent();
                        if (!wsConnected) {
                            throw new Error('WebSocket connection failed');
                        }
                        this.logger.info('🔌 CONNECTION: WebSocket connected, requesting session info');
                        sessionResponse = void 0;
                        _a.label = 3;
                    case 3:
                        _a.trys.push([3, 5, , 6]);
                        return [4 /*yield*/, this.sessionHandler.requestSessionInfo()];
                    case 4:
                        sessionResponse = _a.sent();
                        this.logger.info('🔌 CONNECTION: Session info response received', {
                            success: sessionResponse.success,
                            type: sessionResponse.type,
                            deviceId: sessionResponse.deviceId,
                            expiresAt: sessionResponse.expiresAt,
                            simulatorStatus: sessionResponse.simulatorStatus
                        });
                        sessionSuccess = sessionResponse.type === 'session_info' && sessionResponse.deviceId;
                        if (!sessionSuccess) {
                            throw new Error("Session validation failed: ".concat(sessionResponse.error || 'Unknown error'));
                        }
                        return [3 /*break*/, 6];
                    case 5:
                        sessionError_1 = _a.sent();
                        this.logger.error('🔌 CONNECTION: Session request failed', {
                            error: sessionError_1 instanceof Error ? sessionError_1.message : String(sessionError_1)
                        });
                        throw sessionError_1;
                    case 6:
                        this.stateManager.updateConnectionState({
                            webSocketStatus: ConnectionStatus.CONNECTED,
                            overallStatus: ConnectionStatus.CONNECTED,
                            simulatorStatus: sessionResponse.simulatorStatus || 'NONE'
                        });
                        this.logger.info('🔌 CONNECTION: Session validated successfully, starting heartbeats');
                        this.heartbeat.start();
                        return [2 /*return*/, true];
                    case 7:
                        error_1 = _a.sent();
                        errorMessage = error_1 instanceof Error ? error_1.message : String(error_1);
                        this.logger.error("\uD83D\uDD0C CONNECTION: Connection process failed: ".concat(errorMessage));
                        this.stateManager.updateConnectionState({
                            webSocketStatus: ConnectionStatus.DISCONNECTED,
                            lastConnectionError: errorMessage
                        });
                        this.resilience.recordFailure("Connection process error: ".concat(errorMessage));
                        this.attemptRecovery('connect_error');
                        return [2 /*return*/, handleError(errorMessage, 'ConnectionProcess', 'high').success];
                    case 8: return [2 /*return*/];
                }
            });
        });
    };
    ConnectionManager.prototype.disconnect = function (reason) {
        if (reason === void 0) { reason = 'manual'; }
        return __awaiter(this, void 0, void 0, function () {
            var connState, response, error_2, error_3;
            return __generator(this, function (_a) {
                switch (_a.label) {
                    case 0:
                        if (this.isDisposed && reason !== 'dispose')
                            return [2 /*return*/, true];
                        this.logger.info("\uD83D\uDD0C CONNECTION: Disconnecting. Reason: ".concat(reason));
                        connState = this.stateManager.getConnectionState();
                        if (connState.webSocketStatus === ConnectionStatus.DISCONNECTED && !connState.isRecovering) {
                            this.logger.debug('🔌 CONNECTION: Disconnect ignored - already disconnected');
                            return [2 /*return*/, true];
                        }
                        _a.label = 1;
                    case 1:
                        _a.trys.push([1, 6, , 7]);
                        if (!(connState.webSocketStatus === ConnectionStatus.CONNECTED)) return [3 /*break*/, 5];
                        this.logger.info('🔌 CONNECTION: Stopping session before disconnecting');
                        _a.label = 2;
                    case 2:
                        _a.trys.push([2, 4, , 5]);
                        return [4 /*yield*/, this.sessionHandler.stopSession()];
                    case 3:
                        response = _a.sent();
                        if (response.success) {
                            this.logger.info('🔌 CONNECTION: Session stop request successful');
                            this.stateManager.updateConnectionState({ simulatorStatus: 'STOPPED' });
                            this.desiredState.simulatorRunning = false;
                        }
                        else {
                            this.logger.warn("\uD83D\uDD0C CONNECTION: Session stop request failed: ".concat(response.error));
                        }
                        return [3 /*break*/, 5];
                    case 4:
                        error_2 = _a.sent();
                        this.logger.error('🔌 CONNECTION: Error stopping session', {
                            error: error_2 instanceof Error ? error_2.message : String(error_2)
                        });
                        return [3 /*break*/, 5];
                    case 5:
                        this.resilience.reset();
                        this.heartbeat.stop();
                        this.socketClient.disconnect(reason);
                        this.stateManager.updateConnectionState({
                            webSocketStatus: ConnectionStatus.DISCONNECTED,
                            isRecovering: false,
                            recoveryAttempt: 0,
                            lastConnectionError: "Disconnected: ".concat(reason)
                        });
                        return [2 /*return*/, true];
                    case 6:
                        error_3 = _a.sent();
                        this.logger.error("\uD83D\uDD0C CONNECTION: Error during disconnect: ".concat(error_3 instanceof Error ? error_3.message : String(error_3)));
                        return [2 /*return*/, false];
                    case 7: return [2 /*return*/];
                }
            });
        });
    };
    ConnectionManager.prototype.attemptRecovery = function (reason) {
        if (reason === void 0) { reason = 'manual'; }
        return __awaiter(this, void 0, void 0, function () {
            var authState, connState, resilienceState, successSubscription, failureSubscription, initiated;
            var _this = this;
            return __generator(this, function (_a) {
                switch (_a.label) {
                    case 0:
                        if (this.isDisposed)
                            return [2 /*return*/, false];
                        // 🚨 CRITICAL: Block recovery until auth is initialized
                        if (!this.hasAuthInitialized) {
                            this.logger.warn('🔌 CONNECTION: Recovery blocked - auth not yet initialized');
                            return [2 /*return*/, false];
                        }
                        authState = this.stateManager.getAuthState();
                        if (!authState.isAuthenticated) {
                            this.logger.warn('🔌 CONNECTION: Recovery ignored - not authenticated');
                            return [2 /*return*/, false];
                        }
                        connState = this.stateManager.getConnectionState();
                        resilienceState = this.resilience.getState();
                        if (connState.isRecovering ||
                            resilienceState.state === ResilienceState.SUSPENDED ||
                            resilienceState.state === ResilienceState.FAILED) {
                            this.logger.warn("\uD83D\uDD0C CONNECTION: Recovery ignored - already recovering or resilience prevents (".concat(resilienceState.state, ")"));
                            return [2 /*return*/, false];
                        }
                        this.logger.info("\uD83D\uDD0C CONNECTION: Attempting recovery. Reason: ".concat(reason));
                        this.stateManager.updateConnectionState({
                            isRecovering: true,
                            recoveryAttempt: resilienceState.attempt + 1
                        });
                        successSubscription = this.resilience.on('reconnect_success', function (data) { return __awaiter(_this, void 0, void 0, function () {
                            var sessionResponse, error_4;
                            return __generator(this, function (_a) {
                                switch (_a.label) {
                                    case 0:
                                        successSubscription.unsubscribe();
                                        _a.label = 1;
                                    case 1:
                                        _a.trys.push([1, 3, , 4]);
                                        this.logger.info('🔌 CONNECTION: Reconnection successful, requesting session info');
                                        return [4 /*yield*/, this.sessionHandler.requestSessionInfo()];
                                    case 2:
                                        sessionResponse = _a.sent();
                                        if (sessionResponse.type === 'session_info' && sessionResponse.deviceId) {
                                            this.logger.info('🔌 CONNECTION: Session validated after reconnect, starting heartbeats');
                                            this.stateManager.updateConnectionState({
                                                webSocketStatus: ConnectionStatus.CONNECTED,
                                                overallStatus: ConnectionStatus.CONNECTED,
                                                simulatorStatus: sessionResponse.simulatorStatus || 'NONE',
                                                isRecovering: false,
                                                recoveryAttempt: 0
                                            });
                                            this.heartbeat.start();
                                        }
                                        else {
                                            this.logger.error('🔌 CONNECTION: Session validation failed after reconnect');
                                            this.disconnect('session_validation_failed');
                                        }
                                        return [3 /*break*/, 4];
                                    case 3:
                                        error_4 = _a.sent();
                                        this.logger.error('🔌 CONNECTION: Error validating session after reconnect', {
                                            error: error_4 instanceof Error ? error_4.message : String(error_4)
                                        });
                                        this.disconnect('session_validation_error');
                                        return [3 /*break*/, 4];
                                    case 4: return [2 /*return*/];
                                }
                            });
                        }); });
                        failureSubscription = this.resilience.on('reconnect_failure', function () {
                            failureSubscription.unsubscribe();
                            _this.logger.warn('🔌 CONNECTION: Reconnection attempt failed');
                        });
                        return [4 /*yield*/, this.resilience.attemptReconnection(function () { return _this.connect(); })];
                    case 1:
                        initiated = _a.sent();
                        if (!initiated) {
                            this.logger.warn('🔌 CONNECTION: Recovery could not be initiated');
                            this.stateManager.updateConnectionState({
                                isRecovering: false,
                                recoveryAttempt: 0
                            });
                            successSubscription.unsubscribe();
                            failureSubscription.unsubscribe();
                        }
                        else {
                            this.logger.info('🔌 CONNECTION: Recovery process initiated');
                        }
                        return [2 /*return*/, initiated];
                }
            });
        });
    };
    ConnectionManager.prototype.manualReconnect = function () {
        return __awaiter(this, void 0, void 0, function () {
            var connState;
            return __generator(this, function (_a) {
                this.logger.info('🔌 CONNECTION: Manual reconnect triggered');
                if (this.isDisposed)
                    return [2 /*return*/, false];
                this.setDesiredState({ connected: true });
                connState = this.stateManager.getConnectionState();
                this.toastService.info('Attempting to reconnect...', 5000, 'connection-recovery-attempt');
                if (connState.webSocketStatus === ConnectionStatus.CONNECTED) {
                    this.socketClient.disconnect('manual_reconnect');
                    return [2 /*return*/, this.attemptRecovery('manual_user_request')];
                }
                else {
                    return [2 /*return*/, this.attemptRecovery('manual_user_request')];
                }
                return [2 /*return*/];
            });
        });
    };
    ConnectionManager.prototype.handleDeviceIdInvalidation = function (source, reason) {
        if (this.isDisposed)
            return;
        this.logger.warn("\uD83D\uDD0C CONNECTION: Device ID invalidated. Source: ".concat(source, ", Reason: ").concat(reason || 'Unknown'));
        var deviceId = DeviceIdManager.getInstance().getDeviceId();
        DeviceIdManager.getInstance().clearDeviceId();
        this.toastService.error("Your session has been deactivated: ".concat(reason || 'Device ID invalidated'), 0);
        this.events.emit('device_id_invalidated', {
            deviceId: deviceId,
            reason: reason
        });
        this.disconnect('device_id_invalidated');
    };
    ConnectionManager.prototype.startSimulator = function () {
        return __awaiter(this, void 0, void 0, function () {
            var connState;
            return __generator(this, function (_a) {
                if (this.isDisposed) {
                    return [2 /*return*/, { success: false, error: 'ConnectionManager disposed' }];
                }
                this.desiredState.simulatorRunning = true;
                connState = this.stateManager.getConnectionState();
                if (connState.webSocketStatus !== ConnectionStatus.CONNECTED) {
                    return [2 /*return*/, { success: false, error: 'Not connected' }];
                }
                if (connState.simulatorStatus === 'RUNNING' || connState.simulatorStatus === 'STARTING') {
                    this.logger.warn("\uD83D\uDD0C CONNECTION: Start simulator ignored: Status=".concat(connState.simulatorStatus));
                    return [2 /*return*/, { success: true, status: connState.simulatorStatus }];
                }
                return [2 /*return*/, this.simulatorClient.startSimulator()];
            });
        });
    };
    ConnectionManager.prototype.stopSimulator = function () {
        return __awaiter(this, void 0, void 0, function () {
            var connState;
            return __generator(this, function (_a) {
                if (this.isDisposed) {
                    return [2 /*return*/, { success: false, error: 'ConnectionManager disposed' }];
                }
                this.desiredState.simulatorRunning = false;
                connState = this.stateManager.getConnectionState();
                if (connState.webSocketStatus !== ConnectionStatus.CONNECTED) {
                    return [2 /*return*/, { success: false, error: 'Not connected' }];
                }
                if (connState.simulatorStatus !== 'RUNNING' && connState.simulatorStatus !== 'STARTING') {
                    this.logger.warn("\uD83D\uDD0C CONNECTION: Stop simulator ignored: Status=".concat(connState.simulatorStatus));
                    return [2 /*return*/, { success: true, status: connState.simulatorStatus }];
                }
                return [2 /*return*/, this.simulatorClient.stopSimulator()];
            });
        });
    };
    ConnectionManager.prototype.on = function (event, callback) {
        return this.events.on(event, callback);
    };
    ConnectionManager.prototype.dispose = function () {
        if (this.isDisposed)
            return;
        this.isDisposed = true;
        this.logger.info('🔌 CONNECTION: Disposing ConnectionManager');
        this.disconnect('dispose');
        this.heartbeat.dispose();
        this.resilience.dispose();
        this.events.clear();
        this.logger.info('🔌 CONNECTION: ConnectionManager disposed');
    };
    return ConnectionManager;
}());
export { ConnectionManager };
