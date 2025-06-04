/** @internal */
export declare class Attribute {
    static NUMBER: string;
    static STRING: string;
    static BOOLEAN: string;
    name: string;
    alias: string | undefined;
    modelName?: string;
    pairedAttr?: Attribute;
    pairedType?: string;
    defaultValue: any;
    alwaysWriteJson?: boolean;
    type?: string;
    required: boolean;
    fixed: boolean;
    description?: string;
    constructor(name: string, modelName: string | undefined, defaultValue: any, alwaysWriteJson?: boolean);
    setType(value: string): this;
    setAlias(value: string): this;
    setDescription(value: string): void;
    setRequired(): this;
    setFixed(): this;
    setpairedAttr(value: Attribute): void;
    setPairedType(value: string): void;
}
