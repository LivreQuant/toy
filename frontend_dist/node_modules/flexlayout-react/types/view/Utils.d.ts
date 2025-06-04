import * as React from "react";
import { Node } from "../model/Node";
import { TabNode } from "../model/TabNode";
import { LayoutInternal } from "./Layout";
/** @internal */
export declare function isDesktop(): boolean;
/** @internal */
export declare function getRenderStateEx(layout: LayoutInternal, node: TabNode, iconAngle?: number): {
    leading: import("react/jsx-runtime").JSX.Element | undefined;
    content: string | Iterable<React.ReactNode>;
    name: string;
    buttons: any[];
};
/** @internal */
export declare function isAuxMouseEvent(event: React.MouseEvent<HTMLElement, MouseEvent> | React.TouchEvent<HTMLElement>): boolean;
export declare function enablePointerOnIFrames(enable: boolean, currentDocument: Document): void;
export declare function getElementsByTagName(tag: string, currentDocument: Document): Element[];
export declare function startDrag(doc: Document, event: React.PointerEvent<HTMLElement>, drag: (x: number, y: number) => void, dragEnd: () => void, dragCancel: () => void): void;
export declare function canDockToWindow(node: Node): boolean;
export declare function copyInlineStyles(source: HTMLElement, target: HTMLElement): boolean;
export declare function isSafari(): boolean;
