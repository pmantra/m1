import React from 'react';
import './ErrorBanner.scss';

export default function ErrorBanner({error}) {
    return (
        <div className="alert alert-error error-banner">
            <h2 id="error-title">
                <span role="img" aria-label="Error Icon" id="error-icon">❌</span>
                Cost Breakdown Error
            </h2>
            {/* eslint-disable-next-line react/no-danger */}
            <p id="error-message" dangerouslySetInnerHTML={{ __html: error }} />
        </div>
    );
}
