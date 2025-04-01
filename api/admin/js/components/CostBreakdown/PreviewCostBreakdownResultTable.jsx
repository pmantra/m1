import React from 'react';
import './PreviewCostBreakdownResultTable.scss';

export default function PreviewCostBreakdownResultTable({costBreakdown}) {
    return (
        (
            <table className="result-table">
                <tr>
                    <th colSpan="10">Cost Breakdown Result</th>
                </tr>
                <tbody>
                <tr>
                    <td><strong>Total Treatment Cost</strong></td>
                    <td>${costBreakdown.total.cost}</td>
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
                    <td><strong>Member Responsibility</strong></td>
                    <td>${costBreakdown.total.memberResponsibility}</td>
                    <td>Plan Name: {costBreakdown.plan.name}</td>
                    {costBreakdown.plan.rxIntegrated ? <td>Rx Type: Integrated</td> : <td>Rx Type: Non Integrated</td>}
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
                </tr>
                <tr>
                    <td><strong>Treatment Procedure name</strong></td>
                    <td><strong>Procedure Type</strong></td>
                    <td><strong>Cost Sharing Category</strong></td>
                    <td><strong>Treatment Cost</strong></td>
                    <td><strong>Deductible</strong></td>
                    <td><strong>Coinsurance</strong></td>
                    <td><strong>Copay</strong></td>
                    <td><strong>Not Covered</strong></td>
                    <td><strong>HRA Applied</strong></td>
                    <td><strong>Total</strong></td>
                </tr>
                {costBreakdown.breakdowns.map(breakdown => (
                    <tr>
                        <td>{breakdown.procedureName}</td>
                        <td>{breakdown.procedureType}</td>
                        <td>{breakdown.costSharingCategory}</td>
                        <td>${breakdown.cost}</td>
                        <td>${breakdown.deductible}</td>
                        <td>${breakdown.coinsurance}</td>
                        <td>${breakdown.copay}</td>
                        <td>${breakdown.overageAmount}</td>
                        <td>${breakdown.hraApplied}</td>
                        <td>${breakdown.memberResponsibility}</td>
                    </tr>
                ))}
                <tr>
                    <td><strong>Total</strong></td>
                    <td/>
                    <td/>
                    <td>${costBreakdown.total.cost}</td>
                    <td>${costBreakdown.total.deductible}</td>
                    <td>${costBreakdown.total.coinsurance}</td>
                    <td>${costBreakdown.total.copay}</td>
                    <td>${costBreakdown.total.notCovered}</td>
                    <td>${costBreakdown.total.hraApplied}</td>
                    <td>${costBreakdown.total.memberResponsibility}</td>
                </tr>
                <tr>
                    <td><strong>Employer Responsibility</strong></td>
                    <td>${costBreakdown.total.employerResponsibility}</td>
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
                </tr>
                <tr>
                    <td><strong>Beginning Wallet Balance</strong></td>
                    <td>${costBreakdown.total.beginningWalletBalance}</td>
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
                    <td><strong>Ending Wallet Balance</strong></td>
                    <td>${costBreakdown.total.endingWalletBalance}</td>
                    <td/>
                    <td/>
                    <td/>
                    <td/>
                    <td/>
                    <td/>
                    <td/>
                    <td/>
                </tr>
                </tbody>
            </table>
        )
    );
}
