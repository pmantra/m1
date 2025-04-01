import React, {useState} from 'react';
import axios from 'axios';
import './InlineReimbursementCostBreakdownCalculator.scss';

export default function InlineReimbursementCostBreakdownCalculator({ args }) {
    const [formError, setFormError] = useState('')
    const [costBreakdown, setCostBreakdown] = useState('')
    const [created, setCreated] = useState(false)
    const [displayOverrides, setDisplayOverrides] = useState(false)
    const [ytdIndDeduct, setYtdIndDeduct] = useState('')
    const [ytdIndOOP, setYtdIndOOP] = useState('')
    const [ytdFamDeduct, setYtdFamDeduct] = useState('')
    const [ytdFamOOP, setYtdFamOOP] = useState('')
    const [hraRemaining, setHraRemaining] = useState('')
    const [tier, setTier] = useState('')
    const clearState = () => {
        setFormError('')
        setCostBreakdown('')
    }

    const handleDisplayOverride = () => {
        setDisplayOverrides(!displayOverrides);
    }

    const handleCalculate = async (e) => {
        e.preventDefault()
        clearState()

        const {data, status, statusText} = await axios.post('/admin/reimbursement_request_calculator/submit', {
            "reimbursement_request_id": args.reimbursement_request_id,
            "overrides": {
                'ytd_individual_deductible': ytdIndDeduct,
                'ytd_individual_oop': ytdIndOOP,
                'ytd_family_deductible': ytdFamDeduct,
                'ytd_family_oop': ytdFamOOP,
                'hra_remaining': hraRemaining,
                'tier': tier,
            }
        }, {
            headers: {
                'Content-Type': 'application/json',
            },
        });
        if (status !== 200) {
            setFormError(statusText);
            return;
        }
        if (data) {
            if (data.error) {
                setFormError(data.error);
                return;
            }
            setCostBreakdown(data.cost_breakdown);
            setFormError(data.message)
            setCreated(false);
        }
    }

    const handleSaveCalculation = async (e) => {
        e.preventDefault()
        e.stopPropagation()

        if (!costBreakdown || costBreakdown === "") {
            clearState()
            setFormError("You must first calculate the cost breakdown data prior to saving.");
            return
        }
        if (window.confirm("Are you sure you want to save this cost breakdown? " +
            "This will permanently record the calculated values to the database, update the reimbursement request as needed, and reload this page. It may also create a payer accumulation mapping. " +
            "Save any other changes you may have made to this reimbursement request first!")) {
            const form = document.querySelector("#save_rr_calculator");
            form.submit();
        }
    }

    return (
        <div className="inline-calculator">
            <div className="row">
                <div className="span">
                    <b>Cost Breakdown Calculator:</b> &nbsp;
                </div>
            </div>
            <div className="row">
                <div className="span">
                    <label className="inline checkbox" htmlFor="display-overrides">
                        Display Override Fields <input type="checkbox" id="display-overrides" checked={displayOverrides} onChange={handleDisplayOverride}/>
                    </label>
                </div>
            </div>
            {displayOverrides && <div className="row">
                <div className="span">
                    <table><tbody>
                        <tr>
                           <td><label htmlFor="ytd_ind_deduct">YTD Individual Deductible (in dollars):&nbsp;</label></td>
                            <td><input type="number" step="any" value={ytdIndDeduct} onChange={e => setYtdIndDeduct(e.target.value)} id="ytd_ind_deduct"/></td>
                        </tr>
                        <tr>
                            <td><label htmlFor="ytd_ind_oop">YTD Individual OOP (in dollars):&nbsp;</label></td>
                            <td><input type="number" step="any" value={ytdIndOOP} onChange={e => setYtdIndOOP(e.target.value)} id="ytd_ind_oop"/></td>
                        </tr>
                        <tr>
                            <td><label htmlFor="ytd_fam_deduct">YTD Family Deductible (in dollars):&nbsp;</label></td>
                            <td><input type="number" step="any" value={ytdFamDeduct} onChange={e => setYtdFamDeduct(e.target.value)} id="ytd_fam_deduct"/></td>
                        </tr>
                        <tr>
                            <td><label htmlFor="ytd_fam_oop">YTD Family OOP (in dollars):&nbsp;</label></td>
                            <td><input type="number" step="any" value={ytdFamOOP} onChange={e => setYtdFamOOP(e.target.value)} id="ytd_fam_oop"/></td>
                        </tr>
                        <tr>
                            <td><label htmlFor="hra_remaining">HRA Remaining (in dollars):&nbsp;</label></td>
                            <td><input type="number" step="any" value={hraRemaining} onChange={e => setHraRemaining(e.target.value)} id="hra_remaining"/></td>
                        </tr>
                        <tr>
                            <td><label htmlFor="tier">Tier (leave blank for non-tiered plans; defaults to 2 for tiered plans):&nbsp;</label></td>
                            <td>
                                <select value={tier || ''} onChange={e => setTier(e.target.value === '' ? null : Number(e.target.value))} id="tier">
                                    <option value="">None</option>
                                    <option value="1">1</option>
                                    <option value="2">2</option>
                                </select>
                            </td>
                        </tr>
                    </tbody></table>
                </div>
            </div>}
            <div className="row">
                <div className="span">
                    <input type="submit" className="btn" value="Calculate" onClick={handleCalculate}/>&nbsp;
                    <form id="save_rr_calculator" method="post" action="/admin/reimbursement_request_calculator/save">
                        <input type="hidden" name="reimbursement_request_id" value={args.reimbursement_request_id}/>
                        <input type="hidden" name="cost_breakdown" value={JSON.stringify(costBreakdown)}/>
                        <input type="submit" className="btn btn-primary" value="Save" onClick={handleSaveCalculation}/>
                    </form>&nbsp;&nbsp;&nbsp;
                </div>
            </div>
            {(formError || costBreakdown) && <br/>}
            <div className="row">
                    {formError && <div className="alert alert-error span12">{formError}</div>}
                    {costBreakdown && <div className="alert alert-success span12">
                        <p>{created ? "Cost Breakdown Saved!" : ""}</p>
                        <p>Treatment Cost: ${costBreakdown.cost}</p>
                        <br/>
                        <p>Member Responsibility: ${costBreakdown.total_member_responsibility}</p>
                        <p> - Deductible: ${costBreakdown.deductible}</p>
                        <p> - Coinsurance: ${costBreakdown.coinsurance}</p>
                        <p> - Copay: ${costBreakdown.copay}</p>
                        <p> - Not Covered: ${costBreakdown.overage_amount}</p>
                        <br/>
                        <p>Employer Responsibility: ${costBreakdown.total_employer_responsibility}</p>
                        <br/>
                        <p>Unlimited Coverage: ${costBreakdown.is_unlimited ? "Yes" : "No" }</p>
                        <p>Beginning Wallet Balance: ${costBreakdown.beginning_wallet_balance}</p>
                        <p>Ending Wallet Balance: ${costBreakdown.ending_wallet_balance}</p>
                    </div>}
            </div>
        </div>
    );
}