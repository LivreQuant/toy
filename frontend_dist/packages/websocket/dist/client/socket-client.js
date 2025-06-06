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
// frontend_dist/packages/websocket/src/client/socket-client.ts
import { BehaviorSubject } from 'rxjs';
import { getLogger } from '@trading-app/logging';
import { DeviceIdManager } from '@trading-app/auth';
import { ConnectionStatus } from '@trading-app/state';
import { EventEmitter } from '@trading-app/utils';
var SocketClient = /** @class */ (function () {
    function SocketClient(tokenManager, configService, options) {
        var _this = this;
        this.tokenManager = tokenManager;
        this.configService = configService;
        this.logger = getLogger('SocketClient');
        this.socket = null;
        this.status$ = new BehaviorSubject(ConnectionStatus.DISCONNECTED);
        this.events = new EventEmitter();
        // Handle incoming messages
        this.handleMessage = function (event) {
            try {
                var message = JSON.parse(event.data);
                _this.logger.debug('📥 WebSocket message received', {
                    messageType: message.type,
                    timestamp: message.timestamp,
                    hasRequestId: !!message.requestId,
                    dataLength: event.data.length
                });
                _this.events.emit('message', message);
            }
            catch (error) {
                _this.logger.error('Error parsing WebSocket message', {
                    error: error instanceof Error ? error.message : String(error),
                    data: typeof event.data === 'string' ? event.data.substring(0, 100) : 'non-string data',
                    dataType: typeof event.data
                });
                _this.events.emit('error', error instanceof Error ? error : new Error(String(error)));
            }
        };
        // Handle connection close
        this.handleClose = function (event) {
            _this.logger.info("WebSocket connection closed. Code: ".concat(event.code, ", Reason: ").concat(event.reason, ", Clean: ").concat(event.wasClean), {
                code: event.code,
                reason: event.reason,
                wasClean: event.wasClean,
                timeStamp: event.timeStamp
            });
            _this.cleanup();
            _this.status$.next(ConnectionStatus.DISCONNECTED);
            _this.events.emit('close', {
                code: event.code,
                reason: event.reason,
                wasClean: event.wasClean
            });
        };
        this.options = __assign({ autoReconnect: false, connectTimeout: 10000, secureConnection: false }, options);
    }
    // Get the connection status observable
    SocketClient.prototype.getStatus = function () {
        return this.status$.asObservable();
    };
    // Get the current connection status
    SocketClient.prototype.getCurrentStatus = function () {
        return this.status$.getValue();
    };
    // Connect to the WebSocket server
    SocketClient.prototype.connect = function () {
        return __awaiter(this, void 0, void 0, function () {
            var currentStatus, token, csrfToken, deviceId, params, baseWsUrl, wsUrl, maskedUrl_1, error_1;
            var _this = this;
            return __generator(this, function (_a) {
                switch (_a.label) {
                    case 0:
                        if (this.socket) {
                            this.logger.warn('Connect called with existing socket, cleaning up previous instance');
                            this.cleanup();
                        }
                        if (!this.tokenManager.isAuthenticated()) {
                            this.logger.error('Cannot connect: Not authenticated');
                            this.status$.next(ConnectionStatus.DISCONNECTED);
                            return [2 /*return*/, false];
                        }
                        currentStatus = this.status$.getValue();
                        if (currentStatus === ConnectionStatus.CONNECTING || currentStatus === ConnectionStatus.CONNECTED) {
                            this.logger.warn("Connect call ignored: WebSocket status is already ".concat(currentStatus));
                            return [2 /*return*/, currentStatus === ConnectionStatus.CONNECTED];
                        }
                        _a.label = 1;
                    case 1:
                        _a.trys.push([1, 4, , 5]);
                        this.logger.info('🚀 Initiating WebSocket connection...');
                        this.status$.next(ConnectionStatus.CONNECTING);
                        return [4 /*yield*/, this.tokenManager.getAccessToken()];
                    case 2:
                        token = _a.sent();
                        if (!token) {
                            throw new Error('Failed to get authentication token for WebSocket');
                        }
                        return [4 /*yield*/, this.tokenManager.getCsrfToken()];
                    case 3:
                        csrfToken = _a.sent();
                        deviceId = DeviceIdManager.getInstance().getDeviceId();
                        params = new URLSearchParams({
                            token: token,
                            deviceId: deviceId,
                            csrfToken: csrfToken
                        });
                        baseWsUrl = this.configService.getWebSocketUrl();
                        // Log the URL construction process
                        this.logger.info('🔍 WEBSOCKET URL DEBUG: Constructing connection URL', {
                            baseWsUrl: baseWsUrl,
                            hasToken: !!token,
                            hasDeviceId: !!deviceId,
                            hasCsrfToken: !!csrfToken,
                            paramsString: params.toString(),
                            configServiceType: this.configService.constructor.name
                        });
                        wsUrl = "".concat(baseWsUrl, "?").concat(params.toString());
                        maskedUrl_1 = wsUrl.replace(/token=[^&]+/, 'token=***MASKED***')
                            .replace(/csrfToken=[^&]+/, 'csrfToken=***MASKED***');
                        this.logger.info('🔗 WEBSOCKET CONNECTION: Final URL constructed', {
                            maskedUrl: maskedUrl_1,
                            urlLength: wsUrl.length,
                            protocol: wsUrl.startsWith('wss:') ? 'secure' : 'insecure',
                            hostname: this.extractHostname(wsUrl),
                            port: this.extractPort(wsUrl)
                        });
                        this.socket = new WebSocket(wsUrl);
                        return [2 /*return*/, new Promise(function (resolve) {
                                var timeoutId = setTimeout(function () {
                                    var _a;
                                    _this.logger.error('❌ WebSocket connection attempt timed out', {
                                        timeoutMs: _this.options.connectTimeout,
                                        maskedUrl: maskedUrl_1,
                                        socketReadyState: (_a = _this.socket) === null || _a === void 0 ? void 0 : _a.readyState
                                    });
                                    if (_this.status$.getValue() === ConnectionStatus.CONNECTING) {
                                        _this.cleanup();
                                        _this.status$.next(ConnectionStatus.DISCONNECTED);
                                        resolve(false);
                                    }
                                }, _this.options.connectTimeout);
                                _this.socket.addEventListener('open', function () {
                                    var _a, _b, _c;
                                    clearTimeout(timeoutId);
                                    _this.logger.info('✅ WebSocket connection established successfully', {
                                        maskedUrl: maskedUrl_1,
                                        readyState: (_a = _this.socket) === null || _a === void 0 ? void 0 : _a.readyState,
                                        extensions: (_b = _this.socket) === null || _b === void 0 ? void 0 : _b.extensions,
                                        protocol: (_c = _this.socket) === null || _c === void 0 ? void 0 : _c.protocol
                                    });
                                    _this.status$.next(ConnectionStatus.CONNECTED);
                                    _this.events.emit('open', undefined);
                                    resolve(true);
                                });
                                _this.socket.addEventListener('error', function (event) {
                                    var _a;
                                    _this.logger.error('❌ WebSocket connection error', {
                                        event: event,
                                        maskedUrl: maskedUrl_1,
                                        readyState: (_a = _this.socket) === null || _a === void 0 ? void 0 : _a.readyState,
                                        errorType: event.type,
                                        timeStamp: event.timeStamp
                                    });
                                    _this.events.emit('error', new Error("WebSocket connection error: ".concat(event.type)));
                                });
                                _this.socket.addEventListener('close', function (event) {
                                    clearTimeout(timeoutId);
                                    _this.logger.warn('🔌 WebSocket connection closed during connection attempt', {
                                        code: event.code,
                                        reason: event.reason,
                                        wasClean: event.wasClean,
                                        maskedUrl: maskedUrl_1,
                                        timeStamp: event.timeStamp
                                    });
                                    _this.handleClose(event);
                                    if (_this.status$.getValue() === ConnectionStatus.CONNECTING) {
                                        resolve(false);
                                    }
                                });
                                _this.socket.addEventListener('message', _this.handleMessage);
                            })];
                    case 4:
                        error_1 = _a.sent();
                        this.logger.error('💥 Error initiating WebSocket connection', {
                            error: error_1 instanceof Error ? error_1.message : String(error_1),
                            errorStack: error_1 instanceof Error ? error_1.stack : undefined,
                            errorName: error_1 instanceof Error ? error_1.name : 'Unknown'
                        });
                        this.status$.next(ConnectionStatus.DISCONNECTED);
                        return [2 /*return*/, false];
                    case 5: return [2 /*return*/];
                }
            });
        });
    };
    // Helper method to extract hostname from URL for logging
    SocketClient.prototype.extractHostname = function (url) {
        try {
            return new URL(url).hostname;
        }
        catch (_a) {
            return 'invalid-url';
        }
    };
    // Helper method to extract port from URL for logging
    SocketClient.prototype.extractPort = function (url) {
        try {
            var urlObj = new URL(url);
            return urlObj.port || (urlObj.protocol === 'wss:' ? '443' : '80');
        }
        catch (_a) {
            return 'unknown';
        }
    };
    // Disconnect from the WebSocket server
    SocketClient.prototype.disconnect = function (reason) {
        if (reason === void 0) { reason = 'manual'; }
        this.logger.info("Disconnecting WebSocket. Reason: ".concat(reason));
        if (this.socket) {
            if (this.socket.readyState === WebSocket.OPEN) {
                this.socket.close(1000, reason);
            }
            else {
                this.cleanup();
            }
        }
        this.status$.next(ConnectionStatus.DISCONNECTED);
    };
    // Send a message to the WebSocket server
    SocketClient.prototype.send = function (data) {
        var _a;
        if (!this.socket || this.socket.readyState !== WebSocket.OPEN) {
            this.logger.error('Cannot send message: WebSocket not connected', {
                hasSocket: !!this.socket,
                readyState: (_a = this.socket) === null || _a === void 0 ? void 0 : _a.readyState,
                readyStateText: this.socket ? this.getReadyStateText(this.socket.readyState) : 'no socket'
            });
            return false;
        }
        try {
            var messageStr = typeof data === 'string' ? data : JSON.stringify(data);
            this.socket.send(messageStr);
            this.logger.debug('📤 WebSocket message sent', {
                messageType: typeof data === 'object' && data.type ? data.type : 'unknown',
                messageLength: messageStr.length
            });
            return true;
        }
        catch (error) {
            this.logger.error('Error sending WebSocket message', {
                error: error instanceof Error ? error.message : String(error),
                messageType: typeof data === 'object' && data.type ? data.type : 'unknown'
            });
            return false;
        }
    };
    // Helper method to get readable ready state
    SocketClient.prototype.getReadyStateText = function (readyState) {
        switch (readyState) {
            case WebSocket.CONNECTING: return 'CONNECTING';
            case WebSocket.OPEN: return 'OPEN';
            case WebSocket.CLOSING: return 'CLOSING';
            case WebSocket.CLOSED: return 'CLOSED';
            default: return "UNKNOWN(".concat(readyState, ")");
        }
    };
    // Listen for events
    SocketClient.prototype.on = function (event, callback) {
        return this.events.on(event, callback);
    };
    // Clean up WebSocket resources
    SocketClient.prototype.cleanup = function () {
        if (this.socket) {
            this.logger.debug('🧹 Cleaning up WebSocket resources', {
                readyState: this.getReadyStateText(this.socket.readyState)
            });
            this.socket.removeEventListener('message', this.handleMessage);
            this.socket.removeEventListener('close', this.handleClose);
            this.socket.onopen = null;
            this.socket.onclose = null;
            this.socket.onerror = null;
            if (this.socket.readyState === WebSocket.OPEN ||
                this.socket.readyState === WebSocket.CONNECTING) {
                try {
                    this.socket.close(1000, 'Client cleanup');
                }
                catch (e) {
                    this.logger.warn('Error closing WebSocket during cleanup', {
                        error: e instanceof Error ? e.message : String(e)
                    });
                }
            }
            this.socket = null;
        }
    };
    // Implement Disposable interface
    SocketClient.prototype.dispose = function () {
        this.logger.info('🗑️ Disposing SocketClient');
        this.disconnect('disposed');
        this.events.clear();
        this.status$.complete();
    };
    return SocketClient;
}());
export { SocketClient };
