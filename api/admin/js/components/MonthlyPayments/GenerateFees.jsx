import React, { useState } from 'react';
import axios from 'axios';
import { isEmpty } from 'lodash';
import moment from 'moment';

import exportAsCSV from '../../utils/csv';

const DATE_FORMAT = 'YYYY-MM-DD';

function formatToArray(fees = []) {

  return fees.map((fee) => [
    fee.fae_id,
    fee.practitioner_id,
    fee.practitioner_name,
    fee.amount,
    fee.status,
  ]);
}

export default function GenerateFees() {
  const [error, setError] = useState('');
  const [info, setInfo] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [fees, setFees] = useState([]);
  const [date, setDate] = useState(moment().date(0).format(DATE_FORMAT));
  const [allowToGenerate, setAllowToGenerate] = useState(false);

  const handleGenerateFees = async () => {
    const formData = new FormData();
    const csv = document.querySelector('#providers-validated-payments-file');
    setAllowToGenerate(false);
    if (!csv.files.length) {
      setError('You need to upload a csv file with the validated payments info.');
      return;
    }

    formData.append('providers_validated_payments_csv', csv.files[0]);
    formData.append('payment_date', moment(date, DATE_FORMAT).format('MM/DD/YYYY'));
    csv.value = null;

    try {
      setIsLoading(true);

      const { data, status, statusText } = await axios.post('/admin/monthly_payments/generate_fees', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });

      if (status !== 200) {
        setError(statusText);
        return;
      }

      if (isEmpty(data.fees)) {
        setInfo('No fees generated for the provided practitioner IDs');
        return;
      }

      setFees(data.fees || []);

    } catch (e) {
      const errorMsg = (e.response && e.response.data.error) || e.message;
      setError(errorMsg);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div>
      <h3>Generate Fees</h3>
      <div className="form-group" style={{ display: 'flex' }}>
        <div>
          <label htmlFor="providers-validated-payments-file">
            <div>Upload CSV <strong style={{color: "red"}}>*</strong></div>
            <div>(CSV format: ID, Final Payment Amount)</div>

            <input
              id="providers-validated-payments-file"
              onChange={() => setError('')}
              type="file"
              accept=".csv,.xls,.xlsx,"
              className="form-control"
              style={{ marginBottom: 15 }}
            />
          </label>
        </div>
      </div>
      <div>
        <label htmlFor="payments-date">
          Date
          <input
            className="form-control"
            id="payments-date"
            onChange={(e) => setDate(e.target.value)}
            value={date}
            min={moment().subtract(1, 'months').format(DATE_FORMAT)}
            max={moment().format(DATE_FORMAT)}
            type="date"
            style={{ height: 30, marginLeft: 10 }}
          />
        </label>
      </div>
      {info && <div className="alert alert-info">{info}</div>}
      {error && <div className="alert alert-error" style={{ whiteSpace: 'pre-wrap' }}>{error}</div>}
      <div style={{ display: 'flex' }}>
        <label htmlFor="allow-generate">
          Generating fees cannot be undone <strong style={{color: "red"}}>*</strong>
          <input
            onChange={() => setAllowToGenerate(!allowToGenerate)}
            style={{ marginLeft: '10px', marginTop: '0px' }}
            id="allow-generate"
            type="checkbox"
            checked={allowToGenerate}
          />
        </label>
      </div>
      <button
        type="button"
        className="btn btn-primary"
        onClick={handleGenerateFees}
        disabled={!allowToGenerate || isLoading}
      >
        Generate Fees
      </button>
      {isLoading && <div>Loading...</div>}
      {fees.length > 0 && (
        <div style={{ maxHeight: 500, overflow: 'auto', marginTop: '50px' }}>
          <table cellPadding="8" border="1" width="100%" style={{ tableLayout: 'fixed' }}>
            <thead>
              <tr>
                <td style={{ width: '178px' }}>Fee Accounting Entry ID</td>
                <td style={{ width: '114px' }}>Practitioner ID</td>
                <td style={{ width: '170px' }}>Practitioner Name</td>
                <td style={{ width: '114px' }}>Amount</td>
                <td>Status</td>
              </tr>
            </thead>
            <tbody>
              {fees.map((fee) => (
                <tr key={fee.fae_id}>
                  <td>
                    <a target="_blank" href={`/admin/feeaccountingentry/edit/?id=${fee.fae_id}`} rel="noreferrer">
                      {fee.fae_id}
                    </a>
                  </td>
                  <td>
                    <a target="_blank" href={`/admin/practitionerprofile/edit/?id=${fee.practitioner_id}`} rel="noreferrer">
                      {fee.practitioner_id}
                    </a>
                  </td>
                  <td>
                    <a target="_blank" href={`/admin/practitionerprofile/edit/?id=${fee.practitioner_id}`} rel="noreferrer">
                      {fee.practitioner_name}
                    </a>
                  </td>
                  <td>{fee.amount}</td>
                  <td>{fee.status}</td>
                </tr>
              ))}
            </tbody>
          </table>

          <button
            type="button"
            className="btn btn-primary pull-right"
            onClick={() => exportAsCSV(
              ['fee accounting entry id', 'practitioner id', 'practitioner name', 'amount', 'status'],
                formatToArray(fees), // convert from array of objects, to array of arrays
              'generated-fees.csv',
            )}
            style={{ marginTop: '10px', marginLeft: '10px' }}
          >
            Download
          </button>
        </div>
      )}
    </div>
  );
}
