
// src/utils/backoff-strategy.ts
export class BackoffStrategy {
  private attempt: number = 0;
  private initialBackoff: number;
  private maxBackoff: number;
  private readonly jitterFactor: number = 0.5; // Controls jitter range (0.5 to 1.5)
  
  constructor(initialBackoff: number, maxBackoff: number) {
    this.initialBackoff = initialBackoff;
    this.maxBackoff = maxBackoff;
  }
  
  public nextBackoffTime(): number {
    this.attempt++;
    
    // Calculate base backoff with exponential increase
    const baseBackoff = Math.min(
      this.maxBackoff,
      this.initialBackoff * Math.pow(2, this.attempt - 1)
    );
    
    // Add jitter (baseBackoff * random value between 0.5 and 1.5)
    const jitter = 1 - this.jitterFactor + (Math.random() * this.jitterFactor * 2);
    return Math.floor(baseBackoff * jitter);
  }
  
  public reset(): void {
    this.attempt = 0;
  }
  
  public getCurrentAttempt(): number {
    return this.attempt;
  }
}