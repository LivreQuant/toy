// frontend_dist/main-app/src/components/Debug/WebSocketConfigDebug.tsx
import React, { useEffect, useState } from 'react';
import { getLogger } from '@trading-app/logging';
import { getWebSocketConfig } from '../../config/websocket-config';
import { createConnectionManagerWithGlobalDeps } from '@trading-app/websocket';

const logger = getLogger('WebSocketConfigDebug');

interface TestResult {
  status: 'idle' | 'connecting' | 'connected' | 'failed';
  error?: string;
  details?: any;
}

const WebSocketConfigDebug: React.FC = () => {
  const [config, setConfig] = useState<any>(null);
  const [globalConfig, setGlobalConfig] = useState<any>(null);
  const [testConnection, setTestConnection] = useState<TestResult>({ status: 'idle' });
  const [testGlobalConnection, setTestGlobalConnection] = useState<TestResult>({ status: 'idle' });

  useEffect(() => {
    // Test local config
    const wsConfig = getWebSocketConfig();
    setConfig(wsConfig);
    logger.info('Local WebSocket config loaded', wsConfig);

    // Test global config service
    try {
      const { configService } = createConnectionManagerWithGlobalDeps();
      const globalWsUrl = configService.getWebSocketUrl();
      const globalReconnectionConfig = configService.getReconnectionConfig();
      
      setGlobalConfig({
        url: globalWsUrl,
        reconnection: globalReconnectionConfig
      });
      logger.info('Global WebSocket config loaded', { url: globalWsUrl, reconnection: globalReconnectionConfig });
    } catch (error: any) {
      logger.error('Failed to load global config', { error: error.message });
      setGlobalConfig({ error: error.message });
    }
  }, []);

  const testWebSocketConnection = (url: string, isGlobal = false) => {
    const setTestState = isGlobal ? setTestGlobalConnection : setTestConnection;
    
    setTestState({ status: 'connecting' });
    logger.info(`Testing WebSocket connection to: ${url}`, { isGlobal });
    
    try {
      const testWs = new WebSocket(url);
      
      testWs.onopen = () => {
        logger.info('✅ Test WebSocket connection successful', { url, isGlobal });
        setTestState({ 
          status: 'connected',
          details: {
            protocol: testWs.protocol,
            extensions: testWs.extensions,
            readyState: testWs.readyState
          }
        });
        testWs.close();
      };
      
      testWs.onerror = (error) => {
        logger.error('❌ Test WebSocket connection failed', { error, url, isGlobal });
        setTestState({ 
          status: 'failed', 
          error: 'Connection failed - check console for details',
          details: { errorEvent: error }
        });
      };
      
      testWs.onclose = (event) => {
        logger.info('Test WebSocket connection closed', { 
          code: event.code, 
          reason: event.reason,
          url,
          isGlobal
        });
      };
      
      // Timeout after 5 seconds
      setTimeout(() => {
        if (testWs.readyState === WebSocket.CONNECTING) {
          testWs.close();
          setTestState({ 
            status: 'failed', 
            error: 'Connection timeout after 5 seconds',
            details: { reason: 'timeout', readyState: testWs.readyState }
          });
        }
      }, 5000);
      
    } catch (error: any) {
      logger.error('❌ Failed to create test WebSocket', { error: error.message, url, isGlobal });
      setTestState({ 
        status: 'failed', 
        error: error.message,
        details: { exception: error.name }
      });
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'connected': return '#28a745';
      case 'failed': return '#dc3545';
      case 'connecting': return '#ffc107';
      default: return '#6c757d';
    }
  };

  const formatJson = (obj: any) => JSON.stringify(obj, null, 2);

  if (!config) return <div>Loading config...</div>;

  return (
    <div style={{ 
      padding: '20px', 
      border: '2px solid #dc3545', 
      margin: '20px',
      backgroundColor: '#fff5f5',
      borderRadius: '8px',
      fontFamily: 'monospace'
    }}>
      <h2 style={{ color: '#dc3545', marginBottom: '20px' }}>
        🚨 WEBSOCKET DEBUG - React: localhost:3000 → Backend: trading.local/ws
      </h2>
      
      <div style={{ 
        backgroundColor: '#d4edda', 
        border: '1px solid #c3e6cb',
        borderRadius: '4px',
        padding: '15px',
        marginBottom: '20px',
        fontSize: '14px'
      }}>
        <h4 style={{ margin: '0 0 10px 0', color: '#155724' }}>✅ CORRECT SETUP:</h4>
        <ul style={{ margin: 0, paddingLeft: '20px', color: '#155724' }}>
          <li><strong>React App:</strong> Runs on localhost:3000 (npm start)</li>
          <li><strong>WebSocket:</strong> Connects to ws://trading.local/ws (YOUR BACKEND)</li>
          <li><strong>Browser:</strong> Access http://localhost:3000 in browser</li>
        </ul>
      </div>

      {/* Environment Variables Section */}
      <div style={{ marginBottom: '25px' }}>
        <h3 style={{ color: '#495057', borderBottom: '1px solid #dee2e6', paddingBottom: '5px' }}>
          🌍 Environment Variables
        </h3>
        <pre style={{ 
          backgroundColor: '#ffffff', 
          padding: '15px', 
          borderRadius: '4px',
          fontSize: '11px',
          border: '1px solid #dee2e6',
          overflow: 'auto'
        }}>
          {formatJson({
            NODE_ENV: process.env.NODE_ENV,
            REACT_APP_WS_URL: process.env.REACT_APP_WS_URL,
            REACT_APP_API_BASE_URL: process.env.REACT_APP_API_BASE_URL,
            REACT_APP_ENV: process.env.REACT_APP_ENV,
            window_location: typeof window !== 'undefined' ? {
              hostname: window.location.hostname,
              port: window.location.port,
              protocol: window.location.protocol,
              href: window.location.href
            } : 'server-side'
          })}
        </pre>
      </div>

      {/* Local Config Section */}
      <div style={{ marginBottom: '25px' }}>
        <h3 style={{ color: '#495057', borderBottom: '1px solid #dee2e6', paddingBottom: '5px' }}>
          ⚙️ WebSocket Configuration (Should point to YOUR BACKEND)
        </h3>
        <pre style={{ 
          backgroundColor: '#ffffff', 
          padding: '15px', 
          borderRadius: '4px',
          fontSize: '11px',
          border: '1px solid #dee2e6'
        }}>
          {formatJson(config)}
        </pre>
        
        <div style={{ marginTop: '10px' }}>
          <button 
            onClick={() => testWebSocketConnection(config.url, false)}
            disabled={testConnection.status === 'connecting'}
            style={{
              padding: '8px 16px',
              backgroundColor: testConnection.status === 'connecting' ? '#6c757d' : '#007bff',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              cursor: testConnection.status === 'connecting' ? 'not-allowed' : 'pointer',
              fontSize: '12px'
            }}
          >
            {testConnection.status === 'connecting' ? 'Testing Backend...' : 'Test Backend Connection'}
          </button>
          
          <div style={{ marginTop: '8px' }}>
            <strong>Backend Test Status:</strong> 
            <span style={{ color: getStatusColor(testConnection.status), marginLeft: '8px' }}>
              {testConnection.status.toUpperCase()}
            </span>
            {testConnection.error && (
              <div style={{ color: '#dc3545', marginTop: '5px', fontSize: '11px' }}>
                Error: {testConnection.error}
              </div>
            )}
            {testConnection.details && (
              <details style={{ marginTop: '5px', fontSize: '10px' }}>
                <summary>Details</summary>
                <pre style={{ marginTop: '5px', padding: '5px', backgroundColor: '#f8f9fa' }}>
                  {formatJson(testConnection.details)}
                </pre>
              </details>
            )}
          </div>
        </div>
      </div>

      {/* Global Config Section */}
      <div style={{ marginBottom: '25px' }}>
        <h3 style={{ color: '#495057', borderBottom: '1px solid #dee2e6', paddingBottom: '5px' }}>
          🌐 Global WebSocket Configuration (Package)
        </h3>
        <pre style={{ 
          backgroundColor: '#ffffff', 
          padding: '15px', 
          borderRadius: '4px',
          fontSize: '11px',
          border: '1px solid #dee2e6'
        }}>
          {formatJson(globalConfig)}
        </pre>
        
        {globalConfig && !globalConfig.error && (
          <div style={{ marginTop: '10px' }}>
            <button 
              onClick={() => testWebSocketConnection(globalConfig.url, true)}
              disabled={testGlobalConnection.status === 'connecting'}
              style={{
                padding: '8px 16px',
                backgroundColor: testGlobalConnection.status === 'connecting' ? '#6c757d' : '#28a745',
                color: 'white',
                border: 'none',
                borderRadius: '4px',
                cursor: testGlobalConnection.status === 'connecting' ? 'not-allowed' : 'pointer',
                fontSize: '12px'
              }}
            >
              {testGlobalConnection.status === 'connecting' ? 'Testing Global...' : 'Test Global Config'}
            </button>
            
            <div style={{ marginTop: '8px' }}>
              <strong>Global Test Status:</strong> 
              <span style={{ color: getStatusColor(testGlobalConnection.status), marginLeft: '8px' }}>
                {testGlobalConnection.status.toUpperCase()}
              </span>
              {testGlobalConnection.error && (
                <div style={{ color: '#dc3545', marginTop: '5px', fontSize: '11px' }}>
                  Error: {testGlobalConnection.error}
                </div>
              )}
              {testGlobalConnection.details && (
                <details style={{ marginTop: '5px', fontSize: '10px' }}>
                  <summary>Details</summary>
                  <pre style={{ marginTop: '5px', padding: '5px', backgroundColor: '#f8f9fa' }}>
                    {formatJson(testGlobalConnection.details)}
                  </pre>
                </details>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Quick Actions */}
      <div style={{ marginBottom: '15px' }}>
        <h3 style={{ color: '#495057', borderBottom: '1px solid #dee2e6', paddingBottom: '5px' }}>
          ⚡ Quick Actions
        </h3>
        <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
          <button 
            onClick={() => window.location.reload()}
            style={{
              padding: '6px 12px',
              backgroundColor: '#17a2b8',
              color: 'white',
              border: 'none',
              borderRadius: '3px',
              cursor: 'pointer',
              fontSize: '11px'
            }}
          >
            🔄 Reload Page
          </button>
          <button 
            onClick={() => {
              navigator.clipboard.writeText(JSON.stringify({
                config,
                globalConfig,
                env: {
                  NODE_ENV: process.env.NODE_ENV,
                  REACT_APP_WS_URL: process.env.REACT_APP_WS_URL,
                  REACT_APP_API_BASE_URL: process.env.REACT_APP_API_BASE_URL,
                }
              }, null, 2));
              alert('Configuration copied to clipboard!');
            }}
            style={{
              padding: '6px 12px',
              backgroundColor: '#6f42c1',
              color: 'white',
              border: 'none',
              borderRadius: '3px',
              cursor: 'pointer',
              fontSize: '11px'
            }}
          >
            📋 Copy Config
          </button>
        </div>
      </div>
    </div>
  );
};

export default WebSocketConfigDebug;