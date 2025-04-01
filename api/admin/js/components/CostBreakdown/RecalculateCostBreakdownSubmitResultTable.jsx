import React from 'react';
import './RecalculateCostBreakdownSubmitResultTable.scss';

export default function RecalculateCostBreakdownSubmitResultTable({costBreakdowns}) {
    return (
        (
            <table className="submit-result-table">
                <tr>
                    <th colSpan="18">Cost Breakdown Result</th>
                </tr>
                <tbody>
                <tr>
                    <td><strong>Member ID</strong></td>
                    <td><strong>Member Health Plan ID</strong></td>
                    <td><strong>Plan Name</strong></td>
                    <td><strong>RX Integrated</strong></td>
                    <td><strong>Amount Type</strong></td>
                    <td/>
                    <td/>
                    <td/>
                    <td/>
                    <td/>
                    <td/>
                    <td/>
                    <td/>
                    <td/>
                    <td/>
                    <td/>
                    <td/>
                </tr>
                <tr>
                    <td>{costBreakdowns.plan.member_id}</td>
                    <td>{costBreakdowns.plan.member_health_plan_id}</td>
                    <td>{costBreakdowns.plan.plan_name}</td>
                    {costBreakdowns.plan.rx_integrated ? <td>✅</td> : <td>❌</td>}
                    {costBreakdowns.plan.is_family_plan ? <td>Family</td> : <td>Individual</td>}
                    <td/>
                    <td/>
                    <td/>
                    <td/>
                    <td/>
                    <td/>
                    <td/>
                    <td/>
                    <td/>
                    <td/>
                    <td/>
                    <td/>
                </tr>
                <tr>
                    <td/>
                    <td/>
                    <td/>
                    <td/>
                    <td/>
                    <td/>
                    <td/>
                    <td/>
                    <td/>
                    <td/>
                    <td/>
                    <td/>
                    <td/>
                    <td/>
                    <td/>
                    <td/>
                    <td/>
                    <td/>
                    <td/>
                </tr>
                <tr>
                    <td><strong>Treatment Procedure ID</strong></td>
                    <td><strong>Treatment Procedure UUID</strong></td>
                    <td><strong>Treatment Procedure Type</strong></td>
                    <td><strong>Treatment Cost</strong></td>
                    <td><strong>Treatment Credit Cost</strong></td>
                    <td><strong>Member Responsibility</strong></td>
                    <td><strong>Employer Responsibility</strong></td>
                    <td><strong>Deductible</strong></td>
                    <td><strong>Coinsurance</strong></td>
                    <td><strong>copay</strong></td>
                    <td><strong>Not Covered</strong></td>
                    <td><strong>OOP Applied</strong></td>
                    <td><strong>HRA Applied</strong></td>
                    <td><strong>Unlimited Coverage</strong></td>
                    <td><strong>Beginning Wallet Balance</strong></td>
                    <td><strong>Ending Wallet Balance</strong></td>
                    <td><strong>Cost Breakdown Type</strong></td>
                    <td><strong>Calculation Config</strong></td>
                    <td><strong>RTE Transaction ID</strong></td>
                </tr>
                {costBreakdowns.breakdowns.map(breakdown => (
                    <tr>
                        <td>{breakdown.treatment_id}</td>
                        <td>{breakdown.treatment_uuid}</td>
                        <td>{breakdown.treatment_type}</td>
                        <td>${breakdown.cost}</td>
                        <td>{breakdown.treatment_cost_credit}</td>
                        <td>${breakdown.total_member_responsibility}</td>
                        <td>${breakdown.total_employer_responsibility}</td>
                        <td>${breakdown.deductible}</td>
                        <td>${breakdown.coinsurance}</td>
                        <td>${breakdown.copay}</td>
                        <td>${breakdown.overage_amount}</td>
                        <td>${breakdown.oop_applied}</td>
                        <td>${breakdown.hra_applied}</td>
                        <td>{breakdown.is_unlimited ? "Yes" : "No"}</td>
                        <td>${breakdown.beginning_wallet_balance}</td>
                        <td>${breakdown.ending_wallet_balance}</td>
                        <td>{breakdown.cost_breakdown_type}</td>
                        <td>{breakdown.calc_config}</td>
                        <td>{breakdown.rte_transaction_id}</td>
                    </tr>
                ))}
                </tbody>
            </table>
        )
    );
}
