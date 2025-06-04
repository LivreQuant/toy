import { IJsonRect } from "./model/IJsonModel";
import { Orientation } from "./Orientation";
export declare class Rect {
    static empty(): Rect;
    static fromJson(json: IJsonRect): Rect;
    x: number;
    y: number;
    width: number;
    height: number;
    constructor(x: number, y: number, width: number, height: number);
    toJson(): {
        x: number;
        y: number;
        width: number;
        height: number;
    };
    snap(round: number): void;
    static getBoundingClientRect(element: Element): Rect;
    static getContentRect(element: HTMLElement): Rect;
    static fromDomRect(domRect: DOMRect): Rect;
    relativeTo(r: Rect | DOMRect): Rect;
    clone(): Rect;
    equals(rect: Rect | null | undefined): boolean;
    equalSize(rect: Rect | null | undefined): boolean;
    getBottom(): number;
    getRight(): number;
    get bottom(): number;
    get right(): number;
    getCenter(): {
        x: number;
        y: number;
    };
    positionElement(element: HTMLElement, position?: string): void;
    styleWithPosition(style: Record<string, any>, position?: string): Record<string, any>;
    contains(x: number, y: number): boolean;
    removeInsets(insets: {
        top: number;
        left: number;
        bottom: number;
        right: number;
    }): Rect;
    centerInRect(outerRect: Rect): void;
    /** @internal */
    _getSize(orientation: Orientation): number;
    toString(): string;
}
