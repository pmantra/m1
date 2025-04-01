import React from "react";
import './LoadingBanner.scss';

export default function LoadingBanner() {
    return (
        <div className="fancy-loading-banner">
            <div className="loader" />
            <p>Generating Cost Breakdown Report...🚀</p>
        </div>
    );
}
