import { TabSetNode } from "../model/TabSetNode";
import { LayoutInternal } from "./Layout";
/** @internal */
export interface ITabSetProps {
    layout: LayoutInternal;
    node: TabSetNode;
}
/** @internal */
export declare const TabSet: (props: ITabSetProps) => import("react/jsx-runtime").JSX.Element;
