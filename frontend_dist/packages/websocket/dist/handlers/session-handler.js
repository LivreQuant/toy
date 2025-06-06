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
// src/handlers/session-handler.ts
import { getLogger } from '@trading-app/logging';
import { DeviceIdManager } from '@trading-app/auth';
var SessionHandler = /** @class */ (function () {
    function SessionHandler(client) {
        this.client = client;
        this.logger = getLogger('SessionHandler');
        this.responseTimeoutMs = 15000;
        this.logger.info('SessionHandler initialized');
    }
    SessionHandler.prototype.requestSessionInfo = function () {
        return __awaiter(this, void 0, void 0, function () {
            var requestId, message, response, error_1;
            return __generator(this, function (_a) {
                switch (_a.label) {
                    case 0:
                        this.logger.info('Requesting session information');
                        requestId = "session-info-".concat(Date.now(), "-").concat(Math.random().toString(36).substring(2, 10));
                        message = {
                            type: 'request_session',
                            requestId: requestId,
                            timestamp: Date.now(),
                            deviceId: DeviceIdManager.getInstance().getDeviceId()
                        };
                        _a.label = 1;
                    case 1:
                        _a.trys.push([1, 3, , 4]);
                        return [4 /*yield*/, this.sendRequest(message, function (msg) { return msg.type === 'session_info' && msg.requestId === requestId; })];
                    case 2:
                        response = _a.sent();
                        this.logger.info('Session info response received', response);
                        return [2 /*return*/, __assign(__assign({}, response), { success: true, userId: response.userId || 'unknown', status: response.status || 'active', createdAt: response.createdAt || Date.now(), simulatorId: response.simulatorId || null })];
                    case 3:
                        error_1 = _a.sent();
                        this.logger.error('Error requesting session info', {
                            error: error_1 instanceof Error ? error_1.message : String(error_1)
                        });
                        throw error_1;
                    case 4: return [2 /*return*/];
                }
            });
        });
    };
    SessionHandler.prototype.stopSession = function () {
        return __awaiter(this, void 0, void 0, function () {
            var requestId, message;
            return __generator(this, function (_a) {
                this.logger.info('Requesting session stop');
                requestId = "stop-session-".concat(Date.now(), "-").concat(Math.random().toString(36).substring(2, 10));
                message = {
                    type: 'stop_session',
                    requestId: requestId,
                    timestamp: Date.now(),
                    deviceId: DeviceIdManager.getInstance().getDeviceId()
                };
                return [2 /*return*/, this.sendRequest(message, function (msg) { return msg.type === 'session_stopped' && msg.requestId === requestId; })];
            });
        });
    };
    SessionHandler.prototype.sendRequest = function (message, predicate) {
        return __awaiter(this, void 0, void 0, function () {
            var _this = this;
            return __generator(this, function (_a) {
                return [2 /*return*/, new Promise(function (resolve, reject) {
                        var timeoutId = window.setTimeout(function () {
                            subscription.unsubscribe();
                            reject(new Error("Request timed out after ".concat(_this.responseTimeoutMs, "ms")));
                        }, _this.responseTimeoutMs);
                        var subscription = _this.client.on('message', function (msg) {
                            if (predicate(msg)) {
                                window.clearTimeout(timeoutId);
                                subscription.unsubscribe();
                                resolve(msg);
                            }
                        });
                        if (!_this.client.send(message)) {
                            window.clearTimeout(timeoutId);
                            subscription.unsubscribe();
                            reject(new Error('Failed to send request: client not connected'));
                        }
                    })];
            });
        });
    };
    return SessionHandler;
}());
export { SessionHandler };
