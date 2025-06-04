import { LayoutInternal } from "./Layout";
import { BorderNode } from "../model/BorderNode";
/** @internal */
export interface IBorderTabProps {
    layout: LayoutInternal;
    border: BorderNode;
    show: boolean;
}
export declare function BorderTab(props: IBorderTabProps): import("react/jsx-runtime").JSX.Element;
