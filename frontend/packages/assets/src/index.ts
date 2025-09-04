// The base path now points to your local asset server.
// For production, you would change this one line to your real CDN URL.
const IMAGE_BASE_PATH = 'http://localhost:8080/images';

export const ENTERPRISE_IMAGES = {
  CANDIDATE: `${IMAGE_BASE_PATH}/enterprise/candidate.png`,
  MONEYBALL: `${IMAGE_BASE_PATH}/enterprise/moneyball.jpg`,
  NEEDLE: `${IMAGE_BASE_PATH}/enterprise/needle.jpeg`,
  VET: `${IMAGE_BASE_PATH}/enterprise/vet.jpg`,
} as const;

export const FEATURES_IMAGES = {
  ANALYTICS: `${IMAGE_BASE_PATH}/features/analytics.jpeg`,
  API: `${IMAGE_BASE_PATH}/features/api.jpeg`,
  DASHBOARD: `${IMAGE_BASE_PATH}/features/dashboard.png`,
  LOCK: `${IMAGE_BASE_PATH}/features/lock.jpg`,
  MARKET_SIMULATOR: `${IMAGE_BASE_PATH}/features/market_simulator.jpeg`,
  QED: `${IMAGE_BASE_PATH}/features/qed.jpg`,
} as const;

export const HERO_IMAGES = {
  DASHBOARD: `${IMAGE_BASE_PATH}/hero/dashboard.png`,
  FACTSHEET: `${IMAGE_BASE_PATH}/hero/factsheet.jpg`,
  YARN: `${IMAGE_BASE_PATH}/hero/yarn.png`,
} as const;

export const HOW_IT_WORKS_IMAGES = {
  BLOCKCHAIN: `${IMAGE_BASE_PATH}/howItWorks/blockchain.jpeg`,
  FACTSHEET: `${IMAGE_BASE_PATH}/howItWorks/factsheet.jpg`,
  STRATEGY: `${IMAGE_BASE_PATH}/howItWorks/strategy.jpeg`,
  TRADES: `${IMAGE_BASE_PATH}/howItWorks/trades.png`,
} as const;