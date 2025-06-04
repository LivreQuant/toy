import { TabNode } from "../model/TabNode";
import { LayoutInternal } from "./Layout";
/** @internal */
export interface ITabProps {
    layout: LayoutInternal;
    node: TabNode;
    selected: boolean;
    path: string;
}
/** @internal */
export declare const Tab: (props: ITabProps) => import("react/jsx-runtime").JSX.Element;
