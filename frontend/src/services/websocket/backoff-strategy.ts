// src/services/websocket/backoff-strategy.ts
export class BackoffStrategy {
    private attempt: number = 0;
    private initialBackoff: number;
    private maxBackoff: number;
    
    constructor(initialBackoff: number, maxBackoff: number) {
      this.initialBackoff = initialBackoff;
      this.maxBackoff = maxBackoff;
    }
    
    public nextBackoffTime(): number {
      this.attempt++;
      const backoff = Math.min(
        this.maxBackoff,
        this.initialBackoff * Math.pow(2, this.attempt - 1)
      );
      
      // Add jitter to prevent thundering herd problem
      const jitter = 0.5 + Math.random();
      return Math.floor(backoff * jitter);
    }
    
    public reset(): void {
      this.attempt = 0;
    }
    
    public getCurrentAttempt(): number {
      return this.attempt;
    }
  }