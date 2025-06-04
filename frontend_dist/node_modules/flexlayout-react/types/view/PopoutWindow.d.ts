import * as React from "react";
import { LayoutInternal } from "./Layout";
import { LayoutWindow } from "../model/LayoutWindow";
/** @internal */
export interface IPopoutWindowProps {
    title: string;
    layout: LayoutInternal;
    layoutWindow: LayoutWindow;
    url: string;
    onCloseWindow: (layoutWindow: LayoutWindow) => void;
    onSetWindow: (layoutWindow: LayoutWindow, window: Window) => void;
}
/** @internal */
export declare const PopoutWindow: (props: React.PropsWithChildren<IPopoutWindowProps>) => React.ReactPortal | null;
