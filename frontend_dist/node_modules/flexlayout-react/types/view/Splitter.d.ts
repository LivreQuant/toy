import { BorderNode } from "../model/BorderNode";
import { RowNode } from "../model/RowNode";
import { LayoutInternal } from "./Layout";
/** @internal */
export interface ISplitterProps {
    layout: LayoutInternal;
    node: RowNode | BorderNode;
    index: number;
    horizontal: boolean;
}
/** @internal */
export declare let splitterDragging: boolean;
/** @internal */
export declare const Splitter: (props: ISplitterProps) => import("react/jsx-runtime").JSX.Element;
