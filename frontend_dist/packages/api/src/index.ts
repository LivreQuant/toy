// frontend_dist/packages/api/src/index.ts
// Export core classes
export * from './core/http-client';
export * from './core/base-client';

// Export individual clients
export * from './clients/auth-client';
export * from './clients/book-client';
export * from './clients/conviction-client';
export * from './clients/fund-client';

// Export factory
export * from './factories/api-factory';

// Export types
export * from './types';

// Export factory as default for easy consumption
export { ApiFactory as default } from './factories/api-factory';