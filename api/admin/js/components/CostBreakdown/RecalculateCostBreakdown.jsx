import React, {useState} from 'react';
import axios from 'axios';
import './RecalculateCostBreakdown.scss';
import LoadingBanner from "./LoadingBanner";
import RecalculateCostBreakdownSubmitResultTable from "./RecalculateCostBreakdownSubmitResultTable";
import RecalculateCostBreakdownConfirmResultTable from "./RecalculateCostBreakdownConfirmResultTable";
import ErrorBanner from "./ErrorBanner";

export default function RecalculateCostBreakdown() {

    const [formError, setFormError] = useState('')
    const [costBreakdowns, setCostBreakdowns] = useState('')
    const [confirmError, setConfirmError] = useState('')
    const [confirmData, setConfirmData] = useState('')
    const [pending, setPending] = useState(false);


    const clearState = () => {
        setFormError('')
        setCostBreakdowns('')
        setConfirmError('')
        setConfirmData('')
    }

    const scrollToButton = () => {
        window.scrollTo({
            top: document.body.scrollHeight,
            behavior: 'smooth'
        });
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        clearState()
        setPending(true);

        const form = e.target;
        const formData = new FormData(form);
        const {data} = await axios.post('/admin/cost_breakdown_calculator/submit', formData, {
            headers: {
                'Content-Type': 'application/json',
            },
        }).catch((error) => error.response);
        if (data) {
            if (data.error) {
                setFormError(data);
                setPending(false);
                scrollToButton();
                return;
            }
            setCostBreakdowns(data);
            setPending(false);
            scrollToButton();
        }
    }

    const handleConfirm = async (e) => {
        e.preventDefault();
        const {
            data,
            status,
            statusText
        } = await axios.post('/admin/cost_breakdown_calculator/confirm', costBreakdowns, {
            headers: {
                'Content-Type': 'application/json',
            },
        });
        if (status !== 200) {
            setConfirmError(statusText);
            return;
        }
        if (data.error) {
            setConfirmError(data);
            scrollToButton();
            return;
        }
        setConfirmData(data);
        scrollToButton();
    }

    const handleCancel = async () => {
        clearState()
    }

    return (
        <div className="recalculate-cost-breakdown">
            <form onSubmit={handleSubmit}>
                <div className="form">
                    <div className="form-group">
                        {/* eslint-disable-next-line jsx-a11y/label-has-associated-control */}
                        <label htmlFor="treatment_ids"> Treatment procedure ID(s): </label>
                        <input name="treatment_ids" type="text" id="treatment_ids"/>
                    </div>
                    <div className="form-group">
                        {/* eslint-disable-next-line jsx-a11y/label-has-associated-control */}
                        <label htmlFor="ind_deductible">YTD Individual Deductible amount (in dollar): </label>
                        <input name="ind_deductible" type="number" step="any" id="ind_deductible"/>
                    </div>
                    <div className="form-group">
                        {/* eslint-disable-next-line jsx-a11y/label-has-associated-control */}
                        <label htmlFor="ind_oop">YTD Individual OOP amount (in dollar): </label>
                        <input name="ind_oop" type="number" step="any" id="ind_oop"/>
                    </div>
                    <div className="form-group">
                        {/* eslint-disable-next-line jsx-a11y/label-has-associated-control */}
                        <label htmlFor="family_deductible">YTD Family Deductible amount (in dollar): </label>
                        <input name="family_deductible" type="number" step="any" id="family_deductible"/>
                    </div>
                    <div className="form-group">
                        {/* eslint-disable-next-line jsx-a11y/label-has-associated-control */}
                        <label htmlFor="family_oop">YTD Family OOP amount (in dollar): </label>
                        <input name="family_oop" type="number" step="any" id="family_oop"/>
                    </div>
                    <div className="form-group">
                        {/* eslint-disable-next-line jsx-a11y/label-has-associated-control */}
                        <label htmlFor="hra_remaining">HRA Remaining amount (in dollar): </label>
                        <input name="hra_remaining" type="number" step="any" id="hra_remaining"/>
                    </div>
                    <div className="form-group">
                        {/* eslint-disable-next-line jsx-a11y/label-has-associated-control */}
                        <label htmlFor="ind_oop_limit">Individual OOP Limit amount (in dollar, relevant for HDHP plans): </label>
                        <input name="ind_oop_limit" type="number" step="any" id="ind_oop_limit"/>
                    </div>
                    <div className="form-group">
                        {/* eslint-disable-next-line jsx-a11y/label-has-associated-control */}
                        <label htmlFor="family_oop_limit">Family OOP Limit amount (in dollar, relevant for HDHP plans): </label>
                        <input name="family_oop_limit" type="number" step="any" id="family_oop_limit"/>
                    </div>
                    <div className="annotation">(RTE result will be overridden if YTD values are entered)</div>
                </div>
                <br/>
                <div className="button-group">
                    <button type="submit" id="submitFrom">
                        Run Calculation
                    </button>
                    {/* eslint-disable-next-line react/button-has-type */}
                    <button type="reset" onClick={handleCancel}>Reset form</button>
                </div>
            </form>
            {formError && <ErrorBanner error={formError.error}/>}
            {costBreakdowns && <div>
                <RecalculateCostBreakdownSubmitResultTable costBreakdowns={costBreakdowns}/>
                <p>If the above calculation looks right, click &quot;Confirm Calculation&quot; to finalize the
                    update.</p>
                <br/>
                <div>
                    <form className="button-group" onSubmit={handleConfirm}>
                        <button type="submit" id="submitFrom">
                            Confirm Calculation
                        </button>
                        <button type="button" onClick={handleCancel}>Cancel</button>
                    </form>
                </div>
            </div>}
            {pending && <LoadingBanner/>}
            {confirmError && <ErrorBanner error={confirmError.error}/>}
            {confirmData &&
                <RecalculateCostBreakdownConfirmResultTable confirmData={confirmData}/>}
        </div>
    );
}
