const express = require('express');
const { createProxyMiddleware } = require('http-proxy-middleware');

console.log('🔍 Starting proxy server...');

const app = express();

// Add error handling
app.use((err, req, res, next) => {
  console.error('❌ Proxy error:', err);
  res.status(500).send('Proxy error');
});

console.log('📦 Setting up routes...');

// Order matters! Most specific routes first
app.use(['/books', '/simulator'], createProxyMiddleware({
  target: 'http://localhost:3002',
  changeOrigin: true,
  onError: (err, req, res) => {
    console.error('❌ Book app proxy error:', err.message);
    res.status(502).send('Book app unavailable');
  },
  onProxyReq: (proxyReq, req, res) => {
    console.log('📚 Proxying to book app:', req.path);
  }
}));

// IMPORTANT: Add /app route BEFORE the catch-all /
app.use('/app', createProxyMiddleware({
  target: 'http://localhost:3000',
  changeOrigin: true,
  pathRewrite: {
    '^/app': '', // Remove /app prefix when forwarding to main app
  },
  onError: (err, req, res) => {
    console.error('❌ Main app proxy error:', err.message);
    res.status(502).send('Main app unavailable');
  },
  onProxyReq: (proxyReq, req, res) => {
    console.log('🏠 Proxying to main app:', req.path, '-> target path:', req.path.replace('/app', ''));
  }
}));

// Landing app (catch-all, must be last)
app.use('/', createProxyMiddleware({
  target: 'http://localhost:3001',
  changeOrigin: true,
  onError: (err, req, res) => {
    console.error('❌ Landing app proxy error:', err.message);
    res.status(502).send('Landing app unavailable');
  },
  onProxyReq: (proxyReq, req, res) => {
    console.log('🎯 Proxying to landing app:', req.path);
  }
}));

const PORT = 8081;

app.listen(PORT, (err) => {
  if (err) {
    console.error('❌ Failed to start proxy:', err);
    process.exit(1);
  }
  
  console.log(`🚀 Dev proxy running on http://localhost:${PORT}`);
  console.log('🏠 Landing: http://localhost:8081/');
  console.log('📱 Main: http://localhost:8081/app');
  console.log('📚 Books: http://localhost:8081/books/...');
  console.log('🎮 Simulator: http://localhost:8081/simulator/...');
  
  // Test if target servers are reachable
  const http = require('http');
  
  [3001, 3000, 3002].forEach(port => {
    const req = http.get(`http://localhost:${port}`, (res) => {
      console.log(`✅ Port ${port} is responding`);
    }).on('error', (err) => {
      console.log(`❌ Port ${port} is NOT responding:`, err.message);
    });
    
    setTimeout(() => req.destroy(), 1000);
  });
});