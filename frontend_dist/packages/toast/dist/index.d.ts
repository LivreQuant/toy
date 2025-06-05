export interface ToastConfig {
    type: 'success' | 'error' | 'warning' | 'info';
    message: string;
    duration?: number;
    id?: string;
}
export declare class ToastService {
    private static instance;
    private displayToastMethod;
    private logger;
    private activeToastIds;
    private constructor();
    static getInstance(): ToastService;
    /**
     * Called by the ToastContext provider to register the function
     * that adds a toast message to the UI.
     * @param method - The function to call to display a toast.
     */
    registerDisplayMethod(method: (config: ToastConfig) => void): void;
    /**
     * Displays a success toast.
     * @param message - The text to display.
     * @param duration - Optional duration in ms (default: 5000).
     * @param id - Optional unique ID to prevent duplicates.
     */
    success(message: string, duration?: number, id?: string): void;
    /**
     * Displays an error toast.
     * @param message - The text to display.
     * @param duration - Optional duration in ms (default: 7000). Longer for errors.
     * @param id - Optional unique ID to prevent duplicates.
     */
    error(message: string, duration?: number, id?: string): void;
    /**
     * Displays a warning toast.
     * @param message - The text to display.
     * @param duration - Optional duration in ms (default: 6000).
     * @param id - Optional unique ID to prevent duplicates.
     */
    warning(message: string, duration?: number, id?: string): void;
    /**
     * Displays an informational toast.
     * @param message - The text to display.
     * @param duration - Optional duration in ms (default: 5000).
     * @param id - Optional unique ID to prevent duplicates.
     */
    info(message: string, duration?: number, id?: string): void;
    /**
     * Internal method to call the registered display function.
     * @param config - The configuration for the toast message.
     */
    private show;
}
export declare const toastService: ToastService;
