// themes/gridThemes.ts
import { themeQuartz } from 'ag-grid-community';

export const darkTheme = themeQuartz.withParams({
  backgroundColor: "#1f2836",
  borderRadius: 0,
  browserColorScheme: "dark",
  chromeBackgroundColor: {
    ref: "foregroundColor",
    mix: 0.07,
    onto: "backgroundColor"
  },
  fontSize: 14,
  foregroundColor: "#FFF",
  spacing: 6,
  headerFontSize: 14,
  wrapperBorderRadius: 0
});

// Add more themes as needed
export const lightTheme = themeQuartz.withParams({
  backgroundColor: "#ffffff",
  borderRadius: 0,
  browserColorScheme: "light",
  fontSize: 14,
  spacing: 6,
  headerFontSize: 14,
  wrapperBorderRadius: 0
});