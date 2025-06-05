export class AuthApi {
    constructor(client) {
        this.client = client;
    }
    async login(username, password) {
        console.log("🔍 API: Attempting login for user:", username);
        try {
            const response = await this.client.post('/auth/login', { username, password }, { skipAuth: true });
            console.log("🔍 API: Login response received:", JSON.stringify(response));
            return response;
        }
        catch (error) {
            console.error("🔍 API: Login request failed:", error);
            throw error;
        }
    }
    async logout() {
        return this.client.post('/auth/logout');
    }
    async refreshToken(refreshToken) {
        return this.client.post('/auth/refresh', { refreshToken }, { skipAuth: true });
    }
    async signup(data) {
        return this.client.post('/auth/signup', data, { skipAuth: true });
    }
    async verifyEmail(data) {
        return this.client.post('/auth/verify-email', data, { skipAuth: true });
    }
    async resendVerification(data) {
        return this.client.post('/auth/resend-verification', data, { skipAuth: true });
    }
    async forgotUsername(data) {
        return this.client.post('/auth/forgot-username', data, { skipAuth: true });
    }
    async forgotPassword(data) {
        return this.client.post('/auth/forgot-password', data, { skipAuth: true });
    }
    async resetPassword(data) {
        return this.client.post('/auth/reset-password', data, { skipAuth: true });
    }
}
