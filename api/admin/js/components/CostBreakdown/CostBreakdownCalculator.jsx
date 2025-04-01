import React, {useState} from 'react';

import RecalculateCostBreakdown from "./RecalculateCostBreakdown";
import PreviewCostBreakdown from "./PreviewCostBreakdown";
import './CostBreakdownCalculator.scss';

export default function CostBreakdownCalculator() {

    const [selectedButton, setSelectedButton] = useState(1);

    const handleClick = (button) => {
        setSelectedButton(button);
    };


    return (
        <div>
            <div className="button-container">
                <button type="button" className={selectedButton === 1 ? 'button selected' : 'button'}
                        onClick={() => handleClick(1)}>
                    Cost Breakdown Recalculator
                </button>
                <button type="button" className={selectedButton === 2 ? 'button selected' : 'button'}
                        onClick={() => handleClick(2)}>
                    Cost Breakdown Previewer
                </button>
            </div>
            {selectedButton === 1 ? <RecalculateCostBreakdown/> : <PreviewCostBreakdown/>}
        </div>
    )
}
