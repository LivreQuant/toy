// QuestionDialog.tsx
import { AnchorButton, Classes, Dialog, Intent } from '@blueprintjs/core';
import React, { useState, useEffect } from "react";
import { QuestionDialogController } from "../controllers/Controllers";

export interface QuestionDialogProps {
  controller: QuestionDialogController;
}

interface DialogInterface {
  open: (
    question: string,
    title: string,
    callback: (response: boolean) => void
  ) => void;
}

const QuestionDialog: React.FC<QuestionDialogProps> = ({ controller }) => {
  const [isOpen, setIsOpen] = useState(false);
  const [question, setQuestion] = useState("");
  const [title, setTitle] = useState("");
  const [callback, setCallback] = useState<(response: boolean) => void>(() => () => {});
  
  useEffect(() => {
    controller.setDialog({
      open: (
        questionText: string,
        titleText: string,
        callbackFn: (response: boolean) => void
      ) => {
        setIsOpen(true);
        setQuestion(questionText);
        setTitle(titleText);
        setCallback(() => callbackFn);
      }
    } as DialogInterface);
  }, [controller]);
  
  const handleOK = () => {
    setIsOpen(false);
    callback(true);
  };
  
  const handleCancel = () => {
    setIsOpen(false);
    callback(false);
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
      </div>
      <div className={Classes.DIALOG_FOOTER}>
        <div className={Classes.DIALOG_FOOTER_ACTIONS}>
          <AnchorButton 
            onClick={handleOK}
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

export default QuestionDialog;