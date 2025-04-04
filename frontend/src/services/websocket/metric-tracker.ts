import { ConnectionMetrics } from './types';
import { Logger } from '../../utils/logger';

export class MetricTracker {
  private latencyMeasurements: number[] = [];
  private packetLossMeasurements: number[] = [];
  private totalPackets: number = 0;
  private lostPackets: number = 0;

  constructor(private logger: Logger) {} // Assuming you'll implement a Logger

  async collectMetrics(webSocket: WebSocket): Promise<Partial<ConnectionMetrics>> {
    try {
      const latency = await this.measureLatency();
      const packetLoss = this.calculatePacketLoss(webSocket);

      // Log metrics for monitoring
      this.logger.info('Connection Metrics', { latency, packetLoss });

      return {
        latency,
        packetLoss
      };
    } catch (error) {
      this.logger.error('Metric collection failed', { error });
      throw new Error('Failed to collect connection metrics');
    }
  }

  private async measureLatency(): Promise<number> {
    const start = Date.now();
    try {
      // Perform a network request to measure actual latency
      const response = await fetch('/network-ping', { 
        method: 'HEAD',
        cache: 'no-store',
        signal: AbortSignal.timeout(5000) // 5-second timeout
      });
      
      const end = Date.now();
      const latency = end - start;

      // Update latency measurements
      this.latencyMeasurements.push(latency);
      
      // Keep only last 10 measurements
      if (this.latencyMeasurements.length > 10) {
        this.latencyMeasurements.shift();
      }

      return this.calculateAverage(this.latencyMeasurements);
    } catch (error) {
      this.logger.warn('Latency measurement failed', { error });
      return Infinity;
    }
  }

  private calculatePacketLoss(webSocket: WebSocket): number {
    // Actual packet loss tracking based on WebSocket state and events
    if (!webSocket || webSocket.readyState !== WebSocket.OPEN) {
      return 100; // Consider 100% loss if socket is not open
    }

    // Reset metrics periodically
    if (this.totalPackets > 1000) {
      this.totalPackets = 0;
      this.lostPackets = 0;
    }

    // Actual calculation based on tracked packets
    const packetLossPercentage = this.totalPackets > 0 
      ? (this.lostPackets / this.totalPackets) * 100 
      : 0;

    return packetLossPercentage;
  }

  // Method to track packet transmission
  public trackPacketTransmission(success: boolean): void {
    this.totalPackets++;
    if (!success) {
      this.lostPackets++;
    }
  }

  private calculateAverage(measurements: number[]): number {
    if (measurements.length === 0) return 0;
    return measurements.reduce((a, b) => a + b, 0) / measurements.length;
  }
}