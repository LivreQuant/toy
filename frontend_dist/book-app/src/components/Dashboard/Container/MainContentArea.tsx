// frontend_dist/book-app/src/components/Dashboard/Container/MainContentArea.tsx
import React from 'react';
import { Layout, Model } from 'flexlayout-react';
import { Icon } from '@blueprintjs/core';
import { Views } from './layoutTypes';

interface MainContentAreaProps {
  layoutRef: React.RefObject<Layout>;
  model: Model;
  factory: (node: any) => React.ReactNode;
  onModelChange: () => void;
}

const MainContentArea: React.FC<MainContentAreaProps> = ({
  layoutRef,
  model,
  factory,
  onModelChange
}) => {
  return (
    <div style={{ 
      flex: '1 1 0',
      width: '100%', 
      position: 'relative', 
      zIndex: 1,
      minHeight: 0
    }}>
      <Layout 
        ref={layoutRef}
        model={model} 
        factory={factory}
        onModelChange={onModelChange}
        onRenderTab={(node, renderValues) => {
          const component = node.getComponent();
          let icon;
          
          switch (component) {
            case Views.MarketData:
              icon = <Icon icon="chart" style={{ paddingRight: 5 }}></Icon>;
              break;
            case Views.ConvictionBlotter:
              icon = <Icon icon="shield" style={{ paddingRight: 5 }}></Icon>;
              break;
            default:
              icon = <Icon icon="document" style={{ paddingRight: 5 }}></Icon>;
              break;
          }
          
          renderValues.leading = icon;
          return null;
        }}
      />
    </div>
  );
};

export default MainContentArea;