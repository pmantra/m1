import React, { useState, useEffect } from 'react';
import axios from 'axios';
import Select from 'react-select';

function formatProviders(providers = []) {
  return providers.map(({ name, id }) => ({
    label: name,
    value: id,
  }));
}

export default function CreateInvoice() {
  const [isLoading, setIsLoading] = useState(false);
  const [isLoadingProviders, setIsLoadingProviders] = useState(false);
  const [selectedProvider, setSelectedProvider] = useState(0);
  const [amount, setAmount] = useState(0);
  const [error, setError] = useState('');
  const [newInvoiceId, setNewInvoiceId] = useState('');
  const [providers, setProviders] = useState([]);

  useEffect(() => {
    async function fetchProviders() {
      try {
        setIsLoadingProviders(true);
        const { data } = await axios.get('/admin/practitionerprofile/list/');
        setProviders(formatProviders(data.practitioners));
      } catch (e) {
        const errorMsg = (e.response && e.response.data.error) || e.message;
        setError(errorMsg);
      } finally {
        setIsLoadingProviders(false);
      }
    }

    fetchProviders();
  }, []);

  const handleCreateInvoice = async () => {
    try {
      setIsLoading(true);
      const { data, status, statusText } = await axios.post('/admin/monthly_payments/invoice/', {
        fee_amount_cents: amount,
        practitioner_id: selectedProvider,
      });

      if (status !== 200) {
        setError(statusText);
        return;
      }

      setNewInvoiceId(data.invoice_id || 0);
      setAmount(0);
    } catch (e) {
      const errorMsg = (e.response && e.response.data.error) || e.message;
      setError(errorMsg);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div>
      <h3>Create Invoice</h3>
      <div style={{ margin: 10 }}>
        {error && (
          <div className="alert alert-error">
            Error while creating the invoice:
            {error}
          </div>
        )}
        <div style={{ width: 250, marginBottom: 20 }}>
          <span htmlFor="providers-list">
            Providers
            <Select
              options={providers}
              onChange={(provider) => {
                setError('');
                setAmount(0);
                setSelectedProvider(provider.value);
              }}
              inputId="providers-list"
              styles={{ input: (provided) => ({ ...provided, '& input': { boxShadow: 'none !important' } }) }}
              isLoading={isLoadingProviders}
              loadingMessage={() => 'Fetching active providers'}
            />
          </span>
        </div>
        <div style={{ marginBottom: 20 }}>
          <label htmlFor="invoice-amount">
            Invoice Amount (Cents)
            <input
              id="invoice-amount"
              onChange={(event) => setAmount(event.target.value)}
              type="number"
              min="1"
              value={amount}
              style={{ height: 30 }}
            />
          </label>
        </div>
        <button
          type="button"
          className="btn btn-primary"
          onClick={handleCreateInvoice}
          disabled={isLoading || amount < 1 || selectedProvider < 1}
        >
          Create Invoice
        </button>
        {isLoading && <div>Loading...</div>}
        {newInvoiceId && (
          <div>
            <a target="_blank" href={`/admin/invoice/edit/?id=${newInvoiceId}`} rel="noreferrer">
              The invoice has been created, click here to see it.
            </a>
          </div>
        )}
      </div>
    </div>
  );
}
