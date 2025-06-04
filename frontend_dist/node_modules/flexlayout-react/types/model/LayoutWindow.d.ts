import { Rect } from "../Rect";
import { IJsonPopout } from "./IJsonModel";
import { Model } from "./Model";
import { RowNode } from "./RowNode";
import { Node } from "./Node";
import { TabSetNode } from "./TabSetNode";
import { LayoutInternal } from "../view/Layout";
export declare class LayoutWindow {
    private _windowId;
    private _layout;
    private _rect;
    private _window?;
    private _root?;
    private _maximizedTabSet?;
    private _activeTabSet?;
    private _toScreenRectFunction;
    constructor(windowId: string, rect: Rect);
    visitNodes(fn: (node: Node, level: number) => void): void;
    get windowId(): string;
    get rect(): Rect;
    get layout(): LayoutInternal | undefined;
    get window(): Window | undefined;
    get root(): RowNode | undefined;
    get maximizedTabSet(): TabSetNode | undefined;
    get activeTabSet(): TabSetNode | undefined;
    /** @internal */
    set rect(value: Rect);
    /** @internal */
    set layout(value: LayoutInternal);
    /** @internal */
    set window(value: Window | undefined);
    /** @internal */
    set root(value: RowNode | undefined);
    /** @internal */
    set maximizedTabSet(value: TabSetNode | undefined);
    /** @internal */
    set activeTabSet(value: TabSetNode | undefined);
    /** @internal */
    get toScreenRectFunction(): (rect: Rect) => Rect;
    /** @internal */
    set toScreenRectFunction(value: (rect: Rect) => Rect);
    toJson(): IJsonPopout;
    static fromJson(windowJson: IJsonPopout, model: Model, windowId: string): LayoutWindow;
}
