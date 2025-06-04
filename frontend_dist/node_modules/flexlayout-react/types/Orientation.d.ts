export declare class Orientation {
    static HORZ: Orientation;
    static VERT: Orientation;
    static flip(from: Orientation): Orientation;
    /** @internal */
    private _name;
    /** @internal */
    private constructor();
    getName(): string;
    toString(): string;
}
