export class FundApi {
    constructor(client) {
        this.client = client;
    }
    /**
     * Creates a new fund profile
     */
    async createFundProfile(fundData) {
        return this.client.post('/funds', fundData);
    }
    /**
     * Retrieves the current user's fund profile
     */
    async getFundProfile() {
        return this.client.get('/funds');
    }
    /**
     * Updates an existing fund profile
     */
    async updateFundProfile(updates) {
        return this.client.put(`/funds`, updates);
    }
}
