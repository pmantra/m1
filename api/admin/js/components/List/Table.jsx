import React, { useEffect, Fragment } from 'react';
import { useTable, usePagination } from 'react-table';
import { isEmpty } from 'lodash';

const getCellUrl = (cell) => {
  switch (cell.column.id) {
    case 'uploaded_file':
      // Used for /admin/ca_member_transitions/, would be nice not to have implementation specific code here but for now :)
      return 'transition_logs/download_csv/' +cell.row.original["id"];
    default:
      return null;
  }
};

function Row({ row, timeZone }) {
  return (
    <tr {...row.getRowProps(row.original.rowProps)}>
      {row.cells.map((cell) => {
        const hrefValue = getCellUrl(cell);
        const cellProps = cell.getCellProps({
              className: cell.column.className,
              style: { ...cell.column.style },
            });
        return (
          <td
            {...cellProps}
          >
            {hrefValue ? (
              <a target="_blank" href={hrefValue} rel="noreferrer">
                {cell.render('Cell', { timeZone })}
              </a>
            ) : (
              <Fragment>{cell.render('Cell', { timeZone })}</Fragment>
            )}
          </td>
        );
      })}
    </tr>
  );
}


function Table({
    pageData, fetchPageData, loading, pageCount: controlledPageCount, columns, pageSize: pageSizeParam, timeZone, pageInitialIndex=0, showPagination=true
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
      state: { pageIndex, pageSize },
    } = useTable(
      {
        columns,
        data: pageData,
        initialState: { pageIndex: pageInitialIndex, pageSize: pageSizeParam },
        manualPagination: true, 
        pageCount: controlledPageCount,
      },
      usePagination,
    );
  
    useEffect(() => {
      fetchPageData({ pageIndex, pageSize });
    }, [pageIndex]);
  
    return (
      <Fragment>
        {loading && <p>Loading...</p>}
        {!loading && isEmpty(pageData) && <div className="alert alert-info">There is no data available.</div>}
      {!isEmpty(pageData) && (
        <Fragment>
            <table className="table table-striped table-bordered table-hover model-list cf" {...getTableProps()}>
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
                  return <Row key={row.id} row={row} timeZone={timeZone} />;
                })}
              </tbody>
            </table>
            {showPagination && ( <div className="pagination">
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
            </div>)}
          </Fragment>
        )}
      </Fragment>
    );
  }

export default Table;
