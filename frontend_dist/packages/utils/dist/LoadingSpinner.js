import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import './LoadingScreen.css'; // Reuse the loading screen styles if applicable or create new ones
const LoadingSpinner = ({ message, size = 40, thickness = 4 }) => {
    const spinnerStyle = {
        width: `${size}px`,
        height: `${size}px`,
        borderWidth: `${thickness}px`,
        borderTopWidth: `${thickness}px`, // Ensure top border is also set
    };
    return (_jsxs("div", { className: "loading-screen", children: [" ", _jsx("div", { className: "loading-spinner", style: spinnerStyle }), message && _jsx("p", { className: "loading-message", children: message })] }));
};
export default LoadingSpinner;
