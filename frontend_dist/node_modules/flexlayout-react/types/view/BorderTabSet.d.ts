import { BorderNode } from "../model/BorderNode";
import { LayoutInternal } from "./Layout";
/** @internal */
export interface IBorderTabSetProps {
    border: BorderNode;
    layout: LayoutInternal;
    size: number;
}
/** @internal */
export declare const BorderTabSet: (props: IBorderTabSetProps) => import("react/jsx-runtime").JSX.Element;
