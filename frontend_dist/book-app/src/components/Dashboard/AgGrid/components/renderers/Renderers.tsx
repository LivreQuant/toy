// Renderers.tsx (converted to hooks)
import { Colors, Icon } from "@blueprintjs/core";
import React from 'react';
import { GlobalColours } from "../../constants/Colours";

export const DirectionalPriceRenderer: React.FC<any> = (props) => {
  const { value } = props;
  
  if (!value || !value.price) {
    return <span></span>;
  }
  
  if (value.direction) {
    if (value.direction > 0) {
      return <span><Icon icon="arrow-up" style={{ color: GlobalColours.UPTICK }} />{value.price}</span>;
    }
    if (value.direction < 0) {
      return <span><Icon icon="arrow-down" style={{ color: GlobalColours.DOWNTICK }} />{value.price}</span>;
    }
  }
  
  return <span>{value.price}</span>;
};

export const TargetStatusRenderer: React.FC<any> = (props) => {
  if (props.value === "None") {
    return <span>{props.value}</span>;
  } else {
    return <span style={{ color: Colors.ORANGE3 }}><b>{props.value}</b></span>;
  }
};