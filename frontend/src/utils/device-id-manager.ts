// src/utils/device-id-manager.ts
// Keep as static for now to minimize disruption, ensure it's the single source of truth.
export class DeviceIdManager {
  private static readonly DEVICE_ID_KEY = 'trading_device_id';

  /**
   * Generates and stores a new device ID, or returns existing one
   */
  public static getDeviceId(): string {
    let deviceId = localStorage.getItem(this.DEVICE_ID_KEY);

    if (!deviceId) {
      deviceId = this.generateDeviceId();
      localStorage.setItem(this.DEVICE_ID_KEY, deviceId); // Store immediately
    }

    return deviceId;
  }

  /**
   * Generate a new unique device ID (private as it's internal logic)
   */
  private static generateDeviceId(): string {
    return `device_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;
  }

  /**
   * Clear device ID from localStorage
   */
  public static clearDeviceId(): void {
    localStorage.removeItem(this.DEVICE_ID_KEY);
  }

  /**
   * Check if device ID exists
   */
  public static hasDeviceId(): boolean {
    return localStorage.getItem(this.DEVICE_ID_KEY) !== null;
  }
}