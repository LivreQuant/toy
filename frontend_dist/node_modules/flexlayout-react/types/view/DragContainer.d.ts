import { TabNode } from "../model/TabNode";
import { LayoutInternal } from "./Layout";
/** @internal */
export interface IDragContainerProps {
    node: TabNode;
    layout: LayoutInternal;
}
/** @internal */
export declare const DragContainer: (props: IDragContainerProps) => import("react/jsx-runtime").JSX.Element;
