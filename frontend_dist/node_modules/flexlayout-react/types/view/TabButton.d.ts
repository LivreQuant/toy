import { TabNode } from "../model/TabNode";
import { LayoutInternal } from "./Layout";
/** @internal */
export interface ITabButtonProps {
    layout: LayoutInternal;
    node: TabNode;
    selected: boolean;
    path: string;
}
/** @internal */
export declare const TabButton: (props: ITabButtonProps) => import("react/jsx-runtime").JSX.Element;
