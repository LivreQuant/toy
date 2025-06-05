import { DeviceIdManager } from '../services/auth/device-id-manager';
import { config } from '../config';
import { getLogger } from '../boot/logging';
import { toastService } from '../services/notification/toast-service';
export class HttpClient {
    constructor(tokenManager) {
        this.logger = getLogger('HttpClient');
        this.maxRetries = 0; // NO RETRIES
        this.baseUrl = config.apiBaseUrl;
        this.tokenManager = tokenManager;
    }
    // Public methods
    async get(endpoint, options = {}) {
        return this.request('GET', endpoint, undefined, options);
    }
    async post(endpoint, data, options = {}) {
        // For convictions, always set retries to 0
        if (endpoint.includes('/convictions/submit') || endpoint.includes('/convictions/cancel')) {
            options.retries = 0; // Force zero retries for convictions
        }
        return this.request('POST', endpoint, data, options);
    }
    async put(endpoint, data, options = {}) {
        return this.request('PUT', endpoint, data, options);
    }
    async delete(endpoint, options = {}) {
        return this.request('DELETE', endpoint, undefined, options);
    }
    async postMultipart(endpoint, formData, options = {}) {
        var _a;
        // Create full URL string
        const fullUrl = `${this.baseUrl}${endpoint}`;
        // Get device ID for authentication (SAME AS REGULAR REQUESTS)
        const deviceId = DeviceIdManager.getInstance().getDeviceId();
        // Add deviceId as a query parameter by appending to endpoint string (SAME AS REGULAR REQUESTS)
        const urlWithDeviceId = fullUrl + (fullUrl.includes('?') ? '&' : '?') + `deviceId=${deviceId}`;
        // Initialize headers
        const headers = {};
        // Add Authorization header if not skipping auth
        if (!options.skipAuth) {
            const accessToken = await ((_a = this.tokenManager) === null || _a === void 0 ? void 0 : _a.getAccessToken());
            if (!accessToken) {
                throw new Error("Not authenticated");
            }
            headers['Authorization'] = `Bearer ${accessToken}`;
            // Add CSRF protection for authenticated endpoints
            try {
                const csrfToken = await this.tokenManager.getCsrfToken();
                if (csrfToken) {
                    headers['X-CSRF-Token'] = csrfToken;
                }
            }
            catch (error) {
                this.logger.warn('Failed to get CSRF token for multipart request', { error });
            }
        }
        // Don't set Content-Type for FormData - let the browser set it with boundary
        // The browser will automatically set 'multipart/form-data' with the correct boundary
        const fetchOptions = Object.assign({ method: 'POST', headers: headers, body: formData }, options);
        try {
            const response = await fetch(urlWithDeviceId, fetchOptions);
            if (!response.ok) {
                // Handle error response using the same pattern as your main request method
                return await this.handleHttpErrorResponse(response, 'POST', endpoint, formData, options, 0);
            }
            // Handle successful responses
            if (response.status === 204) { // No Content
                return undefined;
            }
            // Assuming successful responses return JSON
            const responseData = await response.json();
            return responseData;
        }
        catch (networkError) {
            // Handle network failures using the same pattern as your main request method
            return await this.handleNetworkOrFetchError(networkError, 'POST', endpoint, formData, options, 0);
        }
    }
    async request(method, endpoint, data, options = {}, retryCount = 0) {
        // Never retry conviction operations
        if ((endpoint.includes('/convictions/submit') || endpoint.includes('/convictions/cancel')) && retryCount > 0) {
            this.logger.error(`BLOCKING RETRY attempt for conviction endpoint: ${endpoint}`, { retryCount });
            throw new Error("Conviction operations cannot be retried");
        }
        // Create full URL string
        const fullUrl = `${this.baseUrl}${endpoint}`;
        // Get device ID for authentication
        const deviceId = DeviceIdManager.getInstance().getDeviceId();
        // Add deviceId as a query parameter by appending to endpoint string
        const urlWithDeviceId = fullUrl + (fullUrl.includes('?') ? '&' : '?') + `deviceId=${deviceId}`;
        const headers = new Headers(options.headers || {});
        headers.append('Content-Type', 'application/json');
        // Add Authorization header if needed
        if (!options.skipAuth) {
            const token = await this.tokenManager.getAccessToken(); // Handles refresh internally
            if (!token) {
                throw new Error("Not authenticated");
            }
            headers.append('Authorization', `Bearer ${token}`);
            // Add CSRF protection for authenticated endpoints
            const csrfToken = await this.tokenManager.getCsrfToken();
            if (csrfToken) {
                headers.append('X-CSRF-Token', csrfToken);
            }
        }
        const fetchOptions = Object.assign(Object.assign({}, options), { method: method, headers: headers, body: data ? JSON.stringify(data) : undefined });
        try {
            const response = await fetch(urlWithDeviceId, fetchOptions);
            if (!response.ok) {
                return await this.handleHttpErrorResponse(response, method, endpoint, data, options, retryCount);
            }
            // Handle successful responses
            if (response.status === 204) { // No Content
                return undefined;
            }
            // Assuming successful responses return JSON
            const responseData = await response.json();
            return responseData;
        }
        catch (networkError) {
            // Handle network failures (never retry convictions)
            if (endpoint.includes('/convictions/submit') || endpoint.includes('/convictions/cancel')) {
                this.logger.error(`Network error for conviction endpoint: ${endpoint} - NO RETRY`, {
                    error: networkError.message
                });
                throw new Error(`Network error for conviction operation: ${networkError.message} - NOT RETRIED`);
            }
            return await this.handleNetworkOrFetchError(networkError, method, endpoint, data, options, retryCount);
        }
    }
    async handleHttpErrorResponse(response, method, endpoint, data, options, retryCount) {
        var _a;
        console.log(`🔍 HTTP: Error response from ${method} ${endpoint}:`, {
            status: response.status,
            statusText: response.statusText
        });
        let errorMessage = options.customErrorMessage || `HTTP Error ${response.status}: ${response.statusText}`;
        let errorDetails = null;
        try {
            // Parse the error response body
            errorDetails = await response.json();
            console.log("🔍 HTTP: Error response body:", JSON.stringify(errorDetails));
            // For authentication endpoints, handle verification required case
            if (endpoint.includes('/auth/login') &&
                response.status === 401 &&
                errorDetails &&
                errorDetails.requiresVerification) {
                // Return the parsed response even though it's a 401
                // This allows the login component to handle the verification redirect
                console.log("🔍 HTTP: Detected verification required response");
                return errorDetails;
            }
            // Normal error message handling
            if (typeof (errorDetails === null || errorDetails === void 0 ? void 0 : errorDetails.message) === 'string') {
                errorMessage = errorDetails.message;
            }
            else if (typeof (errorDetails === null || errorDetails === void 0 ? void 0 : errorDetails.error) === 'string') {
                errorMessage = errorDetails.error;
            }
        }
        catch (e) {
            console.error("🔍 HTTP: Could not parse error response body:", e);
            this.logger.debug('Could not parse error response body as JSON', { status: response.status, endpoint });
        }
        // Check if this is an auth endpoint with special error handling
        if (endpoint.includes('/auth/login') && response.status === 401) {
            console.log("🔍 HTTP: Special handling for login 401 response");
            if (errorDetails) {
                console.log("🔍 HTTP: Returning error details as response");
                return errorDetails;
            }
        }
        // Check if this is an conviction endpoint - never retry
        if (endpoint.includes('/convictions/submit') || endpoint.includes('/convictions/cancel')) {
            this.logger.error(`Error for conviction endpoint ${endpoint}: ${response.status} - NO RETRY`, {
                status: response.status,
                error: errorMessage
            });
            // Show error toast for conviction operations unless suppressed
            if (!options.suppressErrorToast) {
                toastService.error(`Conviction operation failed: ${errorMessage}`);
            }
            throw new Error(`Conviction operation failed (${response.status}): ${errorMessage} - NOT RETRIED`);
        }
        // --- Handle different status codes ---
        if (response.status === 401 && !options.skipAuth && retryCount < 1) {
            this.logger.warn('Received 401 Unauthorized, attempting token refresh...', { endpoint });
            try {
                const refreshed = await this.tokenManager.refreshAccessToken();
                if (refreshed) {
                    this.logger.info('Token refresh successful, retrying original request.', { endpoint });
                    return this.request(method, endpoint, data, options, retryCount + 1);
                }
                else {
                    errorMessage = options.customErrorMessage || 'Session expired or invalid. Please log in again.';
                    this.logger.error(`Token refresh failed after 401. ${errorMessage}`);
                    // Show session expired toast unless suppressed
                    if (!options.suppressErrorToast) {
                        toastService.error(errorMessage, 0); // Manual dismiss for important auth errors
                    }
                    throw new Error(errorMessage);
                }
            }
            catch (refreshError) {
                errorMessage = options.customErrorMessage || 'Session refresh failed. Please log in again.';
                this.logger.error(`Error during token refresh attempt. ${errorMessage}`);
                // Show session refresh error toast unless suppressed
                if (!options.suppressErrorToast) {
                    toastService.error(errorMessage, 0);
                }
                throw new Error(errorMessage);
            }
        }
        else if (response.status === 403) {
            errorMessage = options.customErrorMessage || (errorDetails === null || errorDetails === void 0 ? void 0 : errorDetails.message) || 'Permission denied.';
            this.logger.error(`[Forbidden] ${errorMessage}`);
            // Show permission error toast unless suppressed
            if (!options.suppressErrorToast) {
                toastService.error(`Access denied: ${errorMessage}`);
            }
        }
        else if (response.status === 404) {
            errorMessage = options.customErrorMessage || (errorDetails === null || errorDetails === void 0 ? void 0 : errorDetails.message) || 'Resource not found.';
            this.logger.error(`[NotFound] ${errorMessage}`);
            // Show not found toast unless suppressed
            if (!options.suppressErrorToast) {
                toastService.warning(`Not found: ${errorMessage}`);
            }
        }
        else if (response.status >= 400 && response.status < 500) {
            errorMessage = options.customErrorMessage || (errorDetails === null || errorDetails === void 0 ? void 0 : errorDetails.message) || `Client error ${response.status}.`;
            this.logger.error(`.ClientError${response.status} ${errorMessage}`);
            // Show client error toast unless suppressed
            if (!options.suppressErrorToast) {
                toastService.error(errorMessage);
            }
        }
        else if (response.status >= 500) {
            errorMessage = options.customErrorMessage || `Server error (${response.status}). NOT RETRYING.`;
            // Never retry 5xx errors for conviction endpoints
            if (!endpoint.includes('/convictions/submit') && !endpoint.includes('/convictions/cancel')) {
                const maxRetriesForServerError = (_a = options.retries) !== null && _a !== void 0 ? _a : this.maxRetries;
                if (retryCount < maxRetriesForServerError) {
                    const delay = Math.pow(2, retryCount) * 500 + (Math.random() * 500);
                    this.logger.warn(`Server error ${response.status}. Retrying request in ${delay.toFixed(0)}ms (attempt ${retryCount + 1}/${maxRetriesForServerError})`, { endpoint });
                    // Show retry toast unless suppressed
                    if (!options.suppressErrorToast) {
                        toastService.info(`Server error. Retrying in ${Math.round(delay / 1000)} seconds...`);
                    }
                    await new Promise(resolve => setTimeout(resolve, delay));
                    return this.request(method, endpoint, data, options, retryCount + 1);
                }
                else {
                    this.logger.error(`Server error ${response.status} persisted after ${maxRetriesForServerError} retries.`, { endpoint, details: errorDetails });
                    // Show persistent server error toast unless suppressed
                    if (!options.suppressErrorToast) {
                        toastService.error(`Server error persisted after multiple retries: ${errorMessage}`, 0);
                    }
                }
            }
            else {
                this.logger.error(`Server error ${response.status} for conviction endpoint: ${endpoint} - NO RETRY ATTEMPTED`, { endpoint });
                // Show server error toast for conviction endpoints unless suppressed
                if (!options.suppressErrorToast) {
                    toastService.error(`Server error for conviction operation: ${errorMessage}`);
                }
            }
        }
        if (response.status >= 400) {
            this.logger.error(`.Unhandled${response.status} ${errorMessage}`);
            // Show general error toast unless suppressed
            if (!options.suppressErrorToast) {
                toastService.error(errorMessage);
            }
            throw new Error(errorMessage);
        }
        this.logger.error("handleHttpErrorResponse reached unexpectedly for non-error response", { status: response.status });
        throw new Error("Unexpected non-error response in error handler");
    }
    async getCsrfHeader() {
        // Only add CSRF token for authenticated endpoints
        if (!this.tokenManager.isAuthenticated()) {
            return {};
        }
        try {
            const csrfToken = await this.tokenManager.getCsrfToken();
            return { 'X-CSRF-Token': csrfToken };
        }
        catch (e) {
            this.logger.warn('Failed to get CSRF token for request', { error: e });
            return {};
        }
    }
    async handleNetworkOrFetchError(error, method, endpoint, data, options, retryCount) {
        var _a;
        const errorMessage = options.customErrorMessage || `Network error: ${error.message}`;
        this.logger.error('Network or fetch error occurred', { endpoint, error: error.message, retryCount });
        // Never retry conviction operations
        if (endpoint.includes('/convictions/submit') || endpoint.includes('/convictions/cancel')) {
            this.logger.error(`Network error for conviction endpoint: ${endpoint} - NO RETRY`, {
                error: error.message
            });
            // Show network error toast for conviction operations unless suppressed
            if (!options.suppressErrorToast) {
                toastService.error(`Network error for conviction operation: ${error.message}`);
            }
            throw new Error(`Network error for conviction operation: ${error.message} - NOT RETRIED`);
        }
        // Simple retry logic for non-conviction operations
        const maxRetriesForNetworkError = (_a = options.retries) !== null && _a !== void 0 ? _a : this.maxRetries;
        if (retryCount < maxRetriesForNetworkError) {
            const delay = Math.pow(2, retryCount) * 1000 + (Math.random() * 1000);
            this.logger.warn(`Network error. Retrying request in ${delay.toFixed(0)}ms (attempt ${retryCount + 1}/${maxRetriesForNetworkError})`, { endpoint });
            // Show retry toast unless suppressed
            if (!options.suppressErrorToast) {
                toastService.info(`Connection issue. Retrying in ${Math.round(delay / 1000)} seconds...`);
            }
            await new Promise(resolve => setTimeout(resolve, delay));
            return this.request(method, endpoint, data, options, retryCount + 1);
        }
        else {
            this.logger.error(`Network error persisted after. ${errorMessage}`);
            // Show persistent network error toast unless suppressed
            if (!options.suppressErrorToast) {
                toastService.error(`Connection failed: ${errorMessage}`, 0); // Manual dismiss for persistent errors
            }
            throw new Error(errorMessage);
        }
    }
}
