import { ColDef, Column, ColumnState } from "ag-grid-community";
import { Layout, Model } from "flexlayout-react";

export class AgGridColumnChooserController {
  private dialog?: any;

  setDialog(dialog: any) {
    this.dialog = dialog;
  }

  open(tableName: string, colStates: ColumnState[], cols: Column[], callback: (columns: ColumnState[] | undefined) => void) {
    if (this.dialog) {
      this.dialog.open(tableName, colStates, cols, callback);
    }
  }
}

export class QuestionDialogController {
  private dialog?: any;

  setDialog(dialog: any) {
    this.dialog = dialog;
  }

  open(question: string, title: string, callback: (response: boolean) => void) {
    if (this.dialog) {
      this.dialog.open(question, title, callback);
    }
  }
}

export class ViewNameDialogController {
  private dialog?: any;

  setDialog(dialog: any) {
    this.dialog = dialog;
  }

  open(component: string, componentDislayName: string, layout: Layout, updateLayoutModel?: (model: Model) => void) {
    if (this.dialog) {
      this.dialog.open(component, componentDislayName, layout, updateLayoutModel);
    }
  }
}