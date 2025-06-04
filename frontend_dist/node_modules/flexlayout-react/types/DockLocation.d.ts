import { Orientation } from "./Orientation";
import { Rect } from "./Rect";
export declare class DockLocation {
    static values: Map<string, DockLocation>;
    static TOP: DockLocation;
    static BOTTOM: DockLocation;
    static LEFT: DockLocation;
    static RIGHT: DockLocation;
    static CENTER: DockLocation;
    /** @internal */
    static getByName(name: string): DockLocation;
    /** @internal */
    static getLocation(rect: Rect, x: number, y: number): DockLocation;
    /** @internal */
    name: string;
    /** @internal */
    orientation: Orientation;
    /** @internal */
    indexPlus: number;
    /** @internal */
    constructor(_name: string, _orientation: Orientation, _indexPlus: number);
    getName(): string;
    getOrientation(): Orientation;
    /** @internal */
    getDockRect(r: Rect): Rect;
    /** @internal */
    split(rect: Rect, size: number): {
        start: Rect;
        end: Rect;
    };
    /** @internal */
    reflect(): DockLocation;
    toString(): string;
}
