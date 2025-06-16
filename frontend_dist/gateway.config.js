// Production gateway configuration
const express = require('express');
const { createProxyMiddleware } = require('http-proxy-middleware');
const path = require('path');

const app = express();

// Health check endpoint
app.get('/health', (req, res) => {
  res.json({ status: 'ok', timestamp: new Date().toISOString() });
});

// Static assets for each app
app.use('/static/land', express.static(path.join(__dirname, 'land-app/build/static')));
app.use('/static/main', express.static(path.join(__dirname, 'main-app/build/static')));
app.use('/static/book', express.static(path.join(__dirname, 'book-app/build/static')));

// API proxy
app.use('/api', createProxyMiddleware({
  target: process.env.API_URL || 'http://api-server:8080',
  changeOrigin: true,
  pathRewrite: {
    '^/api': ''
  }
}));

// WebSocket proxy
app.use('/ws', createProxyMiddleware({
  target: process.env.WS_URL || 'ws://api-server:8080',
  ws: true,
  changeOrigin: true
}));

// App routing with fallbacks to built files
const serveApp = (appPath, buildPath) => {
  return (req, res, next) => {
    // Try to serve static file first
    express.static(buildPath)(req, res, () => {
      // Fallback to index.html for SPA routing
      res.sendFile(path.join(buildPath, 'index.html'));
    });
  };
};

// Book app routes
app.use(['/books', '/simulator'], serveApp('/books', path.join(__dirname, 'book-app/build')));

// Main app routes
app.use('/home', serveApp('/home', path.join(__dirname, 'main-app/build')));

// Landing app (catch-all)
app.use('/', serveApp('/', path.join(__dirname, 'land-app/build')));

const PORT = process.env.PORT || 8080;

app.listen(PORT, () => {
  console.log(`🚀 Production gateway running on port ${PORT}`);
  console.log(`🏠 Landing: http://localhost:${PORT}/`);
  console.log(`📱 Main: http://localhost:${PORT}/home`);
  console.log(`📚 Books: http://localhost:${PORT}/books`);
  console.log(`🎮 Simulator: http://localhost:${PORT}/simulator`);
});