import React, { useState } from 'react';
import axios from 'axios';
import { isEmpty } from 'lodash';

import exportAsCSV from '../../utils/csv';

function formatToArray(invoices = []) {
  return invoices.map(({
    invoiceId, practitionerId, isStaff, invoiceCreatedAt, fees, total,
  }) => [
    invoiceId,
    practitionerId,
    isStaff,
    invoiceCreatedAt,
    fees,
    total,
  ]);
}

export default function ValidateInvoices() {
  const [error, setError] = useState('');
  const [info, setInfo] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [invoices, setInvoices] = useState([]);

  const handleValidateInvoices = async () => {
    const formData = new FormData();
    const csv = document.querySelector('#validate-payments-file');
    if (!csv.files.length) {
      setError('You need to upload a csv file with the validated payments info.');
      return;
    }

    formData.append('providers_csv', csv.files[0]);

    try {
      setIsLoading(true);

      const { data, status, statusText } = await axios.post('/admin/monthly_payments/existing_invoice', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });

      if (status !== 200) {
        setError(statusText);
        return;
      }

      if (isEmpty(data.invoices)) {
        setInfo('Validate invoices complete. No existing invoices found for provided practitioner IDs.');
        return;
      }

      setInvoices(data.invoices || []);
    } catch (e) {
      const errorMsg = (e.response && e.response.data.error) || e.message;
      setError(errorMsg);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div>
      <h3>Validate Invoices</h3>
      <h4>Check all provided practitioner IDs for existing invoices.</h4>
      <div className="form-group">
        <label htmlFor="validate-payments-file">
            <div>Upload CSV <strong style={{color: "red"}}>*</strong></div>
            <div>(CSV format: ID)</div>
          <input
            id="validate-payments-file"
            onChange={() => setError('')}
            type="file"
            accept=".csv,.xls,.xlsx,"
            className="form-control"
            style={{ marginBottom: 15 }}
          />
        </label>
      </div>
      {info && <div className="alert alert-info">{info}</div>}
      {error && <div className="alert alert-error">{error}</div>}
      <button type="button" className="btn btn-primary" onClick={handleValidateInvoices} disabled={isLoading}>
        Validate Invoices
      </button>
      {isLoading && <div>Loading...</div>}
      {invoices.length > 0 && (
        <div style={{ maxHeight: 500, overflow: 'auto', marginTop: '50px' }}>
          <table cellPadding="8" border="1" width="100%">
            <thead>
              <tr>
                <td>Invoice Id</td>
                <td>Practitioner Id</td>
                <td>Is Staff</td>
                <td>Created At</td>
                <td>Total Fees</td>
                <td>Total</td>
              </tr>
            </thead>
            <tbody>
              {invoices.map(({
                invoiceId, invoiceCreatedAt, practitionerId, isStaff, total, fees,
              }) => (
                <tr key={invoiceId}>
                  <td>{invoiceId}</td>
                  <td>{practitionerId}</td>
                  {isStaff ? <td>Yes</td> : <td>No</td>}
                  <td>{invoiceCreatedAt}</td>
                  <td>{fees}</td>
                  <td>{total}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <button
            type="button"
            className="btn btn-primary pull-right"
            onClick={() => exportAsCSV(
              ['invoice id', 'practitioner id', 'is_staff', 'created at', 'total fees', 'total'],
              formatToArray(invoices),
              'validated-invoices.csv',
            )}
            style={{ marginTop: '10px' }}
          >
            Download
          </button>
        </div>
      )}
    </div>
  );
}
