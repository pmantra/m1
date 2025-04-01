import React, { useState } from 'react';
import axios from 'axios';

export default function GenerateInvoices() {
  const [error, setError] = useState('');
  const [info, setInfo] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const handleGenerateInvoices = async () => {
    try {
      setIsLoading(true);

      const { status, statusText } = await axios.post('/admin/monthly_payments/generate_invoices');
      if (status !== 200) {
        setError(statusText);
        return;
      }

      setInfo('Invoices generation in progress');
    } catch (e) {
      const errorMsg = (e.response && e.response.data.error) || e.message;
      setError(errorMsg);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div>
      <h3>Generate Invoices</h3>
      {error && <div className="alert alert-error">{error}</div>}
      <button type="button" className="btn btn-primary" onClick={handleGenerateInvoices} disabled={isLoading}>
        Send Accounting Email
      </button>
      <p>
        Note: This will generate the provider invoices and send the email with
        the code to accounting. This could take several minutes, please be patient.
        If accounting does not receive the code, it is safe to click this button again.
      </p>
      {isLoading && <div>Loading...</div>}
      {!isLoading && info && <div className="alert alert-info">{info}</div>}
    </div>
  );
}
