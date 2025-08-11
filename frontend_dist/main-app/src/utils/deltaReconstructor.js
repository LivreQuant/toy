// frontend/src/utils/deltaReconstructor.js
/**
 * Delta message reconstructor for WebSocket client.
 * Handles delta messages and reconstructs full state on the frontend.
 */

class DeltaReconstructor {
    constructor() {
        this.lastCompleteState = null;
        this.lastSequence = 0;
        this.statistics = {
            messagesReceived: 0,
            fullMessages: 0,
            deltaMessages: 0,
            compressedMessages: 0,
            totalOriginalSize: 0,
            totalReceivedSize: 0,
            reconstructionErrors: 0
        };
    }

    /**
     * Process incoming delta message and reconstruct full state
     * @param {Object} message - WebSocket message with delta data
     * @returns {Object} - Reconstructed complete exchange data
     */
    processMessage(message) {
        try {
            this.statistics.messagesReceived++;
            
            const { deltaType, sequence, data, compressed, timestamp } = message;
            
            // Validate sequence
            if (sequence !== this.lastSequence + 1) {
                console.warn(`Sequence gap detected. Expected ${this.lastSequence + 1}, got ${sequence}`);
                // Request full refresh from server
                this.requestFullRefresh();
                return null;
            }
            
            this.lastSequence = sequence;
            
            let processedData = data;
            
            // Decompress if needed
            if (compressed && data.__compressed__) {
                processedData = this.decompressData(data);
                this.statistics.compressedMessages++;
            }
            
            let reconstructedState;
            
            switch (deltaType) {
                case 'FULL':
                case 'COMPRESSED':
                    // Full payload - store as complete state
                    this.lastCompleteState = this.deepCopy(processedData);
                    reconstructedState = this.lastCompleteState;
                    this.statistics.fullMessages++;
                    break;
                    
                case 'DELTA':
                    // Delta payload - apply changes to last state
                    if (!this.lastCompleteState) {
                        console.error('Received delta without previous state');
                        this.requestFullRefresh();
                        return null;
                    }
                    
                    reconstructedState = this.applyDelta(this.lastCompleteState, processedData);
                    this.lastCompleteState = reconstructedState;
                    this.statistics.deltaMessages++;
                    break;
                    
                default:
                    console.error(`Unknown delta type: ${deltaType}`);
                    return null;
            }
            
            // Update statistics
            this.updateStatistics(message);
            
            return {
                ...reconstructedState,
                _meta: {
                    deltaType,
                    sequence,
                    timestamp,
                    compressed,
                    reconstructed: deltaType === 'DELTA'
                }
            };
            
        } catch (error) {
            console.error('Error processing delta message:', error);
            this.statistics.reconstructionErrors++;
            this.requestFullRefresh();
            return null;
        }
    }

    /**
     * Decompress zlib-compressed data
     * @param {Object} compressedData - Compressed data object
     * @returns {Object} - Decompressed data
     */
    decompressData(compressedData) {
        try {
            if (!compressedData.__compressed__ || compressedData.__algorithm__ !== 'zlib') {
                throw new Error('Invalid compressed data format');
            }
            
            // Decode base64
            const compressedBytes = atob(compressedData.__data__);
            const compressedArray = new Uint8Array(compressedBytes.length);
            for (let i = 0; i < compressedBytes.length; i++) {
                compressedArray[i] = compressedBytes.charCodeAt(i);
            }
            
            // Decompress using pako (zlib for JavaScript)
            // Note: You'll need to include pako library in your project
            const decompressed = pako.inflate(compressedArray, { to: 'string' });
            
            return JSON.parse(decompressed);
            
        } catch (error) {
            console.error('Decompression failed:', error);
            throw error;
        }
    }

    /**
     * Apply delta changes to base state
     * @param {Object} baseState - Current complete state
     * @param {Object} delta - Changes to apply
     * @returns {Object} - New state with changes applied
     */
    applyDelta(baseState, delta) {
        const result = this.deepCopy(baseState);
        
        for (const [key, value] of Object.entries(delta)) {
            if (value === null) {
                // Delete key
                delete result[key];
            } else if (typeof value === 'object' && !Array.isArray(value) && 
                      typeof result[key] === 'object' && !Array.isArray(result[key])) {
                // Recursively apply nested delta
                result[key] = this.applyDelta(result[key] || {}, value);
            } else {
                // Set/replace value
                result[key] = this.deepCopy(value);
            }
        }
        
        return result;
    }

    /**
     * Deep copy an object
     * @param {*} obj - Object to copy
     * @returns {*} - Deep copy
     */
    deepCopy(obj) {
        if (obj === null || typeof obj !== 'object') return obj;
        if (obj instanceof Date) return new Date(obj.getTime());
        if (Array.isArray(obj)) return obj.map(item => this.deepCopy(item));
        
        const copy = {};
        for (const [key, value] of Object.entries(obj)) {
            copy[key] = this.deepCopy(value);
        }
        return copy;
    }

    /**
     * Update internal statistics
     * @param {Object} message - WebSocket message
     */
    updateStatistics(message) {
        // Estimate sizes (rough calculation)
        const messageSize = JSON.stringify(message).length;
        this.statistics.totalReceivedSize += messageSize;
        
        // If we have compression ratio info, calculate original size
        if (message.compressionRatio) {
            this.statistics.totalOriginalSize += messageSize * message.compressionRatio;
        } else {
            this.statistics.totalOriginalSize += messageSize;
        }
    }

    /**
     * Request full refresh from server (implementation depends on your WebSocket protocol)
     */
    requestFullRefresh() {
        console.log('Requesting full refresh from server');
        // You would typically send a message to the server requesting a full state
        // This depends on your WebSocket message protocol
        if (this.onRequestFullRefresh) {
            this.onRequestFullRefresh();
        }
    }

    /**
     * Reset reconstructor state
     */
    reset() {
        this.lastCompleteState = null;
        this.lastSequence = 0;
        console.log('Delta reconstructor reset');
    }

    /**
     * Get compression and delta statistics
     * @returns {Object} - Statistics object
     */
    getStatistics() {
        const bandwidthSavings = this.statistics.totalOriginalSize > 0 
            ? ((this.statistics.totalOriginalSize - this.statistics.totalReceivedSize) / this.statistics.totalOriginalSize * 100)
            : 0;
            
        return {
            ...this.statistics,
            bandwidthSavings: `${bandwidthSavings.toFixed(1)}%`,
            averageCompressionRatio: this.statistics.totalOriginalSize / Math.max(1, this.statistics.totalReceivedSize)
        };
    }

    /**
     * Set callback for when full refresh is needed
     * @param {Function} callback - Callback function
     */
    setRefreshCallback(callback) {
        this.onRequestFullRefresh = callback;
    }
}

export default DeltaReconstructor;