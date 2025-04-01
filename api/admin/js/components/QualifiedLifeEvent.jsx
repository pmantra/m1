import React, { useState, useEffect } from 'react';

function QualifiedLifeEvent() {
  const [amount, setAmount] = useState(0.0);
  const [effectiveDate, setEffectiveDate] = useState(new Date().toLocaleDateString('en-CA'));

  const applyToForm = () => {
    const amountInput = document.getElementById('amount');
    const effectiveDateInput = document.getElementById('effective_date');

    amountInput.value = amount;
    effectiveDateInput.value = effectiveDate;
  };

  useEffect(() => {
    applyToForm();
  }, [amount, effectiveDate]);

  return (
    <div>
      <div>
        <b>Amount</b>
        <br />
        <div className="input-prepend">
          <span className="add-on" style={{ height: 'auto' }}>
            $
          </span>
          <input
            type="number"
            value={amount}
            step="1"
            onChange={(e) => setAmount(e.target.value)}
            placeholder="Amount"
            required
            style={{ height: 'auto' }}
          />
        </div>
      </div>
      <div>
        <b>Effective Date</b>
        <p>
          <input
            type="date"
            style={{ height: 30 }}
            value={effectiveDate}
            onChange={(e) => setEffectiveDate(e.target.value)}
            required
          />
        </p>
      </div>
    </div>
  );
}

export default QualifiedLifeEvent;
