// src/components/Form/FormFields/SectionGrid.tsx
import React from 'react';
import { Grid, Typography, Box } from '@mui/material';

export interface SectionGridProps {
  title?: string;
  description?: string;
  children: React.ReactNode;
  columns?: number;
  spacing?: number;
}

export const SectionGrid: React.FC<SectionGridProps> = ({
  title,
  description,
  children,
  columns = 12,
  spacing = 3
}) => {
  return (
    <Box sx={{ mb: 4 }}>
      {title && (
        <Typography variant="h6" gutterBottom>
          {title}
        </Typography>
      )}
      
      {description && (
        <Typography variant="body2" color="text.secondary" paragraph>
          {description}
        </Typography>
      )}
      
      <Grid container spacing={spacing}>
        {React.Children.map(children, (child, index) => (
          <Grid 
            {...{
              component: "div", 
              item: true, 
              xs: 12, 
              md: 6, // Default to 2 columns on medium screens
              key: index
            } as any}
          >
            {child}
          </Grid>
        ))}
      </Grid>
    </Box>
  );
};