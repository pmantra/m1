import React, {useState} from 'react';
import PreviewCostBreakdownForm from "./PreviewCostBreakdownForm";
import PreviewCostBreakdownResultTable from "./PreviewCostBreakdownResultTable";
import LoadingBanner from "./LoadingBanner";
import ErrorBanner from "./ErrorBanner";
import './PreviewCostBreakdown.scss';
import PreviewCostBreakdownResultTableFormatted from "./PreviewCostBreakdownResultTableFormatted";

export default function PreviewCostBreakdown() {

    const [pending, setPending] = useState(false);
    const [costBreakdown, setCostBreakdown] = useState(null);
    const [error, setError] = useState(null);

    return (
        <div className="preview-cost-breakdown">
            <PreviewCostBreakdownForm setPending={setPending} setCostBreakdown={setCostBreakdown} setError={setError}/>
            {pending && <LoadingBanner/>}
            {costBreakdown && <PreviewCostBreakdownResultTable costBreakdown={costBreakdown}/>}
            {costBreakdown && <PreviewCostBreakdownResultTableFormatted costBreakdown={costBreakdown}/>}
            {error && <ErrorBanner error={error}/>}
        </div>
    );
}
