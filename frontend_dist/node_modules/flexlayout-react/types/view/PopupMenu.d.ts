import { TabNode } from "../model/TabNode";
import { LayoutInternal } from "./Layout";
import { TabSetNode } from "../model/TabSetNode";
import { BorderNode } from "../model/BorderNode";
/** @internal */
export declare function showPopup(triggerElement: Element, parentNode: TabSetNode | BorderNode, items: {
    index: number;
    node: TabNode;
}[], onSelect: (item: {
    index: number;
    node: TabNode;
}) => void, layout: LayoutInternal): void;
