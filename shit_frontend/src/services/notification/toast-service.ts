// src/services/notification/toast-service.ts
export class ToastService {
  private static instance: ToastService;
  private addToast: ((message: any) => void) | null = null;

  // Singleton pattern
  public static getInstance(): ToastService {
    if (!ToastService.instance) {
      ToastService.instance = new ToastService();
    }
    return ToastService.instance;
  }

  // Method to set the toast function from context
  setToastMethod(method: (message: any) => void) {
    this.addToast = method;
  }

  success(message: string, duration = 5000) {
    this.addToast?.({
      type: 'success',
      message,
      duration
    });
  }

  error(message: string, duration = 5000) {
    this.addToast?.({
      type: 'error',
      message,
      duration
    });
  }

  warning(message: string, duration = 5000) {
    this.addToast?.({
      type: 'warning',
      message,
      duration
    });
  }

  info(message: string, duration = 5000) {
    this.addToast?.({
      type: 'info',
      message,
      duration
    });
  }
}

// Export singleton instance
export const toastService = ToastService.getInstance();