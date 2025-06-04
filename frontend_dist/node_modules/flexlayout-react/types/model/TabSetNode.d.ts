import { AttributeDefinitions } from "../AttributeDefinitions";
import { DockLocation } from "../DockLocation";
import { DropInfo } from "../DropInfo";
import { Orientation } from "../Orientation";
import { Rect } from "../Rect";
import { IDraggable } from "./IDraggable";
import { IDropTarget } from "./IDropTarget";
import { IJsonTabSetNode } from "./IJsonModel";
import { LayoutWindow } from "./LayoutWindow";
import { Model } from "./Model";
import { Node } from "./Node";
import { TabNode } from "./TabNode";
export declare class TabSetNode extends Node implements IDraggable, IDropTarget {
    static readonly TYPE = "tabset";
    /** @internal */
    static fromJson(json: any, model: Model, layoutWindow: LayoutWindow): TabSetNode;
    /** @internal */
    private static attributeDefinitions;
    /** @internal */
    private tabStripRect;
    /** @internal */
    private contentRect;
    /** @internal */
    private calculatedMinHeight;
    /** @internal */
    private calculatedMinWidth;
    /** @internal */
    private calculatedMaxHeight;
    /** @internal */
    private calculatedMaxWidth;
    /** @internal */
    constructor(model: Model, json: any);
    getName(): string | undefined;
    isEnableActiveIcon(): boolean;
    getSelected(): number;
    getSelectedNode(): Node | undefined;
    getWeight(): number;
    getAttrMinWidth(): number;
    getAttrMinHeight(): number;
    getMinWidth(): number;
    getMinHeight(): number;
    /** @internal */
    getMinSize(orientation: Orientation): number;
    getAttrMaxWidth(): number;
    getAttrMaxHeight(): number;
    getMaxWidth(): number;
    getMaxHeight(): number;
    /** @internal */
    getMaxSize(orientation: Orientation): number;
    /**
     * Returns the config attribute that can be used to store node specific data that
     * WILL be saved to the json. The config attribute should be changed via the action Actions.updateNodeAttributes rather
     * than directly, for example:
     * this.state.model.doAction(
     *   FlexLayout.Actions.updateNodeAttributes(node.getId(), {config:myConfigObject}));
     */
    getConfig(): any;
    isMaximized(): boolean;
    isActive(): boolean;
    isEnableDeleteWhenEmpty(): boolean;
    isEnableDrop(): boolean;
    isEnableTabWrap(): boolean;
    isEnableDrag(): boolean;
    isEnableDivide(): boolean;
    isEnableMaximize(): boolean;
    isEnableClose(): boolean;
    isEnableSingleTabStretch(): boolean;
    isEnableTabStrip(): boolean;
    isAutoSelectTab(): boolean;
    isEnableTabScrollbar(): boolean;
    getClassNameTabStrip(): string | undefined;
    getTabLocation(): string;
    toJson(): IJsonTabSetNode;
    /** @internal */
    calcMinMaxSize(): void;
    /** @internal */
    canMaximize(): boolean;
    /** @internal */
    setContentRect(rect: Rect): void;
    /** @internal */
    getContentRect(): Rect;
    /** @internal */
    setTabStripRect(rect: Rect): void;
    /** @internal */
    setWeight(weight: number): void;
    /** @internal */
    setSelected(index: number): void;
    getWindowId(): string;
    /** @internal */
    canDrop(dragNode: Node & IDraggable, x: number, y: number): DropInfo | undefined;
    /** @internal */
    delete(): void;
    /** @internal */
    remove(node: TabNode): void;
    /** @internal */
    drop(dragNode: Node, location: DockLocation, index: number, select?: boolean): void;
    /** @internal */
    updateAttrs(json: any): void;
    /** @internal */
    getAttributeDefinitions(): AttributeDefinitions;
    /** @internal */
    static getAttributeDefinitions(): AttributeDefinitions;
    /** @internal */
    private static createAttributeDefinitions;
}
