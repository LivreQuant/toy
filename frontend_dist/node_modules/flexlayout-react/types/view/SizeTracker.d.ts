import * as React from "react";
import { Rect } from "../Rect";
import { LayoutInternal } from "./Layout";
import { TabNode } from "../model/TabNode";
export interface ISizeTrackerProps {
    layout: LayoutInternal;
    node: TabNode;
    rect: Rect;
    visible: boolean;
    forceRevision: number;
    tabsRevision: number;
}
export declare const SizeTracker: React.MemoExoticComponent<({ layout, node }: ISizeTrackerProps) => import("react/jsx-runtime").JSX.Element>;
