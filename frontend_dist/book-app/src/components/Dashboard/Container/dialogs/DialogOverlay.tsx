// frontend_dist/book-app/src/components/Dashboard/Container/DialogOverlay.tsx
import React from 'react';
import QuestionDialog from './QuestionDialog';
import ViewNameDialog from './ViewNameDialog';
import ColumnChooserAgGrid from '../../AgGrid/components/dialogs/ColumnChooseAgGrid';
import { Model } from 'flexlayout-react';
import { 
  QuestionDialogController, 
  ViewNameDialogController, 
  AgGridColumnChooserController 
} from '../controllers/Controllers';

interface DialogOverlayProps {
  questionDialogController: QuestionDialogController;
  viewNameDialogController: ViewNameDialogController;
  columnChooserController: AgGridColumnChooserController;
  updateLayoutModel: (model: Model) => void;
}

const DialogOverlay: React.FC<DialogOverlayProps> = ({
  questionDialogController,
  viewNameDialogController,
  columnChooserController,
  updateLayoutModel
}) => {
  return (
    <div style={{ 
      position: 'fixed', 
      top: 0, 
      left: 0, 
      width: '100%', 
      height: '100%', 
      pointerEvents: 'none', 
      zIndex: 5000 
    }}>
      <div style={{ pointerEvents: 'auto' }}>
        <QuestionDialog controller={questionDialogController} />
        <ViewNameDialog 
          controller={viewNameDialogController} 
          updateLayoutModel={updateLayoutModel} 
        />
        <ColumnChooserAgGrid controller={columnChooserController} />
      </div>
    </div>
  );
};

export default DialogOverlay;