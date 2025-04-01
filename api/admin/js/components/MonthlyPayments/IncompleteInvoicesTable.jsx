import React, { useEffect, Fragment } from 'react';
import { useTable, usePagination } from 'react-table';
import { isEmpty } from 'lodash';

export const COLUMNS = [
  {
    header: 'ID',
    accessor: 'invoice_id',
    width: 40,
    url: '/admin/invoice/edit/?id=',
  },
  {
    header: 'Practitioner ID',
    accessor: 'practitioner_id',
    width: 80,
    url: '/admin/practitionerprofile/edit/?id=',
  },
  {
    header: 'Practitioner Email',
    accessor: 'practitioner_email',
    url: '/admin/practitionerprofile/edit/?id=',
  },
  {
    header: 'Amount Due',
    accessor: 'amount_due',
    width: 75,
    url: '',
  },
  {
    header: 'Bank Account Status',
    accessor: 'bank_account_status',
    width: 140,
    url: '',
  },
  {
    header: 'Stripe account ID',
    accessor: 'stripe_account_id',
    width: 200,
    url: '',
  },
];

const getCellUrl = (cell) => {
  switch (cell.column.id) {
    case 'invoice_id':
      return cell.column.url + cell.row.original.invoice_id;
    case 'practitioner_id':
      return cell.column.url + cell.row.original.practitioner_id;
    case 'practitioner_email':
      return cell.column.url + cell.row.original.practitioner_id;
    default:
      return cell.column.url;
  }
};

function Row({ row }) {
  return (
    <tr {...row.getRowProps()}>
      {row.cells.map((cell) => {
        const hrefValue = getCellUrl(cell);
        return (
          <td
            {...cell.getCellProps({
              style: {
                width: cell.column.width,
              },
            })}
          >
            {cell.column.url ? (
              <a target="_blank" href={hrefValue} rel="noreferrer">
                {cell.render('Cell')}
              </a>
            ) : (
              <Fragment>{cell.render('Cell')}</Fragment>
            )}
          </td>
        );
      })}
    </tr>
  );
}

export function IncompleteInvoicesTable({
  pageInvoices, fetchPageInvoices, loading, pageCount: controlledPageCount,
}) {
  const {
    getTableProps,
    getTableBodyProps,
    headerGroups,
    page,
    nextPage,
    previousPage,
    canNextPage,
    canPreviousPage,
    pageOptions,
    gotoPage,
    pageCount,
    prepareRow,
    // Get the state from the instance
    state: { pageIndex, pageSize },
  } = useTable(
    {
      columns: COLUMNS,
      data: pageInvoices,
      initialState: { pageIndex: 0 },
      manualPagination: true, // we will handle our own data fetching
      pageCount: controlledPageCount,
    },
    usePagination,
  );

  // Listen for changes in pagination and use the state to fetch our new data
  useEffect(() => {
    fetchPageInvoices({ pageIndex, pageSize });
  }, [pageIndex]);

  return (
    <Fragment>
      {loading && <p>Loading...</p>}
      {!loading && isEmpty(pageInvoices) && <div className="alert alert-info">There are no incomplete invoices.</div>}
      {!loading && !isEmpty(pageInvoices) && (
        <Fragment>
          <table cellPadding="8" border="1" width="100%" style={{ tableLayout: 'fixed' }} {...getTableProps()}>
            <thead>
              {headerGroups.map((headerGroup) => (
                <tr {...headerGroup.getHeaderGroupProps()}>
                  {headerGroup.headers.map((column) => (
                    <th
                      {...column.getHeaderProps({
                        style: { width: column.width },
                      })}
                    >
                      {column.render('header')}
                    </th>
                  ))}
                </tr>
              ))}
            </thead>
            <tbody {...getTableBodyProps()}>
              {page.map((row) => {
                prepareRow(row);
                return <Row key={row.id} row={row} />;
              })}
            </tbody>
          </table>
          <p>
            Showing
            {' '}
            {page.length}
            {' '}
            of ~
            {controlledPageCount * pageSize}
            {' '}
            results
          </p>
          <div>
            <span>
              Page
              {' '}
              <strong>
                {pageIndex + 1}
                {' '}
                of
                {pageOptions.length}
              </strong>
              {' '}
            </span>
            <button type="button" onClick={() => gotoPage(0)} disabled={!canPreviousPage}>
              {'<<'}
            </button>
            <button type="button" onClick={() => previousPage()} disabled={!canPreviousPage}>
              Previous
            </button>
            <button type="button" onClick={() => nextPage()} disabled={!canNextPage}>
              Next
            </button>
            <button type="button" onClick={() => gotoPage(pageCount - 1)} disabled={!canNextPage}>
              {'>>'}
            </button>
          </div>
        </Fragment>
      )}
    </Fragment>
  );
}
