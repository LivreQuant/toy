import { TabNode } from "../model/TabNode";
import { LayoutInternal } from "./Layout";
/** @internal */
export interface ITabButtonStampProps {
    node: TabNode;
    layout: LayoutInternal;
}
/** @internal */
export declare const TabButtonStamp: (props: ITabButtonStampProps) => import("react/jsx-runtime").JSX.Element;
