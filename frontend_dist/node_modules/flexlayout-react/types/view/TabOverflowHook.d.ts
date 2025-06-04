import * as React from "react";
import { TabSetNode } from "../model/TabSetNode";
import { BorderNode } from "../model/BorderNode";
import { Orientation } from "../Orientation";
import { LayoutInternal } from "./Layout";
/** @internal */
export declare const useTabOverflow: (layout: LayoutInternal, node: TabSetNode | BorderNode, orientation: Orientation, tabStripRef: React.RefObject<HTMLElement | null>, miniScrollRef: React.RefObject<HTMLElement | null>, tabClassName: string) => {
    selfRef: React.RefObject<HTMLDivElement | null>;
    userControlledPositionRef: React.RefObject<boolean>;
    onScroll: () => void;
    onScrollPointerDown: (event: React.PointerEvent<HTMLElement>) => void;
    hiddenTabs: number[];
    onMouseWheel: (event: React.WheelEvent<HTMLElement>) => void;
    isDockStickyButtons: boolean;
    isShowHiddenTabs: boolean;
};
