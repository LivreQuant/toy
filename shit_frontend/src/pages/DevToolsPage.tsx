// src/pages/DevToolsPage.tsx
import React, { useState, useEffect } from 'react';
import globalLogger, { LogLevel } from '../utils/enhanced-logger';

const DevToolsPage: React.FC = () => {
  const [logLevel, setLogLevel] = useState<LogLevel>(() => {
    const storedLevel = localStorage.getItem('log_level');
    return storedLevel ? parseInt(storedLevel) : LogLevel.INFO;
  });
  
  const [logMessages, setLogMessages] = useState<string[]>([]);
  
  // Update log level in localStorage and logger
  const handleLogLevelChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const newLevel = parseInt(e.target.value) as LogLevel;
    setLogLevel(newLevel);
    localStorage.setItem('log_level', String(newLevel));
    globalLogger.setConfig({ minLevel: newLevel });
    globalLogger.info(`Log level changed to ${LogLevel[newLevel]}`);
  };
  
  // src/pages/DevToolsPage.tsx (continued)
  // Add test log entries for each level
  const generateTestLogs = () => {
    globalLogger.debug('This is a DEBUG message');
    globalLogger.info('This is an INFO message');
    globalLogger.warn('This is a WARN message');
    globalLogger.error('This is an ERROR message');
  };
  
  // Capture logs to display in the UI
  useEffect(() => {
    // Create proxies for console methods to capture logs
    const originals = {
      debug: console.debug,
      log: console.log,
      info: console.info,
      warn: console.warn,
      error: console.error
    };
    
    const captureLog = (level: string, args: any[]) => {
      try {
        // Only capture structured logs (JSON strings)
        if (typeof args[0] === 'string' && args[0].startsWith('{')) {
          setLogMessages(prev => [...prev.slice(-49), `[${level}] ${args[0]}`]);
        }
      } catch (e) {
        // Ignore errors in log capturing
      }
    };
    
    console.debug = (...args: any[]) => {
      captureLog('DEBUG', args);
      originals.debug(...args);
    };
    
    console.log = (...args: any[]) => {
      captureLog('LOG', args);
      originals.log(...args);
    };
    
    console.info = (...args: any[]) => {
      captureLog('INFO', args);
      originals.info(...args);
    };
    
    console.warn = (...args: any[]) => {
      captureLog('WARN', args);
      originals.warn(...args);
    };
    
    console.error = (...args: any[]) => {
      captureLog('ERROR', args);
      originals.error(...args);
    };
    
    // Restore original console methods on unmount
    return () => {
      console.debug = originals.debug;
      console.log = originals.log;
      console.info = originals.info;
      console.warn = originals.warn;
      console.error = originals.error;
    };
  }, []);
  
  return (
    <div className="dev-tools-page">
      <h1>Developer Tools</h1>
      
      <div className="section">
        <h2>Logging Configuration</h2>
        <div className="form-group">
          <label htmlFor="logLevel">Log Level:</label>
          <select
            id="logLevel"
            value={logLevel}
            onChange={handleLogLevelChange}
          >
            <option value={LogLevel.DEBUG}>DEBUG</option>
            <option value={LogLevel.INFO}>INFO</option>
            <option value={LogLevel.WARN}>WARN</option>
            <option value={LogLevel.ERROR}>ERROR</option>
            <option value={LogLevel.NONE}>NONE</option>
          </select>
        </div>
        
        <button onClick={generateTestLogs}>Generate Test Logs</button>
      </div>
      
      <div className="section">
        <h2>Recent Log Messages</h2>
        <div className="log-container">
          {logMessages.length === 0 ? (
            <p>No logs captured yet</p>
          ) : (
            <pre>
              {logMessages.map((msg, i) => (
                <div key={i} className="log-entry">
                  {msg}
                </div>
              ))}
            </pre>
          )}
        </div>
      </div>
    </div>
  );
};

export default DevToolsPage;