import React, { useState, useRef } from 'react';
import { slice } from 'lodash';

import axios from 'axios';
import { IncompleteInvoicesTable } from './IncompleteInvoicesTable.jsx';

export const fetchBackendIncompleteInvoices = async (offset, limit) => {
  const { data } = await axios.get(`/admin/monthly_payments/incomplete_invoices?offset=${offset}&limit=${limit}`);
  return data;
};

export default function ViewIncompleteInvoices() {
  const [loading, setLoading] = useState(false);

  // invoices keeps track of all incomplete invoices as we fetch them
  const [invoices, setInvoices] = useState([]);
  // pageInvoices keeps track of incomplete invoices that should be shown in current page
  const [pageInvoices, setPageInvoices] = useState([]);
  const [error, setError] = useState('');
  const [pageCount, setPageCount] = useState(0);
  const nextPageIndexToFetchRef = useRef(0);

  async function loadIncompleteInvoices(offset, pageSize) {
    try {
      setLoading(true);
      setError('');

      const data = await fetchBackendIncompleteInvoices(offset, pageSize);

      setInvoices([...invoices, ...data.incomplete_invoices]);
      setPageInvoices(data.incomplete_invoices);
      setPageCount(Math.ceil(data.pagination.total / data.pagination.limit));
    } catch (e) {
      const errorMsg = (e.response && e.response.data.error) || e.message;
      setError(errorMsg);
    } finally {
      setLoading(false);
    }
  }

  const fetchPageInvoices = ({ pageSize, pageIndex }) => {
    setLoading(true);
    setError('');

    const offset = pageSize * pageIndex;

    // Only fetch data when needed
    // (else, assume it has been already fetched and exists in 'invoices')
    if (pageIndex === nextPageIndexToFetchRef.current) {
      nextPageIndexToFetchRef.current += 1;
      loadIncompleteInvoices(offset, pageSize);
    } else {
      // If there is no need to fetch data,
      // just update pageInvoices with the corresponding invoices slice
      setPageInvoices(slice(invoices, offset, offset + pageSize));
      setLoading(false);
    }
  };

  return (
    <div>
      <h3>View Incomplete Invoices</h3>
      {error && <div className="alert alert-error">{error}</div>}
      {!error && (
        <div>
          <IncompleteInvoicesTable
            pageInvoices={pageInvoices}
            fetchPageInvoices={fetchPageInvoices}
            loading={loading}
            pageCount={pageCount}
          />
        </div>
      )}
    </div>
  );
}
