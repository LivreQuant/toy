import * as React from "react";
import { DockLocation } from "../DockLocation";
import { I18nLabel } from "../I18nLabel";
import { Rect } from "../Rect";
import { Action } from "../model/Action";
import { BorderNode } from "../model/BorderNode";
import { IDraggable } from "../model/IDraggable";
import { IJsonTabNode } from "../model/IJsonModel";
import { Model } from "../model/Model";
import { Node } from "../model/Node";
import { TabNode } from "../model/TabNode";
import { TabSetNode } from "../model/TabSetNode";
import { LayoutWindow } from "../model/LayoutWindow";
export interface ILayoutProps {
    /** the model for this layout */
    model: Model;
    /** factory function for creating the tab components */
    factory: (node: TabNode) => React.ReactNode;
    /** sets a top level class name on popout windows */
    popoutClassName?: string;
    /** object mapping keys among close, maximize, restore, more, popout to React nodes to use in place of the default icons, can alternatively return functions for creating the React nodes */
    icons?: IIcons;
    /** function called whenever the layout generates an action to update the model (allows for intercepting actions before they are dispatched to the model, for example, asking the user to confirm a tab close.) Returning undefined from the function will halt the action, otherwise return the action to continue */
    onAction?: (action: Action) => Action | undefined;
    /** function called when rendering a tab, allows leading (icon), content section, buttons and name used in overflow menu to be customized */
    onRenderTab?: (node: TabNode, renderValues: ITabRenderValues) => void;
    /** function called when rendering a tabset, allows header and buttons to be customized */
    onRenderTabSet?: (tabSetNode: TabSetNode | BorderNode, renderValues: ITabSetRenderValues) => void;
    /** function called when model has changed */
    onModelChange?: (model: Model, action: Action) => void;
    /** function called when an external object (not a tab) gets dragged onto the layout, with a single dragenter argument. Should return either undefined to reject the drag/drop or an object with keys dragText, jsonDrop, to create a tab via drag (similar to a call to addTabToTabSet). Function onDropis passed the added tabNodeand thedrop DragEvent`, unless the drag was canceled. */
    onExternalDrag?: (event: React.DragEvent<HTMLElement>) => undefined | {
        json: any;
        onDrop?: (node?: Node, event?: React.DragEvent<HTMLElement>) => void;
    };
    /** function called with default css class name, return value is class name that will be used. Mainly for use with css modules. */
    classNameMapper?: (defaultClassName: string) => string;
    /** function called for each I18nLabel to allow user translation, currently used for tab and tabset move messages, return undefined to use default values */
    i18nMapper?: (id: I18nLabel, param?: string) => string | undefined;
    /** if left undefined will do simple check based on userAgent */
    supportsPopout?: boolean | undefined;
    /** URL of popout window relative to origin, defaults to popout.html */
    popoutURL?: string | undefined;
    /** boolean value, defaults to false, resize tabs as splitters are dragged. Warning: this can cause resizing to become choppy when tabs are slow to draw */
    realtimeResize?: boolean | undefined;
    /** callback for rendering the drag rectangles */
    onRenderDragRect?: DragRectRenderCallback;
    /** callback for handling context actions on tabs and tabsets */
    onContextMenu?: NodeMouseEvent;
    /** callback for handling mouse clicks on tabs and tabsets with alt, meta, shift keys, also handles center mouse clicks */
    onAuxMouseClick?: NodeMouseEvent;
    /** callback for handling the display of the tab overflow menu */
    onShowOverflowMenu?: ShowOverflowMenuCallback;
    /** callback for rendering a placeholder when a tabset is empty */
    onTabSetPlaceHolder?: TabSetPlaceHolderCallback;
    /** Name given to popout windows, defaults to 'Popout Window' */
    popoutWindowName?: string;
}
/**
 * A React component that hosts a multi-tabbed layout
 */
export declare class Layout extends React.Component<ILayoutProps> {
    /** @internal */
    private selfRef;
    /** @internal */
    private revision;
    /** @internal */
    constructor(props: ILayoutProps);
    /** re-render the layout */
    redraw(): void;
    /**
     * Adds a new tab to the given tabset
     * @param tabsetId the id of the tabset where the new tab will be added
     * @param json the json for the new tab node
     * @returns the added tab node or undefined
     */
    addTabToTabSet(tabsetId: string, json: IJsonTabNode): TabNode | undefined;
    /**
     * Adds a new tab by dragging an item to the drop location, must be called from within an HTML
     * drag start handler. You can use the setDragComponent() method to set the drag image before calling this
     * method.
     * @param event the drag start event
     * @param json the json for the new tab node
     * @param onDrop a callback to call when the drag is complete
     */
    addTabWithDragAndDrop(event: DragEvent, json: IJsonTabNode, onDrop?: (node?: Node, event?: React.DragEvent<HTMLElement>) => void): void;
    /**
     * Move a tab/tabset using drag and drop, must be called from within an HTML
     * drag start handler
     * @param event the drag start event
     * @param node the tab or tabset to drag
     */
    moveTabWithDragAndDrop(event: DragEvent, node: (TabNode | TabSetNode)): void;
    /**
     * Adds a new tab to the active tabset (if there is one)
     * @param json the json for the new tab node
     * @returns the added tab node or undefined
     */
    addTabToActiveTabSet(json: IJsonTabNode): TabNode | undefined;
    /**
     * Sets the drag image from a react component for a drag event
     * @param event the drag event
     * @param component the react component to be used for the drag image
     * @param x the x position of the drag cursor on the image
     * @param y the x position of the drag cursor on the image
     */
    setDragComponent(event: DragEvent, component: React.ReactNode, x: number, y: number): void;
    /** Get the root div element of the layout */
    getRootDiv(): HTMLDivElement | null;
    /** @internal */
    render(): import("react/jsx-runtime").JSX.Element;
}
/** @internal */
interface ILayoutInternalProps extends ILayoutProps {
    renderRevision: number;
    windowId?: string;
    mainLayout?: LayoutInternal;
}
/** @internal */
interface ILayoutInternalState {
    rect: Rect;
    editingTab?: TabNode;
    portal?: React.ReactPortal;
    showEdges: boolean;
    showOverlay: boolean;
    calculatedBorderBarSize: number;
    layoutRevision: number;
    forceRevision: number;
    showHiddenBorder: DockLocation;
}
/** @internal */
export declare class LayoutInternal extends React.Component<ILayoutInternalProps, ILayoutInternalState> {
    static dragState: DragState | undefined;
    private selfRef;
    private moveablesRef;
    private findBorderBarSizeRef;
    private mainRef;
    private previousModel?;
    private orderedTabIds;
    private orderedTabMoveableIds;
    private moveableElementMap;
    private dropInfo;
    private outlineDiv?;
    private currentDocument?;
    private currentWindow?;
    private supportsPopout;
    private popoutURL;
    private icons;
    private resizeObserver?;
    private dragEnterCount;
    private dragging;
    private windowId;
    private layoutWindow;
    private mainLayout;
    private isMainWindow;
    private isDraggingOverWindow;
    private styleObserver;
    private popoutWindowName;
    constructor(props: ILayoutInternalProps);
    componentDidMount(): void;
    componentDidUpdate(): void;
    componentWillUnmount(): void;
    render(): import("react/jsx-runtime").JSX.Element;
    renderBorders(inner: React.ReactNode): import("react/jsx-runtime").JSX.Element;
    renderLayout(): import("react/jsx-runtime").JSX.Element;
    renderEdgeIndicators(): React.ReactNode[];
    renderWindows(): React.ReactNode[];
    renderTabMoveables(): Map<string, React.ReactNode>;
    renderTabStamps(): React.ReactNode[];
    renderTabs(): Map<string, React.ReactNode>;
    renderMetricsElements(): import("react/jsx-runtime").JSX.Element;
    checkForBorderToShow(x: number, y: number): void;
    updateLayoutMetrics: () => void;
    tidyMoveablesMap(): void;
    reorderComponents(components: Map<string, React.ReactNode>, ids: string[]): React.ReactNode[];
    onModelChange: (action: Action) => void;
    redraw(type?: string): void;
    redrawInternal(type: string): void;
    doAction(action: Action): Node | undefined;
    updateRect: () => void;
    getBoundingClientRect(div: HTMLElement): Rect;
    getMoveableContainer(): HTMLDivElement | null;
    getMoveableElement(id: string): HTMLElement;
    getMainLayout(): LayoutInternal;
    getClassName: (defaultClassName: string) => string;
    getCurrentDocument(): Document | undefined;
    getDomRect(): Rect;
    getWindowId(): string;
    getRootDiv(): HTMLDivElement | null;
    getMainElement(): HTMLDivElement | null;
    getFactory(): (node: TabNode) => React.ReactNode;
    isSupportsPopout(): boolean;
    isRealtimeResize(): boolean;
    getPopoutURL(): string;
    setEditingTab(tabNode?: TabNode): void;
    getEditingTab(): TabNode | undefined;
    getModel(): Model;
    onCloseWindow: (windowLayout: LayoutWindow) => void;
    onSetWindow: (windowLayout: LayoutWindow, window: Window) => void;
    getScreenRect(inRect: Rect): Rect;
    addTabToTabSet(tabsetId: string, json: IJsonTabNode): TabNode | undefined;
    addTabToActiveTabSet(json: IJsonTabNode): TabNode | undefined;
    showControlInPortal: (control: React.ReactNode, element: HTMLElement) => void;
    hideControlInPortal: () => void;
    getIcons: () => IIcons;
    maximize(tabsetNode: TabSetNode): void;
    customizeTab(tabNode: TabNode, renderValues: ITabRenderValues): void;
    customizeTabSet(tabSetNode: TabSetNode | BorderNode, renderValues: ITabSetRenderValues): void;
    i18nName(id: I18nLabel, param?: string): string;
    getShowOverflowMenu(): ShowOverflowMenuCallback | undefined;
    getTabSetPlaceHolderCallback(): TabSetPlaceHolderCallback | undefined;
    showContextMenu(node: TabNode | TabSetNode | BorderNode, event: React.MouseEvent<HTMLElement, MouseEvent>): void;
    auxMouseClick(node: TabNode | TabSetNode | BorderNode, event: React.MouseEvent<HTMLElement, MouseEvent>): void;
    showOverlay(show: boolean): void;
    addTabWithDragAndDrop(event: DragEvent, json: IJsonTabNode, onDrop?: (node?: Node, event?: React.DragEvent<HTMLElement>) => void): void;
    moveTabWithDragAndDrop(event: DragEvent, node: (TabNode | TabSetNode)): void;
    setDragNode: (event: DragEvent, node: Node & IDraggable) => void;
    setDragComponent(event: DragEvent, component: React.ReactNode, x: number, y: number): void;
    setDraggingOverWindow(overWindow: boolean): void;
    onDragEnterRaw: (event: React.DragEvent<HTMLElement>) => void;
    onDragLeaveRaw: (event: React.DragEvent<HTMLElement>) => void;
    clearDragMain(): void;
    clearDragLocal(): void;
    onDragEnter: (event: React.DragEvent<HTMLElement>) => void;
    onDragOver: (event: React.DragEvent<HTMLElement>) => void;
    onDragLeave: (event: React.DragEvent<HTMLElement>) => void;
    onDrop: (event: React.DragEvent<HTMLElement>) => void;
}
export declare const FlexLayoutVersion: string;
export type DragRectRenderCallback = (content: React.ReactNode | undefined, node?: Node, json?: IJsonTabNode) => React.ReactNode | undefined;
export type NodeMouseEvent = (node: TabNode | TabSetNode | BorderNode, event: React.MouseEvent<HTMLElement, MouseEvent>) => void;
export type ShowOverflowMenuCallback = (node: TabSetNode | BorderNode, mouseEvent: React.MouseEvent<HTMLElement, MouseEvent>, items: {
    index: number;
    node: TabNode;
}[], onSelect: (item: {
    index: number;
    node: TabNode;
}) => void) => void;
export type TabSetPlaceHolderCallback = (node: TabSetNode) => React.ReactNode;
export interface ITabSetRenderValues {
    /** a component to be placed before the tabs */
    leading: React.ReactNode;
    /** components that will be added after the tabs */
    stickyButtons: React.ReactNode[];
    /** components that will be added at the end of the tabset */
    buttons: React.ReactNode[];
    /** position to insert overflow button within [...stickyButtons, ...buttons]
     * if left undefined position will be after the sticky buttons (if any)
     */
    overflowPosition: number | undefined;
}
export interface ITabRenderValues {
    /** the icon or other leading component */
    leading: React.ReactNode;
    /** the main tab text/component */
    content: React.ReactNode;
    /** a set of react components to add to the tab after the content */
    buttons: React.ReactNode[];
}
export interface IIcons {
    close?: (React.ReactNode | ((tabNode: TabNode) => React.ReactNode));
    closeTabset?: (React.ReactNode | ((tabSetNode: TabSetNode) => React.ReactNode));
    popout?: (React.ReactNode | ((tabNode: TabNode) => React.ReactNode));
    maximize?: (React.ReactNode | ((tabSetNode: TabSetNode) => React.ReactNode));
    restore?: (React.ReactNode | ((tabSetNode: TabSetNode) => React.ReactNode));
    more?: (React.ReactNode | ((tabSetNode: (TabSetNode | BorderNode), hiddenTabs: {
        node: TabNode;
        index: number;
    }[]) => React.ReactNode));
    edgeArrow?: React.ReactNode;
    activeTabset?: (React.ReactNode | ((tabSetNode: TabSetNode) => React.ReactNode));
}
declare enum DragSource {
    Internal = "internal",
    External = "external",
    Add = "add"
}
declare class DragState {
    readonly mainLayout: LayoutInternal;
    readonly dragSource: DragSource;
    readonly dragNode: Node & IDraggable | undefined;
    readonly dragJson: IJsonTabNode | undefined;
    readonly fnNewNodeDropped: ((node?: Node, event?: React.DragEvent<HTMLElement>) => void) | undefined;
    constructor(mainLayout: LayoutInternal, dragSource: DragSource, dragNode: Node & IDraggable | undefined, dragJson: IJsonTabNode | undefined, fnNewNodeDropped: ((node?: Node, event?: React.DragEvent<HTMLElement>) => void) | undefined);
}
export {};
