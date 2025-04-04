import { ConnectionMetrics } from './types';

export class MetricTracker {
  private latencyMeasurements: number[] = [];
  private packetLossMeasurements: number[] = [];

  async collectMetrics(): Promise<Partial<ConnectionMetrics>> {
    const latency = await this.measureLatency();
    const packetLoss = this.calculatePacketLoss();

    return {
      latency,
      packetLoss
    };
  }

  private async measureLatency(): Promise<number> {
    const start = Date.now();
    try {
      // Perform a lightweight ping
      const response = await fetch('/ping', { 
        method: 'HEAD',
        cache: 'no-store'
      });
      
      const end = Date.now();
      
      const latency = end - start;
      this.latencyMeasurements.push(latency);
      
      // Keep only last 10 measurements
      if (this.latencyMeasurements.length > 10) {
        this.latencyMeasurements.shift();
      }

      return this.calculateAverage(this.latencyMeasurements);
    } catch (error) {
      console.warn('Latency measurement failed:', error);
      return Infinity;
    }
  }

  private calculatePacketLoss(): number {
    // Simulate packet loss tracking
    // In a real scenario, this would be more sophisticated
    const totalAttempts = 100;
    const failedAttempts = this.packetLossMeasurements.length;
    
    return (failedAttempts / totalAttempts) * 100;
  }

  private calculateAverage(measurements: number[]): number {
    if (measurements.length === 0) return 0;
    return measurements.reduce((a, b) => a + b, 0) / measurements.length;
  }
}