import { DockLocation } from "../DockLocation";
import { Action } from "./Action";
import { IJsonRect, IJsonRowNode } from "./IJsonModel";
/**
 * The Action creator class for FlexLayout model actions
 */
export declare class Actions {
    static ADD_NODE: string;
    static MOVE_NODE: string;
    static DELETE_TAB: string;
    static DELETE_TABSET: string;
    static RENAME_TAB: string;
    static SELECT_TAB: string;
    static SET_ACTIVE_TABSET: string;
    static ADJUST_WEIGHTS: string;
    static ADJUST_BORDER_SPLIT: string;
    static MAXIMIZE_TOGGLE: string;
    static UPDATE_MODEL_ATTRIBUTES: string;
    static UPDATE_NODE_ATTRIBUTES: string;
    static POPOUT_TAB: string;
    static POPOUT_TABSET: string;
    static CLOSE_WINDOW: string;
    static CREATE_WINDOW: string;
    /**
     * Adds a tab node to the given tabset node
     * @param json the json for the new tab node e.g {type:"tab", component:"table"}
     * @param toNodeId the new tab node will be added to the tabset with this node id
     * @param location the location where the new tab will be added, one of the DockLocation enum values.
     * @param index for docking to the center this value is the index of the tab, use -1 to add to the end.
     * @param select (optional) whether to select the new tab, overriding autoSelectTab
     * @returns {Action} the action
     */
    static addNode(json: any, toNodeId: string, location: DockLocation, index: number, select?: boolean): Action;
    /**
     * Moves a node (tab or tabset) from one location to another
     * @param fromNodeId the id of the node to move
     * @param toNodeId the id of the node to receive the moved node
     * @param location the location where the moved node will be added, one of the DockLocation enum values.
     * @param index for docking to the center this value is the index of the tab, use -1 to add to the end.
     * @param select (optional) whether to select the moved tab(s) in new tabset, overriding autoSelectTab
     * @returns {Action} the action
     */
    static moveNode(fromNodeId: string, toNodeId: string, location: DockLocation, index: number, select?: boolean): Action;
    /**
     * Deletes a tab node from the layout
     * @param tabNodeId the id of the tab node to delete
     * @returns {Action} the action
     */
    static deleteTab(tabNodeId: string): Action;
    /**
     * Deletes a tabset node and all it's child tab nodes from the layout
     * @param tabsetNodeId the id of the tabset node to delete
     * @returns {Action} the action
     */
    static deleteTabset(tabsetNodeId: string): Action;
    /**
     * Change the given nodes tab text
     * @param tabNodeId the id of the node to rename
     * @param text the test of the tab
     * @returns {Action} the action
     */
    static renameTab(tabNodeId: string, text: string): Action;
    /**
     * Selects the given tab in its parent tabset
     * @param tabNodeId the id of the node to set selected
     * @returns {Action} the action
     */
    static selectTab(tabNodeId: string): Action;
    /**
     * Set the given tabset node as the active tabset
     * @param tabsetNodeId the id of the tabset node to set as active
     * @returns {Action} the action
     */
    static setActiveTabset(tabsetNodeId: string | undefined, windowId?: string | undefined): Action;
    /**
     * Adjust the weights of a row, used when the splitter is moved
     * @param nodeId the row node whose childrens weights are being adjusted
     * @param weights an array of weights to be applied to the children
     * @returns {Action} the action
     */
    static adjustWeights(nodeId: string, weights: number[]): Action;
    static adjustBorderSplit(nodeId: string, pos: number): Action;
    /**
     * Maximizes the given tabset
     * @param tabsetNodeId the id of the tabset to maximize
     * @returns {Action} the action
     */
    static maximizeToggle(tabsetNodeId: string, windowId?: string | undefined): Action;
    /**
     * Updates the global model jsone attributes
     * @param attributes the json for the model attributes to update (merge into the existing attributes)
     * @returns {Action} the action
     */
    static updateModelAttributes(attributes: any): Action;
    /**
     * Updates the given nodes json attributes
     * @param nodeId the id of the node to update
     * @param attributes the json attributes to update (merge with the existing attributes)
     * @returns {Action} the action
     */
    static updateNodeAttributes(nodeId: string, attributes: any): Action;
    /**
     * Pops out the given tab node into a new browser window
     * @param nodeId the tab node to popout
     * @returns
     */
    static popoutTab(nodeId: string): Action;
    /**
     * Pops out the given tab set node into a new browser window
     * @param nodeId the tab set node to popout
     * @returns
     */
    static popoutTabset(nodeId: string): Action;
    /**
     * Closes the popout window
     * @param windowId the id of the popout window to close
     * @returns
     */
    static closeWindow(windowId: string): Action;
    /**
     * Creates a new empty popout window with the given layout
     * @param layout the json layout for the new window
     * @param rect the window rectangle in screen coordinates
     * @returns
     */
    static createWindow(layout: IJsonRowNode, rect: IJsonRect): Action;
}
