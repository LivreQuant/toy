const express = require('express');
const { createProxyMiddleware } = require('http-proxy-middleware');

console.log('🔍 Starting proxy server...');

const app = express();

// Add error handling
app.use((req, res, next) => {
 console.log(`🔍 PROXY DEBUG: ${req.method} ${req.path} from ${req.get('host')}`);
 console.log(`🔍 PROXY URL: ${req.url}`);
 console.log(`🔍 REFERER: ${req.get('referer') || 'none'}`);
 next();
});

console.log('📦 Setting up routes...');

// Create proxy middleware instances
const mainProxy = createProxyMiddleware({
 target: 'http://localhost:3000',
 changeOrigin: true,
 onError: (err, req, res) => {
   console.error('❌ Main app proxy error:', err.message);
   res.status(502).send('Main app unavailable');
 },
 onProxyReq: (proxyReq, req, res) => {
   console.log('🏠 MAIN APP PROXY: Forwarding', req.originalUrl, 'to http://localhost:3000');
 },
 onProxyRes: (proxyRes, req, res) => {
   console.log('🏠 MAIN APP RESPONSE: Status', proxyRes.statusCode, 'Content-Type:', proxyRes.headers['content-type']);
 }
});

const landingProxy = createProxyMiddleware({
 target: 'http://localhost:3001',
 changeOrigin: true,
 onError: (err, req, res) => {
   console.error('❌ Landing app proxy error:', err.message);
   res.status(502).send('Landing app unavailable');
 },
 onProxyReq: (proxyReq, req, res) => {
   console.log('🎯 LANDING APP PROXY: Forwarding', req.originalUrl, 'to http://localhost:3001');
 },
 onProxyRes: (proxyRes, req, res) => {
   console.log('🎯 LANDING APP RESPONSE: Status', proxyRes.statusCode, 'Content-Type:', proxyRes.headers['content-type']);
 }
});

const bookProxy = createProxyMiddleware({
 target: 'http://localhost:3002',
 changeOrigin: true,
 onError: (err, req, res) => {
   console.error('❌ Book app proxy error:', err.message);
   res.status(502).send('Book app unavailable');
 },
 onProxyReq: (proxyReq, req, res) => {
   console.log('📚 BOOK APP PROXY: Forwarding', req.originalUrl, 'to http://localhost:3002');
 },
 onProxyRes: (proxyRes, req, res) => {
   console.log('📚 BOOK APP RESPONSE: Status', proxyRes.statusCode, 'Content-Type:', proxyRes.headers['content-type']);
 }
});

// Test route
app.get('/app/test', (req, res) => {
 console.log('🧪 TEST ROUTE HIT: /app/test');
 res.send('TEST ROUTE WORKS - THIS IS THE EXPRESS SERVER');
});

// Book app routes - MUST BE BEFORE main app routes
app.use('/book', (req, res, next) => {
 console.log('📚 EXPRESS ROUTE: /book matched for', req.path);
 console.log('📚 ORIGINAL URL:', req.originalUrl);
 bookProxy(req, res, next);
});

app.use('/simulator', (req, res, next) => {
 console.log('📚 EXPRESS ROUTE: /simulator matched for', req.path);
 console.log('📚 ORIGINAL URL:', req.originalUrl);
 bookProxy(req, res, next);
});

// Main app routes
app.use('/app', (req, res, next) => {
 console.log('🏠 EXPRESS ROUTE: /app matched for', req.path);
 console.log('🏠 ORIGINAL URL:', req.originalUrl);
 mainProxy(req, res, next);
});

// Route static assets with proper path handling
app.use('/static', (req, res, next) => {
 const referer = req.get('referer') || '';
 console.log('📦 STATIC ASSET REQUEST:', req.originalUrl);
 console.log('📦 REFERER:', referer);
 
 // Restore the full path for proxying
 req.url = req.originalUrl;
 
 if (referer.includes('/book/') || referer.includes('/simulator/')) {
   console.log('📦 ROUTING STATIC TO BOOK APP (referer contains /book/ or /simulator/)');
   bookProxy(req, res, next);
 } else if (referer.includes('/app/')) {
   console.log('📦 ROUTING STATIC TO MAIN APP (referer contains /app/)');
   mainProxy(req, res, next);
 } else {
   console.log('📦 ROUTING STATIC TO LANDING APP (default)');
   landingProxy(req, res, next);
 }
});

// Landing app (catch-all) - MUST BE LAST
app.use('/', (req, res, next) => {
 console.log('🎯 EXPRESS ROUTE: catch-all matched for', req.path);
 landingProxy(req, res, next);
});

const PORT = 8081;

app.listen(PORT, (err) => {
 if (err) {
   console.error('❌ Failed to start proxy:', err);
   process.exit(1);
 }
 
 console.log(`🚀 Dev proxy running on http://localhost:${PORT}`);
 console.log('🎯 Landing: http://localhost:8081/');
 console.log('🏠 Main: http://localhost:8081/app');
 console.log('📚 Book: http://localhost:8081/book');
 console.log('🎮 Simulator: http://localhost:8081/simulator');
 console.log('🧪 Test: http://localhost:8081/app/test');
 
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