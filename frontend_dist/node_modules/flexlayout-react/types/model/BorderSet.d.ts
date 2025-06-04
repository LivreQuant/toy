import { DockLocation } from "../DockLocation";
import { DropInfo } from "../DropInfo";
import { BorderNode } from "./BorderNode";
import { IDraggable } from "./IDraggable";
import { Model } from "./Model";
import { Node } from "./Node";
export declare class BorderSet {
    /** @internal */
    static fromJson(json: any, model: Model): BorderSet;
    /** @internal */
    private borders;
    /** @internal */
    private borderMap;
    /** @internal */
    private layoutHorizontal;
    /** @internal */
    constructor(_model: Model);
    toJson(): import("./IJsonModel").IJsonBorderNode[];
    /** @internal */
    getLayoutHorizontal(): boolean;
    /** @internal */
    getBorders(): BorderNode[];
    /** @internal */
    getBorderMap(): Map<DockLocation, BorderNode>;
    /** @internal */
    forEachNode(fn: (node: Node, level: number) => void): void;
    /** @internal */
    setPaths(): void;
    /** @internal */
    findDropTargetNode(dragNode: Node & IDraggable, x: number, y: number): DropInfo | undefined;
}
