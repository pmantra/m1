import React from 'react';
import './RecalculateCostBreakdownConfirmResultTable.scss';

export default function RecalculateCostBreakdownConfirmResultTable({confirmData}) {
    return (
        (
            <table className="confirm-result-table">
                <tr>
                    <th colSpan="5">Confirm Result Table</th>
                </tr>
                <tbody>
                <tr>
                    <td><strong>Cost Breakdown UUID</strong></td>
                    <td><strong>Bill ID</strong></td>
                    <td><strong>Bill Amount</strong></td>
                    <td><strong>Bill Payer Type</strong></td>
                    <td><strong>Treatment ID</strong></td>
                </tr>
                {confirmData.bills.map(value => (
                    <tr>
                        <td>{value.cost_breakdown_uuid}</td>
                        <td>{value.bill_id}</td>
                        <td>${value.bill_amount}</td>
                        <td>{value.bill_payer_type}</td>
                        <td>{value.treatment_id}</td>
                    </tr>
                ))}
                </tbody>
            </table>
        )
    );
}
