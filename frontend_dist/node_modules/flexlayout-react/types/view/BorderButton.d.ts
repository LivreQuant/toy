import { TabNode } from "../model/TabNode";
import { IIcons, LayoutInternal } from "./Layout";
/** @internal */
export interface IBorderButtonProps {
    layout: LayoutInternal;
    node: TabNode;
    selected: boolean;
    border: string;
    icons: IIcons;
    path: string;
}
/** @internal */
export declare const BorderButton: (props: IBorderButtonProps) => import("react/jsx-runtime").JSX.Element;
