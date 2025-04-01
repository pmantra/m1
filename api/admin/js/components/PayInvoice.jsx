import React, { useState } from 'react';
import axios from 'axios';

export default function PayInvoice({ args: { canBePay, invoiceId } }) {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [info, setInfo] = useState('');

  async function handlePayInvoice() {
    try {
      setIsLoading(true);
      const { status, statusText } = await axios.post('/admin/invoice/pay/', {
        invoice_id: invoiceId,
      });

      if (status !== 200) {
        setError(statusText);
        return;
      }

      setInfo('Invoice has been transfered');
    } catch (e) {
      const errorMsg = (e.response && e.response.data.error) || e.message;
      setError(errorMsg);
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div style={{ paddingBottom: '10px' }}>
      {error && (
        <div className="alert alert-error">
          Error while paying the invoice:
          {error}
        </div>
      )}
      {info && <div className="alert alert-info">{info}</div>}
      {canBePay && !info && (
        <button
          type="button"
          className="btn btn-primary"
          onClick={handlePayInvoice}
          disabled={isLoading}
        >
          Pay Now
        </button>
      )}
      {isLoading && <span style={{ padding: 5 }}>Loading...</span>}
    </div>
  );
}
