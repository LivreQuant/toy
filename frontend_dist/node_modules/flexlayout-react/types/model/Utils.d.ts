import { TabSetNode } from "./TabSetNode";
import { BorderNode } from "./BorderNode";
import { RowNode } from "./RowNode";
import { TabNode } from "./TabNode";
/** @internal */
export declare function adjustSelectedIndexAfterDock(node: TabNode): void;
/** @internal */
export declare function adjustSelectedIndex(parent: TabSetNode | BorderNode | RowNode, removedIndex: number): void;
export declare function randomUUID(): string;
