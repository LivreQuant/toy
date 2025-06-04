import { Attribute } from "./Attribute";
/** @internal */
export declare class AttributeDefinitions {
    attributes: Attribute[];
    nameToAttribute: Map<string, Attribute>;
    constructor();
    addWithAll(name: string, modelName: string | undefined, defaultValue: any, alwaysWriteJson?: boolean): Attribute;
    addInherited(name: string, modelName: string): Attribute;
    add(name: string, defaultValue: any, alwaysWriteJson?: boolean): Attribute;
    getAttributes(): Attribute[];
    getModelName(name: string): string | undefined;
    toJson(jsonObj: any, obj: any): void;
    fromJson(jsonObj: any, obj: any): void;
    update(jsonObj: any, obj: any): void;
    setDefaults(obj: any): void;
    pairAttributes(type: string, childAttributes: AttributeDefinitions): void;
    toTypescriptInterface(name: string, parentAttributes: AttributeDefinitions | undefined): string;
}
