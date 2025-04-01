import React, { useState } from 'react';
import './PreviewCostBreakdownResultTable.scss';

export default function PreviewCostBreakdownResultTableFormatted({ costBreakdown }) {
    const [reimbursementId, setReimbursementId] = useState('');
    const [linkingStatus, setLinkingStatus] = useState(null);
    const [showConfirmDialog, setShowConfirmDialog] = useState(false);
    const [notifications, setNotifications] = useState([]);

const getNotificationColor = (category) => {
    switch (category) {
        case 'success':
            return '#4ade80';
        case 'error':
            return '#f87171';
        case 'warning':
            return '#fbbf24';
        default:
            return '#60a5fa';
    }
};
    const addNotification = (category, message) => {
        const id = Date.now();
        setNotifications(prev => [...prev, { id, category, message }]);
    };
    const formatBreakdownText = () => {
        let textToCopy = `Total Treatment Cost: $${costBreakdown.total.cost}\n`;
        textToCopy += `Total Member Responsibility: $${costBreakdown.total.memberResponsibility}\n`;
        textToCopy += `Total Reimbursable Amount: $${costBreakdown.total.employerResponsibility}\n\n`;
        costBreakdown.breakdowns.forEach((breakdown) => {
            textToCopy += `${breakdown.procedureName}: $${breakdown.cost} - ${breakdown.costSharingCategory}\n`;
            textToCopy += `  - Treatment Cost: $${breakdown.cost}\n`;
            textToCopy += `  - Member Responsibility: $${breakdown.memberResponsibility}\n`;
            textToCopy += `  - Deductible: $${breakdown.deductible}\n`;
            textToCopy += `  - Out of Pocket: $${breakdown.oop_applied}\n`;
            textToCopy += `  - Coinsurance: $${breakdown.coinsurance}\n`;
            textToCopy += `  - Copay: $${breakdown.copay}\n`;
            textToCopy += `  - Not covered: $${breakdown.overageAmount}\n`;
            textToCopy += `  - Employer Responsibility: $${breakdown.employerResponsibility}\n\n`;
        });
        return textToCopy;
    };
    const handleCopyToClipboard = () => {
        if (navigator && navigator.clipboard) {
            const textToCopy = formatBreakdownText();
            navigator.clipboard.writeText(textToCopy)
                .then(() => console.log("Copied to clipboard"))
                .catch(() => console.log("Failed to copy to clipboard."));
        } else {
            console.log('Incompatible browser with navigator.clipboard.');
        }
    };
    const checkExistingBreakdown = async () => {
        try {
            const response = await fetch(`/admin/cost_breakdown_calculator/check_existing/${reimbursementId}`);
            const data = await response.json();
            return data.exists;
        } catch (error) {
            console.error('Error checking existing breakdown:', error);
            return false;
        }
    };
    const handleLinkToReimbursement = async () => {
        try {
            setLinkingStatus('pending');
            if (!showConfirmDialog) {
                const hasExisting = await checkExistingBreakdown();
                if (hasExisting) {
                    setShowConfirmDialog(true);
                    setLinkingStatus(null);
                    return;
                }
            }
            const response = await fetch('/admin/cost_breakdown_calculator/linkreimbursement', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    memberId: costBreakdown.plan.memberId,
                    reimbursementRequestId: reimbursementId,
                    description: formatBreakdownText(),
                    totalCost: costBreakdown.total.cost,
                    memberResponsibility: costBreakdown.total.memberResponsibility,
                    employerResponsibility: costBreakdown.total.employerResponsibility,
                    deductible: costBreakdown.total.deductible,
                    oopApplied: costBreakdown.total.oopApplied,
                    deductibleRemaining: costBreakdown.total.deductibleRemaining,
                    oopRemaining: costBreakdown.total.oopRemaining,
                    familyDeductibleRemaining: costBreakdown.total.familyDeductibleRemaining,
                    familyOopRemaining: costBreakdown.total.familyOopRemaining,
                    copay: costBreakdown.total.copay,
                    coinsurance: costBreakdown.total.coinsurance,
                    isUnlimited: costBreakdown.total.isUnlimited,
                    beginningWalletBalance: costBreakdown.total.beginningWalletBalance,
                    endingWalletBalance: costBreakdown.total.endingWalletBalance,
                    hraApplied: costBreakdown.total.hraApplied,
                    overageAmount: costBreakdown.total.notCovered,
                    amountType: costBreakdown.total.amountType,
                    costBreakdownType: costBreakdown.total.costBreakdownType,
                })
            });
            const data = await response.json();
            if (data.flash_messages) {
                data.flash_messages.forEach(([category, message]) => {
                    addNotification(category, message);
                });
            }

            if (!response.ok) {
                throw new Error(data.error || 'Failed to link cost breakdown');
            }

            setLinkingStatus('success');
            setShowConfirmDialog(false);
        } catch (error) {
            setLinkingStatus('error');
            addNotification('error', 'Error linking to reimbursement request');
            console.error('Error linking cost breakdown:', error);
        }
    };
    return (
        <div className="formatted-cost-breakdown-results">
            {notifications.map(({ id, category, message }) => (
                <div
                    key={id}
                    className={`notification ${category}`}
                    style={{
                        padding: '10px 20px',
                        marginBottom: '10px',
                        borderRadius: '4px',
                        backgroundColor: getNotificationColor(category),
                        color: 'white',
                        boxShadow: '0 2px 5px rgba(0,0,0,0.2)',
                        minWidth: '200px'
                    }}
                    dangerouslySetInnerHTML={{ __html: message }}
                />
            ))}
            <button type="button" className="btn" onClick={handleCopyToClipboard}>
                Copy to Clipboard
            </button>
            <p>Total Treatment Cost: ${costBreakdown.total.cost}</p>
            <p>Total Member Responsibility: ${costBreakdown.total.memberResponsibility}</p>
            <p>Total Reimbursable Amount: ${costBreakdown.total.employerResponsibility}</p>
            <p>Total Deductible Amount: ${costBreakdown.total.deductible}</p>
            <p>Total Out of Pocket Amount: ${costBreakdown.total.oopApplied}</p>
            <p>Total Copay Amount: ${costBreakdown.total.copay}</p>
            <p>Total Coinsurance Amount: ${costBreakdown.total.coinsurance}</p>
            <p>Total Not Covered: ${costBreakdown.total.notCovered}</p>
            <p>Total HRA Applied: ${costBreakdown.total.hraApplied}</p>
            <p>Unlimited Coverage: ${costBreakdown.total.isUnlimited ? "Yes" : "No"}</p>
            <p>Beginning Wallet Balance: ${costBreakdown.total.beginningWalletBalance}</p>
            <p>Ending Wallet Balance: ${costBreakdown.total.endingWalletBalance}</p>
            <div className="reimbursement-link-section mt-4">
                <div className="flex items-center justify-start gap-3">
                    <input
                        type="number"
                        value={reimbursementId}
                        onChange={(e) => setReimbursementId(e.target.value)}
                        placeholder="Enter Reimbursement Request ID"
                        className="reimbursement-input px-3 py-2 border rounded w-64"
                    />
                    <button
                        type="button"
                        onClick={handleLinkToReimbursement}
                        disabled={!reimbursementId || linkingStatus === 'pending' || showConfirmDialog}
                        className="link-button px-4 py-2 bg-blue-500 text-white rounded disabled:bg-gray-300 whitespace-nowrap"
                    >
                        {linkingStatus === 'pending' ? 'Linking...' : 'Link to Reimbursement'}
                    </button>
                </div>
                {showConfirmDialog && (
                    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center">
                        <div className="bg-white p-4 rounded-lg shadow-lg max-w-md">
                            <h3 className="text-lg font-semibold mb-2">Existing Cost Breakdown Found</h3>
                            <p className="mb-4">This reimbursement request already has a cost breakdown. Do you want to proceed with creating a new one?</p>
                            <div className="flex justify-end gap-2">
                                <button type="button" className="btn"
                                    onClick={() => setShowConfirmDialog(false)}
                                >
                                    Cancel
                                </button>
                                <button type="button" className="btn"
                                    onClick={handleLinkToReimbursement}
                                >
                                    Proceed
                                </button>
                            </div>
                        </div>
                    </div>
                )}
                {linkingStatus === 'success' && (
                    <div className="mt-2 text-green-600">Successfully linked to reimbursement request!</div>
                )}
                {linkingStatus === 'error' && (
                    <div className="mt-2 text-red-600">Error linking to reimbursement request</div>
                )}
            </div>
            {costBreakdown.breakdowns.map((breakdown) => (
                <div>
                    <p>{breakdown.procedureName}: ${breakdown.cost} - {breakdown.costSharingCategory}</p>
                    <ul>
                        <li>Treatment Cost: ${breakdown.cost}</li>
                        <li>Member Responsibility: ${breakdown.memberResponsibility}</li>
                        <li>Deductible: ${breakdown.deductible}</li>
                        <li>Out of Pocket: ${breakdown.oopApplied}</li>
                        <li>Coinsurance: ${breakdown.coinsurance}</li>
                        <li>Copay: ${breakdown.copay}</li>
                        <li>Not covered: ${breakdown.overageAmount}</li>
                        <li>Employer Responsibility: ${breakdown.employerResponsibility}</li>
                    </ul>
                </div>
            ))}
        </div>
    );
}
