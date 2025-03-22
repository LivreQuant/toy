// api-adapter/index.js
const express = require('express');
const grpc = require('@grpc/grpc-js');
const protoLoader = require('@grpc/proto-loader');
const path = require('path');
const cors = require('cors');
const fs = require('fs');
const https = require('https');
const http = require('http');
const rateLimit = require('express-rate-limit');

// Initialize Express app
const app = express();

// Middleware
app.use(express.json());
app.use(cors({
  origin: process.env.CORS_ORIGIN || '*',
  methods: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
  allowedHeaders: ['Content-Type', 'Authorization'],
  credentials: true
}));

// Add security headers
app.use((req, res, next) => {
  res.setHeader('Strict-Transport-Security', 'max-age=31536000; includeSubDomains');
  res.setHeader('X-Content-Type-Options', 'nosniff');
  res.setHeader('X-Frame-Options', 'DENY');
  res.setHeader('X-XSS-Protection', '1; mode=block');
  res.setHeader('Content-Security-Policy', "default-src 'self'");
  next();
});

// Rate limiters
const authLimiter = rateLimit({
  windowMs: 15 * 60 * 1000, // 15 minutes
  max: 100, // limit each IP to 100 requests per windowMs
  standardHeaders: true,
  legacyHeaders: false,
  message: { error: 'Too many authentication attempts, please try again later' }
});

// General API limiter
const apiLimiter = rateLimit({
  windowMs: 5 * 60 * 1000, // 5 minutes
  max: 300, // limit each IP to 300 requests per windowMs
  standardHeaders: true,
  legacyHeaders: false
});

// Apply rate limiters
app.use('/api/auth/login', authLimiter);
app.use('/api/auth/refresh', authLimiter);
app.use('/api', apiLimiter);

// Environment config
const USE_TLS = process.env.USE_TLS === 'true';
const PORT = process.env.PORT || 3001;
const AUTH_SERVICE = process.env.AUTH_SERVICE || 'auth-service:50051';
const SESSION_SERVICE = process.env.SESSION_SERVICE || 'session-manager:50052';

// TLS configuration
let authClient, sessionClient;

if (USE_TLS) {
  try {
    // Load TLS certificates
    const rootCert = fs.readFileSync(path.resolve(__dirname, '../certs/ca.crt'));
    const clientKey = fs.readFileSync(path.resolve(__dirname, '../certs/client.key'));
    const clientCert = fs.readFileSync(path.resolve(__dirname, '../certs/client.crt'));

    // Create gRPC credentials for secure communication
    const channelCredentials = grpc.credentials.createSsl(
      rootCert,
      clientKey,
      clientCert
    );

    // Load proto definitions
    const AUTH_PROTO_PATH = path.resolve(__dirname, '../protobuf/main/auth.proto');
    const SESSION_PROTO_PATH = path.resolve(__dirname, '../protobuf/main/session_manager.proto');

    const authPackageDefinition = protoLoader.loadSync(AUTH_PROTO_PATH, {
      keepCase: true,
      longs: String,
      enums: String,
      defaults: true,
      oneofs: true
    });

    const sessionPackageDefinition = protoLoader.loadSync(SESSION_PROTO_PATH, {
      keepCase: true,
      longs: String,
      enums: String,
      defaults: true,
      oneofs: true
    });

    const authProto = grpc.loadPackageDefinition(authPackageDefinition);
    const sessionProto = grpc.loadPackageDefinition(sessionPackageDefinition);

    // Create secure gRPC clients
    authClient = new authProto.AuthService(AUTH_SERVICE, channelCredentials);
    sessionClient = new sessionProto.SessionManagerService(SESSION_SERVICE, channelCredentials);

    console.log('gRPC clients initialized with TLS');
  } catch (error) {
    console.error('Failed to initialize secure gRPC clients:', error);
    process.exit(1);
  }
} else {
  // Load proto definitions without TLS
  const AUTH_PROTO_PATH = path.resolve(__dirname, '../protobuf/main/auth.proto');
  const SESSION_PROTO_PATH = path.resolve(__dirname, '../protobuf/main/session_manager.proto');

  const authPackageDefinition = protoLoader.loadSync(AUTH_PROTO_PATH, {
    keepCase: true,
    longs: String,
    enums: String,
    defaults: true,
    oneofs: true
  });

  const sessionPackageDefinition = protoLoader.loadSync(SESSION_PROTO_PATH, {
    keepCase: true,
    longs: String,
    enums: String,
    defaults: true,
    oneofs: true
  });

  const authProto = grpc.loadPackageDefinition(authPackageDefinition);
  const sessionProto = grpc.loadPackageDefinition(sessionPackageDefinition);

  // Create insecure gRPC clients
  authClient = new authProto.AuthService(AUTH_SERVICE, grpc.credentials.createInsecure());
  sessionClient = new sessionProto.SessionManagerService(SESSION_SERVICE, grpc.credentials.createInsecure());

  console.log('gRPC clients initialized without TLS');
}

// Authentication middleware
const authenticateToken = (req, res, next) => {
  const authHeader = req.headers['authorization'];
  const token = authHeader && authHeader.split(' ')[1];
  
  if (!token) {
    return res.status(401).json({ error: 'Authentication required' });
  }
  
  authClient.ValidateToken({ token }, (err, response) => {
    if (err) {
      console.error('Error validating token:', err);
      return res.status(500).json({ error: 'Internal server error' });
    }
    
    if (!response.valid) {
      return res.status(401).json({ error: 'Invalid or expired token' });
    }
    
    // Store user ID for use in route handlers
    req.userId = response.user_id;
    next();
  });
};

// === AUTH SERVICE ENDPOINTS ===

// Login endpoint
app.post('/api/auth/login', (req, res) => {
  const { username, password } = req.body;
  
  if (!username || !password) {
    return res.status(400).json({ error: 'Username and password are required' });
  }
  
  authClient.Login({ username, password }, (err, response) => {
    if (err) {
      console.error('gRPC error during login:', err);
      return res.status(500).json({ error: 'Service unavailable' });
    }
    
    if (!response.success) {
      return res.status(401).json({ error: response.error_message });
    }
    
    res.json({
      accessToken: response.access_token,
      refreshToken: response.refresh_token,
      expiresIn: response.expires_in
    });
  });
});

// Token refresh endpoint
app.post('/api/auth/refresh', (req, res) => {
  const { refreshToken } = req.body;
  
  if (!refreshToken) {
    return res.status(400).json({ error: 'Refresh token is required' });
  }
  
  authClient.RefreshToken({ refresh_token: refreshToken }, (err, response) => {
    if (err) {
      console.error('gRPC error during token refresh:', err);
      return res.status(500).json({ error: 'Service unavailable' });
    }
    
    if (!response.success) {
      return res.status(401).json({ error: response.error_message });
    }
    
    res.json({
      accessToken: response.access_token,
      refreshToken: response.refresh_token,
      expiresIn: response.expires_in
    });
  });
});

// Logout endpoint
app.post('/api/auth/logout', (req, res) => {
  const authHeader = req.headers['authorization'];
  const token = authHeader && authHeader.split(' ')[1];
  const { refreshToken, logoutAllSessions } = req.body;
  
  if (!token) {
    return res.status(200).json({ success: true });
  }
  
  const metadata = new grpc.Metadata();
  if (refreshToken) {
    metadata.add('refresh_token', refreshToken);
  }
  
  if (logoutAllSessions) {
    metadata.add('logout_all_sessions', 'true');
  }
  
  authClient.Logout({ token }, metadata, (err, response) => {
    if (err) {
      console.error('gRPC error during logout:', err);
      return res.status(500).json({ error: 'Service unavailable' });
    }
    
    res.json({ success: response.success });
  });
});

// === SESSION SERVICE ENDPOINTS ===

// Create session endpoint
app.post('/api/session/create', authenticateToken, (req, res) => {
  const token = req.headers['authorization'].split(' ')[1];
  
  sessionClient.CreateSession({
    user_id: req.userId,
    token: token
  }, (err, response) => {
    if (err) {
      console.error('gRPC error during session creation:', err);
      return res.status(500).json({ error: 'Service unavailable' });
    }
    
    if (!response.success) {
      return res.status(400).json({ 
        success: false,
        error: response.error_message 
      });
    }
    
    res.json({
      success: true,
      sessionId: response.session_id,
      podName: response.pod_name || null
    });
  });
});

// Get session endpoint
app.get('/api/session/get', authenticateToken, (req, res) => {
  const token = req.headers['authorization'].split(' ')[1];
  const { sessionId } = req.query;
  
  if (!sessionId) {
    return res.status(400).json({ error: 'Session ID is required' });
  }
  
  sessionClient.GetSession({
    session_id: sessionId,
    token: token
  }, (err, response) => {
    if (err) {
      console.error('gRPC error during session retrieval:', err);
      return res.status(500).json({ error: 'Service unavailable' });
    }
    
    res.json({
      sessionActive: response.session_active,
      simulatorEndpoint: response.simulator_endpoint,
      podName: response.pod_name || null,
      errorMessage: response.error_message
    });
  });
});

// Keep alive endpoint
app.post('/api/session/keep-alive', authenticateToken, (req, res) => {
  const token = req.headers['authorization'].split(' ')[1];
  const { sessionId } = req.body;
  
  if (!sessionId) {
    return res.status(400).json({ error: 'Session ID is required' });
  }
  
  sessionClient.KeepAlive({
    session_id: sessionId,
    token: token
  }, (err, response) => {
    if (err) {
      console.error('gRPC error during keep-alive:', err);
      return res.status(500).json({ error: 'Service unavailable' });
    }
    
    res.json({ success: response.success });
  });
});

// Get session state endpoint
app.get('/api/session/state', authenticateToken, (req, res) => {
  const token = req.headers['authorization'].split(' ')[1];
  const { sessionId } = req.query;
  
  if (!sessionId) {
    return res.status(400).json({ error: 'Session ID is required' });
  }
  
  sessionClient.GetSessionState({
    session_id: sessionId,
    token: token
  }, (err, response) => {
    if (err) {
      console.error('gRPC error during session state retrieval:', err);
      return res.status(500).json({ error: 'Service unavailable' });
    }
    
    if (!response.success) {
      return res.status(400).json({ 
        success: false,
        error: response.error_message 
      });
    }
    
    res.json({
      success: true,
      simulatorId: response.simulator_id,
      simulatorEndpoint: response.simulator_endpoint,
      sessionCreatedAt: response.session_created_at,
      lastActive: response.last_active,
      podName: response.pod_name || null
    });
  });
});

// Reconnect session endpoint
app.post('/api/session/reconnect', authenticateToken, (req, res) => {
  const token = req.headers['authorization'].split(' ')[1];
  const { sessionId, reconnectAttempt } = req.body;
  
  if (!sessionId) {
    return res.status(400).json({ error: 'Session ID is required' });
  }
  
  sessionClient.ReconnectSession({
    session_id: sessionId,
    token: token,
    reconnect_attempt: reconnectAttempt || 1
  }, (err, response) => {
    if (err) {
      console.error('gRPC error during session reconnection:', err);
      return res.status(500).json({ error: 'Service unavailable' });
    }
    
    if (!response.success) {
      return res.status(400).json({ 
        success: false,
        error: response.error_message 
      });
    }
    
    res.json({
      success: true,
      sessionId: response.session_id,
      simulatorId: response.simulator_id,
      simulatorEndpoint: response.simulator_endpoint,
      simulatorStatus: response.simulator_status,
      podTransferred: response.pod_transferred || false,
      podName: response.pod_name || null
    });
  });
});

// Connection quality endpoint
app.post('/api/session/connection-quality', authenticateToken, (req, res) => {
  const token = req.headers['authorization'].split(' ')[1];
  const { sessionId, latencyMs, missedHeartbeats, connectionType } = req.body;
  
  if (!sessionId) {
    return res.status(400).json({ error: 'Session ID is required' });
  }
  
  sessionClient.UpdateConnectionQuality({
    session_id: sessionId,
    token: token,
    latency_ms: latencyMs || 0,
    missed_heartbeats: missedHeartbeats || 0,
    connection_type: connectionType || 'unknown'
  }, (err, response) => {
    if (err) {
      console.error('gRPC error during connection quality update:', err);
      return res.status(500).json({ error: 'Service unavailable' });
    }
    
    res.json({
      quality: response.quality,
      reconnectRecommended: response.reconnect_recommended
    });
  });
});

// Health check endpoint
app.get('/health', (req, res) => {
  res.status(200).send('OK');
});

// Readiness check endpoint that actually checks gRPC services
app.get('/readiness', (req, res) => {
  Promise.all([
    new Promise((resolve, reject) => {
      authClient.ValidateToken({ token: 'health-check' }, (err, _) => {
        if (err) {
          console.error('Auth service health check failed:', err);
          reject(err);
        } else {
          resolve();
        }
      });
    }),
    new Promise((resolve, reject) => {
      // Use a dummy request just to check connectivity
      sessionClient.GetSessionState({ 
        session_id: '00000000-0000-0000-0000-000000000000',
        token: 'health-check'
      }, (err, _) => {
        if (err) {
          console.error('Session service health check failed:', err);
          reject(err);
        } else {
          resolve();
        }
      });
    })
  ]).then(() => {
    res.status(200).send('READY');
  }).catch(() => {
    res.status(503).send('NOT READY');
  });
});

// Generic error handler
app.use((err, req, res, next) => {
  console.error('Unhandled error:', err);
  res.status(500).json({ error: 'Internal server error' });
});

// Server startup
if (USE_TLS) {
  try {
    // HTTPS configuration
    const httpsOptions = {
      key: fs.readFileSync(path.resolve(__dirname, '../certs/server.key')),
      cert: fs.readFileSync(path.resolve(__dirname, '../certs/server.crt')),
      ca: fs.readFileSync(path.resolve(__dirname, '../certs/ca.crt')),
      requestCert: false,  // Don't require client certs for web clients
      rejectUnauthorized: false
    };
    
    // Create HTTPS server
    https.createServer(httpsOptions, app).listen(PORT, () => {
      console.log(`HTTPS API server running on port ${PORT}`);
    });
  } catch (error) {
    console.error('Failed to start HTTPS server:', error);
    // Fallback to HTTP if certificates can't be loaded
    http.createServer(app).listen(PORT, () => {
      console.log(`HTTP API server running on port ${PORT} (TLS failed to initialize)`);
    });
  }
} else {
  // Start regular HTTP server
  http.createServer(app).listen(PORT, () => {
    console.log(`HTTP API server running on port ${PORT}`);
  });
}