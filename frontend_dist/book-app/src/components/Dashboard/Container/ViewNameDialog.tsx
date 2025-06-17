// ViewNameDialog.tsx
import { AnchorButton, Classes, Dialog, InputGroup, Intent } from '@blueprintjs/core';
import { Layout, Model } from 'flexlayout-react';
import React, { useState, useEffect, useRef } from "react";
import { ViewNameDialogController } from "./Controllers";

export interface ViewNameDialogProps {
  controller: ViewNameDialogController;
  updateLayoutModel?: (newModel: Model) => void;
  onLayoutChange?: (newModel: Model) => void; // Optional prop for backwards compatibility
}

// Define the interface that matches what controller.setDialog expects
interface DialogInterface {
  open: (
    component: string,
    displayName: string,
    layout: Layout,
    updateCallback?: (model: Model) => void
  ) => void;
}

const ViewNameDialog: React.FC<ViewNameDialogProps> = ({ 
  controller, 
  updateLayoutModel, 
  onLayoutChange 
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [question, setQuestion] = useState("");
  const [title, setTitle] = useState("");
  const [viewName, setViewName] = useState("");
  const [componentId, setComponentId] = useState("");
  const [componentDisplayName, setComponentDisplayName] = useState("");
  
  const layoutRef = useRef<Layout | undefined>(undefined);
  
  // Set dialog reference in controller when component mounts
  useEffect(() => {
    controller.setDialog({
      open: (
        component: string, 
        displayName: string, 
        layout: Layout, 
        updateCallback?: (model: Model) => void
      ) => {
        layoutRef.current = layout;
        const dialogTitle = "Enter name for Tab";
        
        setIsOpen(true);
        setQuestion(dialogTitle);
        setTitle(dialogTitle);
        setComponentId(component);
        setComponentDisplayName(displayName);
        setViewName(displayName); // Pre-fill with the componentDisplayName
      }
    } as DialogInterface);
  }, [controller]);
  
  const onViewNameChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setViewName(event.target.value);
  };
  
  const handleOK = () => {
    setIsOpen(false);
    
    if (layoutRef.current) {
      const model = layoutRef.current.props.model;
      if (model) {
        const rootJson = model.toJson();
        
        // Find the last child of the root layout
        const lastChild = rootJson.layout.children[rootJson.layout.children.length - 1];
        
        // If the last child is not a row, convert the layout to a row
        if (lastChild.type !== 'row') {
          rootJson.layout = {
            type: 'row',
            weight: 100,
            children: rootJson.layout.children
          };
        }
        
        // Add a new tabset to the row
        rootJson.layout.children.push({
          type: "tabset",
          weight: 50,
          children: [{
            type: "tab",
            name: viewName,
            component: componentId
          }]
        });
        
        const newModel = Model.fromJson(rootJson);
        
        // Use either updateLayoutModel or onLayoutChange
        if (updateLayoutModel) {
          updateLayoutModel(newModel);
        } else if (onLayoutChange) {
          onLayoutChange(newModel);
        }
      }
    }
  };
  
  const handleCancel = () => {
    setIsOpen(false);
  };
  
  return (
    <Dialog
      icon="help"
      onClose={handleCancel}
      title={title}
      isOpen={isOpen}
      className="bp3-dark"
    >
      <div className={Classes.DIALOG_BODY}>
        <h3>{question}</h3>
        <InputGroup 
          style={{ marginBottom: 30 }} 
          placeholder="View name..." 
          value={viewName}
          onChange={onViewNameChange} 
        />
      </div>
      <div className={Classes.DIALOG_FOOTER}>
        <div className={Classes.DIALOG_FOOTER_ACTIONS}>
          <AnchorButton 
            onClick={handleOK} 
            disabled={viewName.length === 0}
            intent={Intent.PRIMARY}
          >
            OK
          </AnchorButton>
          <AnchorButton 
            onClick={handleCancel}
            intent={Intent.DANGER}
          >
            Cancel
          </AnchorButton>
        </div>
      </div>
    </Dialog>
  );
};

export default ViewNameDialog;