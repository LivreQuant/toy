import { DropInfo } from "../DropInfo";
import { Action } from "./Action";
import { BorderSet } from "./BorderSet";
import { IDraggable } from "./IDraggable";
import { IJsonModel, ITabSetAttributes } from "./IJsonModel";
import { Node } from "./Node";
import { RowNode } from "./RowNode";
import { TabNode } from "./TabNode";
import { TabSetNode } from "./TabSetNode";
import { LayoutWindow } from "./LayoutWindow";
/** @internal */
export declare const DefaultMin = 0;
/** @internal */
export declare const DefaultMax = 99999;
/**
 * Class containing the Tree of Nodes used by the FlexLayout component
 */
export declare class Model {
    static MAIN_WINDOW_ID: string;
    /** @internal */
    private static attributeDefinitions;
    /** @internal */
    private attributes;
    /** @internal */
    private idMap;
    /** @internal */
    private changeListeners;
    /** @internal */
    private borders;
    /** @internal */
    private onAllowDrop?;
    /** @internal */
    private onCreateTabSet?;
    /** @internal */
    private windows;
    /** @internal */
    private rootWindow;
    /**
     * 'private' constructor. Use the static method Model.fromJson(json) to create a model
     *  @internal
     */
    protected constructor();
    /**
     * Update the node tree by performing the given action,
     * Actions should be generated via static methods on the Actions class
     * @param action the action to perform
     * @returns added Node for Actions.addNode, windowId for createWindow
     */
    doAction(action: Action): any;
    /**
     * Get the currently active tabset node
     */
    getActiveTabset(windowId?: string): TabSetNode | undefined;
    /**
     * Get the currently maximized tabset node
     */
    getMaximizedTabset(windowId?: string): TabSetNode | undefined;
    /**
     * Gets the root RowNode of the model
     * @returns {RowNode}
     */
    getRoot(windowId?: string): RowNode;
    isRootOrientationVertical(): boolean;
    isEnableRotateBorderIcons(): boolean;
    /**
     * Gets the
     * @returns {BorderSet|*}
     */
    getBorderSet(): BorderSet;
    getwindowsMap(): Map<string, LayoutWindow>;
    /**
     * Visits all the nodes in the model and calls the given function for each
     * @param fn a function that takes visited node and a integer level as parameters
     */
    visitNodes(fn: (node: Node, level: number) => void): void;
    visitWindowNodes(windowId: string, fn: (node: Node, level: number) => void): void;
    /**
     * Gets a node by its id
     * @param id the id to find
     */
    getNodeById(id: string): Node | undefined;
    /**
     * Finds the first/top left tab set of the given node.
     * @param node The top node you want to begin searching from, deafults to the root node
     * @returns The first Tab Set
     */
    getFirstTabSet(node?: Node): TabSetNode;
    /**
 * Loads the model from the given json object
 * @param json the json model to load
 * @returns {Model} a new Model object
 */
    static fromJson(json: IJsonModel): Model;
    /**
     * Converts the model to a json object
     * @returns {IJsonModel} json object that represents this model
     */
    toJson(): IJsonModel;
    getSplitterSize(): number;
    getSplitterExtra(): number;
    isEnableEdgeDock(): boolean;
    isSplitterEnableHandle(): boolean;
    /**
     * Sets a function to allow/deny dropping a node
     * @param onAllowDrop function that takes the drag node and DropInfo and returns true if the drop is allowed
     */
    setOnAllowDrop(onAllowDrop: (dragNode: Node, dropInfo: DropInfo) => boolean): void;
    /**
     * set callback called when a new TabSet is created.
     * The tabNode can be undefined if it's the auto created first tabset in the root row (when the last
     * tab is deleted, the root tabset can be recreated)
     * @param onCreateTabSet
     */
    setOnCreateTabSet(onCreateTabSet: (tabNode?: TabNode) => ITabSetAttributes): void;
    addChangeListener(listener: ((action: Action) => void)): void;
    removeChangeListener(listener: ((action: Action) => void)): void;
    toString(): string;
    /***********************internal ********************************/
    /** @internal */
    removeEmptyWindows(): void;
    /** @internal */
    setActiveTabset(tabsetNode: TabSetNode | undefined, windowId: string): void;
    /** @internal */
    setMaximizedTabset(tabsetNode: (TabSetNode | undefined), windowId: string): void;
    /** @internal */
    updateIdMap(): void;
    /** @internal */
    addNode(node: Node): void;
    /** @internal */
    findDropTargetNode(windowId: string, dragNode: Node & IDraggable, x: number, y: number): DropInfo | undefined;
    /** @internal */
    tidy(): void;
    /** @internal */
    updateAttrs(json: any): void;
    /** @internal */
    nextUniqueId(): string;
    /** @internal */
    getAttribute(name: string): any;
    /** @internal */
    getOnAllowDrop(): ((dragNode: Node, dropInfo: DropInfo) => boolean) | undefined;
    /** @internal */
    getOnCreateTabSet(): ((tabNode?: TabNode) => ITabSetAttributes) | undefined;
    static toTypescriptInterfaces(): void;
    /** @internal */
    private static createAttributeDefinitions;
}
