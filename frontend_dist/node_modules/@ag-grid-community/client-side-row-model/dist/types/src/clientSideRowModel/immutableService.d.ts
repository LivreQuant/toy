import type { BeanCollection, IImmutableService, NamedBean } from '@ag-grid-community/core';
import { BeanStub } from '@ag-grid-community/core';
export declare class ImmutableService extends BeanStub implements NamedBean, IImmutableService {
    beanName: "immutableService";
    private rowModel;
    private selectionService;
    wireBeans(beans: BeanCollection): void;
    private clientSideRowModel;
    postConstruct(): void;
    isActive(): boolean;
    setRowData<TData>(rowData: TData[]): void;
    /** Converts the setRowData() command to a transaction */
    private createTransactionForRowData;
    private onRowDataUpdated;
}
