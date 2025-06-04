/**
 * flexlayout-react
 * @version 0.8.17
 */
var __defProp = Object.defineProperty;
var __defNormalProp = (obj, key, value) => key in obj ? __defProp(obj, key, { enumerable: true, configurable: true, writable: true, value }) : obj[key] = value;
var __publicField = (obj, key, value) => __defNormalProp(obj, typeof key !== "symbol" ? key + "" : key, value);
import { jsx, jsxs, Fragment } from "react/jsx-runtime";
import * as React from "react";
import { useRef, useEffect } from "react";
import { createPortal } from "react-dom";
import { createRoot } from "react-dom/client";
const _Orientation = class _Orientation {
  /** @internal */
  constructor(name) {
    /** @internal */
    __publicField(this, "_name");
    this._name = name;
  }
  static flip(from) {
    if (from === _Orientation.HORZ) {
      return _Orientation.VERT;
    } else {
      return _Orientation.HORZ;
    }
  }
  getName() {
    return this._name;
  }
  toString() {
    return this._name;
  }
};
__publicField(_Orientation, "HORZ", new _Orientation("horz"));
__publicField(_Orientation, "VERT", new _Orientation("vert"));
let Orientation = _Orientation;
class Rect {
  constructor(x, y, width, height) {
    __publicField(this, "x");
    __publicField(this, "y");
    __publicField(this, "width");
    __publicField(this, "height");
    this.x = x;
    this.y = y;
    this.width = width;
    this.height = height;
  }
  static empty() {
    return new Rect(0, 0, 0, 0);
  }
  static fromJson(json) {
    return new Rect(json.x, json.y, json.width, json.height);
  }
  toJson() {
    return { x: this.x, y: this.y, width: this.width, height: this.height };
  }
  snap(round) {
    this.x = Math.round(this.x / round) * round;
    this.y = Math.round(this.y / round) * round;
    this.width = Math.round(this.width / round) * round;
    this.height = Math.round(this.height / round) * round;
  }
  static getBoundingClientRect(element) {
    const { x, y, width, height } = element.getBoundingClientRect();
    return new Rect(x, y, width, height);
  }
  static getContentRect(element) {
    const rect = element.getBoundingClientRect();
    const style2 = window.getComputedStyle(element);
    const paddingLeft = parseFloat(style2.paddingLeft);
    const paddingRight = parseFloat(style2.paddingRight);
    const paddingTop = parseFloat(style2.paddingTop);
    const paddingBottom = parseFloat(style2.paddingBottom);
    const borderLeftWidth = parseFloat(style2.borderLeftWidth);
    const borderRightWidth = parseFloat(style2.borderRightWidth);
    const borderTopWidth = parseFloat(style2.borderTopWidth);
    const borderBottomWidth = parseFloat(style2.borderBottomWidth);
    const contentWidth = rect.width - borderLeftWidth - paddingLeft - paddingRight - borderRightWidth;
    const contentHeight = rect.height - borderTopWidth - paddingTop - paddingBottom - borderBottomWidth;
    return new Rect(
      rect.left + borderLeftWidth + paddingLeft,
      rect.top + borderTopWidth + paddingTop,
      contentWidth,
      contentHeight
    );
  }
  static fromDomRect(domRect) {
    return new Rect(domRect.x, domRect.y, domRect.width, domRect.height);
  }
  relativeTo(r) {
    return new Rect(this.x - r.x, this.y - r.y, this.width, this.height);
  }
  clone() {
    return new Rect(this.x, this.y, this.width, this.height);
  }
  equals(rect) {
    return this.x === (rect == null ? void 0 : rect.x) && this.y === (rect == null ? void 0 : rect.y) && this.width === (rect == null ? void 0 : rect.width) && this.height === (rect == null ? void 0 : rect.height);
  }
  equalSize(rect) {
    return this.width === (rect == null ? void 0 : rect.width) && this.height === (rect == null ? void 0 : rect.height);
  }
  getBottom() {
    return this.y + this.height;
  }
  getRight() {
    return this.x + this.width;
  }
  get bottom() {
    return this.y + this.height;
  }
  get right() {
    return this.x + this.width;
  }
  getCenter() {
    return { x: this.x + this.width / 2, y: this.y + this.height / 2 };
  }
  positionElement(element, position) {
    this.styleWithPosition(element.style, position);
  }
  styleWithPosition(style2, position = "absolute") {
    style2.left = this.x + "px";
    style2.top = this.y + "px";
    style2.width = Math.max(0, this.width) + "px";
    style2.height = Math.max(0, this.height) + "px";
    style2.position = position;
    return style2;
  }
  contains(x, y) {
    if (this.x <= x && x <= this.getRight() && this.y <= y && y <= this.getBottom()) {
      return true;
    } else {
      return false;
    }
  }
  removeInsets(insets) {
    return new Rect(this.x + insets.left, this.y + insets.top, Math.max(0, this.width - insets.left - insets.right), Math.max(0, this.height - insets.top - insets.bottom));
  }
  centerInRect(outerRect) {
    this.x = (outerRect.width - this.width) / 2;
    this.y = (outerRect.height - this.height) / 2;
  }
  /** @internal */
  _getSize(orientation) {
    let prefSize = this.width;
    if (orientation === Orientation.VERT) {
      prefSize = this.height;
    }
    return prefSize;
  }
  toString() {
    return "(Rect: x=" + this.x + ", y=" + this.y + ", width=" + this.width + ", height=" + this.height + ")";
  }
}
const _DockLocation = class _DockLocation {
  /** @internal */
  constructor(_name, _orientation, _indexPlus) {
    /** @internal */
    __publicField(this, "name");
    /** @internal */
    __publicField(this, "orientation");
    /** @internal */
    __publicField(this, "indexPlus");
    this.name = _name;
    this.orientation = _orientation;
    this.indexPlus = _indexPlus;
    _DockLocation.values.set(this.name, this);
  }
  /** @internal */
  static getByName(name) {
    return _DockLocation.values.get(name);
  }
  /** @internal */
  static getLocation(rect, x, y) {
    x = (x - rect.x) / rect.width;
    y = (y - rect.y) / rect.height;
    if (x >= 0.25 && x < 0.75 && y >= 0.25 && y < 0.75) {
      return _DockLocation.CENTER;
    }
    const bl = y >= x;
    const br = y >= 1 - x;
    if (bl) {
      return br ? _DockLocation.BOTTOM : _DockLocation.LEFT;
    } else {
      return br ? _DockLocation.RIGHT : _DockLocation.TOP;
    }
  }
  getName() {
    return this.name;
  }
  getOrientation() {
    return this.orientation;
  }
  /** @internal */
  getDockRect(r) {
    if (this === _DockLocation.TOP) {
      return new Rect(r.x, r.y, r.width, r.height / 2);
    } else if (this === _DockLocation.BOTTOM) {
      return new Rect(r.x, r.getBottom() - r.height / 2, r.width, r.height / 2);
    }
    if (this === _DockLocation.LEFT) {
      return new Rect(r.x, r.y, r.width / 2, r.height);
    } else if (this === _DockLocation.RIGHT) {
      return new Rect(r.getRight() - r.width / 2, r.y, r.width / 2, r.height);
    } else {
      return r.clone();
    }
  }
  /** @internal */
  split(rect, size) {
    if (this === _DockLocation.TOP) {
      const r1 = new Rect(rect.x, rect.y, rect.width, size);
      const r2 = new Rect(rect.x, rect.y + size, rect.width, rect.height - size);
      return { start: r1, end: r2 };
    } else if (this === _DockLocation.LEFT) {
      const r1 = new Rect(rect.x, rect.y, size, rect.height);
      const r2 = new Rect(rect.x + size, rect.y, rect.width - size, rect.height);
      return { start: r1, end: r2 };
    }
    if (this === _DockLocation.RIGHT) {
      const r1 = new Rect(rect.getRight() - size, rect.y, size, rect.height);
      const r2 = new Rect(rect.x, rect.y, rect.width - size, rect.height);
      return { start: r1, end: r2 };
    } else {
      const r1 = new Rect(rect.x, rect.getBottom() - size, rect.width, size);
      const r2 = new Rect(rect.x, rect.y, rect.width, rect.height - size);
      return { start: r1, end: r2 };
    }
  }
  /** @internal */
  reflect() {
    if (this === _DockLocation.TOP) {
      return _DockLocation.BOTTOM;
    } else if (this === _DockLocation.LEFT) {
      return _DockLocation.RIGHT;
    }
    if (this === _DockLocation.RIGHT) {
      return _DockLocation.LEFT;
    } else {
      return _DockLocation.TOP;
    }
  }
  toString() {
    return "(DockLocation: name=" + this.name + ", orientation=" + this.orientation + ")";
  }
};
__publicField(_DockLocation, "values", /* @__PURE__ */ new Map());
__publicField(_DockLocation, "TOP", new _DockLocation("top", Orientation.VERT, 0));
__publicField(_DockLocation, "BOTTOM", new _DockLocation("bottom", Orientation.VERT, 1));
__publicField(_DockLocation, "LEFT", new _DockLocation("left", Orientation.HORZ, 0));
__publicField(_DockLocation, "RIGHT", new _DockLocation("right", Orientation.HORZ, 1));
__publicField(_DockLocation, "CENTER", new _DockLocation("center", Orientation.VERT, 0));
let DockLocation = _DockLocation;
var I18nLabel = /* @__PURE__ */ ((I18nLabel2) => {
  I18nLabel2["Close_Tab"] = "Close";
  I18nLabel2["Close_Tabset"] = "Close tab set";
  I18nLabel2["Active_Tabset"] = "Active tab set";
  I18nLabel2["Move_Tabset"] = "Move tab set";
  I18nLabel2["Move_Tabs"] = "Move tabs(?)";
  I18nLabel2["Maximize"] = "Maximize tab set";
  I18nLabel2["Restore"] = "Restore tab set";
  I18nLabel2["Popout_Tab"] = "Popout selected tab";
  I18nLabel2["Overflow_Menu_Tooltip"] = "Hidden tabs";
  I18nLabel2["Error_rendering_component"] = "Error rendering component";
  I18nLabel2["Error_rendering_component_retry"] = "Retry";
  return I18nLabel2;
})(I18nLabel || {});
var CLASSES = /* @__PURE__ */ ((CLASSES2) => {
  CLASSES2["FLEXLAYOUT__BORDER"] = "flexlayout__border";
  CLASSES2["FLEXLAYOUT__BORDER_"] = "flexlayout__border_";
  CLASSES2["FLEXLAYOUT__BORDER_TAB_CONTENTS"] = "flexlayout__border_tab_contents";
  CLASSES2["FLEXLAYOUT__BORDER_BUTTON"] = "flexlayout__border_button";
  CLASSES2["FLEXLAYOUT__BORDER_BUTTON_"] = "flexlayout__border_button_";
  CLASSES2["FLEXLAYOUT__BORDER_BUTTON_CONTENT"] = "flexlayout__border_button_content";
  CLASSES2["FLEXLAYOUT__BORDER_BUTTON_LEADING"] = "flexlayout__border_button_leading";
  CLASSES2["FLEXLAYOUT__BORDER_BUTTON_TRAILING"] = "flexlayout__border_button_trailing";
  CLASSES2["FLEXLAYOUT__BORDER_BUTTON__SELECTED"] = "flexlayout__border_button--selected";
  CLASSES2["FLEXLAYOUT__BORDER_BUTTON__UNSELECTED"] = "flexlayout__border_button--unselected";
  CLASSES2["FLEXLAYOUT__BORDER_TOOLBAR_BUTTON_OVERFLOW"] = "flexlayout__border_toolbar_button_overflow";
  CLASSES2["FLEXLAYOUT__BORDER_TOOLBAR_BUTTON_OVERFLOW_"] = "flexlayout__border_toolbar_button_overflow_";
  CLASSES2["FLEXLAYOUT__BORDER_INNER"] = "flexlayout__border_inner";
  CLASSES2["FLEXLAYOUT__BORDER_INNER_"] = "flexlayout__border_inner_";
  CLASSES2["FLEXLAYOUT__BORDER_INNER_TAB_CONTAINER"] = "flexlayout__border_inner_tab_container";
  CLASSES2["FLEXLAYOUT__BORDER_INNER_TAB_CONTAINER_"] = "flexlayout__border_inner_tab_container_";
  CLASSES2["FLEXLAYOUT__BORDER_TAB_DIVIDER"] = "flexlayout__border_tab_divider";
  CLASSES2["FLEXLAYOUT__BORDER_LEADING"] = "flexlayout__border_leading";
  CLASSES2["FLEXLAYOUT__BORDER_SIZER"] = "flexlayout__border_sizer";
  CLASSES2["FLEXLAYOUT__BORDER_TOOLBAR"] = "flexlayout__border_toolbar";
  CLASSES2["FLEXLAYOUT__BORDER_TOOLBAR_"] = "flexlayout__border_toolbar_";
  CLASSES2["FLEXLAYOUT__BORDER_TOOLBAR_BUTTON"] = "flexlayout__border_toolbar_button";
  CLASSES2["FLEXLAYOUT__BORDER_TOOLBAR_BUTTON_FLOAT"] = "flexlayout__border_toolbar_button-float";
  CLASSES2["FLEXLAYOUT__DRAG_RECT"] = "flexlayout__drag_rect";
  CLASSES2["FLEXLAYOUT__EDGE_RECT"] = "flexlayout__edge_rect";
  CLASSES2["FLEXLAYOUT__EDGE_RECT_TOP"] = "flexlayout__edge_rect_top";
  CLASSES2["FLEXLAYOUT__EDGE_RECT_LEFT"] = "flexlayout__edge_rect_left";
  CLASSES2["FLEXLAYOUT__EDGE_RECT_BOTTOM"] = "flexlayout__edge_rect_bottom";
  CLASSES2["FLEXLAYOUT__EDGE_RECT_RIGHT"] = "flexlayout__edge_rect_right";
  CLASSES2["FLEXLAYOUT__ERROR_BOUNDARY_CONTAINER"] = "flexlayout__error_boundary_container";
  CLASSES2["FLEXLAYOUT__ERROR_BOUNDARY_CONTENT"] = "flexlayout__error_boundary_content";
  CLASSES2["FLEXLAYOUT__FLOATING_WINDOW_CONTENT"] = "flexlayout__floating_window_content";
  CLASSES2["FLEXLAYOUT__LAYOUT"] = "flexlayout__layout";
  CLASSES2["FLEXLAYOUT__LAYOUT_MOVEABLES"] = "flexlayout__layout_moveables";
  CLASSES2["FLEXLAYOUT__LAYOUT_OVERLAY"] = "flexlayout__layout_overlay";
  CLASSES2["FLEXLAYOUT__LAYOUT_TAB_STAMPS"] = "flexlayout__layout_tab_stamps";
  CLASSES2["FLEXLAYOUT__LAYOUT_MAIN"] = "flexlayout__layout_main";
  CLASSES2["FLEXLAYOUT__LAYOUT_BORDER_CONTAINER"] = "flexlayout__layout_border_container";
  CLASSES2["FLEXLAYOUT__LAYOUT_BORDER_CONTAINER_INNER"] = "flexlayout__layout_border_container_inner";
  CLASSES2["FLEXLAYOUT__OUTLINE_RECT"] = "flexlayout__outline_rect";
  CLASSES2["FLEXLAYOUT__OUTLINE_RECT_EDGE"] = "flexlayout__outline_rect_edge";
  CLASSES2["FLEXLAYOUT__SPLITTER"] = "flexlayout__splitter";
  CLASSES2["FLEXLAYOUT__SPLITTER_EXTRA"] = "flexlayout__splitter_extra";
  CLASSES2["FLEXLAYOUT__SPLITTER_"] = "flexlayout__splitter_";
  CLASSES2["FLEXLAYOUT__SPLITTER_BORDER"] = "flexlayout__splitter_border";
  CLASSES2["FLEXLAYOUT__SPLITTER_DRAG"] = "flexlayout__splitter_drag";
  CLASSES2["FLEXLAYOUT__SPLITTER_HANDLE"] = "flexlayout__splitter_handle";
  CLASSES2["FLEXLAYOUT__SPLITTER_HANDLE_HORZ"] = "flexlayout__splitter_handle_horz";
  CLASSES2["FLEXLAYOUT__SPLITTER_HANDLE_VERT"] = "flexlayout__splitter_handle_vert";
  CLASSES2["FLEXLAYOUT__ROW"] = "flexlayout__row";
  CLASSES2["FLEXLAYOUT__TAB"] = "flexlayout__tab";
  CLASSES2["FLEXLAYOUT__TAB_POSITION"] = "flexlayout__tab_position";
  CLASSES2["FLEXLAYOUT__TAB_MOVEABLE"] = "flexlayout__tab_moveable";
  CLASSES2["FLEXLAYOUT__TAB_OVERLAY"] = "flexlayout__tab_overlay";
  CLASSES2["FLEXLAYOUT__TABSET"] = "flexlayout__tabset";
  CLASSES2["FLEXLAYOUT__TABSET_CONTAINER"] = "flexlayout__tabset_container";
  CLASSES2["FLEXLAYOUT__TABSET_HEADER"] = "flexlayout__tabset_header";
  CLASSES2["FLEXLAYOUT__TABSET_HEADER_CONTENT"] = "flexlayout__tabset_header_content";
  CLASSES2["FLEXLAYOUT__TABSET_MAXIMIZED"] = "flexlayout__tabset-maximized";
  CLASSES2["FLEXLAYOUT__TABSET_SELECTED"] = "flexlayout__tabset-selected";
  CLASSES2["FLEXLAYOUT__TABSET_TAB_DIVIDER"] = "flexlayout__tabset_tab_divider";
  CLASSES2["FLEXLAYOUT__TABSET_CONTENT"] = "flexlayout__tabset_content";
  CLASSES2["FLEXLAYOUT__TABSET_TABBAR_INNER"] = "flexlayout__tabset_tabbar_inner";
  CLASSES2["FLEXLAYOUT__TABSET_TABBAR_INNER_"] = "flexlayout__tabset_tabbar_inner_";
  CLASSES2["FLEXLAYOUT__TABSET_LEADING"] = "flexlayout__tabset_leading";
  CLASSES2["FLEXLAYOUT__TABSET_TABBAR_INNER_TAB_CONTAINER"] = "flexlayout__tabset_tabbar_inner_tab_container";
  CLASSES2["FLEXLAYOUT__TABSET_TABBAR_INNER_TAB_CONTAINER_"] = "flexlayout__tabset_tabbar_inner_tab_container_";
  CLASSES2["FLEXLAYOUT__TABSET_TABBAR_OUTER"] = "flexlayout__tabset_tabbar_outer";
  CLASSES2["FLEXLAYOUT__TABSET_TABBAR_OUTER_"] = "flexlayout__tabset_tabbar_outer_";
  CLASSES2["FLEXLAYOUT__TAB_BORDER"] = "flexlayout__tab_border";
  CLASSES2["FLEXLAYOUT__TAB_BORDER_"] = "flexlayout__tab_border_";
  CLASSES2["FLEXLAYOUT__TAB_BUTTON"] = "flexlayout__tab_button";
  CLASSES2["FLEXLAYOUT__TAB_BUTTON_STRETCH"] = "flexlayout__tab_button_stretch";
  CLASSES2["FLEXLAYOUT__TAB_BUTTON_CONTENT"] = "flexlayout__tab_button_content";
  CLASSES2["FLEXLAYOUT__TAB_BUTTON_LEADING"] = "flexlayout__tab_button_leading";
  CLASSES2["FLEXLAYOUT__TAB_BUTTON_OVERFLOW"] = "flexlayout__tab_button_overflow";
  CLASSES2["FLEXLAYOUT__TAB_BUTTON_OVERFLOW_COUNT"] = "flexlayout__tab_button_overflow_count";
  CLASSES2["FLEXLAYOUT__TAB_BUTTON_TEXTBOX"] = "flexlayout__tab_button_textbox";
  CLASSES2["FLEXLAYOUT__TAB_BUTTON_TRAILING"] = "flexlayout__tab_button_trailing";
  CLASSES2["FLEXLAYOUT__TAB_BUTTON_STAMP"] = "flexlayout__tab_button_stamp";
  CLASSES2["FLEXLAYOUT__TAB_TOOLBAR"] = "flexlayout__tab_toolbar";
  CLASSES2["FLEXLAYOUT__TAB_TOOLBAR_BUTTON"] = "flexlayout__tab_toolbar_button";
  CLASSES2["FLEXLAYOUT__TAB_TOOLBAR_ICON"] = "flexlayout__tab_toolbar_icon";
  CLASSES2["FLEXLAYOUT__TAB_TOOLBAR_BUTTON_"] = "flexlayout__tab_toolbar_button-";
  CLASSES2["FLEXLAYOUT__TAB_TOOLBAR_BUTTON_FLOAT"] = "flexlayout__tab_toolbar_button-float";
  CLASSES2["FLEXLAYOUT__TAB_TOOLBAR_STICKY_BUTTONS_CONTAINER"] = "flexlayout__tab_toolbar_sticky_buttons_container";
  CLASSES2["FLEXLAYOUT__TAB_TOOLBAR_BUTTON_CLOSE"] = "flexlayout__tab_toolbar_button-close";
  CLASSES2["FLEXLAYOUT__POPUP_MENU_CONTAINER"] = "flexlayout__popup_menu_container";
  CLASSES2["FLEXLAYOUT__POPUP_MENU_ITEM"] = "flexlayout__popup_menu_item";
  CLASSES2["FLEXLAYOUT__POPUP_MENU_ITEM__SELECTED"] = "flexlayout__popup_menu_item--selected";
  CLASSES2["FLEXLAYOUT__POPUP_MENU"] = "flexlayout__popup_menu";
  CLASSES2["FLEXLAYOUT__MINI_SCROLLBAR"] = "flexlayout__mini_scrollbar";
  CLASSES2["FLEXLAYOUT__MINI_SCROLLBAR_CONTAINER"] = "flexlayout__mini_scrollbar_container";
  return CLASSES2;
})(CLASSES || {});
class Action {
  constructor(type, data) {
    __publicField(this, "type");
    __publicField(this, "data");
    this.type = type;
    this.data = data;
  }
}
const _Actions = class _Actions {
  /**
   * Adds a tab node to the given tabset node
   * @param json the json for the new tab node e.g {type:"tab", component:"table"}
   * @param toNodeId the new tab node will be added to the tabset with this node id
   * @param location the location where the new tab will be added, one of the DockLocation enum values.
   * @param index for docking to the center this value is the index of the tab, use -1 to add to the end.
   * @param select (optional) whether to select the new tab, overriding autoSelectTab
   * @returns {Action} the action
   */
  static addNode(json, toNodeId, location, index, select) {
    return new Action(_Actions.ADD_NODE, {
      json,
      toNode: toNodeId,
      location: location.getName(),
      index,
      select
    });
  }
  /**
   * Moves a node (tab or tabset) from one location to another
   * @param fromNodeId the id of the node to move
   * @param toNodeId the id of the node to receive the moved node
   * @param location the location where the moved node will be added, one of the DockLocation enum values.
   * @param index for docking to the center this value is the index of the tab, use -1 to add to the end.
   * @param select (optional) whether to select the moved tab(s) in new tabset, overriding autoSelectTab
   * @returns {Action} the action
   */
  static moveNode(fromNodeId, toNodeId, location, index, select) {
    return new Action(_Actions.MOVE_NODE, {
      fromNode: fromNodeId,
      toNode: toNodeId,
      location: location.getName(),
      index,
      select
    });
  }
  /**
   * Deletes a tab node from the layout
   * @param tabNodeId the id of the tab node to delete
   * @returns {Action} the action
   */
  static deleteTab(tabNodeId) {
    return new Action(_Actions.DELETE_TAB, { node: tabNodeId });
  }
  /**
   * Deletes a tabset node and all it's child tab nodes from the layout
   * @param tabsetNodeId the id of the tabset node to delete
   * @returns {Action} the action
   */
  static deleteTabset(tabsetNodeId) {
    return new Action(_Actions.DELETE_TABSET, { node: tabsetNodeId });
  }
  /**
   * Change the given nodes tab text
   * @param tabNodeId the id of the node to rename
   * @param text the test of the tab
   * @returns {Action} the action
   */
  static renameTab(tabNodeId, text) {
    return new Action(_Actions.RENAME_TAB, { node: tabNodeId, text });
  }
  /**
   * Selects the given tab in its parent tabset
   * @param tabNodeId the id of the node to set selected
   * @returns {Action} the action
   */
  static selectTab(tabNodeId) {
    return new Action(_Actions.SELECT_TAB, { tabNode: tabNodeId });
  }
  /**
   * Set the given tabset node as the active tabset
   * @param tabsetNodeId the id of the tabset node to set as active
   * @returns {Action} the action
   */
  static setActiveTabset(tabsetNodeId, windowId) {
    return new Action(_Actions.SET_ACTIVE_TABSET, { tabsetNode: tabsetNodeId, windowId });
  }
  /**
   * Adjust the weights of a row, used when the splitter is moved
   * @param nodeId the row node whose childrens weights are being adjusted
   * @param weights an array of weights to be applied to the children 
   * @returns {Action} the action
   */
  static adjustWeights(nodeId, weights) {
    return new Action(_Actions.ADJUST_WEIGHTS, { nodeId, weights });
  }
  static adjustBorderSplit(nodeId, pos) {
    return new Action(_Actions.ADJUST_BORDER_SPLIT, { node: nodeId, pos });
  }
  /**
   * Maximizes the given tabset
   * @param tabsetNodeId the id of the tabset to maximize
   * @returns {Action} the action
   */
  static maximizeToggle(tabsetNodeId, windowId) {
    return new Action(_Actions.MAXIMIZE_TOGGLE, { node: tabsetNodeId, windowId });
  }
  /**
   * Updates the global model jsone attributes
   * @param attributes the json for the model attributes to update (merge into the existing attributes)
   * @returns {Action} the action
   */
  static updateModelAttributes(attributes) {
    return new Action(_Actions.UPDATE_MODEL_ATTRIBUTES, { json: attributes });
  }
  /**
   * Updates the given nodes json attributes
   * @param nodeId the id of the node to update
   * @param attributes the json attributes to update (merge with the existing attributes)
   * @returns {Action} the action
   */
  static updateNodeAttributes(nodeId, attributes) {
    return new Action(_Actions.UPDATE_NODE_ATTRIBUTES, { node: nodeId, json: attributes });
  }
  /**
   * Pops out the given tab node into a new browser window
   * @param nodeId the tab node to popout
   * @returns 
   */
  static popoutTab(nodeId) {
    return new Action(_Actions.POPOUT_TAB, { node: nodeId });
  }
  /**
   * Pops out the given tab set node into a new browser window
   * @param nodeId the tab set node to popout
   * @returns 
   */
  static popoutTabset(nodeId) {
    return new Action(_Actions.POPOUT_TABSET, { node: nodeId });
  }
  /**
   * Closes the popout window
   * @param windowId the id of the popout window to close
   * @returns 
   */
  static closeWindow(windowId) {
    return new Action(_Actions.CLOSE_WINDOW, { windowId });
  }
  /**
   * Creates a new empty popout window with the given layout
   * @param layout the json layout for the new window
   * @param rect the window rectangle in screen coordinates
   * @returns 
   */
  static createWindow(layout, rect) {
    return new Action(_Actions.CREATE_WINDOW, { layout, rect });
  }
};
__publicField(_Actions, "ADD_NODE", "FlexLayout_AddNode");
__publicField(_Actions, "MOVE_NODE", "FlexLayout_MoveNode");
__publicField(_Actions, "DELETE_TAB", "FlexLayout_DeleteTab");
__publicField(_Actions, "DELETE_TABSET", "FlexLayout_DeleteTabset");
__publicField(_Actions, "RENAME_TAB", "FlexLayout_RenameTab");
__publicField(_Actions, "SELECT_TAB", "FlexLayout_SelectTab");
__publicField(_Actions, "SET_ACTIVE_TABSET", "FlexLayout_SetActiveTabset");
__publicField(_Actions, "ADJUST_WEIGHTS", "FlexLayout_AdjustWeights");
__publicField(_Actions, "ADJUST_BORDER_SPLIT", "FlexLayout_AdjustBorderSplit");
__publicField(_Actions, "MAXIMIZE_TOGGLE", "FlexLayout_MaximizeToggle");
__publicField(_Actions, "UPDATE_MODEL_ATTRIBUTES", "FlexLayout_UpdateModelAttributes");
__publicField(_Actions, "UPDATE_NODE_ATTRIBUTES", "FlexLayout_UpdateNodeAttributes");
__publicField(_Actions, "POPOUT_TAB", "FlexLayout_PopoutTab");
__publicField(_Actions, "POPOUT_TABSET", "FlexLayout_PopoutTabset");
__publicField(_Actions, "CLOSE_WINDOW", "FlexLayout_CloseWindow");
__publicField(_Actions, "CREATE_WINDOW", "FlexLayout_CreateWindow");
let Actions = _Actions;
class Attribute {
  constructor(name, modelName, defaultValue, alwaysWriteJson) {
    __publicField(this, "name");
    __publicField(this, "alias");
    __publicField(this, "modelName");
    __publicField(this, "pairedAttr");
    __publicField(this, "pairedType");
    __publicField(this, "defaultValue");
    __publicField(this, "alwaysWriteJson");
    __publicField(this, "type");
    __publicField(this, "required");
    __publicField(this, "fixed");
    __publicField(this, "description");
    this.name = name;
    this.alias = void 0;
    this.modelName = modelName;
    this.defaultValue = defaultValue;
    this.alwaysWriteJson = alwaysWriteJson;
    this.required = false;
    this.fixed = false;
    this.type = "any";
  }
  setType(value) {
    this.type = value;
    return this;
  }
  setAlias(value) {
    this.alias = value;
    return this;
  }
  setDescription(value) {
    this.description = value;
  }
  setRequired() {
    this.required = true;
    return this;
  }
  setFixed() {
    this.fixed = true;
    return this;
  }
  // sets modelAttr for nodes, and nodeAttr for model
  setpairedAttr(value) {
    this.pairedAttr = value;
  }
  setPairedType(value) {
    this.pairedType = value;
  }
}
__publicField(Attribute, "NUMBER", "number");
__publicField(Attribute, "STRING", "string");
__publicField(Attribute, "BOOLEAN", "boolean");
class AttributeDefinitions {
  constructor() {
    __publicField(this, "attributes");
    __publicField(this, "nameToAttribute");
    this.attributes = [];
    this.nameToAttribute = /* @__PURE__ */ new Map();
  }
  addWithAll(name, modelName, defaultValue, alwaysWriteJson) {
    const attr = new Attribute(name, modelName, defaultValue, alwaysWriteJson);
    this.attributes.push(attr);
    this.nameToAttribute.set(name, attr);
    return attr;
  }
  addInherited(name, modelName) {
    return this.addWithAll(name, modelName, void 0, false);
  }
  add(name, defaultValue, alwaysWriteJson) {
    return this.addWithAll(name, void 0, defaultValue, alwaysWriteJson);
  }
  getAttributes() {
    return this.attributes;
  }
  getModelName(name) {
    const conversion = this.nameToAttribute.get(name);
    if (conversion !== void 0) {
      return conversion.modelName;
    }
    return void 0;
  }
  toJson(jsonObj, obj) {
    for (const attr of this.attributes) {
      const fromValue = obj[attr.name];
      if (attr.alwaysWriteJson || fromValue !== attr.defaultValue) {
        jsonObj[attr.name] = fromValue;
      }
    }
  }
  fromJson(jsonObj, obj) {
    for (const attr of this.attributes) {
      let fromValue = jsonObj[attr.name];
      if (fromValue === void 0 && attr.alias) {
        fromValue = jsonObj[attr.alias];
      }
      if (fromValue === void 0) {
        obj[attr.name] = attr.defaultValue;
      } else {
        obj[attr.name] = fromValue;
      }
    }
  }
  update(jsonObj, obj) {
    for (const attr of this.attributes) {
      if (Object.prototype.hasOwnProperty.call(jsonObj, attr.name)) {
        const fromValue = jsonObj[attr.name];
        if (fromValue === void 0) {
          delete obj[attr.name];
        } else {
          obj[attr.name] = fromValue;
        }
      }
    }
  }
  setDefaults(obj) {
    for (const attr of this.attributes) {
      obj[attr.name] = attr.defaultValue;
    }
  }
  pairAttributes(type, childAttributes) {
    for (const attr of childAttributes.attributes) {
      if (attr.modelName && this.nameToAttribute.has(attr.modelName)) {
        const pairedAttr = this.nameToAttribute.get(attr.modelName);
        pairedAttr.setpairedAttr(attr);
        attr.setpairedAttr(pairedAttr);
        pairedAttr.setPairedType(type);
      }
    }
  }
  toTypescriptInterface(name, parentAttributes) {
    var _a, _b;
    const lines = [];
    const sorted = this.attributes.sort((a, b) => a.name.localeCompare(b.name));
    lines.push("export interface I" + name + "Attributes {");
    for (let i = 0; i < sorted.length; i++) {
      const c = sorted[i];
      let type = c.type;
      let defaultValue = void 0;
      let attr = c;
      let inherited = void 0;
      if (attr.defaultValue !== void 0) {
        defaultValue = attr.defaultValue;
      } else if (attr.modelName !== void 0 && parentAttributes !== void 0 && parentAttributes.nameToAttribute.get(attr.modelName) !== void 0) {
        inherited = attr.modelName;
        attr = parentAttributes.nameToAttribute.get(inherited);
        defaultValue = attr.defaultValue;
        type = attr.type;
      }
      const defValue = JSON.stringify(defaultValue);
      const required = attr.required ? "" : "?";
      let sb = "	/**\n	  ";
      if (c.description) {
        sb += c.description;
      } else if (c.pairedType && ((_a = c.pairedAttr) == null ? void 0 : _a.description)) {
        sb += `Value for ${c.pairedType} attribute ${c.pairedAttr.name} if not overridden`;
        sb += "\n\n	  ";
        sb += (_b = c.pairedAttr) == null ? void 0 : _b.description;
      }
      sb += "\n\n	  ";
      if (c.fixed) {
        sb += `Fixed value: ${defValue}`;
      } else if (inherited) {
        sb += `Default: inherited from Global attribute ${c.modelName} (default ${defValue})`;
      } else {
        sb += `Default: ${defValue}`;
      }
      sb += "\n	 */";
      lines.push(sb);
      lines.push("	" + c.name + required + ": " + type + ";\n");
    }
    lines.push("}");
    return lines.join("\n");
  }
}
class DropInfo {
  constructor(node, rect, location, index, className) {
    __publicField(this, "node");
    __publicField(this, "rect");
    __publicField(this, "location");
    __publicField(this, "index");
    __publicField(this, "className");
    this.node = node;
    this.rect = rect;
    this.location = location;
    this.index = index;
    this.className = className;
  }
}
class BorderSet {
  /** @internal */
  constructor(_model) {
    /** @internal */
    __publicField(this, "borders");
    /** @internal */
    __publicField(this, "borderMap");
    /** @internal */
    __publicField(this, "layoutHorizontal");
    this.borders = [];
    this.borderMap = /* @__PURE__ */ new Map();
    this.layoutHorizontal = true;
  }
  /** @internal */
  static fromJson(json, model) {
    const borderSet = new BorderSet(model);
    borderSet.borders = json.map((borderJson) => BorderNode.fromJson(borderJson, model));
    for (const border of borderSet.borders) {
      borderSet.borderMap.set(border.getLocation(), border);
    }
    return borderSet;
  }
  toJson() {
    return this.borders.map((borderNode) => borderNode.toJson());
  }
  /** @internal */
  getLayoutHorizontal() {
    return this.layoutHorizontal;
  }
  /** @internal */
  getBorders() {
    return this.borders;
  }
  /** @internal */
  getBorderMap() {
    return this.borderMap;
  }
  /** @internal */
  forEachNode(fn) {
    for (const borderNode of this.borders) {
      fn(borderNode, 0);
      for (const node of borderNode.getChildren()) {
        node.forEachNode(fn, 1);
      }
    }
  }
  /** @internal */
  setPaths() {
    for (const borderNode of this.borders) {
      const path = "/border/" + borderNode.getLocation().getName();
      borderNode.setPath(path);
      let i = 0;
      for (const node of borderNode.getChildren()) {
        node.setPath(path + "/t" + i);
        i++;
      }
    }
  }
  /** @internal */
  findDropTargetNode(dragNode, x, y) {
    for (const border of this.borders) {
      if (border.isShowing()) {
        const dropInfo = border.canDrop(dragNode, x, y);
        if (dropInfo !== void 0) {
          return dropInfo;
        }
      }
    }
    return void 0;
  }
}
class Node {
  /** @internal */
  constructor(_model) {
    /** @internal */
    __publicField(this, "model");
    /** @internal */
    __publicField(this, "attributes");
    /** @internal */
    __publicField(this, "parent");
    /** @internal */
    __publicField(this, "children");
    /** @internal */
    __publicField(this, "rect");
    /** @internal */
    __publicField(this, "path");
    /** @internal */
    __publicField(this, "listeners");
    this.model = _model;
    this.attributes = {};
    this.children = [];
    this.rect = Rect.empty();
    this.listeners = /* @__PURE__ */ new Map();
    this.path = "";
  }
  getId() {
    let id = this.attributes.id;
    if (id !== void 0) {
      return id;
    }
    id = this.model.nextUniqueId();
    this.setId(id);
    return id;
  }
  getModel() {
    return this.model;
  }
  getType() {
    return this.attributes.type;
  }
  getParent() {
    return this.parent;
  }
  getChildren() {
    return this.children;
  }
  getRect() {
    return this.rect;
  }
  getPath() {
    return this.path;
  }
  getOrientation() {
    if (this.parent === void 0) {
      return this.model.isRootOrientationVertical() ? Orientation.VERT : Orientation.HORZ;
    } else {
      return Orientation.flip(this.parent.getOrientation());
    }
  }
  // event can be: resize, visibility, maximize (on tabset), close
  setEventListener(event, callback) {
    this.listeners.set(event, callback);
  }
  removeEventListener(event) {
    this.listeners.delete(event);
  }
  /** @internal */
  setId(id) {
    this.attributes.id = id;
  }
  /** @internal */
  fireEvent(event, params) {
    if (this.listeners.has(event)) {
      this.listeners.get(event)(params);
    }
  }
  /** @internal */
  getAttr(name) {
    let val = this.attributes[name];
    if (val === void 0) {
      const modelName = this.getAttributeDefinitions().getModelName(name);
      if (modelName !== void 0) {
        val = this.model.getAttribute(modelName);
      }
    }
    return val;
  }
  /** @internal */
  forEachNode(fn, level) {
    fn(this, level);
    level++;
    for (const node of this.children) {
      node.forEachNode(fn, level);
    }
  }
  /** @internal */
  setPaths(path) {
    let i = 0;
    for (const node of this.children) {
      let newPath = path;
      if (node.getType() === "row") {
        newPath += "/r" + i;
      } else if (node.getType() === "tabset") {
        newPath += "/ts" + i;
      } else if (node.getType() === "tab") {
        newPath += "/t" + i;
      }
      node.path = newPath;
      node.setPaths(newPath);
      i++;
    }
  }
  /** @internal */
  setParent(parent) {
    this.parent = parent;
  }
  /** @internal */
  setRect(rect) {
    this.rect = rect;
  }
  /** @internal */
  setPath(path) {
    this.path = path;
  }
  /** @internal */
  setWeight(weight) {
    this.attributes.weight = weight;
  }
  /** @internal */
  setSelected(index) {
    this.attributes.selected = index;
  }
  /** @internal */
  findDropTargetNode(windowId, dragNode, x, y) {
    let rtn;
    if (this.rect.contains(x, y)) {
      if (this.model.getMaximizedTabset(windowId) !== void 0) {
        rtn = this.model.getMaximizedTabset(windowId).canDrop(dragNode, x, y);
      } else {
        rtn = this.canDrop(dragNode, x, y);
        if (rtn === void 0) {
          if (this.children.length !== 0) {
            for (const child of this.children) {
              rtn = child.findDropTargetNode(windowId, dragNode, x, y);
              if (rtn !== void 0) {
                break;
              }
            }
          }
        }
      }
    }
    return rtn;
  }
  /** @internal */
  canDrop(dragNode, x, y) {
    return void 0;
  }
  /** @internal */
  canDockInto(dragNode, dropInfo) {
    if (dropInfo != null) {
      if (dropInfo.location === DockLocation.CENTER && dropInfo.node.isEnableDrop() === false) {
        return false;
      }
      if (dropInfo.location === DockLocation.CENTER && dragNode.getType() === "tabset" && dragNode.getName() !== void 0) {
        return false;
      }
      if (dropInfo.location !== DockLocation.CENTER && dropInfo.node.isEnableDivide() === false) {
        return false;
      }
      if (this.model.getOnAllowDrop()) {
        return this.model.getOnAllowDrop()(dragNode, dropInfo);
      }
    }
    return true;
  }
  /** @internal */
  removeChild(childNode) {
    const pos = this.children.indexOf(childNode);
    if (pos !== -1) {
      this.children.splice(pos, 1);
    }
    return pos;
  }
  /** @internal */
  addChild(childNode, pos) {
    if (pos != null) {
      this.children.splice(pos, 0, childNode);
    } else {
      this.children.push(childNode);
      pos = this.children.length - 1;
    }
    childNode.parent = this;
    return pos;
  }
  /** @internal */
  removeAll() {
    this.children = [];
  }
  /** @internal */
  styleWithPosition(style2) {
    if (style2 == null) {
      style2 = {};
    }
    return this.rect.styleWithPosition(style2);
  }
  /** @internal */
  isEnableDivide() {
    return true;
  }
  /** @internal */
  toAttributeString() {
    return JSON.stringify(this.attributes, void 0, "	");
  }
}
const _TabNode = class _TabNode extends Node {
  /** @internal */
  constructor(model, json, addToModel = true) {
    super(model);
    /** @internal */
    __publicField(this, "tabRect", Rect.empty());
    /** @internal */
    __publicField(this, "moveableElement");
    /** @internal */
    __publicField(this, "tabStamp");
    /** @internal */
    __publicField(this, "renderedName");
    /** @internal */
    __publicField(this, "extra");
    /** @internal */
    __publicField(this, "visible");
    /** @internal */
    __publicField(this, "rendered");
    /** @internal */
    __publicField(this, "scrollTop");
    /** @internal */
    __publicField(this, "scrollLeft");
    this.extra = {};
    this.moveableElement = null;
    this.tabStamp = null;
    this.rendered = false;
    this.visible = false;
    _TabNode.attributeDefinitions.fromJson(json, this.attributes);
    if (addToModel === true) {
      model.addNode(this);
    }
  }
  /** @internal */
  static fromJson(json, model, addToModel = true) {
    const newLayoutNode = new _TabNode(model, json, addToModel);
    return newLayoutNode;
  }
  getName() {
    return this.getAttr("name");
  }
  getHelpText() {
    return this.getAttr("helpText");
  }
  getComponent() {
    return this.getAttr("component");
  }
  getWindowId() {
    if (this.parent instanceof TabSetNode) {
      return this.parent.getWindowId();
    }
    return Model.MAIN_WINDOW_ID;
  }
  getWindow() {
    const layoutWindow = this.model.getwindowsMap().get(this.getWindowId());
    if (layoutWindow) {
      return layoutWindow.window;
    }
    return void 0;
  }
  /**
   * Returns the config attribute that can be used to store node specific data that
   * WILL be saved to the json. The config attribute should be changed via the action Actions.updateNodeAttributes rather
   * than directly, for example:
   * this.state.model.doAction(
   *   FlexLayout.Actions.updateNodeAttributes(node.getId(), {config:myConfigObject}));
   */
  getConfig() {
    return this.attributes.config;
  }
  /**
   * Returns an object that can be used to store transient node specific data that will
   * NOT be saved in the json.
   */
  getExtraData() {
    return this.extra;
  }
  isPoppedOut() {
    return this.getWindowId() !== Model.MAIN_WINDOW_ID;
  }
  isSelected() {
    return this.getParent().getSelectedNode() === this;
  }
  getIcon() {
    return this.getAttr("icon");
  }
  isEnableClose() {
    return this.getAttr("enableClose");
  }
  getCloseType() {
    return this.getAttr("closeType");
  }
  isEnablePopout() {
    return this.getAttr("enablePopout");
  }
  isEnablePopoutIcon() {
    return this.getAttr("enablePopoutIcon");
  }
  isEnablePopoutOverlay() {
    return this.getAttr("enablePopoutOverlay");
  }
  isEnableDrag() {
    return this.getAttr("enableDrag");
  }
  isEnableRename() {
    return this.getAttr("enableRename");
  }
  isEnableWindowReMount() {
    return this.getAttr("enableWindowReMount");
  }
  getClassName() {
    return this.getAttr("className");
  }
  getContentClassName() {
    return this.getAttr("contentClassName");
  }
  getTabSetClassName() {
    return this.getAttr("tabsetClassName");
  }
  isEnableRenderOnDemand() {
    return this.getAttr("enableRenderOnDemand");
  }
  getMinWidth() {
    return this.getAttr("minWidth");
  }
  getMinHeight() {
    return this.getAttr("minHeight");
  }
  getMaxWidth() {
    return this.getAttr("maxWidth");
  }
  getMaxHeight() {
    return this.getAttr("maxHeight");
  }
  isVisible() {
    return this.visible;
  }
  toJson() {
    const json = {};
    _TabNode.attributeDefinitions.toJson(json, this.attributes);
    return json;
  }
  /** @internal */
  saveScrollPosition() {
    if (this.moveableElement) {
      this.scrollLeft = this.moveableElement.scrollLeft;
      this.scrollTop = this.moveableElement.scrollTop;
    }
  }
  /** @internal */
  restoreScrollPosition() {
    if (this.scrollTop) {
      requestAnimationFrame(() => {
        if (this.moveableElement) {
          if (this.scrollTop) {
            this.moveableElement.scrollTop = this.scrollTop;
            this.moveableElement.scrollLeft = this.scrollLeft;
          }
        }
      });
    }
  }
  /** @internal */
  setRect(rect) {
    if (!rect.equals(this.rect)) {
      this.fireEvent("resize", { rect });
      this.rect = rect;
    }
  }
  /** @internal */
  setVisible(visible) {
    if (visible !== this.visible) {
      this.visible = visible;
      this.fireEvent("visibility", { visible });
    }
  }
  /** @internal */
  getScrollTop() {
    return this.scrollTop;
  }
  /** @internal */
  setScrollTop(scrollTop) {
    this.scrollTop = scrollTop;
  }
  /** @internal */
  getScrollLeft() {
    return this.scrollLeft;
  }
  /** @internal */
  setScrollLeft(scrollLeft) {
    this.scrollLeft = scrollLeft;
  }
  /** @internal */
  isRendered() {
    return this.rendered;
  }
  /** @internal */
  setRendered(rendered) {
    this.rendered = rendered;
  }
  /** @internal */
  getTabRect() {
    return this.tabRect;
  }
  /** @internal */
  setTabRect(rect) {
    this.tabRect = rect;
  }
  /** @internal */
  getTabStamp() {
    return this.tabStamp;
  }
  /** @internal */
  setTabStamp(stamp) {
    this.tabStamp = stamp;
  }
  /** @internal */
  getMoveableElement() {
    return this.moveableElement;
  }
  /** @internal */
  setMoveableElement(element) {
    this.moveableElement = element;
  }
  /** @internal */
  setRenderedName(name) {
    this.renderedName = name;
  }
  /** @internal */
  getNameForOverflowMenu() {
    const altName = this.getAttr("altName");
    if (altName !== void 0) {
      return altName;
    }
    return this.renderedName;
  }
  /** @internal */
  setName(name) {
    this.attributes.name = name;
  }
  /** @internal */
  delete() {
    this.parent.remove(this);
    this.fireEvent("close", {});
  }
  /** @internal */
  updateAttrs(json) {
    _TabNode.attributeDefinitions.update(json, this.attributes);
  }
  /** @internal */
  getAttributeDefinitions() {
    return _TabNode.attributeDefinitions;
  }
  /** @internal */
  setBorderWidth(width) {
    this.attributes.borderWidth = width;
  }
  /** @internal */
  setBorderHeight(height) {
    this.attributes.borderHeight = height;
  }
  /** @internal */
  static getAttributeDefinitions() {
    return _TabNode.attributeDefinitions;
  }
  /** @internal */
  static createAttributeDefinitions() {
    const attributeDefinitions = new AttributeDefinitions();
    attributeDefinitions.add("type", _TabNode.TYPE, true).setType(Attribute.STRING).setFixed();
    attributeDefinitions.add("id", void 0).setType(Attribute.STRING).setDescription(
      `the unique id of the tab, if left undefined a uuid will be assigned`
    );
    attributeDefinitions.add("name", "[Unnamed Tab]").setType(Attribute.STRING).setDescription(
      `name of tab to be displayed in the tab button`
    );
    attributeDefinitions.add("altName", void 0).setType(Attribute.STRING).setDescription(
      `if there is no name specifed then this value will be used in the overflow menu`
    );
    attributeDefinitions.add("helpText", void 0).setType(Attribute.STRING).setDescription(
      `An optional help text for the tab to be displayed upon tab hover.`
    );
    attributeDefinitions.add("component", void 0).setType(Attribute.STRING).setDescription(
      `string identifying which component to run (for factory)`
    );
    attributeDefinitions.add("config", void 0).setType("any").setDescription(
      `a place to hold json config for the hosted component`
    );
    attributeDefinitions.add("tabsetClassName", void 0).setType(Attribute.STRING).setDescription(
      `class applied to parent tabset when this is the only tab and it is stretched to fill the tabset`
    );
    attributeDefinitions.add("enableWindowReMount", false).setType(Attribute.BOOLEAN).setDescription(
      `if enabled the tab will re-mount when popped out/in`
    );
    attributeDefinitions.addInherited("enableClose", "tabEnableClose").setType(Attribute.BOOLEAN).setDescription(
      `allow user to close tab via close button`
    );
    attributeDefinitions.addInherited("closeType", "tabCloseType").setType("ICloseType").setDescription(
      `see values in ICloseType`
    );
    attributeDefinitions.addInherited("enableDrag", "tabEnableDrag").setType(Attribute.BOOLEAN).setDescription(
      `allow user to drag tab to new location`
    );
    attributeDefinitions.addInherited("enableRename", "tabEnableRename").setType(Attribute.BOOLEAN).setDescription(
      `allow user to rename tabs by double clicking`
    );
    attributeDefinitions.addInherited("className", "tabClassName").setType(Attribute.STRING).setDescription(
      `class applied to tab button`
    );
    attributeDefinitions.addInherited("contentClassName", "tabContentClassName").setType(Attribute.STRING).setDescription(
      `class applied to tab content`
    );
    attributeDefinitions.addInherited("icon", "tabIcon").setType(Attribute.STRING).setDescription(
      `the tab icon`
    );
    attributeDefinitions.addInherited("enableRenderOnDemand", "tabEnableRenderOnDemand").setType(Attribute.BOOLEAN).setDescription(
      `whether to avoid rendering component until tab is visible`
    );
    attributeDefinitions.addInherited("enablePopout", "tabEnablePopout").setType(Attribute.BOOLEAN).setAlias("enableFloat").setDescription(
      `enable popout (in popout capable browser)`
    );
    attributeDefinitions.addInherited("enablePopoutIcon", "tabEnablePopoutIcon").setType(Attribute.BOOLEAN).setDescription(
      `whether to show the popout icon in the tabset header if this tab enables popouts`
    );
    attributeDefinitions.addInherited("enablePopoutOverlay", "tabEnablePopoutOverlay").setType(Attribute.BOOLEAN).setDescription(
      `if this tab will not work correctly in a popout window when the main window is backgrounded (inactive)
            then enabling this option will gray out this tab`
    );
    attributeDefinitions.addInherited("borderWidth", "tabBorderWidth").setType(Attribute.NUMBER).setDescription(
      `width when added to border, -1 will use border size`
    );
    attributeDefinitions.addInherited("borderHeight", "tabBorderHeight").setType(Attribute.NUMBER).setDescription(
      `height when added to border, -1 will use border size`
    );
    attributeDefinitions.addInherited("minWidth", "tabMinWidth").setType(Attribute.NUMBER).setDescription(
      `the min width of this tab`
    );
    attributeDefinitions.addInherited("minHeight", "tabMinHeight").setType(Attribute.NUMBER).setDescription(
      `the min height of this tab`
    );
    attributeDefinitions.addInherited("maxWidth", "tabMaxWidth").setType(Attribute.NUMBER).setDescription(
      `the max width of this tab`
    );
    attributeDefinitions.addInherited("maxHeight", "tabMaxHeight").setType(Attribute.NUMBER).setDescription(
      `the max height of this tab`
    );
    return attributeDefinitions;
  }
};
__publicField(_TabNode, "TYPE", "tab");
/** @internal */
__publicField(_TabNode, "attributeDefinitions", _TabNode.createAttributeDefinitions());
let TabNode = _TabNode;
function isDesktop() {
  const desktop = typeof window !== "undefined" && window.matchMedia && window.matchMedia("(hover: hover) and (pointer: fine)").matches;
  return desktop;
}
function getRenderStateEx(layout, node, iconAngle) {
  let leadingContent = void 0;
  const titleContent = node.getName();
  const name = node.getName();
  if (iconAngle === void 0) {
    iconAngle = 0;
  }
  if (leadingContent === void 0 && node.getIcon() !== void 0) {
    if (iconAngle !== 0) {
      leadingContent = /* @__PURE__ */ jsx("img", { style: { width: "1em", height: "1em", transform: "rotate(" + iconAngle + "deg)" }, src: node.getIcon(), alt: "leadingContent" });
    } else {
      leadingContent = /* @__PURE__ */ jsx("img", { style: { width: "1em", height: "1em" }, src: node.getIcon(), alt: "leadingContent" });
    }
  }
  const buttons = [];
  const renderState = { leading: leadingContent, content: titleContent, name, buttons };
  layout.customizeTab(node, renderState);
  node.setRenderedName(renderState.name);
  return renderState;
}
function isAuxMouseEvent(event) {
  let auxEvent = false;
  if (event.nativeEvent instanceof MouseEvent) {
    if (event.nativeEvent.button !== 0 || event.ctrlKey || event.altKey || event.metaKey || event.shiftKey) {
      auxEvent = true;
    }
  }
  return auxEvent;
}
function enablePointerOnIFrames(enable, currentDocument) {
  const iframes = [
    ...getElementsByTagName("iframe", currentDocument),
    ...getElementsByTagName("webview", currentDocument)
  ];
  for (const iframe of iframes) {
    iframe.style.pointerEvents = enable ? "auto" : "none";
  }
}
function getElementsByTagName(tag, currentDocument) {
  return [...currentDocument.getElementsByTagName(tag)];
}
function startDrag(doc, event, drag, dragEnd, dragCancel) {
  event.preventDefault();
  const pointerMove = (ev) => {
    ev.preventDefault();
    drag(ev.clientX, ev.clientY);
  };
  const pointerCancel = (ev) => {
    ev.preventDefault();
    dragCancel();
  };
  const pointerUp = () => {
    doc.removeEventListener("pointermove", pointerMove);
    doc.removeEventListener("pointerup", pointerUp);
    doc.removeEventListener("pointercancel", pointerCancel);
    dragEnd();
  };
  doc.addEventListener("pointermove", pointerMove);
  doc.addEventListener("pointerup", pointerUp);
  doc.addEventListener("pointercancel", pointerCancel);
}
function canDockToWindow(node) {
  if (node instanceof TabNode) {
    return node.isEnablePopout();
  } else if (node instanceof TabSetNode) {
    for (const child of node.getChildren()) {
      if (child.isEnablePopout() === false) {
        return false;
      }
    }
    return true;
  }
  return false;
}
function copyInlineStyles(source, target) {
  const sourceStyle = source.getAttribute("style");
  const targetStyle = target.getAttribute("style");
  if (sourceStyle === targetStyle) return false;
  if (sourceStyle) {
    target.setAttribute("style", sourceStyle);
  } else {
    target.removeAttribute("style");
  }
  return true;
}
function isSafari() {
  const userAgent = navigator.userAgent;
  return userAgent.includes("Safari") && !userAgent.includes("Chrome") && !userAgent.includes("Chromium");
}
function adjustSelectedIndex(parent, removedIndex) {
  if (parent !== void 0 && (parent instanceof TabSetNode || parent instanceof BorderNode)) {
    const selectedIndex = parent.getSelected();
    if (selectedIndex !== -1) {
      if (removedIndex === selectedIndex && parent.getChildren().length > 0) {
        if (removedIndex >= parent.getChildren().length) {
          parent.setSelected(parent.getChildren().length - 1);
        }
      } else if (removedIndex < selectedIndex) {
        parent.setSelected(selectedIndex - 1);
      } else if (removedIndex > selectedIndex) ;
      else {
        parent.setSelected(-1);
      }
    }
  }
}
function randomUUID() {
  return ("10000000-1000-4000-8000" + -1e11).replace(
    /[018]/g,
    (c) => (c ^ crypto.getRandomValues(new Uint8Array(1))[0] & 15 >> c / 4).toString(16)
  );
}
const _TabSetNode = class _TabSetNode extends Node {
  /** @internal */
  constructor(model, json) {
    super(model);
    /** @internal */
    __publicField(this, "tabStripRect", Rect.empty());
    /** @internal */
    __publicField(this, "contentRect", Rect.empty());
    /** @internal */
    __publicField(this, "calculatedMinHeight");
    /** @internal */
    __publicField(this, "calculatedMinWidth");
    /** @internal */
    __publicField(this, "calculatedMaxHeight");
    /** @internal */
    __publicField(this, "calculatedMaxWidth");
    this.calculatedMinHeight = 0;
    this.calculatedMinWidth = 0;
    this.calculatedMaxHeight = 0;
    this.calculatedMaxWidth = 0;
    _TabSetNode.attributeDefinitions.fromJson(json, this.attributes);
    model.addNode(this);
  }
  /** @internal */
  static fromJson(json, model, layoutWindow) {
    const newLayoutNode = new _TabSetNode(model, json);
    if (json.children != null) {
      for (const jsonChild of json.children) {
        const child = TabNode.fromJson(jsonChild, model);
        newLayoutNode.addChild(child);
      }
    }
    if (newLayoutNode.children.length === 0) {
      newLayoutNode.setSelected(-1);
    }
    if (json.maximized && json.maximized === true) {
      layoutWindow.maximizedTabSet = newLayoutNode;
    }
    if (json.active && json.active === true) {
      layoutWindow.activeTabSet = newLayoutNode;
    }
    return newLayoutNode;
  }
  getName() {
    return this.getAttr("name");
  }
  isEnableActiveIcon() {
    return this.getAttr("enableActiveIcon");
  }
  getSelected() {
    const selected = this.attributes.selected;
    if (selected !== void 0) {
      return selected;
    }
    return -1;
  }
  getSelectedNode() {
    const selected = this.getSelected();
    if (selected !== -1) {
      return this.children[selected];
    }
    return void 0;
  }
  getWeight() {
    return this.getAttr("weight");
  }
  getAttrMinWidth() {
    return this.getAttr("minWidth");
  }
  getAttrMinHeight() {
    return this.getAttr("minHeight");
  }
  getMinWidth() {
    return this.calculatedMinWidth;
  }
  getMinHeight() {
    return this.calculatedMinHeight;
  }
  /** @internal */
  getMinSize(orientation) {
    if (orientation === Orientation.HORZ) {
      return this.getMinWidth();
    } else {
      return this.getMinHeight();
    }
  }
  getAttrMaxWidth() {
    return this.getAttr("maxWidth");
  }
  getAttrMaxHeight() {
    return this.getAttr("maxHeight");
  }
  getMaxWidth() {
    return this.calculatedMaxWidth;
  }
  getMaxHeight() {
    return this.calculatedMaxHeight;
  }
  /** @internal */
  getMaxSize(orientation) {
    if (orientation === Orientation.HORZ) {
      return this.getMaxWidth();
    } else {
      return this.getMaxHeight();
    }
  }
  /**
   * Returns the config attribute that can be used to store node specific data that
   * WILL be saved to the json. The config attribute should be changed via the action Actions.updateNodeAttributes rather
   * than directly, for example:
   * this.state.model.doAction(
   *   FlexLayout.Actions.updateNodeAttributes(node.getId(), {config:myConfigObject}));
   */
  getConfig() {
    return this.attributes.config;
  }
  isMaximized() {
    return this.model.getMaximizedTabset(this.getWindowId()) === this;
  }
  isActive() {
    return this.model.getActiveTabset(this.getWindowId()) === this;
  }
  isEnableDeleteWhenEmpty() {
    return this.getAttr("enableDeleteWhenEmpty");
  }
  isEnableDrop() {
    return this.getAttr("enableDrop");
  }
  isEnableTabWrap() {
    return this.getAttr("enableTabWrap");
  }
  isEnableDrag() {
    return this.getAttr("enableDrag");
  }
  isEnableDivide() {
    return this.getAttr("enableDivide");
  }
  isEnableMaximize() {
    return this.getAttr("enableMaximize");
  }
  isEnableClose() {
    return this.getAttr("enableClose");
  }
  isEnableSingleTabStretch() {
    return this.getAttr("enableSingleTabStretch");
  }
  isEnableTabStrip() {
    return this.getAttr("enableTabStrip");
  }
  isAutoSelectTab() {
    return this.getAttr("autoSelectTab");
  }
  isEnableTabScrollbar() {
    return this.getAttr("enableTabScrollbar");
  }
  getClassNameTabStrip() {
    return this.getAttr("classNameTabStrip");
  }
  getTabLocation() {
    return this.getAttr("tabLocation");
  }
  toJson() {
    const json = {};
    _TabSetNode.attributeDefinitions.toJson(json, this.attributes);
    json.children = this.children.map((child) => child.toJson());
    if (this.isActive()) {
      json.active = true;
    }
    if (this.isMaximized()) {
      json.maximized = true;
    }
    return json;
  }
  /** @internal */
  calcMinMaxSize() {
    this.calculatedMinHeight = this.getAttrMinHeight();
    this.calculatedMinWidth = this.getAttrMinWidth();
    this.calculatedMaxHeight = this.getAttrMaxHeight();
    this.calculatedMaxWidth = this.getAttrMaxWidth();
    for (const child of this.children) {
      const c = child;
      this.calculatedMinWidth = Math.max(this.calculatedMinWidth, c.getMinWidth());
      this.calculatedMinHeight = Math.max(this.calculatedMinHeight, c.getMinHeight());
      this.calculatedMaxWidth = Math.min(this.calculatedMaxWidth, c.getMaxWidth());
      this.calculatedMaxHeight = Math.min(this.calculatedMaxHeight, c.getMaxHeight());
    }
    this.calculatedMinHeight += this.tabStripRect.height;
    this.calculatedMaxHeight += this.tabStripRect.height;
  }
  /** @internal */
  canMaximize() {
    if (this.isEnableMaximize()) {
      if (this.getModel().getMaximizedTabset(this.getWindowId()) === this) {
        return true;
      }
      if (this.getParent() === this.getModel().getRoot(this.getWindowId()) && this.getModel().getRoot(this.getWindowId()).getChildren().length === 1) {
        return false;
      }
      return true;
    }
    return false;
  }
  /** @internal */
  setContentRect(rect) {
    this.contentRect = rect;
  }
  /** @internal */
  getContentRect() {
    return this.contentRect;
  }
  /** @internal */
  setTabStripRect(rect) {
    this.tabStripRect = rect;
  }
  /** @internal */
  setWeight(weight) {
    this.attributes.weight = weight;
  }
  /** @internal */
  setSelected(index) {
    this.attributes.selected = index;
  }
  getWindowId() {
    return this.parent.getWindowId();
  }
  /** @internal */
  canDrop(dragNode, x, y) {
    let dropInfo;
    if (dragNode === this) {
      const dockLocation = DockLocation.CENTER;
      const outlineRect = this.tabStripRect;
      dropInfo = new DropInfo(this, outlineRect, dockLocation, -1, CLASSES.FLEXLAYOUT__OUTLINE_RECT);
    } else if (this.getWindowId() !== Model.MAIN_WINDOW_ID && !canDockToWindow(dragNode)) {
      return void 0;
    } else if (this.contentRect.contains(x, y)) {
      let dockLocation = DockLocation.CENTER;
      if (this.model.getMaximizedTabset(this.parent.getWindowId()) === void 0) {
        dockLocation = DockLocation.getLocation(this.contentRect, x, y);
      }
      const outlineRect = dockLocation.getDockRect(this.rect);
      dropInfo = new DropInfo(this, outlineRect, dockLocation, -1, CLASSES.FLEXLAYOUT__OUTLINE_RECT);
    } else if (this.tabStripRect != null && this.tabStripRect.contains(x, y)) {
      let r;
      let yy;
      let h;
      if (this.children.length === 0) {
        r = this.tabStripRect.clone();
        yy = r.y + 3;
        h = r.height - 4;
        r.width = 2;
      } else {
        let child = this.children[0];
        r = child.getTabRect();
        yy = r.y;
        h = r.height;
        let p = this.tabStripRect.x;
        let childCenter = 0;
        for (let i = 0; i < this.children.length; i++) {
          child = this.children[i];
          r = child.getTabRect();
          if (r.y !== yy) {
            yy = r.y;
            p = this.tabStripRect.x;
          }
          childCenter = r.x + r.width / 2;
          if (p <= x && x < childCenter && r.y < y && y < r.getBottom()) {
            const dockLocation = DockLocation.CENTER;
            const outlineRect = new Rect(r.x - 2, r.y, 3, r.height);
            if (this.rect.x < r.x && r.x < this.rect.getRight()) {
              dropInfo = new DropInfo(this, outlineRect, dockLocation, i, CLASSES.FLEXLAYOUT__OUTLINE_RECT);
              break;
            } else {
              return void 0;
            }
          }
          p = childCenter;
        }
      }
      if (dropInfo == null && r.getRight() < this.rect.getRight()) {
        const dockLocation = DockLocation.CENTER;
        const outlineRect = new Rect(r.getRight() - 2, yy, 3, h);
        dropInfo = new DropInfo(this, outlineRect, dockLocation, this.children.length, CLASSES.FLEXLAYOUT__OUTLINE_RECT);
      }
    }
    if (!dragNode.canDockInto(dragNode, dropInfo)) {
      return void 0;
    }
    return dropInfo;
  }
  /** @internal */
  delete() {
    this.parent.removeChild(this);
  }
  /** @internal */
  remove(node) {
    const removedIndex = this.removeChild(node);
    this.model.tidy();
    adjustSelectedIndex(this, removedIndex);
  }
  /** @internal */
  drop(dragNode, location, index, select) {
    const dockLocation = location;
    if (this === dragNode) {
      return;
    }
    let dragParent = dragNode.getParent();
    let fromIndex = 0;
    if (dragParent !== void 0) {
      fromIndex = dragParent.removeChild(dragNode);
      if (dragParent instanceof BorderNode && dragParent.getSelected() === fromIndex) {
        dragParent.setSelected(-1);
      } else {
        adjustSelectedIndex(dragParent, fromIndex);
      }
    }
    if (dragNode instanceof TabNode && dragParent === this && fromIndex < index && index > 0) {
      index--;
    }
    if (dockLocation === DockLocation.CENTER) {
      let insertPos = index;
      if (insertPos === -1) {
        insertPos = this.children.length;
      }
      if (dragNode instanceof TabNode) {
        this.addChild(dragNode, insertPos);
        if (select || select !== false && this.isAutoSelectTab()) {
          this.setSelected(insertPos);
        }
      } else if (dragNode instanceof RowNode) {
        dragNode.forEachNode((child, level) => {
          if (child instanceof TabNode) {
            this.addChild(child, insertPos);
            insertPos++;
          }
        }, 0);
      } else {
        for (let i = 0; i < dragNode.getChildren().length; i++) {
          const child = dragNode.getChildren()[i];
          this.addChild(child, insertPos);
          insertPos++;
        }
        if (this.getSelected() === -1 && this.children.length > 0) {
          this.setSelected(0);
        }
      }
      this.model.setActiveTabset(this, this.parent.getWindowId());
    } else {
      let moveNode = dragNode;
      if (dragNode instanceof TabNode) {
        const callback = this.model.getOnCreateTabSet();
        moveNode = new _TabSetNode(this.model, callback ? callback(dragNode) : {});
        moveNode.addChild(dragNode);
        dragParent = moveNode;
      } else if (dragNode instanceof RowNode) {
        const parent = this.getParent();
        if (dragNode.getOrientation() === parent.getOrientation() && (location.getOrientation() === parent.getOrientation() || location === DockLocation.CENTER)) {
          const node = new RowNode(this.model, this.getWindowId(), {});
          node.addChild(dragNode);
          moveNode = node;
        }
      } else {
        moveNode = dragNode;
      }
      const parentRow = this.parent;
      const pos = parentRow.getChildren().indexOf(this);
      if (parentRow.getOrientation() === dockLocation.orientation) {
        moveNode.setWeight(this.getWeight() / 2);
        this.setWeight(this.getWeight() / 2);
        parentRow.addChild(moveNode, pos + dockLocation.indexPlus);
      } else {
        const newRow = new RowNode(this.model, this.getWindowId(), {});
        newRow.setWeight(this.getWeight());
        newRow.addChild(this);
        this.setWeight(50);
        moveNode.setWeight(50);
        newRow.addChild(moveNode, dockLocation.indexPlus);
        parentRow.removeChild(this);
        parentRow.addChild(newRow, pos);
      }
      if (moveNode instanceof _TabSetNode) {
        this.model.setActiveTabset(moveNode, this.getWindowId());
      }
    }
    this.model.tidy();
  }
  /** @internal */
  updateAttrs(json) {
    _TabSetNode.attributeDefinitions.update(json, this.attributes);
  }
  /** @internal */
  getAttributeDefinitions() {
    return _TabSetNode.attributeDefinitions;
  }
  /** @internal */
  static getAttributeDefinitions() {
    return _TabSetNode.attributeDefinitions;
  }
  /** @internal */
  static createAttributeDefinitions() {
    const attributeDefinitions = new AttributeDefinitions();
    attributeDefinitions.add("type", _TabSetNode.TYPE, true).setType(Attribute.STRING).setFixed();
    attributeDefinitions.add("id", void 0).setType(Attribute.STRING).setDescription(
      `the unique id of the tab set, if left undefined a uuid will be assigned`
    );
    attributeDefinitions.add("weight", 100).setType(Attribute.NUMBER).setDescription(
      `relative weight for sizing of this tabset in parent row`
    );
    attributeDefinitions.add("selected", 0).setType(Attribute.NUMBER).setDescription(
      `index of selected/visible tab in tabset`
    );
    attributeDefinitions.add("name", void 0).setType(Attribute.STRING);
    attributeDefinitions.add("config", void 0).setType("any").setDescription(
      `a place to hold json config used in your own code`
    );
    attributeDefinitions.addInherited("enableDeleteWhenEmpty", "tabSetEnableDeleteWhenEmpty").setDescription(
      `whether to delete this tabset when is has no tabs`
    );
    attributeDefinitions.addInherited("enableDrop", "tabSetEnableDrop").setDescription(
      `allow user to drag tabs into this tabset`
    );
    attributeDefinitions.addInherited("enableDrag", "tabSetEnableDrag").setDescription(
      `allow user to drag tabs out this tabset`
    );
    attributeDefinitions.addInherited("enableDivide", "tabSetEnableDivide").setDescription(
      `allow user to drag tabs to region of this tabset, splitting into new tabset`
    );
    attributeDefinitions.addInherited("enableMaximize", "tabSetEnableMaximize").setDescription(
      `allow user to maximize tabset to fill view via maximize button`
    );
    attributeDefinitions.addInherited("enableClose", "tabSetEnableClose").setDescription(
      `allow user to close tabset via a close button`
    );
    attributeDefinitions.addInherited("enableSingleTabStretch", "tabSetEnableSingleTabStretch").setDescription(
      `if the tabset has only a single tab then stretch the single tab to fill area and display in a header style`
    );
    attributeDefinitions.addInherited("classNameTabStrip", "tabSetClassNameTabStrip").setDescription(
      `a class name to apply to the tab strip`
    );
    attributeDefinitions.addInherited("enableTabStrip", "tabSetEnableTabStrip").setDescription(
      `enable tab strip and allow multiple tabs in this tabset`
    );
    attributeDefinitions.addInherited("minWidth", "tabSetMinWidth").setDescription(
      `minimum width (in px) for this tabset`
    );
    attributeDefinitions.addInherited("minHeight", "tabSetMinHeight").setDescription(
      `minimum height (in px) for this tabset`
    );
    attributeDefinitions.addInherited("maxWidth", "tabSetMaxWidth").setDescription(
      `maximum width (in px) for this tabset`
    );
    attributeDefinitions.addInherited("maxHeight", "tabSetMaxHeight").setDescription(
      `maximum height (in px) for this tabset`
    );
    attributeDefinitions.addInherited("enableTabWrap", "tabSetEnableTabWrap").setDescription(
      `wrap tabs onto multiple lines`
    );
    attributeDefinitions.addInherited("tabLocation", "tabSetTabLocation").setDescription(
      `the location of the tabs either top or bottom`
    );
    attributeDefinitions.addInherited("autoSelectTab", "tabSetAutoSelectTab").setType(Attribute.BOOLEAN).setDescription(
      `whether to select new/moved tabs in tabset`
    );
    attributeDefinitions.addInherited("enableActiveIcon", "tabSetEnableActiveIcon").setType(Attribute.BOOLEAN).setDescription(
      `whether the active icon (*) should be displayed when the tabset is active`
    );
    attributeDefinitions.addInherited("enableTabScrollbar", "tabSetEnableTabScrollbar").setType(Attribute.BOOLEAN).setDescription(
      `whether to show a mini scrollbar for the tabs`
    );
    return attributeDefinitions;
  }
};
__publicField(_TabSetNode, "TYPE", "tabset");
/** @internal */
__publicField(_TabSetNode, "attributeDefinitions", _TabSetNode.createAttributeDefinitions());
let TabSetNode = _TabSetNode;
const _RowNode = class _RowNode extends Node {
  /** @internal */
  constructor(model, windowId, json) {
    super(model);
    /** @internal */
    __publicField(this, "windowId");
    /** @internal */
    __publicField(this, "minHeight");
    /** @internal */
    __publicField(this, "minWidth");
    /** @internal */
    __publicField(this, "maxHeight");
    /** @internal */
    __publicField(this, "maxWidth");
    this.windowId = windowId;
    this.minHeight = DefaultMin;
    this.minWidth = DefaultMin;
    this.maxHeight = DefaultMax;
    this.maxWidth = DefaultMax;
    _RowNode.attributeDefinitions.fromJson(json, this.attributes);
    this.normalizeWeights();
    model.addNode(this);
  }
  /** @internal */
  static fromJson(json, model, layoutWindow) {
    const newLayoutNode = new _RowNode(model, layoutWindow.windowId, json);
    if (json.children != null) {
      for (const jsonChild of json.children) {
        if (jsonChild.type === TabSetNode.TYPE) {
          const child = TabSetNode.fromJson(jsonChild, model, layoutWindow);
          newLayoutNode.addChild(child);
        } else {
          const child = _RowNode.fromJson(jsonChild, model, layoutWindow);
          newLayoutNode.addChild(child);
        }
      }
    }
    return newLayoutNode;
  }
  getWeight() {
    return this.attributes.weight;
  }
  toJson() {
    const json = {};
    _RowNode.attributeDefinitions.toJson(json, this.attributes);
    json.children = [];
    for (const child of this.children) {
      json.children.push(child.toJson());
    }
    return json;
  }
  /** @internal */
  getWindowId() {
    return this.windowId;
  }
  setWindowId(windowId) {
    this.windowId = windowId;
  }
  /** @internal */
  setWeight(weight) {
    this.attributes.weight = weight;
  }
  /** @internal */
  getSplitterBounds(index) {
    const h = this.getOrientation() === Orientation.HORZ;
    const c = this.getChildren();
    const ss = this.model.getSplitterSize();
    const fr = c[0].getRect();
    const lr = c[c.length - 1].getRect();
    let p = h ? [fr.x, lr.getRight()] : [fr.y, lr.getBottom()];
    const q = h ? [fr.x, lr.getRight()] : [fr.y, lr.getBottom()];
    for (let i = 0; i < index; i++) {
      const n = c[i];
      p[0] += h ? n.getMinWidth() : n.getMinHeight();
      q[0] += h ? n.getMaxWidth() : n.getMaxHeight();
      if (i > 0) {
        p[0] += ss;
        q[0] += ss;
      }
    }
    for (let i = c.length - 1; i >= index; i--) {
      const n = c[i];
      p[1] -= (h ? n.getMinWidth() : n.getMinHeight()) + ss;
      q[1] -= (h ? n.getMaxWidth() : n.getMaxHeight()) + ss;
    }
    p = [Math.max(q[1], p[0]), Math.min(q[0], p[1])];
    return p;
  }
  /** @internal */
  getSplitterInitials(index) {
    const h = this.getOrientation() === Orientation.HORZ;
    const c = this.getChildren();
    const ss = this.model.getSplitterSize();
    const initialSizes = [];
    let sum = 0;
    for (let i = 0; i < c.length; i++) {
      const n = c[i];
      const r = n.getRect();
      const s = h ? r.width : r.height;
      initialSizes.push(s);
      sum += s;
    }
    const startRect = c[index].getRect();
    const startPosition = (h ? startRect.x : startRect.y) - ss;
    return { initialSizes, sum, startPosition };
  }
  /** @internal */
  calculateSplit(index, splitterPos, initialSizes, sum, startPosition) {
    const h = this.getOrientation() === Orientation.HORZ;
    const c = this.getChildren();
    const sn = c[index];
    const smax = h ? sn.getMaxWidth() : sn.getMaxHeight();
    const sizes = [...initialSizes];
    if (splitterPos < startPosition) {
      let shift = startPosition - splitterPos;
      let altShift = 0;
      if (sizes[index] + shift > smax) {
        altShift = sizes[index] + shift - smax;
        sizes[index] = smax;
      } else {
        sizes[index] += shift;
      }
      for (let i = index - 1; i >= 0; i--) {
        const n = c[i];
        const m = h ? n.getMinWidth() : n.getMinHeight();
        if (sizes[i] - shift > m) {
          sizes[i] -= shift;
          break;
        } else {
          shift -= sizes[i] - m;
          sizes[i] = m;
        }
      }
      for (let i = index + 1; i < c.length; i++) {
        const n = c[i];
        const m = h ? n.getMaxWidth() : n.getMaxHeight();
        if (sizes[i] + altShift < m) {
          sizes[i] += altShift;
          break;
        } else {
          altShift -= m - sizes[i];
          sizes[i] = m;
        }
      }
    } else {
      let shift = splitterPos - startPosition;
      let altShift = 0;
      if (sizes[index - 1] + shift > smax) {
        altShift = sizes[index - 1] + shift - smax;
        sizes[index - 1] = smax;
      } else {
        sizes[index - 1] += shift;
      }
      for (let i = index; i < c.length; i++) {
        const n = c[i];
        const m = h ? n.getMinWidth() : n.getMinHeight();
        if (sizes[i] - shift > m) {
          sizes[i] -= shift;
          break;
        } else {
          shift -= sizes[i] - m;
          sizes[i] = m;
        }
      }
      for (let i = index - 1; i >= 0; i--) {
        const n = c[i];
        const m = h ? n.getMaxWidth() : n.getMaxHeight();
        if (sizes[i] + altShift < m) {
          sizes[i] += altShift;
          break;
        } else {
          altShift -= m - sizes[i];
          sizes[i] = m;
        }
      }
    }
    const weights = sizes.map((s) => Math.max(0.1, s) * 100 / sum);
    return weights;
  }
  /** @internal */
  getMinSize(orientation) {
    if (orientation === Orientation.HORZ) {
      return this.getMinWidth();
    } else {
      return this.getMinHeight();
    }
  }
  /** @internal */
  getMinWidth() {
    return this.minWidth;
  }
  /** @internal */
  getMinHeight() {
    return this.minHeight;
  }
  /** @internal */
  getMaxSize(orientation) {
    if (orientation === Orientation.HORZ) {
      return this.getMaxWidth();
    } else {
      return this.getMaxHeight();
    }
  }
  /** @internal */
  getMaxWidth() {
    return this.maxWidth;
  }
  /** @internal */
  getMaxHeight() {
    return this.maxHeight;
  }
  /** @internal */
  calcMinMaxSize() {
    this.minHeight = DefaultMin;
    this.minWidth = DefaultMin;
    this.maxHeight = DefaultMax;
    this.maxWidth = DefaultMax;
    let first = true;
    for (const child of this.children) {
      const c = child;
      c.calcMinMaxSize();
      if (this.getOrientation() === Orientation.VERT) {
        this.minHeight += c.getMinHeight();
        this.maxHeight += c.getMaxHeight();
        if (!first) {
          this.minHeight += this.model.getSplitterSize();
          this.maxHeight += this.model.getSplitterSize();
        }
        this.minWidth = Math.max(this.minWidth, c.getMinWidth());
        this.maxWidth = Math.min(this.maxWidth, c.getMaxWidth());
      } else {
        this.minWidth += c.getMinWidth();
        this.maxWidth += c.getMaxWidth();
        if (!first) {
          this.minWidth += this.model.getSplitterSize();
          this.maxWidth += this.model.getSplitterSize();
        }
        this.minHeight = Math.max(this.minHeight, c.getMinHeight());
        this.maxHeight = Math.min(this.maxHeight, c.getMaxHeight());
      }
      first = false;
    }
  }
  /** @internal */
  tidy() {
    let i = 0;
    while (i < this.children.length) {
      const child = this.children[i];
      if (child instanceof _RowNode) {
        child.tidy();
        const childChildren = child.getChildren();
        if (childChildren.length === 0) {
          this.removeChild(child);
        } else if (childChildren.length === 1) {
          const subchild = childChildren[0];
          this.removeChild(child);
          if (subchild instanceof _RowNode) {
            let subChildrenTotal = 0;
            const subChildChildren = subchild.getChildren();
            for (const ssc of subChildChildren) {
              const subsubChild = ssc;
              subChildrenTotal += subsubChild.getWeight();
            }
            for (let j = 0; j < subChildChildren.length; j++) {
              const subsubChild = subChildChildren[j];
              subsubChild.setWeight(child.getWeight() * subsubChild.getWeight() / subChildrenTotal);
              this.addChild(subsubChild, i + j);
            }
          } else {
            subchild.setWeight(child.getWeight());
            this.addChild(subchild, i);
          }
        } else {
          i++;
        }
      } else if (child instanceof TabSetNode && child.getChildren().length === 0) {
        if (child.isEnableDeleteWhenEmpty()) {
          this.removeChild(child);
          if (child === this.model.getMaximizedTabset(this.windowId)) {
            this.model.setMaximizedTabset(void 0, this.windowId);
          }
        } else {
          i++;
        }
      } else {
        i++;
      }
    }
    if (this === this.model.getRoot(this.windowId) && this.children.length === 0) {
      const callback = this.model.getOnCreateTabSet();
      let attrs = callback ? callback() : {};
      attrs = { ...attrs, selected: -1 };
      const child = new TabSetNode(this.model, attrs);
      this.model.setActiveTabset(child, this.windowId);
      this.addChild(child);
    }
  }
  /** @internal */
  canDrop(dragNode, x, y) {
    const yy = y - this.rect.y;
    const xx = x - this.rect.x;
    const w = this.rect.width;
    const h = this.rect.height;
    const margin = 10;
    const half = 50;
    let dropInfo;
    if (this.getWindowId() !== Model.MAIN_WINDOW_ID && !canDockToWindow(dragNode)) {
      return void 0;
    }
    if (this.model.isEnableEdgeDock() && this.parent === void 0) {
      if (x < this.rect.x + margin && yy > h / 2 - half && yy < h / 2 + half) {
        const dockLocation = DockLocation.LEFT;
        const outlineRect = dockLocation.getDockRect(this.rect);
        outlineRect.width = outlineRect.width / 2;
        dropInfo = new DropInfo(this, outlineRect, dockLocation, -1, CLASSES.FLEXLAYOUT__OUTLINE_RECT_EDGE);
      } else if (x > this.rect.getRight() - margin && yy > h / 2 - half && yy < h / 2 + half) {
        const dockLocation = DockLocation.RIGHT;
        const outlineRect = dockLocation.getDockRect(this.rect);
        outlineRect.width = outlineRect.width / 2;
        outlineRect.x += outlineRect.width;
        dropInfo = new DropInfo(this, outlineRect, dockLocation, -1, CLASSES.FLEXLAYOUT__OUTLINE_RECT_EDGE);
      } else if (y < this.rect.y + margin && xx > w / 2 - half && xx < w / 2 + half) {
        const dockLocation = DockLocation.TOP;
        const outlineRect = dockLocation.getDockRect(this.rect);
        outlineRect.height = outlineRect.height / 2;
        dropInfo = new DropInfo(this, outlineRect, dockLocation, -1, CLASSES.FLEXLAYOUT__OUTLINE_RECT_EDGE);
      } else if (y > this.rect.getBottom() - margin && xx > w / 2 - half && xx < w / 2 + half) {
        const dockLocation = DockLocation.BOTTOM;
        const outlineRect = dockLocation.getDockRect(this.rect);
        outlineRect.height = outlineRect.height / 2;
        outlineRect.y += outlineRect.height;
        dropInfo = new DropInfo(this, outlineRect, dockLocation, -1, CLASSES.FLEXLAYOUT__OUTLINE_RECT_EDGE);
      }
      if (dropInfo !== void 0) {
        if (!dragNode.canDockInto(dragNode, dropInfo)) {
          return void 0;
        }
      }
    }
    return dropInfo;
  }
  /** @internal */
  drop(dragNode, location, index) {
    const dockLocation = location;
    const parent = dragNode.getParent();
    if (parent) {
      parent.removeChild(dragNode);
    }
    if (parent !== void 0 && parent instanceof TabSetNode) {
      parent.setSelected(0);
    }
    if (parent !== void 0 && parent instanceof BorderNode) {
      parent.setSelected(-1);
    }
    let node;
    if (dragNode instanceof TabSetNode || dragNode instanceof _RowNode) {
      node = dragNode;
      if (node instanceof _RowNode && node.getOrientation() === this.getOrientation() && (location.getOrientation() === this.getOrientation() || location === DockLocation.CENTER)) {
        node = new _RowNode(this.model, this.windowId, {});
        node.addChild(dragNode);
      }
    } else {
      const callback = this.model.getOnCreateTabSet();
      node = new TabSetNode(this.model, callback ? callback(dragNode) : {});
      node.addChild(dragNode);
    }
    let size = this.children.reduce((sum, child) => {
      return sum + child.getWeight();
    }, 0);
    if (size === 0) {
      size = 100;
    }
    node.setWeight(size / 3);
    const horz = !this.model.isRootOrientationVertical();
    if (dockLocation === DockLocation.CENTER) {
      if (index === -1) {
        this.addChild(node, this.children.length);
      } else {
        this.addChild(node, index);
      }
    } else if (horz && dockLocation === DockLocation.LEFT || !horz && dockLocation === DockLocation.TOP) {
      this.addChild(node, 0);
    } else if (horz && dockLocation === DockLocation.RIGHT || !horz && dockLocation === DockLocation.BOTTOM) {
      this.addChild(node);
    } else if (horz && dockLocation === DockLocation.TOP || !horz && dockLocation === DockLocation.LEFT) {
      const vrow = new _RowNode(this.model, this.windowId, {});
      const hrow = new _RowNode(this.model, this.windowId, {});
      hrow.setWeight(75);
      node.setWeight(25);
      for (const child of this.children) {
        hrow.addChild(child);
      }
      this.removeAll();
      vrow.addChild(node);
      vrow.addChild(hrow);
      this.addChild(vrow);
    } else if (horz && dockLocation === DockLocation.BOTTOM || !horz && dockLocation === DockLocation.RIGHT) {
      const vrow = new _RowNode(this.model, this.windowId, {});
      const hrow = new _RowNode(this.model, this.windowId, {});
      hrow.setWeight(75);
      node.setWeight(25);
      for (const child of this.children) {
        hrow.addChild(child);
      }
      this.removeAll();
      vrow.addChild(hrow);
      vrow.addChild(node);
      this.addChild(vrow);
    }
    if (node instanceof TabSetNode) {
      this.model.setActiveTabset(node, this.windowId);
    }
    this.model.tidy();
  }
  /** @internal */
  isEnableDrop() {
    return true;
  }
  /** @internal */
  getAttributeDefinitions() {
    return _RowNode.attributeDefinitions;
  }
  /** @internal */
  updateAttrs(json) {
    _RowNode.attributeDefinitions.update(json, this.attributes);
  }
  /** @internal */
  static getAttributeDefinitions() {
    return _RowNode.attributeDefinitions;
  }
  // NOTE:  flex-grow cannot have values < 1 otherwise will not fill parent, need to normalize 
  normalizeWeights() {
    let sum = 0;
    for (const n of this.children) {
      const node = n;
      sum += node.getWeight();
    }
    if (sum === 0) {
      sum = 1;
    }
    for (const n of this.children) {
      const node = n;
      node.setWeight(Math.max(1e-3, 100 * node.getWeight() / sum));
    }
  }
  /** @internal */
  static createAttributeDefinitions() {
    const attributeDefinitions = new AttributeDefinitions();
    attributeDefinitions.add("type", _RowNode.TYPE, true).setType(Attribute.STRING).setFixed();
    attributeDefinitions.add("id", void 0).setType(Attribute.STRING).setDescription(
      `the unique id of the row, if left undefined a uuid will be assigned`
    );
    attributeDefinitions.add("weight", 100).setType(Attribute.NUMBER).setDescription(
      `relative weight for sizing of this row in parent row`
    );
    return attributeDefinitions;
  }
};
__publicField(_RowNode, "TYPE", "row");
/** @internal */
__publicField(_RowNode, "attributeDefinitions", _RowNode.createAttributeDefinitions());
let RowNode = _RowNode;
class LayoutWindow {
  constructor(windowId, rect) {
    __publicField(this, "_windowId");
    __publicField(this, "_layout");
    __publicField(this, "_rect");
    __publicField(this, "_window");
    __publicField(this, "_root");
    __publicField(this, "_maximizedTabSet");
    __publicField(this, "_activeTabSet");
    __publicField(this, "_toScreenRectFunction");
    this._windowId = windowId;
    this._rect = rect;
    this._toScreenRectFunction = (r) => r;
  }
  visitNodes(fn) {
    this.root.forEachNode(fn, 0);
  }
  get windowId() {
    return this._windowId;
  }
  get rect() {
    return this._rect;
  }
  get layout() {
    return this._layout;
  }
  get window() {
    return this._window;
  }
  get root() {
    return this._root;
  }
  get maximizedTabSet() {
    return this._maximizedTabSet;
  }
  get activeTabSet() {
    return this._activeTabSet;
  }
  /** @internal */
  set rect(value) {
    this._rect = value;
  }
  /** @internal */
  set layout(value) {
    this._layout = value;
  }
  /** @internal */
  set window(value) {
    this._window = value;
  }
  /** @internal */
  set root(value) {
    this._root = value;
  }
  /** @internal */
  set maximizedTabSet(value) {
    this._maximizedTabSet = value;
  }
  /** @internal */
  set activeTabSet(value) {
    this._activeTabSet = value;
  }
  /** @internal */
  get toScreenRectFunction() {
    return this._toScreenRectFunction;
  }
  /** @internal */
  set toScreenRectFunction(value) {
    this._toScreenRectFunction = value;
  }
  toJson() {
    if (this._window && this._window.screenTop > -1e4) {
      this.rect = new Rect(
        this._window.screenLeft,
        this._window.screenTop,
        this._window.outerWidth,
        this._window.outerHeight
      );
    }
    return { layout: this.root.toJson(), rect: this.rect.toJson() };
  }
  static fromJson(windowJson, model, windowId) {
    const count = model.getwindowsMap().size;
    const rect = windowJson.rect ? Rect.fromJson(windowJson.rect) : new Rect(50 + 50 * count, 50 + 50 * count, 600, 400);
    rect.snap(10);
    const layoutWindow = new LayoutWindow(windowId, rect);
    layoutWindow.root = RowNode.fromJson(windowJson.layout, model, layoutWindow);
    return layoutWindow;
  }
}
const DefaultMin = 0;
const DefaultMax = 99999;
const _Model = class _Model {
  /**
   * 'private' constructor. Use the static method Model.fromJson(json) to create a model
   *  @internal
   */
  constructor() {
    /** @internal */
    __publicField(this, "attributes");
    /** @internal */
    __publicField(this, "idMap");
    /** @internal */
    __publicField(this, "changeListeners");
    /** @internal */
    __publicField(this, "borders");
    /** @internal */
    __publicField(this, "onAllowDrop");
    /** @internal */
    __publicField(this, "onCreateTabSet");
    /** @internal */
    __publicField(this, "windows");
    /** @internal */
    __publicField(this, "rootWindow");
    this.attributes = {};
    this.idMap = /* @__PURE__ */ new Map();
    this.borders = new BorderSet(this);
    this.windows = /* @__PURE__ */ new Map();
    this.rootWindow = new LayoutWindow(_Model.MAIN_WINDOW_ID, Rect.empty());
    this.windows.set(_Model.MAIN_WINDOW_ID, this.rootWindow);
    this.changeListeners = [];
  }
  /**
   * Update the node tree by performing the given action,
   * Actions should be generated via static methods on the Actions class
   * @param action the action to perform
   * @returns added Node for Actions.addNode, windowId for createWindow
   */
  doAction(action) {
    var _a;
    let returnVal = void 0;
    switch (action.type) {
      case Actions.ADD_NODE: {
        const newNode = new TabNode(this, action.data.json, true);
        const toNode = this.idMap.get(action.data.toNode);
        if (toNode instanceof TabSetNode || toNode instanceof BorderNode || toNode instanceof RowNode) {
          toNode.drop(newNode, DockLocation.getByName(action.data.location), action.data.index, action.data.select);
          returnVal = newNode;
        }
        break;
      }
      case Actions.MOVE_NODE: {
        const fromNode = this.idMap.get(action.data.fromNode);
        if (fromNode instanceof TabNode || fromNode instanceof TabSetNode || fromNode instanceof RowNode) {
          if (fromNode === this.getMaximizedTabset(fromNode.getWindowId())) {
            const fromWindow = this.windows.get(fromNode.getWindowId());
            fromWindow.maximizedTabSet = void 0;
          }
          const toNode = this.idMap.get(action.data.toNode);
          if (toNode instanceof TabSetNode || toNode instanceof BorderNode || toNode instanceof RowNode) {
            toNode.drop(fromNode, DockLocation.getByName(action.data.location), action.data.index, action.data.select);
          }
        }
        this.removeEmptyWindows();
        break;
      }
      case Actions.DELETE_TAB: {
        const node = this.idMap.get(action.data.node);
        if (node instanceof TabNode) {
          node.delete();
        }
        this.removeEmptyWindows();
        break;
      }
      case Actions.DELETE_TABSET: {
        const node = this.idMap.get(action.data.node);
        if (node instanceof TabSetNode) {
          const children = [...node.getChildren()];
          for (let i = 0; i < children.length; i++) {
            const child = children[i];
            if (child.isEnableClose()) {
              child.delete();
            }
          }
          if (node.getChildren().length === 0) {
            node.delete();
          }
          this.tidy();
        }
        this.removeEmptyWindows();
        break;
      }
      case Actions.POPOUT_TABSET: {
        const node = this.idMap.get(action.data.node);
        if (node instanceof TabSetNode) {
          const isMaximized = node.isMaximized();
          const oldLayoutWindow = this.windows.get(node.getWindowId());
          const windowId = randomUUID();
          const layoutWindow = new LayoutWindow(windowId, oldLayoutWindow.toScreenRectFunction(node.getRect()));
          const json = {
            type: "row",
            children: []
          };
          const row = RowNode.fromJson(json, this, layoutWindow);
          layoutWindow.root = row;
          this.windows.set(windowId, layoutWindow);
          row.drop(node, DockLocation.CENTER, 0);
          if (isMaximized) {
            this.rootWindow.maximizedTabSet = void 0;
          }
        }
        this.removeEmptyWindows();
        break;
      }
      case Actions.POPOUT_TAB: {
        const node = this.idMap.get(action.data.node);
        if (node instanceof TabNode) {
          const windowId = randomUUID();
          let r = Rect.empty();
          if (node.getParent() instanceof TabSetNode) {
            r = node.getParent().getRect();
          } else {
            r = node.getParent().getContentRect();
          }
          const oldLayoutWindow = this.windows.get(node.getWindowId());
          const layoutWindow = new LayoutWindow(windowId, oldLayoutWindow.toScreenRectFunction(r));
          const tabsetId = randomUUID();
          const json = {
            type: "row",
            children: [
              { type: "tabset", id: tabsetId }
            ]
          };
          const row = RowNode.fromJson(json, this, layoutWindow);
          layoutWindow.root = row;
          this.windows.set(windowId, layoutWindow);
          const tabset = this.idMap.get(tabsetId);
          tabset.drop(node, DockLocation.CENTER, 0, true);
        }
        this.removeEmptyWindows();
        break;
      }
      case Actions.CLOSE_WINDOW: {
        const window2 = this.windows.get(action.data.windowId);
        if (window2) {
          (_a = this.rootWindow.root) == null ? void 0 : _a.drop(window2.root, DockLocation.CENTER, -1);
          this.rootWindow.visitNodes((node, level) => {
            if (node instanceof RowNode) {
              node.setWindowId(_Model.MAIN_WINDOW_ID);
            }
          });
          this.windows.delete(action.data.windowId);
        }
        break;
      }
      case Actions.CREATE_WINDOW: {
        const windowId = randomUUID();
        const layoutWindow = new LayoutWindow(windowId, Rect.fromJson(action.data.rect));
        const row = RowNode.fromJson(action.data.layout, this, layoutWindow);
        layoutWindow.root = row;
        this.windows.set(windowId, layoutWindow);
        returnVal = windowId;
        break;
      }
      case Actions.RENAME_TAB: {
        const node = this.idMap.get(action.data.node);
        if (node instanceof TabNode) {
          node.setName(action.data.text);
        }
        break;
      }
      case Actions.SELECT_TAB: {
        const tabNode = this.idMap.get(action.data.tabNode);
        const windowId = action.data.windowId ? action.data.windowId : _Model.MAIN_WINDOW_ID;
        const window2 = this.windows.get(windowId);
        if (tabNode instanceof TabNode) {
          const parent = tabNode.getParent();
          const pos = parent.getChildren().indexOf(tabNode);
          if (parent instanceof BorderNode) {
            if (parent.getSelected() === pos) {
              parent.setSelected(-1);
            } else {
              parent.setSelected(pos);
            }
          } else if (parent instanceof TabSetNode) {
            if (parent.getSelected() !== pos) {
              parent.setSelected(pos);
            }
            window2.activeTabSet = parent;
          }
        }
        break;
      }
      case Actions.SET_ACTIVE_TABSET: {
        const windowId = action.data.windowId ? action.data.windowId : _Model.MAIN_WINDOW_ID;
        const window2 = this.windows.get(windowId);
        if (action.data.tabsetNode === void 0) {
          window2.activeTabSet = void 0;
        } else {
          const tabsetNode = this.idMap.get(action.data.tabsetNode);
          if (tabsetNode instanceof TabSetNode) {
            window2.activeTabSet = tabsetNode;
          }
        }
        break;
      }
      case Actions.ADJUST_WEIGHTS: {
        const row = this.idMap.get(action.data.nodeId);
        const c = row.getChildren();
        for (let i = 0; i < c.length; i++) {
          const n = c[i];
          n.setWeight(action.data.weights[i]);
        }
        break;
      }
      case Actions.ADJUST_BORDER_SPLIT: {
        const node = this.idMap.get(action.data.node);
        if (node instanceof BorderNode) {
          node.setSize(action.data.pos);
        }
        break;
      }
      case Actions.MAXIMIZE_TOGGLE: {
        const windowId = action.data.windowId ? action.data.windowId : _Model.MAIN_WINDOW_ID;
        const window2 = this.windows.get(windowId);
        const node = this.idMap.get(action.data.node);
        if (node instanceof TabSetNode) {
          if (node === window2.maximizedTabSet) {
            window2.maximizedTabSet = void 0;
          } else {
            window2.maximizedTabSet = node;
            window2.activeTabSet = node;
          }
        }
        break;
      }
      case Actions.UPDATE_MODEL_ATTRIBUTES: {
        this.updateAttrs(action.data.json);
        break;
      }
      case Actions.UPDATE_NODE_ATTRIBUTES: {
        const node = this.idMap.get(action.data.node);
        node.updateAttrs(action.data.json);
        break;
      }
    }
    this.updateIdMap();
    for (const listener of this.changeListeners) {
      listener(action);
    }
    return returnVal;
  }
  /**
   * Get the currently active tabset node
   */
  getActiveTabset(windowId = _Model.MAIN_WINDOW_ID) {
    const window2 = this.windows.get(windowId);
    if (window2 && window2.activeTabSet && this.getNodeById(window2.activeTabSet.getId())) {
      return window2.activeTabSet;
    } else {
      return void 0;
    }
  }
  /**
   * Get the currently maximized tabset node
   */
  getMaximizedTabset(windowId = _Model.MAIN_WINDOW_ID) {
    return this.windows.get(windowId).maximizedTabSet;
  }
  /**
   * Gets the root RowNode of the model
   * @returns {RowNode}
   */
  getRoot(windowId = _Model.MAIN_WINDOW_ID) {
    return this.windows.get(windowId).root;
  }
  isRootOrientationVertical() {
    return this.attributes.rootOrientationVertical;
  }
  isEnableRotateBorderIcons() {
    return this.attributes.enableRotateBorderIcons;
  }
  /**
   * Gets the
   * @returns {BorderSet|*}
   */
  getBorderSet() {
    return this.borders;
  }
  getwindowsMap() {
    return this.windows;
  }
  /**
   * Visits all the nodes in the model and calls the given function for each
   * @param fn a function that takes visited node and a integer level as parameters
   */
  visitNodes(fn) {
    this.borders.forEachNode(fn);
    for (const [_, w] of this.windows) {
      w.root.forEachNode(fn, 0);
    }
  }
  visitWindowNodes(windowId, fn) {
    if (this.windows.has(windowId)) {
      if (windowId === _Model.MAIN_WINDOW_ID) {
        this.borders.forEachNode(fn);
      }
      this.windows.get(windowId).visitNodes(fn);
    }
  }
  /**
   * Gets a node by its id
   * @param id the id to find
   */
  getNodeById(id) {
    return this.idMap.get(id);
  }
  /**
   * Finds the first/top left tab set of the given node.
   * @param node The top node you want to begin searching from, deafults to the root node
   * @returns The first Tab Set
   */
  getFirstTabSet(node = this.windows.get(_Model.MAIN_WINDOW_ID).root) {
    const child = node.getChildren()[0];
    if (child instanceof TabSetNode) {
      return child;
    } else {
      return this.getFirstTabSet(child);
    }
  }
  /**
  * Loads the model from the given json object
  * @param json the json model to load
  * @returns {Model} a new Model object
  */
  static fromJson(json) {
    const model = new _Model();
    _Model.attributeDefinitions.fromJson(json.global, model.attributes);
    if (json.borders) {
      model.borders = BorderSet.fromJson(json.borders, model);
    }
    if (json.popouts) {
      for (const windowId in json.popouts) {
        const windowJson = json.popouts[windowId];
        const layoutWindow = LayoutWindow.fromJson(windowJson, model, windowId);
        model.windows.set(windowId, layoutWindow);
      }
    }
    model.rootWindow.root = RowNode.fromJson(json.layout, model, model.getwindowsMap().get(_Model.MAIN_WINDOW_ID));
    model.tidy();
    return model;
  }
  /**
   * Converts the model to a json object
   * @returns {IJsonModel} json object that represents this model
   */
  toJson() {
    const global = {};
    _Model.attributeDefinitions.toJson(global, this.attributes);
    this.visitNodes((node) => {
      node.fireEvent("save", {});
    });
    const windows = {};
    for (const [id, window2] of this.windows) {
      if (id !== _Model.MAIN_WINDOW_ID) {
        windows[id] = window2.toJson();
      }
    }
    return {
      global,
      borders: this.borders.toJson(),
      layout: this.rootWindow.root.toJson(),
      popouts: windows
    };
  }
  getSplitterSize() {
    return this.attributes.splitterSize;
  }
  getSplitterExtra() {
    return this.attributes.splitterExtra;
  }
  isEnableEdgeDock() {
    return this.attributes.enableEdgeDock;
  }
  isSplitterEnableHandle() {
    return this.attributes.splitterEnableHandle;
  }
  /**
   * Sets a function to allow/deny dropping a node
   * @param onAllowDrop function that takes the drag node and DropInfo and returns true if the drop is allowed
   */
  setOnAllowDrop(onAllowDrop) {
    this.onAllowDrop = onAllowDrop;
  }
  /**
   * set callback called when a new TabSet is created.
   * The tabNode can be undefined if it's the auto created first tabset in the root row (when the last
   * tab is deleted, the root tabset can be recreated)
   * @param onCreateTabSet 
   */
  setOnCreateTabSet(onCreateTabSet) {
    this.onCreateTabSet = onCreateTabSet;
  }
  addChangeListener(listener) {
    this.changeListeners.push(listener);
  }
  removeChangeListener(listener) {
    const pos = this.changeListeners.findIndex((l) => l === listener);
    if (pos !== -1) {
      this.changeListeners.splice(pos, 1);
    }
  }
  toString() {
    return JSON.stringify(this.toJson());
  }
  /***********************internal ********************************/
  /** @internal */
  removeEmptyWindows() {
    const emptyWindows = /* @__PURE__ */ new Set();
    for (const [windowId] of this.windows) {
      if (windowId !== _Model.MAIN_WINDOW_ID) {
        let count = 0;
        this.visitWindowNodes(windowId, (node) => {
          if (node instanceof TabNode) {
            count++;
          }
        });
        if (count === 0) {
          emptyWindows.add(windowId);
        }
      }
    }
    for (const windowId of emptyWindows) {
      this.windows.delete(windowId);
    }
  }
  /** @internal */
  setActiveTabset(tabsetNode, windowId) {
    const window2 = this.windows.get(windowId);
    if (window2) {
      if (tabsetNode) {
        window2.activeTabSet = tabsetNode;
      } else {
        window2.activeTabSet = void 0;
      }
    }
  }
  /** @internal */
  setMaximizedTabset(tabsetNode, windowId) {
    const window2 = this.windows.get(windowId);
    if (window2) {
      if (tabsetNode) {
        window2.maximizedTabSet = tabsetNode;
      } else {
        window2.maximizedTabSet = void 0;
      }
    }
  }
  /** @internal */
  updateIdMap() {
    this.idMap.clear();
    this.visitNodes((node) => {
      this.idMap.set(node.getId(), node);
    });
  }
  /** @internal */
  addNode(node) {
    const id = node.getId();
    if (this.idMap.has(id)) {
      throw new Error(`Error: each node must have a unique id, duplicate id:${node.getId()}`);
    }
    this.idMap.set(id, node);
  }
  /** @internal */
  findDropTargetNode(windowId, dragNode, x, y) {
    let node = this.windows.get(windowId).root.findDropTargetNode(windowId, dragNode, x, y);
    if (node === void 0 && windowId === _Model.MAIN_WINDOW_ID) {
      node = this.borders.findDropTargetNode(dragNode, x, y);
    }
    return node;
  }
  /** @internal */
  tidy() {
    for (const [_, window2] of this.windows) {
      window2.root.tidy();
    }
  }
  /** @internal */
  updateAttrs(json) {
    _Model.attributeDefinitions.update(json, this.attributes);
  }
  /** @internal */
  nextUniqueId() {
    return "#" + randomUUID();
  }
  /** @internal */
  getAttribute(name) {
    return this.attributes[name];
  }
  /** @internal */
  getOnAllowDrop() {
    return this.onAllowDrop;
  }
  /** @internal */
  getOnCreateTabSet() {
    return this.onCreateTabSet;
  }
  static toTypescriptInterfaces() {
    _Model.attributeDefinitions.pairAttributes("RowNode", RowNode.getAttributeDefinitions());
    _Model.attributeDefinitions.pairAttributes("TabSetNode", TabSetNode.getAttributeDefinitions());
    _Model.attributeDefinitions.pairAttributes("TabNode", TabNode.getAttributeDefinitions());
    _Model.attributeDefinitions.pairAttributes("BorderNode", BorderNode.getAttributeDefinitions());
    const sb = [];
    sb.push(_Model.attributeDefinitions.toTypescriptInterface("Global", void 0));
    sb.push(RowNode.getAttributeDefinitions().toTypescriptInterface("Row", _Model.attributeDefinitions));
    sb.push(TabSetNode.getAttributeDefinitions().toTypescriptInterface("TabSet", _Model.attributeDefinitions));
    sb.push(TabNode.getAttributeDefinitions().toTypescriptInterface("Tab", _Model.attributeDefinitions));
    sb.push(BorderNode.getAttributeDefinitions().toTypescriptInterface("Border", _Model.attributeDefinitions));
    console.log(sb.join("\n"));
  }
  /** @internal */
  static createAttributeDefinitions() {
    const attributeDefinitions = new AttributeDefinitions();
    attributeDefinitions.add("enableEdgeDock", true).setType(Attribute.BOOLEAN).setDescription(
      `enable docking to the edges of the layout, this will show the edge indicators`
    );
    attributeDefinitions.add("rootOrientationVertical", false).setType(Attribute.BOOLEAN).setDescription(
      `the top level 'row' will layout horizontally by default, set this option true to make it layout vertically`
    );
    attributeDefinitions.add("enableRotateBorderIcons", true).setType(Attribute.BOOLEAN).setDescription(
      `boolean indicating if tab icons should rotate with the text in the left and right borders`
    );
    attributeDefinitions.add("splitterSize", 8).setType(Attribute.NUMBER).setDescription(
      `width in pixels of all splitters between tabsets/borders`
    );
    attributeDefinitions.add("splitterExtra", 0).setType(Attribute.NUMBER).setDescription(
      `additional width in pixels of the splitter hit test area`
    );
    attributeDefinitions.add("splitterEnableHandle", false).setType(Attribute.BOOLEAN).setDescription(
      `enable a small centralized handle on all splitters`
    );
    attributeDefinitions.add("tabEnableClose", true).setType(Attribute.BOOLEAN);
    attributeDefinitions.add("tabCloseType", 1).setType("ICloseType");
    attributeDefinitions.add("tabEnablePopout", false).setType(Attribute.BOOLEAN).setAlias("tabEnableFloat");
    attributeDefinitions.add("tabEnablePopoutIcon", true).setType(Attribute.BOOLEAN);
    attributeDefinitions.add("tabEnablePopoutOverlay", false).setType(Attribute.BOOLEAN);
    attributeDefinitions.add("tabEnableDrag", true).setType(Attribute.BOOLEAN);
    attributeDefinitions.add("tabEnableRename", true).setType(Attribute.BOOLEAN);
    attributeDefinitions.add("tabContentClassName", void 0).setType(Attribute.STRING);
    attributeDefinitions.add("tabClassName", void 0).setType(Attribute.STRING);
    attributeDefinitions.add("tabIcon", void 0).setType(Attribute.STRING);
    attributeDefinitions.add("tabEnableRenderOnDemand", true).setType(Attribute.BOOLEAN);
    attributeDefinitions.add("tabDragSpeed", 0.3).setType(Attribute.NUMBER);
    attributeDefinitions.add("tabBorderWidth", -1).setType(Attribute.NUMBER);
    attributeDefinitions.add("tabBorderHeight", -1).setType(Attribute.NUMBER);
    attributeDefinitions.add("tabSetEnableDeleteWhenEmpty", true).setType(Attribute.BOOLEAN);
    attributeDefinitions.add("tabSetEnableDrop", true).setType(Attribute.BOOLEAN);
    attributeDefinitions.add("tabSetEnableDrag", true).setType(Attribute.BOOLEAN);
    attributeDefinitions.add("tabSetEnableDivide", true).setType(Attribute.BOOLEAN);
    attributeDefinitions.add("tabSetEnableMaximize", true).setType(Attribute.BOOLEAN);
    attributeDefinitions.add("tabSetEnableClose", false).setType(Attribute.BOOLEAN);
    attributeDefinitions.add("tabSetEnableSingleTabStretch", false).setType(Attribute.BOOLEAN);
    attributeDefinitions.add("tabSetAutoSelectTab", true).setType(Attribute.BOOLEAN);
    attributeDefinitions.add("tabSetEnableActiveIcon", false).setType(Attribute.BOOLEAN);
    attributeDefinitions.add("tabSetClassNameTabStrip", void 0).setType(Attribute.STRING);
    attributeDefinitions.add("tabSetEnableTabStrip", true).setType(Attribute.BOOLEAN);
    attributeDefinitions.add("tabSetEnableTabWrap", false).setType(Attribute.BOOLEAN);
    attributeDefinitions.add("tabSetTabLocation", "top").setType("ITabLocation");
    attributeDefinitions.add("tabMinWidth", DefaultMin).setType(Attribute.NUMBER);
    attributeDefinitions.add("tabMinHeight", DefaultMin).setType(Attribute.NUMBER);
    attributeDefinitions.add("tabSetMinWidth", DefaultMin).setType(Attribute.NUMBER);
    attributeDefinitions.add("tabSetMinHeight", DefaultMin).setType(Attribute.NUMBER);
    attributeDefinitions.add("tabMaxWidth", DefaultMax).setType(Attribute.NUMBER);
    attributeDefinitions.add("tabMaxHeight", DefaultMax).setType(Attribute.NUMBER);
    attributeDefinitions.add("tabSetMaxWidth", DefaultMax).setType(Attribute.NUMBER);
    attributeDefinitions.add("tabSetMaxHeight", DefaultMax).setType(Attribute.NUMBER);
    attributeDefinitions.add("tabSetEnableTabScrollbar", false).setType(Attribute.BOOLEAN);
    attributeDefinitions.add("borderSize", 200).setType(Attribute.NUMBER);
    attributeDefinitions.add("borderMinSize", DefaultMin).setType(Attribute.NUMBER);
    attributeDefinitions.add("borderMaxSize", DefaultMax).setType(Attribute.NUMBER);
    attributeDefinitions.add("borderEnableDrop", true).setType(Attribute.BOOLEAN);
    attributeDefinitions.add("borderAutoSelectTabWhenOpen", true).setType(Attribute.BOOLEAN);
    attributeDefinitions.add("borderAutoSelectTabWhenClosed", false).setType(Attribute.BOOLEAN);
    attributeDefinitions.add("borderClassName", void 0).setType(Attribute.STRING);
    attributeDefinitions.add("borderEnableAutoHide", false).setType(Attribute.BOOLEAN);
    attributeDefinitions.add("borderEnableTabScrollbar", false).setType(Attribute.BOOLEAN);
    return attributeDefinitions;
  }
};
__publicField(_Model, "MAIN_WINDOW_ID", "__main_window_id__");
/** @internal */
__publicField(_Model, "attributeDefinitions", _Model.createAttributeDefinitions());
let Model = _Model;
const _BorderNode = class _BorderNode extends Node {
  /** @internal */
  constructor(location, json, model) {
    super(model);
    /** @internal */
    __publicField(this, "contentRect", Rect.empty());
    /** @internal */
    __publicField(this, "tabHeaderRect", Rect.empty());
    /** @internal */
    __publicField(this, "location");
    this.location = location;
    this.attributes.id = `border_${location.getName()}`;
    _BorderNode.attributeDefinitions.fromJson(json, this.attributes);
    model.addNode(this);
  }
  /** @internal */
  static fromJson(json, model) {
    const location = DockLocation.getByName(json.location);
    const border = new _BorderNode(location, json, model);
    if (json.children) {
      border.children = json.children.map((jsonChild) => {
        const child = TabNode.fromJson(jsonChild, model);
        child.setParent(border);
        return child;
      });
    }
    return border;
  }
  getLocation() {
    return this.location;
  }
  getClassName() {
    return this.getAttr("className");
  }
  isHorizontal() {
    return this.location.orientation === Orientation.HORZ;
  }
  getSize() {
    const defaultSize = this.getAttr("size");
    const selected = this.getSelected();
    if (selected === -1) {
      return defaultSize;
    } else {
      const tabNode = this.children[selected];
      const tabBorderSize = this.isHorizontal() ? tabNode.getAttr("borderWidth") : tabNode.getAttr("borderHeight");
      if (tabBorderSize === -1) {
        return defaultSize;
      } else {
        return tabBorderSize;
      }
    }
  }
  getMinSize() {
    const selectedNode = this.getSelectedNode();
    let min = this.getAttr("minSize");
    if (selectedNode) {
      const nodeMin = this.isHorizontal() ? selectedNode.getMinWidth() : selectedNode.getMinHeight();
      min = Math.max(min, nodeMin);
    }
    return min;
  }
  getMaxSize() {
    const selectedNode = this.getSelectedNode();
    let max = this.getAttr("maxSize");
    if (selectedNode) {
      const nodeMax = this.isHorizontal() ? selectedNode.getMaxWidth() : selectedNode.getMaxHeight();
      max = Math.min(max, nodeMax);
    }
    return max;
  }
  getSelected() {
    return this.attributes.selected;
  }
  isAutoHide() {
    return this.getAttr("enableAutoHide");
  }
  getSelectedNode() {
    if (this.getSelected() !== -1) {
      return this.children[this.getSelected()];
    }
    return void 0;
  }
  getOrientation() {
    return this.location.getOrientation();
  }
  /**
   * Returns the config attribute that can be used to store node specific data that
   * WILL be saved to the json. The config attribute should be changed via the action Actions.updateNodeAttributes rather
   * than directly, for example:
   * this.state.model.doAction(
   *   FlexLayout.Actions.updateNodeAttributes(node.getId(), {config:myConfigObject}));
   */
  getConfig() {
    return this.attributes.config;
  }
  isMaximized() {
    return false;
  }
  isShowing() {
    return this.attributes.show;
  }
  toJson() {
    const json = {};
    _BorderNode.attributeDefinitions.toJson(json, this.attributes);
    json.location = this.location.getName();
    json.children = this.children.map((child) => child.toJson());
    return json;
  }
  /** @internal */
  isAutoSelectTab(whenOpen) {
    if (whenOpen == null) {
      whenOpen = this.getSelected() !== -1;
    }
    if (whenOpen) {
      return this.getAttr("autoSelectTabWhenOpen");
    } else {
      return this.getAttr("autoSelectTabWhenClosed");
    }
  }
  isEnableTabScrollbar() {
    return this.getAttr("enableTabScrollbar");
  }
  /** @internal */
  setSelected(index) {
    this.attributes.selected = index;
  }
  /** @internal */
  getTabHeaderRect() {
    return this.tabHeaderRect;
  }
  /** @internal */
  setTabHeaderRect(r) {
    this.tabHeaderRect = r;
  }
  /** @internal */
  getRect() {
    return this.tabHeaderRect;
  }
  /** @internal */
  getContentRect() {
    return this.contentRect;
  }
  /** @internal */
  setContentRect(r) {
    this.contentRect = r;
  }
  /** @internal */
  isEnableDrop() {
    return this.getAttr("enableDrop");
  }
  /** @internal */
  setSize(pos) {
    const selected = this.getSelected();
    if (selected === -1) {
      this.attributes.size = pos;
    } else {
      const tabNode = this.children[selected];
      const tabBorderSize = this.isHorizontal() ? tabNode.getAttr("borderWidth") : tabNode.getAttr("borderHeight");
      if (tabBorderSize === -1) {
        this.attributes.size = pos;
      } else {
        if (this.isHorizontal()) {
          tabNode.setBorderWidth(pos);
        } else {
          tabNode.setBorderHeight(pos);
        }
      }
    }
  }
  /** @internal */
  updateAttrs(json) {
    _BorderNode.attributeDefinitions.update(json, this.attributes);
  }
  /** @internal */
  remove(node) {
    const removedIndex = this.removeChild(node);
    if (this.getSelected() !== -1) {
      adjustSelectedIndex(this, removedIndex);
    }
  }
  /** @internal */
  canDrop(dragNode, x, y) {
    if (!(dragNode instanceof TabNode)) {
      return void 0;
    }
    let dropInfo;
    const dockLocation = DockLocation.CENTER;
    if (this.tabHeaderRect.contains(x, y)) {
      if (this.location.orientation === Orientation.VERT) {
        if (this.children.length > 0) {
          let child = this.children[0];
          let childRect = child.getTabRect();
          const childY = childRect.y;
          const childHeight = childRect.height;
          let pos = this.tabHeaderRect.x;
          let childCenter = 0;
          for (let i = 0; i < this.children.length; i++) {
            child = this.children[i];
            childRect = child.getTabRect();
            childCenter = childRect.x + childRect.width / 2;
            if (x >= pos && x < childCenter) {
              const outlineRect = new Rect(childRect.x - 2, childY, 3, childHeight);
              dropInfo = new DropInfo(this, outlineRect, dockLocation, i, CLASSES.FLEXLAYOUT__OUTLINE_RECT);
              break;
            }
            pos = childCenter;
          }
          if (dropInfo == null) {
            const outlineRect = new Rect(childRect.getRight() - 2, childY, 3, childHeight);
            dropInfo = new DropInfo(this, outlineRect, dockLocation, this.children.length, CLASSES.FLEXLAYOUT__OUTLINE_RECT);
          }
        } else {
          const outlineRect = new Rect(this.tabHeaderRect.x + 1, this.tabHeaderRect.y + 2, 3, 18);
          dropInfo = new DropInfo(this, outlineRect, dockLocation, 0, CLASSES.FLEXLAYOUT__OUTLINE_RECT);
        }
      } else {
        if (this.children.length > 0) {
          let child = this.children[0];
          let childRect = child.getTabRect();
          const childX = childRect.x;
          const childWidth = childRect.width;
          let pos = this.tabHeaderRect.y;
          let childCenter = 0;
          for (let i = 0; i < this.children.length; i++) {
            child = this.children[i];
            childRect = child.getTabRect();
            childCenter = childRect.y + childRect.height / 2;
            if (y >= pos && y < childCenter) {
              const outlineRect = new Rect(childX, childRect.y - 2, childWidth, 3);
              dropInfo = new DropInfo(this, outlineRect, dockLocation, i, CLASSES.FLEXLAYOUT__OUTLINE_RECT);
              break;
            }
            pos = childCenter;
          }
          if (dropInfo == null) {
            const outlineRect = new Rect(childX, childRect.getBottom() - 2, childWidth, 3);
            dropInfo = new DropInfo(this, outlineRect, dockLocation, this.children.length, CLASSES.FLEXLAYOUT__OUTLINE_RECT);
          }
        } else {
          const outlineRect = new Rect(this.tabHeaderRect.x + 2, this.tabHeaderRect.y + 1, 18, 3);
          dropInfo = new DropInfo(this, outlineRect, dockLocation, 0, CLASSES.FLEXLAYOUT__OUTLINE_RECT);
        }
      }
      if (!dragNode.canDockInto(dragNode, dropInfo)) {
        return void 0;
      }
    } else if (this.getSelected() !== -1 && this.contentRect.contains(x, y)) {
      const outlineRect = this.contentRect;
      dropInfo = new DropInfo(this, outlineRect, dockLocation, -1, CLASSES.FLEXLAYOUT__OUTLINE_RECT);
      if (!dragNode.canDockInto(dragNode, dropInfo)) {
        return void 0;
      }
    }
    return dropInfo;
  }
  /** @internal */
  drop(dragNode, location, index, select) {
    let fromIndex = 0;
    const dragParent = dragNode.getParent();
    if (dragParent !== void 0) {
      fromIndex = dragParent.removeChild(dragNode);
      if (dragParent !== this && dragParent instanceof _BorderNode && dragParent.getSelected() === fromIndex) {
        dragParent.setSelected(-1);
      } else {
        adjustSelectedIndex(dragParent, fromIndex);
      }
    }
    if (dragNode instanceof TabNode && dragParent === this && fromIndex < index && index > 0) {
      index--;
    }
    let insertPos = index;
    if (insertPos === -1) {
      insertPos = this.children.length;
    }
    if (dragNode instanceof TabNode) {
      this.addChild(dragNode, insertPos);
    }
    if (select || select !== false && this.isAutoSelectTab()) {
      this.setSelected(insertPos);
    }
    this.model.tidy();
  }
  /** @internal */
  getSplitterBounds(index, useMinSize = false) {
    const pBounds = [0, 0];
    const minSize = useMinSize ? this.getMinSize() : 0;
    const maxSize = useMinSize ? this.getMaxSize() : 99999;
    const rootRow = this.model.getRoot(Model.MAIN_WINDOW_ID);
    const innerRect = rootRow.getRect();
    const splitterSize = this.model.getSplitterSize();
    if (this.location === DockLocation.TOP) {
      pBounds[0] = this.tabHeaderRect.getBottom() + minSize;
      const maxPos = this.tabHeaderRect.getBottom() + maxSize;
      pBounds[1] = Math.max(pBounds[0], innerRect.getBottom() - rootRow.getMinHeight() - splitterSize);
      pBounds[1] = Math.min(pBounds[1], maxPos);
    } else if (this.location === DockLocation.LEFT) {
      pBounds[0] = this.tabHeaderRect.getRight() + minSize;
      const maxPos = this.tabHeaderRect.getRight() + maxSize;
      pBounds[1] = Math.max(pBounds[0], innerRect.getRight() - rootRow.getMinWidth() - splitterSize);
      pBounds[1] = Math.min(pBounds[1], maxPos);
    } else if (this.location === DockLocation.BOTTOM) {
      pBounds[1] = this.tabHeaderRect.y - minSize - splitterSize;
      const maxPos = this.tabHeaderRect.y - maxSize - splitterSize;
      pBounds[0] = Math.min(pBounds[1], innerRect.y + rootRow.getMinHeight());
      pBounds[0] = Math.max(pBounds[0], maxPos);
    } else if (this.location === DockLocation.RIGHT) {
      pBounds[1] = this.tabHeaderRect.x - minSize - splitterSize;
      const maxPos = this.tabHeaderRect.x - maxSize - splitterSize;
      pBounds[0] = Math.min(pBounds[1], innerRect.x + rootRow.getMinWidth());
      pBounds[0] = Math.max(pBounds[0], maxPos);
    }
    return pBounds;
  }
  /** @internal */
  calculateSplit(splitter, splitterPos) {
    const pBounds = this.getSplitterBounds(splitterPos);
    if (this.location === DockLocation.BOTTOM || this.location === DockLocation.RIGHT) {
      return Math.max(0, pBounds[1] - splitterPos);
    } else {
      return Math.max(0, splitterPos - pBounds[0]);
    }
  }
  /** @internal */
  getAttributeDefinitions() {
    return _BorderNode.attributeDefinitions;
  }
  /** @internal */
  static getAttributeDefinitions() {
    return _BorderNode.attributeDefinitions;
  }
  /** @internal */
  static createAttributeDefinitions() {
    const attributeDefinitions = new AttributeDefinitions();
    attributeDefinitions.add("type", _BorderNode.TYPE, true).setType(Attribute.STRING).setFixed();
    attributeDefinitions.add("selected", -1).setType(Attribute.NUMBER).setDescription(
      `index of selected/visible tab in border; -1 means no tab selected`
    );
    attributeDefinitions.add("show", true).setType(Attribute.BOOLEAN).setDescription(
      `show/hide this border`
    );
    attributeDefinitions.add("config", void 0).setType("any").setDescription(
      `a place to hold json config used in your own code`
    );
    attributeDefinitions.addInherited("enableDrop", "borderEnableDrop").setType(Attribute.BOOLEAN).setDescription(
      `whether tabs can be dropped into this border`
    );
    attributeDefinitions.addInherited("className", "borderClassName").setType(Attribute.STRING).setDescription(
      `class applied to tab button`
    );
    attributeDefinitions.addInherited("autoSelectTabWhenOpen", "borderAutoSelectTabWhenOpen").setType(Attribute.BOOLEAN).setDescription(
      `whether to select new/moved tabs in border when the border is already open`
    );
    attributeDefinitions.addInherited("autoSelectTabWhenClosed", "borderAutoSelectTabWhenClosed").setType(Attribute.BOOLEAN).setDescription(
      `whether to select new/moved tabs in border when the border is currently closed`
    );
    attributeDefinitions.addInherited("size", "borderSize").setType(Attribute.NUMBER).setDescription(
      `size of the tab area when selected`
    );
    attributeDefinitions.addInherited("minSize", "borderMinSize").setType(Attribute.NUMBER).setDescription(
      `the minimum size of the tab area`
    );
    attributeDefinitions.addInherited("maxSize", "borderMaxSize").setType(Attribute.NUMBER).setDescription(
      `the maximum size of the tab area`
    );
    attributeDefinitions.addInherited("enableAutoHide", "borderEnableAutoHide").setType(Attribute.BOOLEAN).setDescription(
      `hide border if it has zero tabs`
    );
    attributeDefinitions.addInherited("enableTabScrollbar", "borderEnableTabScrollbar").setType(Attribute.BOOLEAN).setDescription(
      `whether to show a mini scrollbar for the tabs`
    );
    return attributeDefinitions;
  }
};
__publicField(_BorderNode, "TYPE", "border");
/** @internal */
__publicField(_BorderNode, "attributeDefinitions", _BorderNode.createAttributeDefinitions());
let BorderNode = _BorderNode;
let splitterDragging = false;
const Splitter = (props) => {
  const { layout, node, index, horizontal } = props;
  const [dragging, setDragging] = React.useState(false);
  const selfRef = React.useRef(null);
  const extendedRef = React.useRef(null);
  const pBounds = React.useRef([]);
  const outlineDiv = React.useRef(void 0);
  const handleDiv = React.useRef(void 0);
  const dragStartX = React.useRef(0);
  const dragStartY = React.useRef(0);
  const initalSizes = React.useRef({ initialSizes: [], sum: 0, startPosition: 0 });
  const size = node.getModel().getSplitterSize();
  let extra = node.getModel().getSplitterExtra();
  if (!isDesktop()) {
    extra = Math.max(20, extra + size) - size;
  }
  React.useEffect(() => {
    var _a, _b;
    (_a = selfRef.current) == null ? void 0 : _a.addEventListener("touchstart", onTouchStart, { passive: false });
    (_b = extendedRef.current) == null ? void 0 : _b.addEventListener("touchstart", onTouchStart, { passive: false });
    return () => {
      var _a2, _b2;
      (_a2 = selfRef.current) == null ? void 0 : _a2.removeEventListener("touchstart", onTouchStart);
      (_b2 = extendedRef.current) == null ? void 0 : _b2.removeEventListener("touchstart", onTouchStart);
    };
  }, []);
  const onTouchStart = (event) => {
    event.preventDefault();
    event.stopImmediatePropagation();
  };
  const onPointerDown = (event) => {
    var _a;
    event.stopPropagation();
    if (node instanceof RowNode) {
      initalSizes.current = node.getSplitterInitials(index);
    }
    enablePointerOnIFrames(false, layout.getCurrentDocument());
    startDrag(event.currentTarget.ownerDocument, event, onDragMove, onDragEnd, onDragCancel);
    pBounds.current = node.getSplitterBounds(index, true);
    const rootdiv = layout.getRootDiv();
    outlineDiv.current = layout.getCurrentDocument().createElement("div");
    outlineDiv.current.style.flexDirection = horizontal ? "row" : "column";
    outlineDiv.current.className = layout.getClassName(CLASSES.FLEXLAYOUT__SPLITTER_DRAG);
    outlineDiv.current.style.cursor = node.getOrientation() === Orientation.VERT ? "ns-resize" : "ew-resize";
    if (node.getModel().isSplitterEnableHandle()) {
      handleDiv.current = layout.getCurrentDocument().createElement("div");
      handleDiv.current.className = cm(CLASSES.FLEXLAYOUT__SPLITTER_HANDLE) + " " + (horizontal ? cm(CLASSES.FLEXLAYOUT__SPLITTER_HANDLE_HORZ) : cm(CLASSES.FLEXLAYOUT__SPLITTER_HANDLE_VERT));
      outlineDiv.current.appendChild(handleDiv.current);
    }
    const r = (_a = selfRef.current) == null ? void 0 : _a.getBoundingClientRect();
    const rect = new Rect(
      r.x - layout.getDomRect().x,
      r.y - layout.getDomRect().y,
      r.width,
      r.height
    );
    dragStartX.current = event.clientX - r.x;
    dragStartY.current = event.clientY - r.y;
    rect.positionElement(outlineDiv.current);
    if (rootdiv) {
      rootdiv.appendChild(outlineDiv.current);
    }
    setDragging(true);
    splitterDragging = true;
  };
  const onDragCancel = () => {
    const rootdiv = layout.getRootDiv();
    if (rootdiv && outlineDiv.current) {
      rootdiv.removeChild(outlineDiv.current);
    }
    outlineDiv.current = void 0;
    setDragging(false);
    splitterDragging = false;
  };
  const onDragMove = (x, y) => {
    if (outlineDiv.current) {
      const clientRect = layout.getDomRect();
      if (!clientRect) {
        return;
      }
      if (node.getOrientation() === Orientation.VERT) {
        outlineDiv.current.style.top = getBoundPosition(y - clientRect.y - dragStartY.current) + "px";
      } else {
        outlineDiv.current.style.left = getBoundPosition(x - clientRect.x - dragStartX.current) + "px";
      }
      if (layout.isRealtimeResize()) {
        updateLayout();
      }
    }
  };
  const onDragEnd = () => {
    if (outlineDiv.current) {
      updateLayout();
      const rootdiv = layout.getRootDiv();
      if (rootdiv && outlineDiv.current) {
        rootdiv.removeChild(outlineDiv.current);
      }
      outlineDiv.current = void 0;
    }
    enablePointerOnIFrames(true, layout.getCurrentDocument());
    setDragging(false);
    splitterDragging = false;
  };
  const updateLayout = (realtime) => {
    const redraw = () => {
      if (outlineDiv.current) {
        let value = 0;
        if (node.getOrientation() === Orientation.VERT) {
          value = outlineDiv.current.offsetTop;
        } else {
          value = outlineDiv.current.offsetLeft;
        }
        if (node instanceof BorderNode) {
          const pos = node.calculateSplit(node, value);
          layout.doAction(Actions.adjustBorderSplit(node.getId(), pos));
        } else {
          const init = initalSizes.current;
          const weights = node.calculateSplit(index, value, init.initialSizes, init.sum, init.startPosition);
          layout.doAction(Actions.adjustWeights(node.getId(), weights));
        }
      }
    };
    redraw();
  };
  const getBoundPosition = (p) => {
    const bounds = pBounds.current;
    let rtn = p;
    if (p < bounds[0]) {
      rtn = bounds[0];
    }
    if (p > bounds[1]) {
      rtn = bounds[1];
    }
    return rtn;
  };
  const cm = layout.getClassName;
  const style2 = {
    cursor: horizontal ? "ew-resize" : "ns-resize",
    flexDirection: horizontal ? "column" : "row"
  };
  let className = cm(CLASSES.FLEXLAYOUT__SPLITTER) + " " + cm(CLASSES.FLEXLAYOUT__SPLITTER_ + node.getOrientation().getName());
  if (node instanceof BorderNode) {
    className += " " + cm(CLASSES.FLEXLAYOUT__SPLITTER_BORDER);
  } else {
    if (node.getModel().getMaximizedTabset(layout.getWindowId()) !== void 0) {
      style2.display = "none";
    }
  }
  if (horizontal) {
    style2.width = size + "px";
    style2.minWidth = size + "px";
  } else {
    style2.height = size + "px";
    style2.minHeight = size + "px";
  }
  let handle;
  if (!dragging && node.getModel().isSplitterEnableHandle()) {
    handle = /* @__PURE__ */ jsx(
      "div",
      {
        className: cm(CLASSES.FLEXLAYOUT__SPLITTER_HANDLE) + " " + (horizontal ? cm(CLASSES.FLEXLAYOUT__SPLITTER_HANDLE_HORZ) : cm(CLASSES.FLEXLAYOUT__SPLITTER_HANDLE_VERT))
      }
    );
  }
  if (extra === 0) {
    return /* @__PURE__ */ jsx(
      "div",
      {
        className,
        style: style2,
        ref: selfRef,
        "data-layout-path": node.getPath() + "/s" + (index - 1),
        onPointerDown,
        children: handle
      }
    );
  } else {
    const style22 = {};
    if (node.getOrientation() === Orientation.HORZ) {
      style22.height = "100%";
      style22.width = size + extra + "px";
      style22.cursor = "ew-resize";
    } else {
      style22.height = size + extra + "px";
      style22.width = "100%";
      style22.cursor = "ns-resize";
    }
    const className2 = cm(CLASSES.FLEXLAYOUT__SPLITTER_EXTRA);
    return /* @__PURE__ */ jsx(
      "div",
      {
        className,
        style: style2,
        ref: selfRef,
        "data-layout-path": node.getPath() + "/s" + (index - 1),
        onPointerDown,
        children: /* @__PURE__ */ jsx(
          "div",
          {
            style: style22,
            ref: extendedRef,
            className: className2,
            onPointerDown
          }
        )
      }
    );
  }
};
function BorderTab(props) {
  const { layout, border, show } = props;
  const selfRef = React.useRef(null);
  const timer = React.useRef(void 0);
  React.useLayoutEffect(() => {
    const contentRect = layout.getBoundingClientRect(selfRef.current);
    if (!isNaN(contentRect.x) && contentRect.width > 0) {
      if (!border.getContentRect().equals(contentRect)) {
        border.setContentRect(contentRect);
        if (splitterDragging) {
          if (timer.current) {
            clearTimeout(timer.current);
          }
          timer.current = setTimeout(() => {
            layout.redrawInternal("border content rect " + contentRect);
            timer.current = void 0;
          }, 50);
        } else {
          layout.redrawInternal("border content rect " + contentRect);
        }
      }
    }
  });
  let horizontal = true;
  const style2 = {};
  if (border.getOrientation() === Orientation.HORZ) {
    style2.width = border.getSize();
    style2.minWidth = border.getMinSize();
    style2.maxWidth = border.getMaxSize();
  } else {
    style2.height = border.getSize();
    style2.minHeight = border.getMinSize();
    style2.maxHeight = border.getMaxSize();
    horizontal = false;
  }
  style2.display = show ? "flex" : "none";
  const className = layout.getClassName(CLASSES.FLEXLAYOUT__BORDER_TAB_CONTENTS);
  if (border.getLocation() === DockLocation.LEFT || border.getLocation() === DockLocation.TOP) {
    return /* @__PURE__ */ jsxs(Fragment, { children: [
      /* @__PURE__ */ jsx("div", { ref: selfRef, style: style2, className }),
      show && /* @__PURE__ */ jsx(Splitter, { layout, node: border, index: 0, horizontal })
    ] });
  } else {
    return /* @__PURE__ */ jsxs(Fragment, { children: [
      show && /* @__PURE__ */ jsx(Splitter, { layout, node: border, index: 0, horizontal }),
      /* @__PURE__ */ jsx("div", { ref: selfRef, style: style2, className })
    ] });
  }
}
var ICloseType = /* @__PURE__ */ ((ICloseType2) => {
  ICloseType2[ICloseType2["Visible"] = 1] = "Visible";
  ICloseType2[ICloseType2["Always"] = 2] = "Always";
  ICloseType2[ICloseType2["Selected"] = 3] = "Selected";
  return ICloseType2;
})(ICloseType || {});
const BorderButton = (props) => {
  const { layout, node, selected, border, icons, path } = props;
  const selfRef = React.useRef(null);
  const contentRef = React.useRef(null);
  const onDragStart = (event) => {
    if (node.isEnableDrag()) {
      event.stopPropagation();
      layout.setDragNode(event.nativeEvent, node);
    } else {
      event.preventDefault();
    }
  };
  const onDragEnd = (event) => {
    event.stopPropagation();
    layout.clearDragMain();
  };
  const onAuxMouseClick = (event) => {
    if (isAuxMouseEvent(event)) {
      layout.auxMouseClick(node, event);
    }
  };
  const onContextMenu = (event) => {
    layout.showContextMenu(node, event);
  };
  const onClick = () => {
    layout.doAction(Actions.selectTab(node.getId()));
  };
  const isClosable = () => {
    const closeType = node.getCloseType();
    if (selected || closeType === ICloseType.Always) {
      return true;
    }
    if (closeType === ICloseType.Visible) {
      if (window.matchMedia && window.matchMedia("(hover: hover) and (pointer: fine)").matches) {
        return true;
      }
    }
    return false;
  };
  const onClose = (event) => {
    if (isClosable()) {
      layout.doAction(Actions.deleteTab(node.getId()));
      event.stopPropagation();
    }
  };
  const onClosePointerDown = (event) => {
    event.stopPropagation();
  };
  React.useLayoutEffect(() => {
    node.setTabRect(layout.getBoundingClientRect(selfRef.current));
    if (layout.getEditingTab() === node) {
      contentRef.current.select();
    }
  });
  const onTextBoxPointerDown = (event) => {
    event.stopPropagation();
  };
  const onTextBoxKeyPress = (event) => {
    if (event.code === "Escape") {
      layout.setEditingTab(void 0);
    } else if (event.code === "Enter" || event.code === "NumpadEnter") {
      layout.setEditingTab(void 0);
      layout.doAction(Actions.renameTab(node.getId(), event.target.value));
    }
  };
  const cm = layout.getClassName;
  let classNames = cm(CLASSES.FLEXLAYOUT__BORDER_BUTTON) + " " + cm(CLASSES.FLEXLAYOUT__BORDER_BUTTON_ + border);
  if (selected) {
    classNames += " " + cm(CLASSES.FLEXLAYOUT__BORDER_BUTTON__SELECTED);
  } else {
    classNames += " " + cm(CLASSES.FLEXLAYOUT__BORDER_BUTTON__UNSELECTED);
  }
  if (node.getClassName() !== void 0) {
    classNames += " " + node.getClassName();
  }
  let iconAngle = 0;
  if (node.getModel().isEnableRotateBorderIcons() === false) {
    if (border === "left") {
      iconAngle = 90;
    } else if (border === "right") {
      iconAngle = -90;
    }
  }
  const renderState = getRenderStateEx(layout, node, iconAngle);
  let content = renderState.content ? /* @__PURE__ */ jsx("div", { className: cm(CLASSES.FLEXLAYOUT__BORDER_BUTTON_CONTENT), children: renderState.content }) : null;
  const leading = renderState.leading ? /* @__PURE__ */ jsx("div", { className: cm(CLASSES.FLEXLAYOUT__BORDER_BUTTON_LEADING), children: renderState.leading }) : null;
  if (layout.getEditingTab() === node) {
    content = /* @__PURE__ */ jsx(
      "input",
      {
        ref: contentRef,
        className: cm(CLASSES.FLEXLAYOUT__TAB_BUTTON_TEXTBOX),
        "data-layout-path": path + "/textbox",
        type: "text",
        autoFocus: true,
        defaultValue: node.getName(),
        onKeyDown: onTextBoxKeyPress,
        onPointerDown: onTextBoxPointerDown
      }
    );
  }
  if (node.isEnableClose()) {
    const closeTitle = layout.i18nName(I18nLabel.Close_Tab);
    renderState.buttons.push(
      /* @__PURE__ */ jsx(
        "div",
        {
          "data-layout-path": path + "/button/close",
          title: closeTitle,
          className: cm(CLASSES.FLEXLAYOUT__BORDER_BUTTON_TRAILING),
          onPointerDown: onClosePointerDown,
          onClick: onClose,
          children: typeof icons.close === "function" ? icons.close(node) : icons.close
        },
        "close"
      )
    );
  }
  return /* @__PURE__ */ jsxs(
    "div",
    {
      ref: selfRef,
      "data-layout-path": path,
      className: classNames,
      onClick,
      onAuxClick: onAuxMouseClick,
      onContextMenu,
      title: node.getHelpText(),
      draggable: true,
      onDragStart,
      onDragEnd,
      children: [
        leading,
        content,
        renderState.buttons
      ]
    }
  );
};
const TabButtonStamp = (props) => {
  const { layout, node } = props;
  const cm = layout.getClassName;
  const classNames = cm(CLASSES.FLEXLAYOUT__TAB_BUTTON_STAMP);
  const renderState = getRenderStateEx(layout, node);
  const content = renderState.content ? /* @__PURE__ */ jsx("div", { className: cm(CLASSES.FLEXLAYOUT__TAB_BUTTON_CONTENT), children: renderState.content }) : node.getNameForOverflowMenu();
  const leading = renderState.leading ? /* @__PURE__ */ jsx("div", { className: cm(CLASSES.FLEXLAYOUT__TAB_BUTTON_LEADING), children: renderState.leading }) : null;
  return /* @__PURE__ */ jsxs(
    "div",
    {
      className: classNames,
      title: node.getHelpText(),
      children: [
        leading,
        content
      ]
    }
  );
};
function showPopup(triggerElement, parentNode, items, onSelect, layout) {
  const layoutDiv = layout.getRootDiv();
  const classNameMapper = layout.getClassName;
  const currentDocument = triggerElement.ownerDocument;
  const triggerRect = triggerElement.getBoundingClientRect();
  const layoutRect = (layoutDiv == null ? void 0 : layoutDiv.getBoundingClientRect()) ?? new DOMRect(0, 0, 100, 100);
  const elm = currentDocument.createElement("div");
  elm.className = classNameMapper(CLASSES.FLEXLAYOUT__POPUP_MENU_CONTAINER);
  if (triggerRect.left < layoutRect.left + layoutRect.width / 2) {
    elm.style.left = triggerRect.left - layoutRect.left + "px";
  } else {
    elm.style.right = layoutRect.right - triggerRect.right + "px";
  }
  if (triggerRect.top < layoutRect.top + layoutRect.height / 2) {
    elm.style.top = triggerRect.top - layoutRect.top + "px";
  } else {
    elm.style.bottom = layoutRect.bottom - triggerRect.bottom + "px";
  }
  layout.showOverlay(true);
  if (layoutDiv) {
    layoutDiv.appendChild(elm);
  }
  const onHide = () => {
    layout.hideControlInPortal();
    layout.showOverlay(false);
    if (layoutDiv) {
      layoutDiv.removeChild(elm);
    }
    elm.removeEventListener("pointerdown", onElementPointerDown);
    currentDocument.removeEventListener("pointerdown", onDocPointerDown);
  };
  const onElementPointerDown = (event) => {
    event.stopPropagation();
  };
  const onDocPointerDown = (_event) => {
    onHide();
  };
  elm.addEventListener("pointerdown", onElementPointerDown);
  currentDocument.addEventListener("pointerdown", onDocPointerDown);
  layout.showControlInPortal(/* @__PURE__ */ jsx(
    PopupMenu,
    {
      currentDocument,
      parentNode,
      onSelect,
      onHide,
      items,
      classNameMapper,
      layout
    }
  ), elm);
}
const PopupMenu = (props) => {
  const { parentNode, items, onHide, onSelect, classNameMapper, layout } = props;
  const divRef = useRef(null);
  useEffect(() => {
    if (divRef.current) {
      divRef.current.focus();
    }
  }, []);
  const onItemClick = (item, event) => {
    onSelect(item);
    onHide();
    event.stopPropagation();
  };
  const onDragStart = (event, node) => {
    event.stopPropagation();
    layout.setDragNode(event.nativeEvent, node);
    setTimeout(() => {
      onHide();
    }, 0);
  };
  const onDragEnd = (event) => {
    layout.clearDragMain();
  };
  const handleKeyDown = (event) => {
    if (event.key === "Escape") {
      onHide();
    }
  };
  const itemElements = items.map(
    (item, i) => {
      let classes = classNameMapper(CLASSES.FLEXLAYOUT__POPUP_MENU_ITEM);
      if (parentNode.getSelected() === item.index) {
        classes += " " + classNameMapper(CLASSES.FLEXLAYOUT__POPUP_MENU_ITEM__SELECTED);
      }
      return /* @__PURE__ */ jsx(
        "div",
        {
          className: classes,
          "data-layout-path": "/popup-menu/tb" + i,
          onClick: (event) => onItemClick(item, event),
          draggable: true,
          onDragStart: (e) => onDragStart(e, item.node),
          onDragEnd,
          title: item.node.getHelpText(),
          children: /* @__PURE__ */ jsx(
            TabButtonStamp,
            {
              node: item.node,
              layout
            }
          )
        },
        item.index
      );
    }
  );
  return /* @__PURE__ */ jsx(
    "div",
    {
      className: classNameMapper(CLASSES.FLEXLAYOUT__POPUP_MENU),
      ref: divRef,
      tabIndex: 0,
      onKeyDown: handleKeyDown,
      "data-layout-path": "/popup-menu",
      children: itemElements
    }
  );
};
const useTabOverflow = (layout, node, orientation, tabStripRef, miniScrollRef, tabClassName) => {
  const [hiddenTabs, setHiddenTabs] = React.useState([]);
  const [isShowHiddenTabs, setShowHiddenTabs] = React.useState(false);
  const [isDockStickyButtons, setDockStickyButtons] = React.useState(false);
  const selfRef = React.useRef(null);
  const userControlledPositionRef = React.useRef(false);
  const updateHiddenTabsTimerRef = React.useRef(void 0);
  const hiddenTabsRef = React.useRef([]);
  const thumbInternalPos = React.useRef(0);
  const repositioningRef = React.useRef(false);
  hiddenTabsRef.current = hiddenTabs;
  React.useLayoutEffect(() => {
    if (tabStripRef.current) {
      setScrollPosition(0);
    }
  }, [node.getId()]);
  React.useLayoutEffect(() => {
    userControlledPositionRef.current = false;
  }, [node.getSelectedNode(), node.getRect().width, node.getRect().height]);
  React.useLayoutEffect(() => {
    checkForOverflow();
    if (userControlledPositionRef.current === false) {
      scrollIntoView();
    }
    updateScrollMetrics();
    updateHiddenTabs();
  });
  React.useEffect(() => {
    var _a;
    (_a = selfRef.current) == null ? void 0 : _a.addEventListener("wheel", onWheel, { passive: false });
    return () => {
      var _a2;
      (_a2 = selfRef.current) == null ? void 0 : _a2.removeEventListener("wheel", onWheel);
    };
  }, [selfRef.current]);
  const onWheel = (event) => {
    event.preventDefault();
  };
  function scrollIntoView() {
    const selectedTabNode = node.getSelectedNode();
    if (selectedTabNode && tabStripRef.current) {
      const stripRect = layout.getBoundingClientRect(tabStripRef.current);
      const selectedRect = selectedTabNode.getTabRect();
      let shift = getNear(stripRect) - getNear(selectedRect);
      if (shift > 0 || getSize(selectedRect) > getSize(stripRect)) {
        setScrollPosition(getScrollPosition(tabStripRef.current) - shift);
        repositioningRef.current = true;
      } else {
        shift = getFar(selectedRect) - getFar(stripRect);
        if (shift > 0) {
          setScrollPosition(getScrollPosition(tabStripRef.current) + shift);
          repositioningRef.current = true;
        }
      }
    }
  }
  const updateScrollMetrics = () => {
    if (tabStripRef.current && miniScrollRef.current) {
      const t = tabStripRef.current;
      const s = miniScrollRef.current;
      const size = getElementSize(t);
      const scrollSize = getScrollSize(t);
      const position = getScrollPosition(t);
      if (scrollSize > size && scrollSize > 0) {
        let thumbSize = size * size / scrollSize;
        let adjust = 0;
        if (thumbSize < 20) {
          adjust = 20 - thumbSize;
          thumbSize = 20;
        }
        const thumbPos = position * (size - adjust) / scrollSize;
        if (orientation === Orientation.HORZ) {
          s.style.width = thumbSize + "px";
          s.style.left = thumbPos + "px";
        } else {
          s.style.height = thumbSize + "px";
          s.style.top = thumbPos + "px";
        }
        s.style.display = "block";
      } else {
        s.style.display = "none";
      }
      if (orientation === Orientation.HORZ) {
        s.style.bottom = "0px";
      } else {
        s.style.right = "0px";
      }
    }
  };
  const updateHiddenTabs = () => {
    const newHiddenTabs = findHiddenTabs();
    const showHidden = newHiddenTabs.length > 0;
    if (showHidden !== isShowHiddenTabs) {
      setShowHiddenTabs(showHidden);
    }
    if (updateHiddenTabsTimerRef.current === void 0) {
      updateHiddenTabsTimerRef.current = setTimeout(() => {
        const newHiddenTabs2 = findHiddenTabs();
        if (!arraysEqual(newHiddenTabs2, hiddenTabsRef.current)) {
          setHiddenTabs(newHiddenTabs2);
        }
        updateHiddenTabsTimerRef.current = void 0;
      }, 100);
    }
  };
  const onScroll = () => {
    if (!repositioningRef.current) {
      userControlledPositionRef.current = true;
    }
    repositioningRef.current = false;
    updateScrollMetrics();
    updateHiddenTabs();
  };
  const onScrollPointerDown = (event) => {
    var _a;
    event.stopPropagation();
    miniScrollRef.current.setPointerCapture(event.pointerId);
    const r = (_a = miniScrollRef.current) == null ? void 0 : _a.getBoundingClientRect();
    if (orientation === Orientation.HORZ) {
      thumbInternalPos.current = event.clientX - r.x;
    } else {
      thumbInternalPos.current = event.clientY - r.y;
    }
    startDrag(event.currentTarget.ownerDocument, event, onDragMove, onDragEnd, onDragCancel);
  };
  const onDragMove = (x, y) => {
    if (tabStripRef.current && miniScrollRef.current) {
      const t = tabStripRef.current;
      const s = miniScrollRef.current;
      const size = getElementSize(t);
      const scrollSize = getScrollSize(t);
      const thumbSize = getElementSize(s);
      const r = t.getBoundingClientRect();
      let thumb = 0;
      if (orientation === Orientation.HORZ) {
        thumb = x - r.x - thumbInternalPos.current;
      } else {
        thumb = y - r.y - thumbInternalPos.current;
      }
      thumb = Math.max(0, Math.min(scrollSize - thumbSize, thumb));
      if (size > 0) {
        const scrollPos = thumb * scrollSize / size;
        setScrollPosition(scrollPos);
      }
    }
  };
  const onDragEnd = () => {
  };
  const onDragCancel = () => {
  };
  const checkForOverflow = () => {
    if (tabStripRef.current) {
      const strip = tabStripRef.current;
      const tabContainer = strip.firstElementChild;
      const offset = isDockStickyButtons ? 10 : 0;
      const dock = getElementSize(tabContainer) + offset > getElementSize(tabStripRef.current);
      if (dock !== isDockStickyButtons) {
        setDockStickyButtons(dock);
      }
    }
  };
  const findHiddenTabs = () => {
    const hidden = [];
    if (tabStripRef.current) {
      const strip = tabStripRef.current;
      const stripRect = strip.getBoundingClientRect();
      const visibleNear = getNear(stripRect) - 1;
      const visibleFar = getFar(stripRect) + 1;
      const tabContainer = strip.firstElementChild;
      let i = 0;
      Array.from(tabContainer.children).forEach((child) => {
        const tabRect = child.getBoundingClientRect();
        if (child.classList.contains(tabClassName)) {
          if (getNear(tabRect) < visibleNear || getFar(tabRect) > visibleFar) {
            hidden.push(i);
          }
          i++;
        }
      });
    }
    return hidden;
  };
  const onMouseWheel = (event) => {
    if (tabStripRef.current) {
      if (node.getChildren().length === 0) return;
      let delta = 0;
      if (Math.abs(event.deltaY) > 0) {
        delta = -event.deltaY;
        if (event.deltaMode === 1) {
          delta *= 40;
        }
        const newPos = getScrollPosition(tabStripRef.current) - delta;
        const maxScroll = getScrollSize(tabStripRef.current) - getElementSize(tabStripRef.current);
        const p = Math.max(0, Math.min(maxScroll, newPos));
        setScrollPosition(p);
        event.stopPropagation();
      }
    }
  };
  const getNear = (rect) => {
    if (orientation === Orientation.HORZ) {
      return rect.x;
    } else {
      return rect.y;
    }
  };
  const getFar = (rect) => {
    if (orientation === Orientation.HORZ) {
      return rect.right;
    } else {
      return rect.bottom;
    }
  };
  const getElementSize = (elm) => {
    if (orientation === Orientation.HORZ) {
      return elm.clientWidth;
    } else {
      return elm.clientHeight;
    }
  };
  const getSize = (rect) => {
    if (orientation === Orientation.HORZ) {
      return rect.width;
    } else {
      return rect.height;
    }
  };
  const getScrollSize = (elm) => {
    if (orientation === Orientation.HORZ) {
      return elm.scrollWidth;
    } else {
      return elm.scrollHeight;
    }
  };
  const setScrollPosition = (p) => {
    if (orientation === Orientation.HORZ) {
      tabStripRef.current.scrollLeft = p;
    } else {
      tabStripRef.current.scrollTop = p;
    }
  };
  const getScrollPosition = (elm) => {
    if (orientation === Orientation.HORZ) {
      return elm.scrollLeft;
    } else {
      return elm.scrollTop;
    }
  };
  return { selfRef, userControlledPositionRef, onScroll, onScrollPointerDown, hiddenTabs, onMouseWheel, isDockStickyButtons, isShowHiddenTabs };
};
function arraysEqual(arr1, arr2) {
  return arr1.length === arr2.length && arr1.every((val, index) => val === arr2[index]);
}
const BorderTabSet = (props) => {
  const { border, layout, size } = props;
  const toolbarRef = React.useRef(null);
  const miniScrollRef = React.useRef(null);
  const overflowbuttonRef = React.useRef(null);
  const stickyButtonsRef = React.useRef(null);
  const tabStripInnerRef = React.useRef(null);
  const icons = layout.getIcons();
  React.useLayoutEffect(() => {
    border.setTabHeaderRect(layout.getBoundingClientRect(selfRef.current));
  });
  const { selfRef, userControlledPositionRef, onScroll, onScrollPointerDown, hiddenTabs, onMouseWheel, isDockStickyButtons, isShowHiddenTabs } = useTabOverflow(
    layout,
    border,
    Orientation.flip(border.getOrientation()),
    tabStripInnerRef,
    miniScrollRef,
    layout.getClassName(CLASSES.FLEXLAYOUT__BORDER_BUTTON)
  );
  const onAuxMouseClick = (event) => {
    if (isAuxMouseEvent(event)) {
      layout.auxMouseClick(border, event);
    }
  };
  const onContextMenu = (event) => {
    layout.showContextMenu(border, event);
  };
  const onInterceptPointerDown = (event) => {
    event.stopPropagation();
  };
  const onOverflowClick = (event) => {
    const callback = layout.getShowOverflowMenu();
    const items = hiddenTabs.map((h) => {
      return { index: h, node: border.getChildren()[h] };
    });
    if (callback !== void 0) {
      callback(border, event, items, onOverflowItemSelect);
    } else {
      const element = overflowbuttonRef.current;
      showPopup(
        element,
        border,
        items,
        onOverflowItemSelect,
        layout
      );
    }
    event.stopPropagation();
  };
  const onOverflowItemSelect = (item) => {
    layout.doAction(Actions.selectTab(item.node.getId()));
    userControlledPositionRef.current = false;
  };
  const onPopoutTab = (event) => {
    const selectedTabNode = border.getChildren()[border.getSelected()];
    if (selectedTabNode !== void 0) {
      layout.doAction(Actions.popoutTab(selectedTabNode.getId()));
    }
    event.stopPropagation();
  };
  const cm = layout.getClassName;
  const tabButtons = [];
  const layoutTab = (i) => {
    const isSelected = border.getSelected() === i;
    const child = border.getChildren()[i];
    tabButtons.push(
      /* @__PURE__ */ jsx(
        BorderButton,
        {
          layout,
          border: border.getLocation().getName(),
          node: child,
          path: border.getPath() + "/tb" + i,
          selected: isSelected,
          icons
        },
        child.getId()
      )
    );
    if (i < border.getChildren().length - 1) {
      tabButtons.push(
        /* @__PURE__ */ jsx("div", { className: cm(CLASSES.FLEXLAYOUT__BORDER_TAB_DIVIDER) }, "divider" + i)
      );
    }
  };
  for (let i = 0; i < border.getChildren().length; i++) {
    layoutTab(i);
  }
  let borderClasses = cm(CLASSES.FLEXLAYOUT__BORDER) + " " + cm(CLASSES.FLEXLAYOUT__BORDER_ + border.getLocation().getName());
  if (border.getClassName() !== void 0) {
    borderClasses += " " + border.getClassName();
  }
  let leading = void 0;
  let buttons = [];
  let stickyButtons = [];
  const renderState = { leading, buttons, stickyButtons, overflowPosition: void 0 };
  layout.customizeTabSet(border, renderState);
  leading = renderState.leading;
  stickyButtons = renderState.stickyButtons;
  buttons = renderState.buttons;
  if (renderState.overflowPosition === void 0) {
    renderState.overflowPosition = stickyButtons.length;
  }
  if (stickyButtons.length > 0) {
    if (isDockStickyButtons) {
      buttons = [...stickyButtons, ...buttons];
    } else {
      tabButtons.push(/* @__PURE__ */ jsx(
        "div",
        {
          ref: stickyButtonsRef,
          onPointerDown: onInterceptPointerDown,
          onDragStart: (e) => {
            e.preventDefault();
          },
          className: cm(CLASSES.FLEXLAYOUT__TAB_TOOLBAR_STICKY_BUTTONS_CONTAINER),
          children: stickyButtons
        },
        "sticky_buttons_container"
      ));
    }
  }
  if (isShowHiddenTabs) {
    const overflowTitle = layout.i18nName(I18nLabel.Overflow_Menu_Tooltip);
    let overflowContent;
    if (typeof icons.more === "function") {
      const items = hiddenTabs.map((h) => {
        return { index: h, node: border.getChildren()[h] };
      });
      overflowContent = icons.more(border, items);
    } else {
      overflowContent = /* @__PURE__ */ jsxs(Fragment, { children: [
        icons.more,
        /* @__PURE__ */ jsx("div", { className: cm(CLASSES.FLEXLAYOUT__TAB_BUTTON_OVERFLOW_COUNT), children: hiddenTabs.length > 0 ? hiddenTabs.length : "" })
      ] });
    }
    buttons.splice(
      Math.min(renderState.overflowPosition, buttons.length),
      0,
      /* @__PURE__ */ jsx(
        "button",
        {
          ref: overflowbuttonRef,
          className: cm(CLASSES.FLEXLAYOUT__BORDER_TOOLBAR_BUTTON) + " " + cm(CLASSES.FLEXLAYOUT__BORDER_TOOLBAR_BUTTON_OVERFLOW) + " " + cm(CLASSES.FLEXLAYOUT__BORDER_TOOLBAR_BUTTON_OVERFLOW_ + border.getLocation().getName()),
          title: overflowTitle,
          onClick: onOverflowClick,
          onPointerDown: onInterceptPointerDown,
          children: overflowContent
        },
        "overflowbutton"
      )
    );
  }
  const selectedIndex = border.getSelected();
  if (selectedIndex !== -1) {
    const selectedTabNode = border.getChildren()[selectedIndex];
    if (selectedTabNode !== void 0 && layout.isSupportsPopout() && selectedTabNode.isEnablePopout()) {
      const popoutTitle = layout.i18nName(I18nLabel.Popout_Tab);
      buttons.push(
        /* @__PURE__ */ jsx(
          "button",
          {
            title: popoutTitle,
            className: cm(CLASSES.FLEXLAYOUT__BORDER_TOOLBAR_BUTTON) + " " + cm(CLASSES.FLEXLAYOUT__BORDER_TOOLBAR_BUTTON_FLOAT),
            onClick: onPopoutTab,
            onPointerDown: onInterceptPointerDown,
            children: typeof icons.popout === "function" ? icons.popout(selectedTabNode) : icons.popout
          },
          "popout"
        )
      );
    }
  }
  const toolbar = /* @__PURE__ */ jsx("div", { ref: toolbarRef, className: cm(CLASSES.FLEXLAYOUT__BORDER_TOOLBAR) + " " + cm(CLASSES.FLEXLAYOUT__BORDER_TOOLBAR_ + border.getLocation().getName()), children: buttons }, "toolbar");
  let innerStyle = {};
  let outerStyle = {};
  const borderHeight = size - 1;
  if (border.getLocation() === DockLocation.LEFT) {
    innerStyle = { right: "100%", top: 0 };
    outerStyle = { width: borderHeight, overflowY: "auto" };
  } else if (border.getLocation() === DockLocation.RIGHT) {
    innerStyle = { left: "100%", top: 0 };
    outerStyle = { width: borderHeight, overflowY: "auto" };
  } else {
    innerStyle = { left: 0 };
    outerStyle = { height: borderHeight, overflowX: "auto" };
  }
  let miniScrollbar = void 0;
  if (border.isEnableTabScrollbar()) {
    miniScrollbar = /* @__PURE__ */ jsx(
      "div",
      {
        ref: miniScrollRef,
        className: cm(CLASSES.FLEXLAYOUT__MINI_SCROLLBAR),
        onPointerDown: onScrollPointerDown
      }
    );
  }
  let leadingContainer = void 0;
  if (leading) {
    leadingContainer = /* @__PURE__ */ jsx("div", { className: cm(CLASSES.FLEXLAYOUT__BORDER_LEADING), children: leading });
  }
  return /* @__PURE__ */ jsxs(
    "div",
    {
      ref: selfRef,
      style: {
        display: "flex",
        flexDirection: border.getOrientation() === Orientation.VERT ? "row" : "column"
      },
      className: borderClasses,
      "data-layout-path": border.getPath(),
      onClick: onAuxMouseClick,
      onAuxClick: onAuxMouseClick,
      onContextMenu,
      onWheel: onMouseWheel,
      children: [
        leadingContainer,
        /* @__PURE__ */ jsxs("div", { className: cm(CLASSES.FLEXLAYOUT__MINI_SCROLLBAR_CONTAINER), children: [
          /* @__PURE__ */ jsx(
            "div",
            {
              ref: tabStripInnerRef,
              className: cm(CLASSES.FLEXLAYOUT__BORDER_INNER) + " " + cm(CLASSES.FLEXLAYOUT__BORDER_INNER_ + border.getLocation().getName()),
              style: outerStyle,
              onScroll,
              children: /* @__PURE__ */ jsx(
                "div",
                {
                  style: innerStyle,
                  className: cm(CLASSES.FLEXLAYOUT__BORDER_INNER_TAB_CONTAINER) + " " + cm(CLASSES.FLEXLAYOUT__BORDER_INNER_TAB_CONTAINER_ + border.getLocation().getName()),
                  children: tabButtons
                }
              )
            }
          ),
          miniScrollbar
        ] }),
        toolbar
      ]
    }
  );
};
const DragContainer = (props) => {
  const { layout, node } = props;
  const selfRef = React.useRef(null);
  React.useEffect(() => {
    node.setTabStamp(selfRef.current);
  }, [node, selfRef.current]);
  const cm = layout.getClassName;
  const classNames = cm(CLASSES.FLEXLAYOUT__DRAG_RECT);
  return /* @__PURE__ */ jsx(
    "div",
    {
      ref: selfRef,
      className: classNames,
      children: /* @__PURE__ */ jsx(TabButtonStamp, { layout, node }, node.getId())
    }
  );
};
const PopoutWindow = (props) => {
  const { title, layout, layoutWindow, url, onCloseWindow, onSetWindow, children } = props;
  const popoutWindow = React.useRef(null);
  const [content, setContent] = React.useState(void 0);
  const styleMap = /* @__PURE__ */ new Map();
  React.useLayoutEffect(() => {
    if (!popoutWindow.current) {
      const windowId = layoutWindow.windowId;
      const rect = layoutWindow.rect;
      popoutWindow.current = window.open(url, windowId, `left=${rect.x},top=${rect.y},width=${rect.width},height=${rect.height}`);
      if (popoutWindow.current) {
        layoutWindow.window = popoutWindow.current;
        onSetWindow(layoutWindow, popoutWindow.current);
        window.addEventListener("beforeunload", () => {
          if (popoutWindow.current) {
            const closedWindow = popoutWindow.current;
            popoutWindow.current = null;
            closedWindow.close();
          }
        });
        popoutWindow.current.addEventListener("load", () => {
          if (popoutWindow.current) {
            popoutWindow.current.focus();
            popoutWindow.current.resizeTo(rect.width, rect.height);
            popoutWindow.current.moveTo(rect.x, rect.y);
            const popoutDocument = popoutWindow.current.document;
            popoutDocument.title = title;
            const popoutContent = popoutDocument.createElement("div");
            popoutContent.className = CLASSES.FLEXLAYOUT__FLOATING_WINDOW_CONTENT;
            popoutDocument.body.appendChild(popoutContent);
            copyStyles(popoutDocument, styleMap).then(() => {
              setContent(popoutContent);
            });
            const observer = new MutationObserver((mutationsList) => handleStyleMutations(mutationsList, popoutDocument, styleMap));
            observer.observe(document.head, { childList: true });
            popoutWindow.current.addEventListener("beforeunload", () => {
              if (popoutWindow.current) {
                onCloseWindow(layoutWindow);
                popoutWindow.current = null;
                observer.disconnect();
              }
            });
          }
        });
      } else {
        console.warn(`Unable to open window ${url}`);
        onCloseWindow(layoutWindow);
      }
    }
    return () => {
      var _a;
      if (!layout.getModel().getwindowsMap().has(layoutWindow.windowId)) {
        (_a = popoutWindow.current) == null ? void 0 : _a.close();
        popoutWindow.current = null;
      }
    };
  }, []);
  if (content !== void 0) {
    return createPortal(children, content);
  } else {
    return null;
  }
};
function handleStyleMutations(mutationsList, popoutDocument, styleMap) {
  for (const mutation of mutationsList) {
    if (mutation.type === "childList") {
      for (const addition of mutation.addedNodes) {
        if (addition instanceof HTMLLinkElement || addition instanceof HTMLStyleElement) {
          copyStyle(popoutDocument, addition, styleMap);
        }
      }
      for (const removal of mutation.removedNodes) {
        if (removal instanceof HTMLLinkElement || removal instanceof HTMLStyleElement) {
          const popoutStyle = styleMap.get(removal);
          if (popoutStyle) {
            popoutDocument.head.removeChild(popoutStyle);
          }
        }
      }
    }
  }
}
function copyStyles(popoutDoc, styleMap) {
  const promises = [];
  const styleElements = document.querySelectorAll('style, link[rel="stylesheet"]');
  for (const element of styleElements) {
    copyStyle(popoutDoc, element, styleMap, promises);
  }
  return Promise.all(promises);
}
function copyStyle(popoutDoc, element, styleMap, promises) {
  if (element instanceof HTMLLinkElement) {
    const linkElement = element.cloneNode(true);
    popoutDoc.head.appendChild(linkElement);
    styleMap.set(element, linkElement);
    if (promises) {
      promises.push(new Promise((resolve) => {
        linkElement.onload = () => resolve(true);
      }));
    }
  } else if (element instanceof HTMLStyleElement) {
    try {
      const styleElement = element.cloneNode(true);
      popoutDoc.head.appendChild(styleElement);
      styleMap.set(element, styleElement);
    } catch (e) {
    }
  }
}
const style = { width: "1em", height: "1em", display: "flex", alignItems: "center" };
const CloseIcon = () => {
  return /* @__PURE__ */ jsxs("svg", { xmlns: "http://www.w3.org/2000/svg", style, viewBox: "0 0 24 24", children: [
    /* @__PURE__ */ jsx("path", { fill: "none", d: "M0 0h24v24H0z" }),
    /* @__PURE__ */ jsx("path", { stroke: "var(--color-icon)", fill: "var(--color-icon)", d: "M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z" })
  ] });
};
const MaximizeIcon = () => {
  return /* @__PURE__ */ jsxs("svg", { xmlns: "http://www.w3.org/2000/svg", style, viewBox: "0 0 24 24", fill: "var(--color-icon)", children: [
    /* @__PURE__ */ jsx("path", { d: "M0 0h24v24H0z", fill: "none" }),
    /* @__PURE__ */ jsx("path", { stroke: "var(--color-icon)", d: "M7 14H5v5h5v-2H7v-3zm-2-4h2V7h3V5H5v5zm12 7h-3v2h5v-5h-2v3zM14 5v2h3v3h2V5h-5z" })
  ] });
};
const OverflowIcon = () => {
  return /* @__PURE__ */ jsxs("svg", { xmlns: "http://www.w3.org/2000/svg", style, viewBox: "0 0 24 24", fill: "var(--color-icon)", children: [
    /* @__PURE__ */ jsx("path", { d: "M0 0h24v24H0z", fill: "none" }),
    /* @__PURE__ */ jsx("path", { stroke: "var(--color-icon)", d: "M7 10l5 5 5-5z" })
  ] });
};
const EdgeIcon = () => {
  return /* @__PURE__ */ jsx("svg", { xmlns: "http://www.w3.org/2000/svg", style: { display: "block", width: 10, height: 10 }, preserveAspectRatio: "none", viewBox: "0 0 100 100", children: /* @__PURE__ */ jsx(
    "path",
    {
      fill: "var(--color-edge-icon)",
      stroke: "var(--color-edge-icon)",
      d: "M10 30 L90 30 l-40 40 Z"
    }
  ) });
};
const PopoutIcon = () => {
  return (
    // <svg xmlns="http://www.w3.org/2000/svg"  style={style}  viewBox="0 0 24 24" fill="var(--color-icon)"><path d="M0 0h24v24H0z" fill="none"/><path stroke="var(--color-icon)" d="M9 5v2h6.59L4 18.59 5.41 20 17 8.41V15h2V5z"/></svg>
    // <svg xmlns="http://www.w3.org/2000/svg" style={style} fill="none" viewBox="0 0 24 24" stroke="var(--color-icon)" stroke-width="2">
    //     <path stroke-linecap="round" stroke-linejoin="round" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
    // </svg>
    /* @__PURE__ */ jsxs("svg", { xmlns: "http://www.w3.org/2000/svg", style, viewBox: "0 0 20 20", fill: "var(--color-icon)", children: [
      /* @__PURE__ */ jsx("path", { d: "M11 3a1 1 0 100 2h2.586l-6.293 6.293a1 1 0 101.414 1.414L15 6.414V9a1 1 0 102 0V4a1 1 0 00-1-1h-5z" }),
      /* @__PURE__ */ jsx("path", { d: "M5 5a2 2 0 00-2 2v8a2 2 0 002 2h8a2 2 0 002-2v-3a1 1 0 10-2 0v3H5V7h3a1 1 0 000-2H5z" })
    ] })
  );
};
const RestoreIcon = () => {
  return /* @__PURE__ */ jsxs("svg", { xmlns: "http://www.w3.org/2000/svg", style, viewBox: "0 0 24 24", fill: "var(--color-icon)", children: [
    /* @__PURE__ */ jsx("path", { d: "M0 0h24v24H0z", fill: "none" }),
    /* @__PURE__ */ jsx("path", { stroke: "var(--color-icon)", d: "M5 16h3v3h2v-5H5v2zm3-8H5v2h5V5H8v3zm6 11h2v-3h3v-2h-5v5zm2-11V5h-2v5h5V8h-3z" })
  ] });
};
const AsterickIcon = () => {
  return /* @__PURE__ */ jsx("svg", { xmlns: "http://www.w3.org/2000/svg", style, height: "24px", viewBox: "0 -960 960 960", width: "24px", children: /* @__PURE__ */ jsx("path", { fill: "var(--color-icon)", stroke: "var(--color-icon)", d: "M440-120v-264L254-197l-57-57 187-186H120v-80h264L197-706l57-57 186 187v-264h80v264l186-187 57 57-187 186h264v80H576l187 186-57 57-186-187v264h-80Z" }) });
};
const AddIcon = () => {
  return /* @__PURE__ */ jsxs("svg", { xmlns: "http://www.w3.org/2000/svg", style, height: "24px", viewBox: "0 0 24 24", fill: "var(--color-icon)", children: [
    /* @__PURE__ */ jsx("path", { d: "M0 0h24v24H0z", fill: "none" }),
    /* @__PURE__ */ jsx("path", { stroke: "var(--color-icon)", d: "M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z" })
  ] });
};
const MenuIcon = () => {
  return /* @__PURE__ */ jsx("svg", { xmlns: "http://www.w3.org/2000/svg", style, height: "24px", width: "24px", viewBox: "0 -960 960 960", fill: "var(--color-icon)", children: /* @__PURE__ */ jsx("path", { d: "M120-240v-80h720v80H120Zm0-200v-80h720v80H120Zm0-200v-80h720v80H120Z" }) });
};
const SettingsIcon = (props) => {
  return /* @__PURE__ */ jsx("svg", { xmlns: "http://www.w3.org/2000/svg", ...props, style, viewBox: "0 0 24 24", fill: "var(--color-icon)", children: /* @__PURE__ */ jsxs("g", { children: [
    /* @__PURE__ */ jsx("path", { d: "M0,0h24v24H0V0z", fill: "none" }),
    /* @__PURE__ */ jsx("path", { d: "M19.14,12.94c0.04-0.3,0.06-0.61,0.06-0.94c0-0.32-0.02-0.64-0.07-0.94l2.03-1.58c0.18-0.14,0.23-0.41,0.12-0.61 l-1.92-3.32c-0.12-0.22-0.37-0.29-0.59-0.22l-2.39,0.96c-0.5-0.38-1.03-0.7-1.62-0.94L14.4,2.81c-0.04-0.24-0.24-0.41-0.48-0.41 h-3.84c-0.24,0-0.43,0.17-0.47,0.41L9.25,5.35C8.66,5.59,8.12,5.92,7.63,6.29L5.24,5.33c-0.22-0.08-0.47,0-0.59,0.22L2.74,8.87 C2.62,9.08,2.66,9.34,2.86,9.48l2.03,1.58C4.84,11.36,4.8,11.69,4.8,12s0.02,0.64,0.07,0.94l-2.03,1.58 c-0.18,0.14-0.23,0.41-0.12,0.61l1.92,3.32c0.12,0.22,0.37,0.29,0.59,0.22l2.39-0.96c0.5,0.38,1.03,0.7,1.62,0.94l0.36,2.54 c0.05,0.24,0.24,0.41,0.48,0.41h3.84c0.24,0,0.44-0.17,0.47-0.41l0.36-2.54c0.59-0.24,1.13-0.56,1.62-0.94l2.39,0.96 c0.22,0.08,0.47,0,0.59-0.22l1.92-3.32c0.12-0.22,0.07-0.47-0.12-0.61L19.14,12.94z M12,15.6c-1.98,0-3.6-1.62-3.6-3.6 s1.62-3.6,3.6-3.6s3.6,1.62,3.6,3.6S13.98,15.6,12,15.6z" })
  ] }) });
};
const Overlay = (props) => {
  const { layout, show } = props;
  return /* @__PURE__ */ jsx(
    "div",
    {
      className: layout.getClassName(CLASSES.FLEXLAYOUT__LAYOUT_OVERLAY),
      style: {
        display: show ? "flex" : "none"
      }
    }
  );
};
const TabButton = (props) => {
  const { layout, node, selected, path } = props;
  const selfRef = React.useRef(null);
  const contentRef = React.useRef(null);
  const icons = layout.getIcons();
  React.useLayoutEffect(() => {
    node.setTabRect(layout.getBoundingClientRect(selfRef.current));
    if (layout.getEditingTab() === node) {
      contentRef.current.select();
    }
  });
  const onDragStart = (event) => {
    if (node.isEnableDrag()) {
      event.stopPropagation();
      layout.setDragNode(event.nativeEvent, node);
    } else {
      event.preventDefault();
    }
  };
  const onDragEnd = (event) => {
    layout.clearDragMain();
  };
  const onAuxMouseClick = (event) => {
    if (isAuxMouseEvent(event)) {
      layout.auxMouseClick(node, event);
    }
  };
  const onContextMenu = (event) => {
    layout.showContextMenu(node, event);
  };
  const onClick = () => {
    layout.doAction(Actions.selectTab(node.getId()));
  };
  const onDoubleClick = (event) => {
    if (node.isEnableRename()) {
      onRename();
      event.stopPropagation();
    }
  };
  const onRename = () => {
    layout.setEditingTab(node);
    layout.getCurrentDocument().body.addEventListener("pointerdown", onEndEdit);
  };
  const onEndEdit = (event) => {
    if (event.target !== contentRef.current) {
      layout.getCurrentDocument().body.removeEventListener("pointerdown", onEndEdit);
      layout.setEditingTab(void 0);
    }
  };
  const isClosable = () => {
    const closeType = node.getCloseType();
    if (selected || closeType === ICloseType.Always) {
      return true;
    }
    if (closeType === ICloseType.Visible) {
      if (window.matchMedia && window.matchMedia("(hover: hover) and (pointer: fine)").matches) {
        return true;
      }
    }
    return false;
  };
  const onClose = (event) => {
    if (isClosable()) {
      layout.doAction(Actions.deleteTab(node.getId()));
      event.stopPropagation();
    }
  };
  const onClosePointerDown = (event) => {
    event.stopPropagation();
  };
  const onTextBoxPointerDown = (event) => {
    event.stopPropagation();
  };
  const onTextBoxKeyPress = (event) => {
    if (event.code === "Escape") {
      layout.setEditingTab(void 0);
    } else if (event.code === "Enter" || event.code === "NumpadEnter") {
      layout.setEditingTab(void 0);
      layout.doAction(Actions.renameTab(node.getId(), event.target.value));
    }
  };
  const cm = layout.getClassName;
  const parentNode = node.getParent();
  const isStretch = parentNode.isEnableSingleTabStretch() && parentNode.getChildren().length === 1;
  const baseClassName = isStretch ? CLASSES.FLEXLAYOUT__TAB_BUTTON_STRETCH : CLASSES.FLEXLAYOUT__TAB_BUTTON;
  let classNames = cm(baseClassName);
  classNames += " " + cm(baseClassName + "_" + parentNode.getTabLocation());
  if (!isStretch) {
    if (selected) {
      classNames += " " + cm(baseClassName + "--selected");
    } else {
      classNames += " " + cm(baseClassName + "--unselected");
    }
  }
  if (node.getClassName() !== void 0) {
    classNames += " " + node.getClassName();
  }
  const renderState = getRenderStateEx(layout, node);
  let content = renderState.content ? /* @__PURE__ */ jsx("div", { className: cm(CLASSES.FLEXLAYOUT__TAB_BUTTON_CONTENT), children: renderState.content }) : null;
  const leading = renderState.leading ? /* @__PURE__ */ jsx("div", { className: cm(CLASSES.FLEXLAYOUT__TAB_BUTTON_LEADING), children: renderState.leading }) : null;
  if (layout.getEditingTab() === node) {
    content = /* @__PURE__ */ jsx(
      "input",
      {
        ref: contentRef,
        className: cm(CLASSES.FLEXLAYOUT__TAB_BUTTON_TEXTBOX),
        "data-layout-path": path + "/textbox",
        type: "text",
        autoFocus: true,
        defaultValue: node.getName(),
        onKeyDown: onTextBoxKeyPress,
        onPointerDown: onTextBoxPointerDown
      }
    );
  }
  if (node.isEnableClose() && !isStretch) {
    const closeTitle = layout.i18nName(I18nLabel.Close_Tab);
    renderState.buttons.push(
      /* @__PURE__ */ jsx(
        "div",
        {
          "data-layout-path": path + "/button/close",
          title: closeTitle,
          className: cm(CLASSES.FLEXLAYOUT__TAB_BUTTON_TRAILING),
          onPointerDown: onClosePointerDown,
          onClick: onClose,
          children: typeof icons.close === "function" ? icons.close(node) : icons.close
        },
        "close"
      )
    );
  }
  return /* @__PURE__ */ jsxs(
    "div",
    {
      ref: selfRef,
      "data-layout-path": path,
      className: classNames,
      onClick,
      onAuxClick: onAuxMouseClick,
      onContextMenu,
      title: node.getHelpText(),
      draggable: true,
      onDragStart,
      onDragEnd,
      onDoubleClick,
      children: [
        leading,
        content,
        renderState.buttons
      ]
    }
  );
};
const TabSet = (props) => {
  const { node, layout } = props;
  const tabStripRef = React.useRef(null);
  const miniScrollRef = React.useRef(null);
  const tabStripInnerRef = React.useRef(null);
  const contentRef = React.useRef(null);
  const buttonBarRef = React.useRef(null);
  const overflowbuttonRef = React.useRef(null);
  const stickyButtonsRef = React.useRef(null);
  const timer = React.useRef(void 0);
  const icons = layout.getIcons();
  React.useLayoutEffect(() => {
    node.setRect(layout.getBoundingClientRect(selfRef.current));
    if (tabStripRef.current) {
      node.setTabStripRect(layout.getBoundingClientRect(tabStripRef.current));
    }
    const newContentRect = layout.getBoundingClientRect(contentRef.current);
    if (!node.getContentRect().equals(newContentRect) && !isNaN(newContentRect.x)) {
      node.setContentRect(newContentRect);
      if (splitterDragging) {
        if (timer.current) {
          clearTimeout(timer.current);
        }
        timer.current = setTimeout(() => {
          layout.redrawInternal("border content rect " + newContentRect);
          timer.current = void 0;
        }, 50);
      } else {
        layout.redrawInternal("border content rect " + newContentRect);
      }
    }
  });
  const { selfRef, userControlledPositionRef, onScroll, onScrollPointerDown, hiddenTabs, onMouseWheel, isDockStickyButtons, isShowHiddenTabs } = useTabOverflow(
    layout,
    node,
    Orientation.HORZ,
    tabStripInnerRef,
    miniScrollRef,
    layout.getClassName(CLASSES.FLEXLAYOUT__TAB_BUTTON)
  );
  const onOverflowClick = (event) => {
    const callback = layout.getShowOverflowMenu();
    const items = hiddenTabs.map((h) => {
      return { index: h, node: node.getChildren()[h] };
    });
    if (callback !== void 0) {
      callback(node, event, items, onOverflowItemSelect);
    } else {
      const element = overflowbuttonRef.current;
      showPopup(
        element,
        node,
        items,
        onOverflowItemSelect,
        layout
      );
    }
    event.stopPropagation();
  };
  const onOverflowItemSelect = (item) => {
    layout.doAction(Actions.selectTab(item.node.getId()));
    userControlledPositionRef.current = false;
  };
  const onDragStart = (event) => {
    if (!layout.getEditingTab()) {
      if (node.isEnableDrag()) {
        event.stopPropagation();
        layout.setDragNode(event.nativeEvent, node);
      } else {
        event.preventDefault();
      }
    } else {
      event.preventDefault();
    }
  };
  const onPointerDown = (event) => {
    if (!isAuxMouseEvent(event)) {
      layout.doAction(Actions.setActiveTabset(node.getId(), layout.getWindowId()));
    }
  };
  const onAuxMouseClick = (event) => {
    if (isAuxMouseEvent(event)) {
      layout.auxMouseClick(node, event);
    }
  };
  const onContextMenu = (event) => {
    layout.showContextMenu(node, event);
  };
  const onInterceptPointerDown = (event) => {
    event.stopPropagation();
  };
  const onMaximizeToggle = (event) => {
    if (node.canMaximize()) {
      layout.maximize(node);
    }
    event.stopPropagation();
  };
  const onClose = (event) => {
    layout.doAction(Actions.deleteTabset(node.getId()));
    event.stopPropagation();
  };
  const onCloseTab = (event) => {
    layout.doAction(Actions.deleteTab(node.getChildren()[0].getId()));
    event.stopPropagation();
  };
  const onPopoutTab = (event) => {
    if (selectedTabNode !== void 0) {
      layout.doAction(Actions.popoutTab(selectedTabNode.getId()));
    }
    event.stopPropagation();
  };
  const onDoubleClick = (event) => {
    if (node.canMaximize()) {
      layout.maximize(node);
    }
  };
  const cm = layout.getClassName;
  const selectedTabNode = node.getSelectedNode();
  const path = node.getPath();
  const tabs = [];
  if (node.isEnableTabStrip()) {
    for (let i = 0; i < node.getChildren().length; i++) {
      const child = node.getChildren()[i];
      const isSelected = node.getSelected() === i;
      tabs.push(
        /* @__PURE__ */ jsx(
          TabButton,
          {
            layout,
            node: child,
            path: path + "/tb" + i,
            selected: isSelected
          },
          child.getId()
        )
      );
      if (i < node.getChildren().length - 1) {
        tabs.push(
          /* @__PURE__ */ jsx("div", { className: cm(CLASSES.FLEXLAYOUT__TABSET_TAB_DIVIDER) }, "divider" + i)
        );
      }
    }
  }
  let leading = void 0;
  let stickyButtons = [];
  let buttons = [];
  const renderState = { leading, stickyButtons, buttons, overflowPosition: void 0 };
  layout.customizeTabSet(node, renderState);
  leading = renderState.leading;
  stickyButtons = renderState.stickyButtons;
  buttons = renderState.buttons;
  const isTabStretch = node.isEnableSingleTabStretch() && node.getChildren().length === 1;
  const showClose = isTabStretch && node.getChildren()[0].isEnableClose() || node.isEnableClose();
  if (renderState.overflowPosition === void 0) {
    renderState.overflowPosition = stickyButtons.length;
  }
  if (stickyButtons.length > 0) {
    if (!node.isEnableTabWrap() && (isDockStickyButtons || isTabStretch)) {
      buttons = [...stickyButtons, ...buttons];
    } else {
      tabs.push(/* @__PURE__ */ jsx(
        "div",
        {
          ref: stickyButtonsRef,
          onPointerDown: onInterceptPointerDown,
          onDragStart: (e) => {
            e.preventDefault();
          },
          className: cm(CLASSES.FLEXLAYOUT__TAB_TOOLBAR_STICKY_BUTTONS_CONTAINER),
          children: stickyButtons
        },
        "sticky_buttons_container"
      ));
    }
  }
  if (!node.isEnableTabWrap()) {
    if (isShowHiddenTabs) {
      const overflowTitle = layout.i18nName(I18nLabel.Overflow_Menu_Tooltip);
      let overflowContent;
      if (typeof icons.more === "function") {
        const items = hiddenTabs.map((h) => {
          return { index: h, node: node.getChildren()[h] };
        });
        overflowContent = icons.more(node, items);
      } else {
        overflowContent = /* @__PURE__ */ jsxs(Fragment, { children: [
          icons.more,
          /* @__PURE__ */ jsx("div", { className: cm(CLASSES.FLEXLAYOUT__TAB_BUTTON_OVERFLOW_COUNT), children: hiddenTabs.length > 0 ? hiddenTabs.length : "" })
        ] });
      }
      buttons.splice(
        Math.min(renderState.overflowPosition, buttons.length),
        0,
        /* @__PURE__ */ jsx(
          "button",
          {
            "data-layout-path": path + "/button/overflow",
            ref: overflowbuttonRef,
            className: cm(CLASSES.FLEXLAYOUT__TAB_TOOLBAR_BUTTON) + " " + cm(CLASSES.FLEXLAYOUT__TAB_BUTTON_OVERFLOW),
            title: overflowTitle,
            onClick: onOverflowClick,
            onPointerDown: onInterceptPointerDown,
            children: overflowContent
          },
          "overflowbutton"
        )
      );
    }
  }
  if (selectedTabNode !== void 0 && layout.isSupportsPopout() && selectedTabNode.isEnablePopout() && selectedTabNode.isEnablePopoutIcon()) {
    const popoutTitle = layout.i18nName(I18nLabel.Popout_Tab);
    buttons.push(
      /* @__PURE__ */ jsx(
        "button",
        {
          "data-layout-path": path + "/button/popout",
          title: popoutTitle,
          className: cm(CLASSES.FLEXLAYOUT__TAB_TOOLBAR_BUTTON) + " " + cm(CLASSES.FLEXLAYOUT__TAB_TOOLBAR_BUTTON_FLOAT),
          onClick: onPopoutTab,
          onPointerDown: onInterceptPointerDown,
          children: typeof icons.popout === "function" ? icons.popout(selectedTabNode) : icons.popout
        },
        "popout"
      )
    );
  }
  if (node.canMaximize()) {
    const minTitle = layout.i18nName(I18nLabel.Restore);
    const maxTitle = layout.i18nName(I18nLabel.Maximize);
    buttons.push(
      /* @__PURE__ */ jsx(
        "button",
        {
          "data-layout-path": path + "/button/max",
          title: node.isMaximized() ? minTitle : maxTitle,
          className: cm(CLASSES.FLEXLAYOUT__TAB_TOOLBAR_BUTTON) + " " + cm(CLASSES.FLEXLAYOUT__TAB_TOOLBAR_BUTTON_ + (node.isMaximized() ? "max" : "min")),
          onClick: onMaximizeToggle,
          onPointerDown: onInterceptPointerDown,
          children: node.isMaximized() ? typeof icons.restore === "function" ? icons.restore(node) : icons.restore : typeof icons.maximize === "function" ? icons.maximize(node) : icons.maximize
        },
        "max"
      )
    );
  }
  if (!node.isMaximized() && showClose) {
    const title = isTabStretch ? layout.i18nName(I18nLabel.Close_Tab) : layout.i18nName(I18nLabel.Close_Tabset);
    buttons.push(
      /* @__PURE__ */ jsx(
        "button",
        {
          "data-layout-path": path + "/button/close",
          title,
          className: cm(CLASSES.FLEXLAYOUT__TAB_TOOLBAR_BUTTON) + " " + cm(CLASSES.FLEXLAYOUT__TAB_TOOLBAR_BUTTON_CLOSE),
          onClick: isTabStretch ? onCloseTab : onClose,
          onPointerDown: onInterceptPointerDown,
          children: typeof icons.closeTabset === "function" ? icons.closeTabset(node) : icons.closeTabset
        },
        "close"
      )
    );
  }
  if (node.isActive() && node.isEnableActiveIcon()) {
    const title = layout.i18nName(I18nLabel.Active_Tabset);
    buttons.push(
      /* @__PURE__ */ jsx(
        "div",
        {
          "data-layout-path": path + "/button/active",
          title,
          className: cm(CLASSES.FLEXLAYOUT__TAB_TOOLBAR_ICON),
          children: typeof icons.activeTabset === "function" ? icons.activeTabset(node) : icons.activeTabset
        },
        "active"
      )
    );
  }
  const buttonbar = /* @__PURE__ */ jsx(
    "div",
    {
      ref: buttonBarRef,
      className: cm(CLASSES.FLEXLAYOUT__TAB_TOOLBAR),
      onPointerDown: onInterceptPointerDown,
      onDragStart: (e) => {
        e.preventDefault();
      },
      children: buttons
    },
    "buttonbar"
  );
  let tabStrip;
  let tabStripClasses = cm(CLASSES.FLEXLAYOUT__TABSET_TABBAR_OUTER);
  if (node.getClassNameTabStrip() !== void 0) {
    tabStripClasses += " " + node.getClassNameTabStrip();
  }
  tabStripClasses += " " + CLASSES.FLEXLAYOUT__TABSET_TABBAR_OUTER_ + node.getTabLocation();
  if (node.isActive()) {
    tabStripClasses += " " + cm(CLASSES.FLEXLAYOUT__TABSET_SELECTED);
  }
  if (node.isMaximized()) {
    tabStripClasses += " " + cm(CLASSES.FLEXLAYOUT__TABSET_MAXIMIZED);
  }
  if (isTabStretch) {
    const tabNode = node.getChildren()[0];
    if (tabNode.getTabSetClassName() !== void 0) {
      tabStripClasses += " " + tabNode.getTabSetClassName();
    }
  }
  let leadingContainer = void 0;
  if (leading) {
    leadingContainer = /* @__PURE__ */ jsx("div", { className: cm(CLASSES.FLEXLAYOUT__TABSET_LEADING), children: leading });
  }
  if (node.isEnableTabWrap()) {
    if (node.isEnableTabStrip()) {
      tabStrip = /* @__PURE__ */ jsxs(
        "div",
        {
          className: tabStripClasses,
          style: { flexWrap: "wrap", gap: "1px", marginTop: "2px" },
          ref: tabStripRef,
          "data-layout-path": path + "/tabstrip",
          onPointerDown,
          onDoubleClick,
          onContextMenu,
          onClick: onAuxMouseClick,
          onAuxClick: onAuxMouseClick,
          draggable: true,
          onDragStart,
          children: [
            leadingContainer,
            tabs,
            /* @__PURE__ */ jsx("div", { style: { flexGrow: 1 } }),
            buttonbar
          ]
        }
      );
    }
  } else {
    if (node.isEnableTabStrip()) {
      let miniScrollbar = void 0;
      if (node.isEnableTabScrollbar()) {
        miniScrollbar = /* @__PURE__ */ jsx(
          "div",
          {
            ref: miniScrollRef,
            className: cm(CLASSES.FLEXLAYOUT__MINI_SCROLLBAR),
            onPointerDown: onScrollPointerDown
          }
        );
      }
      tabStrip = /* @__PURE__ */ jsxs(
        "div",
        {
          className: tabStripClasses,
          ref: tabStripRef,
          "data-layout-path": path + "/tabstrip",
          onPointerDown,
          onDoubleClick,
          onContextMenu,
          onClick: onAuxMouseClick,
          onAuxClick: onAuxMouseClick,
          draggable: true,
          onWheel: onMouseWheel,
          onDragStart,
          children: [
            leadingContainer,
            /* @__PURE__ */ jsxs("div", { className: cm(CLASSES.FLEXLAYOUT__MINI_SCROLLBAR_CONTAINER), children: [
              /* @__PURE__ */ jsx(
                "div",
                {
                  ref: tabStripInnerRef,
                  className: cm(CLASSES.FLEXLAYOUT__TABSET_TABBAR_INNER) + " " + cm(CLASSES.FLEXLAYOUT__TABSET_TABBAR_INNER_ + node.getTabLocation()),
                  style: { overflowX: "auto", overflowY: "hidden" },
                  onScroll,
                  children: /* @__PURE__ */ jsx(
                    "div",
                    {
                      style: { width: isTabStretch ? "100%" : "none" },
                      className: cm(CLASSES.FLEXLAYOUT__TABSET_TABBAR_INNER_TAB_CONTAINER) + " " + cm(CLASSES.FLEXLAYOUT__TABSET_TABBAR_INNER_TAB_CONTAINER_ + node.getTabLocation()),
                      children: tabs
                    }
                  )
                }
              ),
              miniScrollbar
            ] }),
            buttonbar
          ]
        }
      );
    }
  }
  let emptyTabset;
  if (node.getChildren().length === 0) {
    const placeHolderCallback = layout.getTabSetPlaceHolderCallback();
    if (placeHolderCallback) {
      emptyTabset = placeHolderCallback(node);
    }
  }
  let content = /* @__PURE__ */ jsx("div", { ref: contentRef, className: cm(CLASSES.FLEXLAYOUT__TABSET_CONTENT), children: emptyTabset });
  if (node.getTabLocation() === "top") {
    content = /* @__PURE__ */ jsxs(Fragment, { children: [
      tabStrip,
      content
    ] });
  } else {
    content = /* @__PURE__ */ jsxs(Fragment, { children: [
      content,
      tabStrip
    ] });
  }
  const style2 = {
    flexGrow: Math.max(1, node.getWeight() * 1e3),
    minWidth: node.getMinWidth(),
    minHeight: node.getMinHeight(),
    maxWidth: node.getMaxWidth(),
    maxHeight: node.getMaxHeight()
  };
  if (node.getModel().getMaximizedTabset(layout.getWindowId()) !== void 0 && !node.isMaximized()) {
    style2.display = "none";
  }
  const tabset = /* @__PURE__ */ jsx(
    "div",
    {
      ref: selfRef,
      className: cm(CLASSES.FLEXLAYOUT__TABSET_CONTAINER),
      style: style2,
      children: /* @__PURE__ */ jsx(
        "div",
        {
          className: cm(CLASSES.FLEXLAYOUT__TABSET),
          "data-layout-path": path,
          children: content
        }
      )
    }
  );
  if (node.isMaximized()) {
    if (layout.getMainElement()) {
      return createPortal(
        /* @__PURE__ */ jsx("div", { style: {
          position: "absolute",
          display: "flex",
          top: 0,
          left: 0,
          bottom: 0,
          right: 0
        }, children: tabset }),
        layout.getMainElement()
      );
    } else {
      return tabset;
    }
  } else {
    return tabset;
  }
};
const Row = (props) => {
  const { layout, node } = props;
  const selfRef = React.useRef(null);
  const horizontal = node.getOrientation() === Orientation.HORZ;
  React.useLayoutEffect(() => {
    node.setRect(layout.getBoundingClientRect(selfRef.current));
  });
  const items = [];
  let i = 0;
  for (const child of node.getChildren()) {
    if (i > 0) {
      items.push(/* @__PURE__ */ jsx(Splitter, { layout, node, index: i, horizontal }, "splitter" + i));
    }
    if (child instanceof RowNode) {
      items.push(/* @__PURE__ */ jsx(Row, { layout, node: child }, child.getId()));
    } else if (child instanceof TabSetNode) {
      items.push(/* @__PURE__ */ jsx(TabSet, { layout, node: child }, child.getId()));
    }
    i++;
  }
  const style2 = {
    flexGrow: Math.max(1, node.getWeight() * 1e3),
    // NOTE:  flex-grow cannot have values < 1 otherwise will not fill parent, need to normalize 
    minWidth: node.getMinWidth(),
    minHeight: node.getMinHeight(),
    maxWidth: node.getMaxWidth(),
    maxHeight: node.getMaxHeight()
  };
  if (horizontal) {
    style2.flexDirection = "row";
  } else {
    style2.flexDirection = "column";
  }
  return /* @__PURE__ */ jsx(
    "div",
    {
      ref: selfRef,
      className: layout.getClassName(CLASSES.FLEXLAYOUT__ROW),
      style: style2,
      children: items
    }
  );
};
const Tab = (props) => {
  const { layout, selected, node, path } = props;
  const selfRef = React.useRef(null);
  const firstSelect = React.useRef(true);
  const parentNode = node.getParent();
  const rect = parentNode.getContentRect();
  React.useLayoutEffect(() => {
    const element = node.getMoveableElement();
    selfRef.current.appendChild(element);
    node.setMoveableElement(element);
    const handleScroll = () => {
      node.saveScrollPosition();
    };
    element.addEventListener("scroll", handleScroll);
    selfRef.current.addEventListener("pointerdown", onPointerDown);
    return () => {
      element.removeEventListener("scroll", handleScroll);
      if (selfRef.current) {
        selfRef.current.removeEventListener("pointerdown", onPointerDown);
      }
      node.setVisible(false);
    };
  }, []);
  React.useEffect(() => {
    if (node.isSelected()) {
      if (firstSelect.current) {
        node.restoreScrollPosition();
        firstSelect.current = false;
      }
    }
  });
  const onPointerDown = () => {
    const parent = node.getParent();
    if (parent instanceof TabSetNode) {
      if (!parent.isActive()) {
        layout.doAction(Actions.setActiveTabset(parent.getId(), layout.getWindowId()));
      }
    }
  };
  node.setRect(rect);
  const cm = layout.getClassName;
  const style2 = {};
  rect.styleWithPosition(style2);
  let overlay = null;
  if (selected) {
    node.setVisible(true);
    if (document.hidden && node.isEnablePopoutOverlay()) {
      const overlayStyle = {};
      rect.styleWithPosition(overlayStyle);
      overlay = /* @__PURE__ */ jsx("div", { style: overlayStyle, className: cm(CLASSES.FLEXLAYOUT__TAB_OVERLAY) });
    }
  } else {
    style2.display = "none";
    node.setVisible(false);
  }
  if (parentNode instanceof TabSetNode) {
    if (node.getModel().getMaximizedTabset(layout.getWindowId()) !== void 0) {
      if (parentNode.isMaximized()) {
        style2.zIndex = 10;
      } else {
        style2.display = "none";
      }
    }
  }
  if (parentNode instanceof BorderNode) {
    if (!parentNode.isShowing()) {
      style2.display = "none";
    }
  }
  let className = cm(CLASSES.FLEXLAYOUT__TAB);
  if (parentNode instanceof BorderNode) {
    className += " " + cm(CLASSES.FLEXLAYOUT__TAB_BORDER);
    className += " " + cm(CLASSES.FLEXLAYOUT__TAB_BORDER_ + parentNode.getLocation().getName());
  }
  if (node.getContentClassName() !== void 0) {
    className += " " + node.getContentClassName();
  }
  return /* @__PURE__ */ jsxs(Fragment, { children: [
    overlay,
    /* @__PURE__ */ jsx(
      "div",
      {
        ref: selfRef,
        style: style2,
        className,
        "data-layout-path": path
      }
    )
  ] });
};
class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    __publicField(this, "retry", () => {
      this.setState({ hasError: false });
    });
    this.state = { hasError: false };
  }
  static getDerivedStateFromError(error) {
    return { hasError: true };
  }
  componentDidCatch(error, errorInfo) {
    console.debug(error);
    console.debug(errorInfo);
  }
  render() {
    if (this.state.hasError) {
      return /* @__PURE__ */ jsx("div", { className: CLASSES.FLEXLAYOUT__ERROR_BOUNDARY_CONTAINER, children: /* @__PURE__ */ jsx("div", { className: CLASSES.FLEXLAYOUT__ERROR_BOUNDARY_CONTENT, children: /* @__PURE__ */ jsxs("div", { style: { display: "flex", flexDirection: "column", alignItems: "center" }, children: [
        this.props.message,
        /* @__PURE__ */ jsx("p", { children: /* @__PURE__ */ jsx("button", { onClick: this.retry, children: this.props.retryText }) })
      ] }) }) });
    }
    return this.props.children;
  }
}
const SizeTracker = React.memo(({ layout, node }) => {
  return /* @__PURE__ */ jsx(
    ErrorBoundary,
    {
      message: layout.i18nName(I18nLabel.Error_rendering_component),
      retryText: layout.i18nName(I18nLabel.Error_rendering_component_retry),
      children: layout.props.factory(node)
    }
  );
}, arePropsEqual);
function arePropsEqual(prevProps, nextProps) {
  const reRender = nextProps.visible && (!prevProps.rect.equalSize(nextProps.rect) || prevProps.forceRevision !== nextProps.forceRevision || prevProps.tabsRevision !== nextProps.tabsRevision);
  return !reRender;
}
class Layout extends React.Component {
  // so LayoutInternal knows this is a parent render (used for optimization)
  /** @internal */
  constructor(props) {
    super(props);
    /** @internal */
    __publicField(this, "selfRef");
    /** @internal */
    __publicField(this, "revision");
    this.selfRef = React.createRef();
    this.revision = 0;
  }
  /** re-render the layout */
  redraw() {
    this.selfRef.current.redraw("parent " + this.revision);
  }
  /**
   * Adds a new tab to the given tabset
   * @param tabsetId the id of the tabset where the new tab will be added
   * @param json the json for the new tab node
   * @returns the added tab node or undefined
   */
  addTabToTabSet(tabsetId, json) {
    return this.selfRef.current.addTabToTabSet(tabsetId, json);
  }
  /**
   * Adds a new tab by dragging an item to the drop location, must be called from within an HTML
   * drag start handler. You can use the setDragComponent() method to set the drag image before calling this 
   * method.
   * @param event the drag start event
   * @param json the json for the new tab node
   * @param onDrop a callback to call when the drag is complete
   */
  addTabWithDragAndDrop(event, json, onDrop) {
    this.selfRef.current.addTabWithDragAndDrop(event, json, onDrop);
  }
  /**
   * Move a tab/tabset using drag and drop, must be called from within an HTML
   * drag start handler
   * @param event the drag start event
   * @param node the tab or tabset to drag
   */
  moveTabWithDragAndDrop(event, node) {
    this.selfRef.current.moveTabWithDragAndDrop(event, node);
  }
  /**
   * Adds a new tab to the active tabset (if there is one)
   * @param json the json for the new tab node
   * @returns the added tab node or undefined
   */
  addTabToActiveTabSet(json) {
    return this.selfRef.current.addTabToActiveTabSet(json);
  }
  /**
   * Sets the drag image from a react component for a drag event
   * @param event the drag event
   * @param component the react component to be used for the drag image
   * @param x the x position of the drag cursor on the image
   * @param y the x position of the drag cursor on the image
   */
  setDragComponent(event, component, x, y) {
    this.selfRef.current.setDragComponent(event, component, x, y);
  }
  /** Get the root div element of the layout */
  getRootDiv() {
    return this.selfRef.current.getRootDiv();
  }
  /** @internal */
  render() {
    return /* @__PURE__ */ jsx(LayoutInternal, { ref: this.selfRef, ...this.props, renderRevision: this.revision++ });
  }
}
const _LayoutInternal = class _LayoutInternal extends React.Component {
  // private renderCount: any;
  constructor(props) {
    super(props);
    __publicField(this, "selfRef");
    __publicField(this, "moveablesRef");
    __publicField(this, "findBorderBarSizeRef");
    __publicField(this, "mainRef");
    __publicField(this, "previousModel");
    __publicField(this, "orderedTabIds");
    __publicField(this, "orderedTabMoveableIds");
    __publicField(this, "moveableElementMap", /* @__PURE__ */ new Map());
    __publicField(this, "dropInfo");
    __publicField(this, "outlineDiv");
    __publicField(this, "currentDocument");
    __publicField(this, "currentWindow");
    __publicField(this, "supportsPopout");
    __publicField(this, "popoutURL");
    __publicField(this, "icons");
    __publicField(this, "resizeObserver");
    __publicField(this, "dragEnterCount", 0);
    __publicField(this, "dragging", false);
    __publicField(this, "windowId");
    __publicField(this, "layoutWindow");
    __publicField(this, "mainLayout");
    __publicField(this, "isMainWindow");
    __publicField(this, "isDraggingOverWindow");
    __publicField(this, "styleObserver");
    __publicField(this, "popoutWindowName");
    __publicField(this, "updateLayoutMetrics", () => {
      if (this.findBorderBarSizeRef.current) {
        const borderBarSize = this.findBorderBarSizeRef.current.getBoundingClientRect().height;
        if (borderBarSize !== this.state.calculatedBorderBarSize) {
          this.setState({ calculatedBorderBarSize: borderBarSize });
        }
      }
    });
    __publicField(this, "onModelChange", (action) => {
      this.redrawInternal("model change");
      if (this.props.onModelChange) {
        this.props.onModelChange(this.props.model, action);
      }
    });
    __publicField(this, "updateRect", () => {
      if (this.selfRef.current) {
        const rect = Rect.fromDomRect(this.selfRef.current.getBoundingClientRect());
        if (!rect.equals(this.state.rect) && rect.width !== 0 && rect.height !== 0) {
          this.setState({ rect });
          if (this.windowId !== Model.MAIN_WINDOW_ID) {
            this.redrawInternal("rect updated");
          }
        }
      }
    });
    __publicField(this, "getClassName", (defaultClassName) => {
      if (this.props.classNameMapper === void 0) {
        return defaultClassName;
      } else {
        return this.props.classNameMapper(defaultClassName);
      }
    });
    __publicField(this, "onCloseWindow", (windowLayout) => {
      this.doAction(Actions.closeWindow(windowLayout.windowId));
    });
    __publicField(this, "onSetWindow", (windowLayout, window2) => {
    });
    __publicField(this, "showControlInPortal", (control, element) => {
      const portal = createPortal(control, element);
      this.setState({ portal });
    });
    __publicField(this, "hideControlInPortal", () => {
      this.setState({ portal: void 0 });
    });
    __publicField(this, "getIcons", () => {
      return this.icons;
    });
    __publicField(this, "setDragNode", (event, node) => {
      _LayoutInternal.dragState = new DragState(this.mainLayout, "internal", node, void 0, void 0);
      event.dataTransfer.setData("text/plain", "--flexlayout--");
      event.dataTransfer.effectAllowed = "copyMove";
      event.dataTransfer.dropEffect = "move";
      this.dragEnterCount = 0;
      if (node instanceof TabSetNode) {
        let rendered = false;
        let content = this.i18nName(I18nLabel.Move_Tabset);
        if (node.getChildren().length > 0) {
          content = this.i18nName(I18nLabel.Move_Tabs).replace("?", String(node.getChildren().length));
        }
        if (this.props.onRenderDragRect) {
          const dragComponent = this.props.onRenderDragRect(content, node, void 0);
          if (dragComponent) {
            this.setDragComponent(event, dragComponent, 10, 10);
            rendered = true;
          }
        }
        if (!rendered) {
          this.setDragComponent(event, content, 10, 10);
        }
      } else {
        const element = event.target;
        const rect = element.getBoundingClientRect();
        const offsetX = event.clientX - rect.left;
        const offsetY = event.clientY - rect.top;
        const parentNode = node == null ? void 0 : node.getParent();
        const isInVerticalBorder = parentNode instanceof BorderNode && parentNode.getOrientation() === Orientation.HORZ;
        const x = isInVerticalBorder ? 10 : offsetX;
        const y = isInVerticalBorder ? 10 : offsetY;
        let rendered = false;
        if (this.props.onRenderDragRect) {
          const content = /* @__PURE__ */ jsx(TabButtonStamp, { layout: this, node }, node.getId());
          const dragComponent = this.props.onRenderDragRect(content, node, void 0);
          if (dragComponent) {
            this.setDragComponent(event, dragComponent, x, y);
            rendered = true;
          }
        }
        if (!rendered) {
          if (isSafari()) {
            this.setDragComponent(event, /* @__PURE__ */ jsx(TabButtonStamp, { node, layout: this }), x, y);
          } else {
            event.dataTransfer.setDragImage(node.getTabStamp(), x, y);
          }
        }
      }
    });
    __publicField(this, "onDragEnterRaw", (event) => {
      this.dragEnterCount++;
      if (this.dragEnterCount === 1) {
        this.onDragEnter(event);
      }
    });
    __publicField(this, "onDragLeaveRaw", (event) => {
      this.dragEnterCount--;
      if (this.dragEnterCount === 0) {
        this.onDragLeave(event);
      }
    });
    __publicField(this, "onDragEnter", (event) => {
      if (!_LayoutInternal.dragState && this.props.onExternalDrag) {
        const externalDrag = this.props.onExternalDrag(event);
        if (externalDrag) {
          const tempNode = TabNode.fromJson(externalDrag.json, this.props.model, false);
          _LayoutInternal.dragState = new DragState(this.mainLayout, "external", tempNode, externalDrag.json, externalDrag.onDrop);
        }
      }
      if (_LayoutInternal.dragState) {
        if (this.windowId !== Model.MAIN_WINDOW_ID && _LayoutInternal.dragState.mainLayout === this.mainLayout) {
          _LayoutInternal.dragState.mainLayout.setDraggingOverWindow(true);
        }
        if (_LayoutInternal.dragState.mainLayout !== this.mainLayout) {
          return;
        }
        event.preventDefault();
        this.dropInfo = void 0;
        const rootdiv = this.selfRef.current;
        this.outlineDiv = this.currentDocument.createElement("div");
        this.outlineDiv.className = this.getClassName(CLASSES.FLEXLAYOUT__OUTLINE_RECT);
        this.outlineDiv.style.visibility = "hidden";
        const speed = this.props.model.getAttribute("tabDragSpeed");
        this.outlineDiv.style.transition = `top ${speed}s, left ${speed}s, width ${speed}s, height ${speed}s`;
        rootdiv.appendChild(this.outlineDiv);
        this.dragging = true;
        this.showOverlay(true);
        if (!this.isDraggingOverWindow && this.props.model.getMaximizedTabset(this.windowId) === void 0) {
          this.setState({ showEdges: this.props.model.isEnableEdgeDock() });
        }
        const clientRect = this.selfRef.current.getBoundingClientRect();
        const r = new Rect(
          event.clientX - clientRect.left,
          event.clientY - clientRect.top,
          1,
          1
        );
        r.positionElement(this.outlineDiv);
      }
    });
    __publicField(this, "onDragOver", (event) => {
      var _a;
      if (this.dragging && !this.isDraggingOverWindow) {
        event.preventDefault();
        const clientRect = (_a = this.selfRef.current) == null ? void 0 : _a.getBoundingClientRect();
        const pos = {
          x: event.clientX - ((clientRect == null ? void 0 : clientRect.left) ?? 0),
          y: event.clientY - ((clientRect == null ? void 0 : clientRect.top) ?? 0)
        };
        this.checkForBorderToShow(pos.x, pos.y);
        const dropInfo = this.props.model.findDropTargetNode(this.windowId, _LayoutInternal.dragState.dragNode, pos.x, pos.y);
        if (dropInfo) {
          this.dropInfo = dropInfo;
          if (this.outlineDiv) {
            this.outlineDiv.className = this.getClassName(dropInfo.className);
            dropInfo.rect.positionElement(this.outlineDiv);
            this.outlineDiv.style.visibility = "visible";
          }
        }
      }
    });
    __publicField(this, "onDragLeave", (event) => {
      if (this.dragging) {
        if (this.windowId !== Model.MAIN_WINDOW_ID) {
          _LayoutInternal.dragState.mainLayout.setDraggingOverWindow(false);
        }
        this.clearDragLocal();
      }
    });
    __publicField(this, "onDrop", (event) => {
      if (this.dragging) {
        event.preventDefault();
        const dragState = _LayoutInternal.dragState;
        if (this.dropInfo) {
          if (dragState.dragJson !== void 0) {
            const newNode = this.doAction(Actions.addNode(dragState.dragJson, this.dropInfo.node.getId(), this.dropInfo.location, this.dropInfo.index));
            if (dragState.fnNewNodeDropped !== void 0) {
              dragState.fnNewNodeDropped(newNode, event);
            }
          } else if (dragState.dragNode !== void 0) {
            this.doAction(Actions.moveNode(dragState.dragNode.getId(), this.dropInfo.node.getId(), this.dropInfo.location, this.dropInfo.index));
          }
        }
        this.mainLayout.clearDragMain();
      }
      this.dragEnterCount = 0;
    });
    this.orderedTabIds = [];
    this.orderedTabMoveableIds = [];
    this.selfRef = React.createRef();
    this.moveablesRef = React.createRef();
    this.mainRef = React.createRef();
    this.findBorderBarSizeRef = React.createRef();
    this.supportsPopout = props.supportsPopout !== void 0 ? props.supportsPopout : defaultSupportsPopout;
    this.popoutURL = props.popoutURL ? props.popoutURL : "popout.html";
    this.icons = { ...defaultIcons, ...props.icons };
    this.windowId = props.windowId ? props.windowId : Model.MAIN_WINDOW_ID;
    this.mainLayout = this.props.mainLayout ? this.props.mainLayout : this;
    this.isDraggingOverWindow = false;
    this.layoutWindow = this.props.model.getwindowsMap().get(this.windowId);
    this.layoutWindow.layout = this;
    this.popoutWindowName = this.props.popoutWindowName || "Popout Window";
    this.state = {
      rect: Rect.empty(),
      editingTab: void 0,
      showEdges: false,
      showOverlay: false,
      calculatedBorderBarSize: 29,
      layoutRevision: 0,
      forceRevision: 0,
      showHiddenBorder: DockLocation.CENTER
    };
    this.isMainWindow = this.windowId === Model.MAIN_WINDOW_ID;
  }
  componentDidMount() {
    this.updateRect();
    this.currentDocument = this.selfRef.current.ownerDocument;
    this.currentWindow = this.currentDocument.defaultView;
    this.layoutWindow.window = this.currentWindow;
    this.layoutWindow.toScreenRectFunction = (r) => this.getScreenRect(r);
    this.resizeObserver = new ResizeObserver((entries) => {
      requestAnimationFrame(() => {
        this.updateRect();
      });
    });
    if (this.selfRef.current) {
      this.resizeObserver.observe(this.selfRef.current);
    }
    if (this.isMainWindow) {
      this.props.model.addChangeListener(this.onModelChange);
      this.updateLayoutMetrics();
    } else {
      this.currentWindow.addEventListener("resize", () => {
        this.updateRect();
      });
      const sourceElement = this.props.mainLayout.getRootDiv();
      const targetElement = this.selfRef.current;
      copyInlineStyles(sourceElement, targetElement);
      this.styleObserver = new MutationObserver(() => {
        const changed = copyInlineStyles(sourceElement, targetElement);
        if (changed) {
          this.redraw("mutation observer");
        }
      });
      this.styleObserver.observe(sourceElement, { attributeFilter: ["style"] });
    }
    document.addEventListener("visibilitychange", () => {
      for (const [_, layoutWindow] of this.props.model.getwindowsMap()) {
        const layout = layoutWindow.layout;
        if (layout) {
          this.redraw("visibility change");
        }
      }
    });
  }
  componentDidUpdate() {
    this.currentDocument = this.selfRef.current.ownerDocument;
    this.currentWindow = this.currentDocument.defaultView;
    if (this.isMainWindow) {
      if (this.props.model !== this.previousModel) {
        if (this.previousModel !== void 0) {
          this.previousModel.removeChangeListener(this.onModelChange);
        }
        this.props.model.getwindowsMap().get(this.windowId).layout = this;
        this.props.model.addChangeListener(this.onModelChange);
        this.layoutWindow = this.props.model.getwindowsMap().get(this.windowId);
        this.layoutWindow.layout = this;
        this.layoutWindow.toScreenRectFunction = (r) => this.getScreenRect(r);
        this.previousModel = this.props.model;
        this.tidyMoveablesMap();
      }
      this.updateLayoutMetrics();
    }
  }
  componentWillUnmount() {
    var _a, _b;
    if (this.selfRef.current) {
      (_a = this.resizeObserver) == null ? void 0 : _a.unobserve(this.selfRef.current);
    }
    if (this.isMainWindow) {
      this.props.model.removeChangeListener(this.onModelChange);
    }
    (_b = this.styleObserver) == null ? void 0 : _b.disconnect();
  }
  render() {
    if (!this.selfRef.current) {
      return /* @__PURE__ */ jsxs("div", { ref: this.selfRef, className: this.getClassName(CLASSES.FLEXLAYOUT__LAYOUT), children: [
        /* @__PURE__ */ jsx("div", { ref: this.moveablesRef, className: this.getClassName(CLASSES.FLEXLAYOUT__LAYOUT_MOVEABLES) }, "__moveables__"),
        this.renderMetricsElements()
      ] });
    }
    const model = this.props.model;
    model.getRoot(this.windowId).calcMinMaxSize();
    model.getRoot(this.windowId).setPaths("");
    model.getBorderSet().setPaths();
    const inner = this.renderLayout();
    const outer = this.renderBorders(inner);
    const tabs = this.renderTabs();
    const reorderedTabs = this.reorderComponents(tabs, this.orderedTabIds);
    let floatingWindows = null;
    let reorderedTabMoveables = null;
    let tabStamps = null;
    let metricElements = null;
    if (this.isMainWindow) {
      floatingWindows = this.renderWindows();
      metricElements = this.renderMetricsElements();
      const tabMoveables = this.renderTabMoveables();
      reorderedTabMoveables = this.reorderComponents(tabMoveables, this.orderedTabMoveableIds);
      tabStamps = /* @__PURE__ */ jsx("div", { className: this.getClassName(CLASSES.FLEXLAYOUT__LAYOUT_TAB_STAMPS), children: this.renderTabStamps() }, "__tabStamps__");
    }
    return /* @__PURE__ */ jsxs(
      "div",
      {
        ref: this.selfRef,
        className: this.getClassName(CLASSES.FLEXLAYOUT__LAYOUT),
        onDragEnter: this.onDragEnterRaw,
        onDragLeave: this.onDragLeaveRaw,
        onDragOver: this.onDragOver,
        onDrop: this.onDrop,
        children: [
          /* @__PURE__ */ jsx("div", { ref: this.moveablesRef, className: this.getClassName(CLASSES.FLEXLAYOUT__LAYOUT_MOVEABLES) }, "__moveables__"),
          metricElements,
          /* @__PURE__ */ jsx(Overlay, { layout: this, show: this.state.showOverlay }, "__overlay__"),
          outer,
          reorderedTabs,
          reorderedTabMoveables,
          tabStamps,
          this.state.portal,
          floatingWindows
        ]
      }
    );
  }
  renderBorders(inner) {
    const classMain = this.getClassName(CLASSES.FLEXLAYOUT__LAYOUT_MAIN);
    const borders = this.props.model.getBorderSet().getBorderMap();
    if (this.isMainWindow && borders.size > 0) {
      inner = /* @__PURE__ */ jsx("div", { className: classMain, ref: this.mainRef, children: inner });
      const borderSetComponents = /* @__PURE__ */ new Map();
      const borderSetContentComponents = /* @__PURE__ */ new Map();
      for (const [_, location] of DockLocation.values) {
        const border = borders.get(location);
        const showBorder = border && border.isShowing() && (!border.isAutoHide() || border.isAutoHide() && (border.getChildren().length > 0 || this.state.showHiddenBorder === location));
        if (showBorder) {
          borderSetComponents.set(location, /* @__PURE__ */ jsx(BorderTabSet, { layout: this, border, size: this.state.calculatedBorderBarSize }));
          borderSetContentComponents.set(location, /* @__PURE__ */ jsx(BorderTab, { layout: this, border, show: border.getSelected() !== -1 }));
        }
      }
      const classBorderOuter = this.getClassName(CLASSES.FLEXLAYOUT__LAYOUT_BORDER_CONTAINER);
      const classBorderInner = this.getClassName(CLASSES.FLEXLAYOUT__LAYOUT_BORDER_CONTAINER_INNER);
      if (this.props.model.getBorderSet().getLayoutHorizontal()) {
        const innerWithBorderTabs = /* @__PURE__ */ jsxs("div", { className: classBorderInner, style: { flexDirection: "column" }, children: [
          borderSetContentComponents.get(DockLocation.TOP),
          /* @__PURE__ */ jsxs("div", { className: classBorderInner, style: { flexDirection: "row" }, children: [
            borderSetContentComponents.get(DockLocation.LEFT),
            inner,
            borderSetContentComponents.get(DockLocation.RIGHT)
          ] }),
          borderSetContentComponents.get(DockLocation.BOTTOM)
        ] });
        return /* @__PURE__ */ jsxs("div", { className: classBorderOuter, style: { flexDirection: "column" }, children: [
          borderSetComponents.get(DockLocation.TOP),
          /* @__PURE__ */ jsxs("div", { className: classBorderInner, style: { flexDirection: "row" }, children: [
            borderSetComponents.get(DockLocation.LEFT),
            innerWithBorderTabs,
            borderSetComponents.get(DockLocation.RIGHT)
          ] }),
          borderSetComponents.get(DockLocation.BOTTOM)
        ] });
      } else {
        const innerWithBorderTabs = /* @__PURE__ */ jsxs("div", { className: classBorderInner, style: { flexDirection: "row" }, children: [
          borderSetContentComponents.get(DockLocation.LEFT),
          /* @__PURE__ */ jsxs("div", { className: classBorderInner, style: { flexDirection: "column" }, children: [
            borderSetContentComponents.get(DockLocation.TOP),
            inner,
            borderSetContentComponents.get(DockLocation.BOTTOM)
          ] }),
          borderSetContentComponents.get(DockLocation.RIGHT)
        ] });
        return /* @__PURE__ */ jsxs("div", { className: classBorderOuter, style: { flexDirection: "row" }, children: [
          borderSetComponents.get(DockLocation.LEFT),
          /* @__PURE__ */ jsxs("div", { className: classBorderInner, style: { flexDirection: "column" }, children: [
            borderSetComponents.get(DockLocation.TOP),
            innerWithBorderTabs,
            borderSetComponents.get(DockLocation.BOTTOM)
          ] }),
          borderSetComponents.get(DockLocation.RIGHT)
        ] });
      }
    } else {
      return /* @__PURE__ */ jsx("div", { className: classMain, ref: this.mainRef, style: { position: "absolute", top: 0, left: 0, bottom: 0, right: 0, display: "flex" }, children: inner });
    }
  }
  renderLayout() {
    return /* @__PURE__ */ jsxs(Fragment, { children: [
      /* @__PURE__ */ jsx(Row, { layout: this, node: this.props.model.getRoot(this.windowId) }, "__row__"),
      this.renderEdgeIndicators()
    ] });
  }
  renderEdgeIndicators() {
    const edges = [];
    const arrowIcon = this.icons.edgeArrow;
    if (this.state.showEdges) {
      const r = this.props.model.getRoot(this.windowId).getRect();
      const length = edgeRectLength;
      const width = edgeRectWidth;
      const offset = edgeRectLength / 2;
      const className = this.getClassName(CLASSES.FLEXLAYOUT__EDGE_RECT);
      const radius = 50;
      edges.push(/* @__PURE__ */ jsx("div", { style: { top: 0, left: r.width / 2 - offset, width: length, height: width, borderBottomLeftRadius: radius, borderBottomRightRadius: radius }, className: className + " " + this.getClassName(CLASSES.FLEXLAYOUT__EDGE_RECT_TOP), children: /* @__PURE__ */ jsx("div", { style: { transform: "rotate(180deg)" }, children: arrowIcon }) }, "North"));
      edges.push(/* @__PURE__ */ jsx("div", { style: { top: r.height / 2 - offset, left: 0, width, height: length, borderTopRightRadius: radius, borderBottomRightRadius: radius }, className: className + " " + this.getClassName(CLASSES.FLEXLAYOUT__EDGE_RECT_LEFT), children: /* @__PURE__ */ jsx("div", { style: { transform: "rotate(90deg)" }, children: arrowIcon }) }, "West"));
      edges.push(/* @__PURE__ */ jsx("div", { style: { top: r.height - width, left: r.width / 2 - offset, width: length, height: width, borderTopLeftRadius: radius, borderTopRightRadius: radius }, className: className + " " + this.getClassName(CLASSES.FLEXLAYOUT__EDGE_RECT_BOTTOM), children: /* @__PURE__ */ jsx("div", { children: arrowIcon }) }, "South"));
      edges.push(/* @__PURE__ */ jsx("div", { style: { top: r.height / 2 - offset, left: r.width - width, width, height: length, borderTopLeftRadius: radius, borderBottomLeftRadius: radius }, className: className + " " + this.getClassName(CLASSES.FLEXLAYOUT__EDGE_RECT_RIGHT), children: /* @__PURE__ */ jsx("div", { style: { transform: "rotate(-90deg)" }, children: arrowIcon }) }, "East"));
    }
    return edges;
  }
  renderWindows() {
    const floatingWindows = [];
    if (this.supportsPopout) {
      const windows = this.props.model.getwindowsMap();
      let i = 1;
      for (const [windowId, layoutWindow] of windows) {
        if (windowId !== Model.MAIN_WINDOW_ID) {
          floatingWindows.push(
            /* @__PURE__ */ jsx(
              PopoutWindow,
              {
                layout: this,
                title: this.popoutWindowName + " " + i,
                layoutWindow,
                url: this.popoutURL + "?id=" + windowId,
                onSetWindow: this.onSetWindow,
                onCloseWindow: this.onCloseWindow,
                children: /* @__PURE__ */ jsx("div", { className: this.props.popoutClassName, children: /* @__PURE__ */ jsx(_LayoutInternal, { ...this.props, windowId, mainLayout: this }) })
              },
              windowId
            )
          );
          i++;
        }
      }
    }
    return floatingWindows;
  }
  renderTabMoveables() {
    const tabMoveables = /* @__PURE__ */ new Map();
    this.props.model.visitNodes((node) => {
      if (node instanceof TabNode) {
        const child = node;
        const element = this.getMoveableElement(child.getId());
        child.setMoveableElement(element);
        const selected = child.isSelected();
        const rect = child.getParent().getContentRect();
        const visible = selected || !child.isEnableRenderOnDemand();
        const renderTab = child.isRendered() || visible && (rect.width > 0 && rect.height > 0);
        if (renderTab) {
          const key = child.getId() + (child.isEnableWindowReMount() ? child.getWindowId() : "");
          tabMoveables.set(node.getId(), createPortal(
            /* @__PURE__ */ jsx(
              SizeTracker,
              {
                layout: this,
                node: child,
                rect,
                visible,
                forceRevision: this.state.forceRevision,
                tabsRevision: this.props.renderRevision
              },
              key
            ),
            element,
            key
          ));
          child.setRendered(renderTab);
        }
      }
    });
    return tabMoveables;
  }
  renderTabStamps() {
    const tabStamps = [];
    this.props.model.visitNodes((node) => {
      if (node instanceof TabNode) {
        const child = node;
        tabStamps.push(/* @__PURE__ */ jsx(DragContainer, { layout: this, node: child }, child.getId()));
      }
    });
    return tabStamps;
  }
  renderTabs() {
    const tabs = /* @__PURE__ */ new Map();
    this.props.model.visitWindowNodes(this.windowId, (node) => {
      if (node instanceof TabNode) {
        const child = node;
        const selected = child.isSelected();
        const path = child.getPath();
        const renderTab = child.isRendered() || selected || !child.isEnableRenderOnDemand();
        if (renderTab) {
          tabs.set(child.getId(), /* @__PURE__ */ jsx(
            Tab,
            {
              layout: this,
              path,
              node: child,
              selected
            },
            child.getId()
          ));
        }
      }
    });
    return tabs;
  }
  renderMetricsElements() {
    return /* @__PURE__ */ jsx("div", { ref: this.findBorderBarSizeRef, className: this.getClassName(CLASSES.FLEXLAYOUT__BORDER_SIZER), children: "FindBorderBarSize" }, "findBorderBarSize");
  }
  checkForBorderToShow(x, y) {
    const r = this.getBoundingClientRect(this.mainRef.current);
    const c = r.getCenter();
    const margin = edgeRectWidth;
    const offset = edgeRectLength / 2;
    let overEdge = false;
    if (this.props.model.isEnableEdgeDock() && this.state.showHiddenBorder === DockLocation.CENTER) {
      if (y > c.y - offset && y < c.y + offset || x > c.x - offset && x < c.x + offset) {
        overEdge = true;
      }
    }
    let location = DockLocation.CENTER;
    if (!overEdge) {
      if (x <= r.x + margin) {
        location = DockLocation.LEFT;
      } else if (x >= r.getRight() - margin) {
        location = DockLocation.RIGHT;
      } else if (y <= r.y + margin) {
        location = DockLocation.TOP;
      } else if (y >= r.getBottom() - margin) {
        location = DockLocation.BOTTOM;
      }
    }
    if (location !== this.state.showHiddenBorder) {
      this.setState({ showHiddenBorder: location });
    }
  }
  tidyMoveablesMap() {
    const tabs = /* @__PURE__ */ new Map();
    this.props.model.visitNodes((node, _) => {
      if (node instanceof TabNode) {
        tabs.set(node.getId(), node);
      }
    });
    for (const [nodeId, element] of this.moveableElementMap) {
      if (!tabs.has(nodeId)) {
        element.remove();
        this.moveableElementMap.delete(nodeId);
      }
    }
  }
  reorderComponents(components, ids) {
    const nextIds = [];
    const nextIdsSet = /* @__PURE__ */ new Set();
    let reordered = [];
    for (const id of ids) {
      if (components.get(id)) {
        nextIds.push(id);
        nextIdsSet.add(id);
      }
    }
    ids.splice(0, ids.length, ...nextIds);
    for (const [id, _] of components) {
      if (!nextIdsSet.has(id)) {
        ids.push(id);
      }
    }
    reordered = ids.map((id) => {
      return components.get(id);
    });
    return reordered;
  }
  redraw(type) {
    this.mainLayout.setState((state, props) => {
      return { forceRevision: state.forceRevision + 1 };
    });
  }
  redrawInternal(type) {
    this.mainLayout.setState((state, props) => {
      return { layoutRevision: state.layoutRevision + 1 };
    });
  }
  doAction(action) {
    if (this.props.onAction !== void 0) {
      const outcome = this.props.onAction(action);
      if (outcome !== void 0) {
        return this.props.model.doAction(outcome);
      }
      return void 0;
    } else {
      return this.props.model.doAction(action);
    }
  }
  getBoundingClientRect(div) {
    const layoutRect = this.getDomRect();
    if (layoutRect) {
      return Rect.getBoundingClientRect(div).relativeTo(layoutRect);
    }
    return Rect.empty();
  }
  getMoveableContainer() {
    return this.moveablesRef.current;
  }
  getMoveableElement(id) {
    let moveableElement = this.moveableElementMap.get(id);
    if (moveableElement === void 0) {
      moveableElement = document.createElement("div");
      this.moveablesRef.current.appendChild(moveableElement);
      moveableElement.className = CLASSES.FLEXLAYOUT__TAB_MOVEABLE;
      this.moveableElementMap.set(id, moveableElement);
    }
    return moveableElement;
  }
  getMainLayout() {
    return this.mainLayout;
  }
  getCurrentDocument() {
    return this.currentDocument;
  }
  getDomRect() {
    if (this.selfRef.current) {
      return Rect.fromDomRect(this.selfRef.current.getBoundingClientRect());
    } else {
      return Rect.empty();
    }
  }
  getWindowId() {
    return this.windowId;
  }
  getRootDiv() {
    return this.selfRef.current;
  }
  getMainElement() {
    return this.mainRef.current;
  }
  getFactory() {
    return this.props.factory;
  }
  isSupportsPopout() {
    return this.supportsPopout;
  }
  isRealtimeResize() {
    return this.props.realtimeResize ?? false;
  }
  getPopoutURL() {
    return this.popoutURL;
  }
  setEditingTab(tabNode) {
    this.setState({ editingTab: tabNode });
  }
  getEditingTab() {
    return this.state.editingTab;
  }
  getModel() {
    return this.props.model;
  }
  getScreenRect(inRect) {
    const rect = inRect.clone();
    const layoutRect = this.getDomRect();
    const navHeight = 60;
    const navWidth = 2;
    rect.x = this.currentWindow.screenX + this.currentWindow.scrollX + navWidth / 2 + layoutRect.x + rect.x;
    rect.y = this.currentWindow.screenY + this.currentWindow.scrollY + (navHeight - navWidth / 2) + layoutRect.y + rect.y;
    rect.height += navHeight;
    rect.width += navWidth;
    return rect;
  }
  addTabToTabSet(tabsetId, json) {
    const tabsetNode = this.props.model.getNodeById(tabsetId);
    if (tabsetNode !== void 0) {
      const node = this.doAction(Actions.addNode(json, tabsetId, DockLocation.CENTER, -1));
      return node;
    }
    return void 0;
  }
  addTabToActiveTabSet(json) {
    const tabsetNode = this.props.model.getActiveTabset(this.windowId);
    if (tabsetNode !== void 0) {
      const node = this.doAction(Actions.addNode(json, tabsetNode.getId(), DockLocation.CENTER, -1));
      return node;
    }
    return void 0;
  }
  maximize(tabsetNode) {
    this.doAction(Actions.maximizeToggle(tabsetNode.getId(), this.getWindowId()));
  }
  customizeTab(tabNode, renderValues) {
    if (this.props.onRenderTab) {
      this.props.onRenderTab(tabNode, renderValues);
    }
  }
  customizeTabSet(tabSetNode, renderValues) {
    if (this.props.onRenderTabSet) {
      this.props.onRenderTabSet(tabSetNode, renderValues);
    }
  }
  i18nName(id, param) {
    let message;
    if (this.props.i18nMapper) {
      message = this.props.i18nMapper(id, param);
    }
    if (message === void 0) {
      message = id + (param === void 0 ? "" : param);
    }
    return message;
  }
  getShowOverflowMenu() {
    return this.props.onShowOverflowMenu;
  }
  getTabSetPlaceHolderCallback() {
    return this.props.onTabSetPlaceHolder;
  }
  showContextMenu(node, event) {
    if (this.props.onContextMenu) {
      this.props.onContextMenu(node, event);
    }
  }
  auxMouseClick(node, event) {
    if (this.props.onAuxMouseClick) {
      this.props.onAuxMouseClick(node, event);
    }
  }
  showOverlay(show) {
    this.setState({ showOverlay: show });
    enablePointerOnIFrames(!show, this.currentDocument);
  }
  // *************************** Start Drag Drop *************************************
  addTabWithDragAndDrop(event, json, onDrop) {
    const tempNode = TabNode.fromJson(json, this.props.model, false);
    _LayoutInternal.dragState = new DragState(this.mainLayout, "add", tempNode, json, onDrop);
  }
  moveTabWithDragAndDrop(event, node) {
    this.setDragNode(event, node);
  }
  setDragComponent(event, component, x, y) {
    const dragElement = /* @__PURE__ */ jsx(
      "div",
      {
        style: { position: "unset" },
        className: this.getClassName(CLASSES.FLEXLAYOUT__LAYOUT) + " " + this.getClassName(CLASSES.FLEXLAYOUT__DRAG_RECT),
        children: component
      }
    );
    const tempDiv = this.currentDocument.createElement("div");
    tempDiv.setAttribute("data-layout-path", "/drag-rectangle");
    tempDiv.style.position = "absolute";
    tempDiv.style.left = "-10000px";
    tempDiv.style.top = "-10000px";
    this.currentDocument.body.appendChild(tempDiv);
    createRoot(tempDiv).render(dragElement);
    event.dataTransfer.setDragImage(tempDiv, x, y);
    setTimeout(() => {
      this.currentDocument.body.removeChild(tempDiv);
    }, 0);
  }
  setDraggingOverWindow(overWindow) {
    if (this.isDraggingOverWindow !== overWindow) {
      if (this.outlineDiv) {
        this.outlineDiv.style.visibility = overWindow ? "hidden" : "visible";
      }
      if (overWindow) {
        this.setState({ showEdges: false });
      } else {
        if (this.props.model.getMaximizedTabset(this.windowId) === void 0) {
          this.setState({ showEdges: this.props.model.isEnableEdgeDock() });
        }
      }
      this.isDraggingOverWindow = overWindow;
    }
  }
  clearDragMain() {
    _LayoutInternal.dragState = void 0;
    if (this.windowId === Model.MAIN_WINDOW_ID) {
      this.isDraggingOverWindow = false;
    }
    for (const [, layoutWindow] of this.props.model.getwindowsMap()) {
      layoutWindow.layout.clearDragLocal();
    }
  }
  clearDragLocal() {
    this.setState({ showEdges: false });
    this.showOverlay(false);
    this.dragEnterCount = 0;
    this.dragging = false;
    if (this.outlineDiv) {
      this.selfRef.current.removeChild(this.outlineDiv);
      this.outlineDiv = void 0;
    }
  }
  // *************************** End Drag Drop *************************************
};
__publicField(_LayoutInternal, "dragState");
let LayoutInternal = _LayoutInternal;
const FlexLayoutVersion = "0.8.17";
const defaultIcons = {
  close: /* @__PURE__ */ jsx(CloseIcon, {}),
  closeTabset: /* @__PURE__ */ jsx(CloseIcon, {}),
  popout: /* @__PURE__ */ jsx(PopoutIcon, {}),
  maximize: /* @__PURE__ */ jsx(MaximizeIcon, {}),
  restore: /* @__PURE__ */ jsx(RestoreIcon, {}),
  more: /* @__PURE__ */ jsx(OverflowIcon, {}),
  edgeArrow: /* @__PURE__ */ jsx(EdgeIcon, {}),
  activeTabset: /* @__PURE__ */ jsx(AsterickIcon, {})
};
const defaultSupportsPopout = isDesktop();
const edgeRectLength = 100;
const edgeRectWidth = 10;
class DragState {
  constructor(mainLayout, dragSource, dragNode, dragJson, fnNewNodeDropped) {
    __publicField(this, "mainLayout");
    __publicField(this, "dragSource");
    __publicField(this, "dragNode");
    __publicField(this, "dragJson");
    __publicField(this, "fnNewNodeDropped");
    this.mainLayout = mainLayout;
    this.dragSource = dragSource;
    this.dragNode = dragNode;
    this.dragJson = dragJson;
    this.fnNewNodeDropped = fnNewNodeDropped;
  }
}
export {
  Action,
  Actions,
  AddIcon,
  AsterickIcon,
  BorderNode,
  BorderSet,
  CLASSES,
  CloseIcon,
  DefaultMax,
  DefaultMin,
  DockLocation,
  DropInfo,
  EdgeIcon,
  FlexLayoutVersion,
  I18nLabel,
  ICloseType,
  Layout,
  LayoutInternal,
  LayoutWindow,
  MaximizeIcon,
  MenuIcon,
  Model,
  Node,
  Orientation,
  OverflowIcon,
  PopoutIcon,
  Rect,
  RestoreIcon,
  RowNode,
  SettingsIcon,
  TabNode,
  TabSetNode
};
