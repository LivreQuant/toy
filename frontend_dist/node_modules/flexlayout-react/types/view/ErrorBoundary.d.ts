import * as React from "react";
import { ErrorInfo } from "react";
/** @internal */
export interface IErrorBoundaryProps {
    message: string;
    retryText: string;
    children: React.ReactNode;
}
/** @internal */
export interface IErrorBoundaryState {
    hasError: boolean;
}
/** @internal */
export declare class ErrorBoundary extends React.Component<IErrorBoundaryProps, IErrorBoundaryState> {
    constructor(props: IErrorBoundaryProps);
    static getDerivedStateFromError(error: Error): {
        hasError: boolean;
    };
    componentDidCatch(error: Error, errorInfo: ErrorInfo): void;
    retry: () => void;
    render(): string | number | bigint | boolean | import("react/jsx-runtime").JSX.Element | Iterable<React.ReactNode> | Promise<string | number | bigint | boolean | React.ReactPortal | React.ReactElement<unknown, string | React.JSXElementConstructor<any>> | Iterable<React.ReactNode> | null | undefined> | null | undefined;
}
