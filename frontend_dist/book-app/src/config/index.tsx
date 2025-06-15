// src/config/index.tsx
// Re-export from unified config package
export * from '@trading-app/config';

// Also export the local environment service for backward compatibility if needed
export { environmentService } from './environment';