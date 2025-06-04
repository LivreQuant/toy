import { RowNode } from "../model/RowNode";
import { LayoutInternal } from "./Layout";
/** @internal */
export interface IRowProps {
    layout: LayoutInternal;
    node: RowNode;
}
/** @internal */
export declare const Row: (props: IRowProps) => import("react/jsx-runtime").JSX.Element;
