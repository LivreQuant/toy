// frontend_dist/book-app/src/components/Dashboard/Container/componentFactory.tsx
import React from 'react';
import { TabNode } from 'flexlayout-react';
import { Views } from './layoutTypes';

// Placeholder components until the actual ones are created
const MarketDataView: React.FC<{ node: TabNode }> = ({ node }) => (
  <div style={{
    padding: '20px',
    height: '100%',
    display: 'flex',
    flexDirection: 'column',
    backgroundColor: '#f8f9fa'
  }}>
    <h3 style={{ marginBottom: '15px', color: '#495057' }}>📈 Market Data View</h3>
    <div style={{
      flex: 1,
      backgroundColor: 'white',
      border: '1px solid #dee2e6',
      borderRadius: '6px',
      padding: '15px',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center'
    }}>
      <div style={{ textAlign: 'center', color: '#6c757d' }}>
        <div style={{ fontSize: '48px', marginBottom: '10px' }}>📊</div>
        <div>Market Data Component</div>
        <div style={{ fontSize: '12px', marginTop: '5px' }}>
          Node: {node.getName()} (ID: {node.getId()})
        </div>
      </div>
    </div>
  </div>
);

const ConvictionBlotterView: React.FC<{ node: TabNode }> = ({ node }) => (
  <div style={{
    padding: '20px',
    height: '100%',
    display: 'flex',
    flexDirection: 'column',
    backgroundColor: '#f8f9fa'
  }}>
    <h3 style={{ marginBottom: '15px', color: '#495057' }}>🛡️ Conviction Blotter</h3>
    <div style={{
      flex: 1,
      backgroundColor: 'white',
      border: '1px solid #dee2e6',
      borderRadius: '6px',
      padding: '15px',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center'
    }}>
      <div style={{ textAlign: 'center', color: '#6c757d' }}>
        <div style={{ fontSize: '48px', marginBottom: '10px' }}>🛡️</div>
        <div>Conviction Blotter Component</div>
        <div style={{ fontSize: '12px', marginTop: '5px' }}>
          Node: {node.getName()} (ID: {node.getId()})
        </div>
      </div>
    </div>
  </div>
);

/**
 * Factory function for flexlayout-react
 * Takes a TabNode and returns the appropriate React component to render
 */
export const factory = (node: TabNode): React.ReactNode => {
  const component = node.getComponent();
  
  console.log('🏭 Factory: Creating component for:', component, 'with config:', node.getConfig());
  
  switch (component) {
    case Views.MarketData:
      return <MarketDataView node={node} />;
      
    case Views.ConvictionBlotter:
      return <ConvictionBlotterView node={node} />;
      
    // Add more cases as you create more view types
    default:
      // Fallback component for unknown view types
      return (
        <div style={{
          padding: '20px',
          textAlign: 'center',
          height: '100%',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'center',
          alignItems: 'center',
          backgroundColor: '#f8f9fa',
          border: '2px dashed #dee2e6',
          borderRadius: '8px'
        }}>
          <h3 style={{ color: '#6c757d', marginBottom: '10px' }}>
            Unknown Component: {component}
          </h3>
          <p style={{ color: '#868e96', fontSize: '14px' }}>
            Component "{component}" is not registered in the factory function.
          </p>
          <div style={{ 
            marginTop: '15px',
            padding: '10px',
            backgroundColor: '#e9ecef',
            borderRadius: '4px',
            fontSize: '12px',
            fontFamily: 'monospace'
          }}>
            Node ID: {node.getId()}<br/>
            Node Name: {node.getName()}<br/>
            Config: {JSON.stringify(node.getConfig(), null, 2)}
          </div>
        </div>
      );
  }
};