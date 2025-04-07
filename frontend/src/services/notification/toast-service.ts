// src/services/notification/toast-service.ts

// Define the structure for toast messages managed by the service/context
export interface ToastConfig {
    type: 'success' | 'error' | 'warning' | 'info';
    message: string;
    duration?: number; // Milliseconds, 0 or undefined for manual dismissal
}


export class ToastService {
  private static instance: ToastService;
  // The function provided by the ToastContext to actually display the toast
  private displayToastMethod: ((config: ToastConfig) => void) | null = null;

  // Private constructor for singleton pattern
  private constructor() {}

  // Singleton getter
  public static getInstance(): ToastService {
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
  registerDisplayMethod(method: (config: ToastConfig) => void) {
    this.displayToastMethod = method;
  }

  // --- Public methods for triggering toasts ---

  /**
   * Displays a success toast.
   * @param message - The text to display.
   * @param duration - Optional duration in ms (default: 5000).
   */
  success(message: string, duration = 5000) {
    this.show({ type: 'success', message, duration });
  }

  /**
   * Displays an error toast.
   * @param message - The text to display.
   * @param duration - Optional duration in ms (default: 7000). Longer for errors.
   */
  error(message: string, duration = 7000) {
    this.show({ type: 'error', message, duration });
  }

  /**
   * Displays a warning toast.
   * @param message - The text to display.
   * @param duration - Optional duration in ms (default: 5000).
   */
  warning(message: string, duration = 5000) {
    this.show({ type: 'warning', message, duration });
  }

  /**
   * Displays an informational toast.
   * @param message - The text to display.
   * @param duration - Optional duration in ms (default: 5000).
   */
  info(message: string, duration = 5000) {
    this.show({ type: 'info', message, duration });
  }

  /**
   * Internal method to call the registered display function.
   * @param config - The configuration for the toast message.
   */
  private show(config: ToastConfig) {
    if (this.displayToastMethod) {
      this.displayToastMethod(config);
    } else {
      // Fallback if the context hasn't registered the method yet
      // (shouldn't happen in normal operation after app initialization)
      console.warn(`ToastService: Display method not registered. Toast dropped:`, config);
       // Basic console logging as a fallback
       switch(config.type) {
           case 'error': console.error(`Toast [${config.type}]: ${config.message}`); break;
           case 'warning': console.warn(`Toast [${config.type}]: ${config.message}`); break;
           default: console.log(`Toast [${config.type}]: ${config.message}`); break;
       }
    }
  }
}

// Export singleton instance for easy import in services like ErrorHandler
export const toastService = ToastService.getInstance();