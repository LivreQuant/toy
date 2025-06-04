import { AttributeDefinitions } from "../AttributeDefinitions";
import { Rect } from "../Rect";
import { IDraggable } from "./IDraggable";
import { IJsonTabNode } from "./IJsonModel";
import { Model } from "./Model";
import { Node } from "./Node";
export declare class TabNode extends Node implements IDraggable {
    static readonly TYPE = "tab";
    /** @internal */
    static fromJson(json: any, model: Model, addToModel?: boolean): TabNode;
    /** @internal */
    private tabRect;
    /** @internal */
    private moveableElement;
    /** @internal */
    private tabStamp;
    /** @internal */
    private renderedName?;
    /** @internal */
    private extra;
    /** @internal */
    private visible;
    /** @internal */
    private rendered;
    /** @internal */
    private scrollTop?;
    /** @internal */
    private scrollLeft?;
    /** @internal */
    constructor(model: Model, json: any, addToModel?: boolean);
    getName(): string;
    getHelpText(): string | undefined;
    getComponent(): string | undefined;
    getWindowId(): string;
    getWindow(): Window | undefined;
    /**
     * Returns the config attribute that can be used to store node specific data that
     * WILL be saved to the json. The config attribute should be changed via the action Actions.updateNodeAttributes rather
     * than directly, for example:
     * this.state.model.doAction(
     *   FlexLayout.Actions.updateNodeAttributes(node.getId(), {config:myConfigObject}));
     */
    getConfig(): any;
    /**
     * Returns an object that can be used to store transient node specific data that will
     * NOT be saved in the json.
     */
    getExtraData(): Record<string, any>;
    isPoppedOut(): boolean;
    isSelected(): boolean;
    getIcon(): string | undefined;
    isEnableClose(): boolean;
    getCloseType(): number;
    isEnablePopout(): boolean;
    isEnablePopoutIcon(): boolean;
    isEnablePopoutOverlay(): boolean;
    isEnableDrag(): boolean;
    isEnableRename(): boolean;
    isEnableWindowReMount(): boolean;
    getClassName(): string | undefined;
    getContentClassName(): string | undefined;
    getTabSetClassName(): string | undefined;
    isEnableRenderOnDemand(): boolean;
    getMinWidth(): number;
    getMinHeight(): number;
    getMaxWidth(): number;
    getMaxHeight(): number;
    isVisible(): boolean;
    toJson(): IJsonTabNode;
    /** @internal */
    saveScrollPosition(): void;
    /** @internal */
    restoreScrollPosition(): void;
    /** @internal */
    setRect(rect: Rect): void;
    /** @internal */
    setVisible(visible: boolean): void;
    /** @internal */
    getScrollTop(): number | undefined;
    /** @internal */
    setScrollTop(scrollTop: number | undefined): void;
    /** @internal */
    getScrollLeft(): number | undefined;
    /** @internal */
    setScrollLeft(scrollLeft: number | undefined): void;
    /** @internal */
    isRendered(): boolean;
    /** @internal */
    setRendered(rendered: boolean): void;
    /** @internal */
    getTabRect(): Rect;
    /** @internal */
    setTabRect(rect: Rect): void;
    /** @internal */
    getTabStamp(): HTMLElement | null;
    /** @internal */
    setTabStamp(stamp: HTMLElement | null): void;
    /** @internal */
    getMoveableElement(): HTMLElement | null;
    /** @internal */
    setMoveableElement(element: HTMLElement | null): void;
    /** @internal */
    setRenderedName(name: string): void;
    /** @internal */
    getNameForOverflowMenu(): string | undefined;
    /** @internal */
    setName(name: string): void;
    /** @internal */
    delete(): void;
    /** @internal */
    updateAttrs(json: any): void;
    /** @internal */
    getAttributeDefinitions(): AttributeDefinitions;
    /** @internal */
    setBorderWidth(width: number): void;
    /** @internal */
    setBorderHeight(height: number): void;
    /** @internal */
    static getAttributeDefinitions(): AttributeDefinitions;
    /** @internal */
    private static attributeDefinitions;
    /** @internal */
    private static createAttributeDefinitions;
}
