import React, { useCallback, useEffect, useRef } from 'react';
import { ICellRendererParams } from 'ag-grid-community';

interface SelectionCheckboxRendererProps extends ICellRendererParams {
  node: any;
}

const SelectionCheckboxRenderer: React.FC<SelectionCheckboxRendererProps> = (props) => {
  const checkboxRef = useRef<HTMLInputElement>(null);
  
  const isChecked = props.node?.isSelected?.() || false;
  
  const handleChange = useCallback((event: React.ChangeEvent<HTMLInputElement>) => {
    const checked = event.target.checked;
    props.node.setSelected(checked);
  }, [props.node]);

  useEffect(() => {
    if (checkboxRef.current) {
      checkboxRef.current.checked = isChecked;
    }
  }, [isChecked]);

  return (
    <div className="custom-checkbox-container">
      <input
        ref={checkboxRef}
        type="checkbox"
        onChange={handleChange}
        checked={isChecked}
        className="custom-checkbox"
      />
    </div>
  );
};

export default SelectionCheckboxRenderer;