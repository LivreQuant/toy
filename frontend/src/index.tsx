// src/index.tsx
import React from 'react';
import ReactDOM from 'react-dom';
import App from './App';
import { setupLocalKubernetesCors } from '../old/services/config/CorsConfig';
import { getServiceConfig } from '../old/services/config/ServiceConfig';
import './index.css';

// Set up CORS for local Kubernetes testing if needed
setupLocalKubernetesCors();

// Log environment information
const config = getServiceConfig();
console.log(`Running in ${config.isLocalK8s ? 'local Kubernetes' : process.env.NODE_ENV} mode`);

ReactDOM.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
  document.getElementById('root')
);