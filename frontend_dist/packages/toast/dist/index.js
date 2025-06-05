// src/services/notification/toast-service.ts
// Import from the correct logging package
import { getLogger } from '@trading-app/logging';
export class ToastService {
    // Private constructor for singleton pattern
    constructor() {
        this.displayToastMethod = null;
        this.logger = getLogger('ToastService');
        // Track active toast IDs to prevent duplicates
        this.activeToastIds = new Set();
    }
    // Singleton getter
    static getInstance() {
        if (!ToastService.instance) {
            ToastService.instance = new ToastService();
        }
        return ToastService.instance;
    }
    /**
     * Called by the ToastContext provider to register the function
     * that adds a toast message to the UI.
     * @param method - The function to call to display a toast.
     */
    registerDisplayMethod(method) {
        this.displayToastMethod = method;
    }
    // --- Public methods for triggering toasts ---
    /**
     * Displays a success toast.
     * @param message - The text to display.
     * @param duration - Optional duration in ms (default: 5000).
     * @param id - Optional unique ID to prevent duplicates.
     */
    success(message, duration = 5000, id) {
        this.show({ type: 'success', message, duration, id });
    }
    /**
     * Displays an error toast.
     * @param message - The text to display.
     * @param duration - Optional duration in ms (default: 7000). Longer for errors.
     * @param id - Optional unique ID to prevent duplicates.
     */
    error(message, duration = 7000, id) {
        this.show({ type: 'error', message, duration, id });
    }
    /**
     * Displays a warning toast.
     * @param message - The text to display.
     * @param duration - Optional duration in ms (default: 6000).
     * @param id - Optional unique ID to prevent duplicates.
     */
    warning(message, duration = 6000, id) {
        this.show({ type: 'warning', message, duration, id });
    }
    /**
     * Displays an informational toast.
     * @param message - The text to display.
     * @param duration - Optional duration in ms (default: 5000).
     * @param id - Optional unique ID to prevent duplicates.
     */
    info(message, duration = 5000, id) {
        this.show({ type: 'info', message, duration, id });
    }
    /**
     * Internal method to call the registered display function.
     * @param config - The configuration for the toast message.
     */
    show(config) {
        // Check for duplicate if ID is provided
        if (config.id && this.activeToastIds.has(config.id)) {
            this.logger.debug(`Toast with ID "${config.id}" already active, skipping duplicate`);
            return;
        }
        if (this.displayToastMethod) {
            // If there's an ID, track it to prevent duplicates
            if (config.id) {
                this.activeToastIds.add(config.id);
                // Set up automatic removal of the ID after the toast duration
                // Add 500ms buffer to ensure toast is fully dismissed
                const clearDelay = config.duration ? config.duration + 500 : 10000; // Default 10s for manual dismiss
                setTimeout(() => {
                    this.activeToastIds.delete(config.id);
                    this.logger.debug(`Removed toast ID "${config.id}" from active tracking`);
                }, clearDelay);
            }
            this.displayToastMethod(config);
        }
        else {
            // Fallback if the context hasn't registered the method yet
            this.logger.warn(`ToastService: Display method not registered. Toast dropped:`, config);
            // Basic console logging as a fallback
            switch (config.type) {
                case 'error':
                    console.error(`Toast [${config.type}]: ${config.message}`);
                    break;
                case 'warning':
                    console.warn(`Toast [${config.type}]: ${config.message}`);
                    break;
                default:
                    console.log(`Toast [${config.type}]: ${config.message}`);
                    break;
            }
        }
    }
}
// Export singleton instance for easy import in services like ErrorHandler
export const toastService = ToastService.getInstance();
