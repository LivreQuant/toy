import { Views } from './layoutTypes';

// Default layout JSON configuration
export const defaultLayoutJson = {
  global: {
    splitterSize: 5,
    enableEdgeDock: true
  },
  borders: [],
  layout: {
    type: "row",
    children: [
      {
        type: "tabset",
        weight: 50,
        children: [
          {
            type: "tab",
            name: "Portfolio",
            component: Views.MarketData
          }
        ]
      },
      /*
      {
        type: "row",
        weight: 50,
        children: [
          {
            type: "tabset",
            weight: 50,
            children: [
              {
                type: "tab",
                name: "Market Data",
                component: Views.MarketData
              }
            ]
          },
          {
            type: "tabset",
            weight: 50,
            children: [
              {
                type: "tab",
                name: "Risk Analysis",
                component: Views.RiskAnalysis
              }
            ]
          }
        ]
      }
      */
    ]
  }
};