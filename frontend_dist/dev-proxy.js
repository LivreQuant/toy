const express = require('express');
const { createProxyMiddleware } = require('http-proxy-middleware');

const app = express();

app.use(['/books', '/simulator'], createProxyMiddleware({
  target: 'http://app.trading.local:3002',
  changeOrigin: true,
}));

app.use('/', createProxyMiddleware({
  target: 'http://app.trading.local:3000', 
  changeOrigin: true,
}));

app.listen(8080, () => console.log('Dev proxy: http://trading.local:8080'));