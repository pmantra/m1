import React, { useMemo, useState, Fragment } from 'react';
import { has } from 'lodash';

import Table from './Table.jsx';
import { fetchData, formatURL } from './helpers.js';
import TimeZoneSelect from '../TimeZoneSelect.jsx';

import { formatDateTime } from '../../utils/time.js';

import defaultTimezones from '../timezones.json';
import commonTimezones from '../most-common-timezones.json';

const allTimeZones = { ...commonTimezones, ...defaultTimezones};

const flexCellStyle = {
  width: '1%',
  whiteSpace: 'nowrap',
};

function getEditMarkup(deleteConf) {
  return {
    header: () => null,
    id: 'EditURL',
    accesor: 'EditURL',
    className: 'list-buttons-column',
    style: { width: '1%' }, 
    Cell: ({ row }) => (
      <Fragment>
        {(deleteConf && deleteConf.canEdit && <a
          className="icon" 
          href={row.original.EditURL}
          title="Edit Record"
        >
          <span className="fa fa-pencil glyphicon icon-pencil" />
        </a>)}
        {(deleteConf && deleteConf.canDelete && row.original.canDelete && <form className="icon" method="POST" action={deleteConf.deleteFormUrl}>
            <input id="id" name="id" required="" type="hidden" value={row.original.id} />
            <input id="url" name="url" type="hidden" value={deleteConf.hiddenUrl} />
            <button type="submit" onClick={
              (ev) => { 
                if (!window.confirm('Are you sure you want to delete this record?')) {
                  ev.preventDefault();
                }
              }
            } title="Delete record">
              <span className="fa fa-trash glyphicon icon-trash" />
            </button>
          </form>
        )}
      </Fragment>
    ),
  }
}

function getActionsMarkup() {
  return {
    header: () => null,
    id: 'Actions',
    accesor: 'Actions',
    style: flexCellStyle,
    Cell: ({ row }) => (
      <input type="checkbox" name="rowid" className="action-checkbox" value={row.original.ID} title="Select record" />
    ),
  }
}

function FormattedDateCell({value , timeZone}) {
  if (!value) return '';
  return `${formatDateTime(value, timeZone.value, 'YYYY-MM-DD h:mm a')} ${timeZone.label}`;
}

function DescArrow() {
  return <i className="fa fa-chevron-down icon-chevron-down" />
}
function AscArrow() {
  return <i className="fa fa-chevron-up icon-chevron-up" />
}

function formattedSortableHeader(label, url, sort, currentSort, desc="") {
  let sortableURL = url.includes('?') ? `${url}&sort=${sort}` : `${url}?sort=${sort}`;
  const sortSelected = parseInt(sort, 10) === parseInt(currentSort, 10);
  if (sortSelected && desc !== "") {
    return <a href={sortableURL}>{label} <AscArrow /></a>;
  }

  sortableURL = sortSelected ? `${sortableURL}&desc=1` : sortableURL;
  return <a href={sortableURL}>{label} {sortSelected ? <DescArrow /> : null}</a>;
}

const FORMATTED_FIELDS_TO_CELL = {
  dateWithTimezone: FormattedDateCell,
}

function toReactTableColums(columns = [], deleteConf={ canDelete: false, canEdit: true }, hasActions=false, formattedURL="", currentSort="", desc="") {

  let formattedColumns =  columns.map(({ id, label, formatterType, sort }) => {

    const finalLabel = sort ? formattedSortableHeader(label, formattedURL, sort, currentSort, desc): label;
      if (formatterType && FORMATTED_FIELDS_TO_CELL[formatterType]) {
        return {
          header: finalLabel,
          accessor: id ? id : label,
          Cell: FORMATTED_FIELDS_TO_CELL[formatterType],
        }
      }

      return {
        header: finalLabel,
        accessor: id ? id : label,
        style: label === 'ID' ? flexCellStyle : {},
      }
    }
  );
  
  formattedColumns = [getEditMarkup(deleteConf), ...formattedColumns];

  if (hasActions) {
    formattedColumns = [getActionsMarkup(), ...formattedColumns];
  }

  return formattedColumns;
}


function List({ args: { dataUrl, columnsConf, filters, pageSize=10, search, deleteConf, canDelete=false, canEdit=true, hasActions, title, page=0, sort, desc, tz="America/New_York", showTz=true, showPagination=true } }) {
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState([]);
  const [pageData, setPageData] = useState([]);
  const [error, setError] = useState('');
  const [pageCount, setPageCount] = useState(0);
  const [timeZone, setTimeZone] = useState({ 
    label: Object.keys(allTimeZones).find(key => allTimeZones[key] === tz),
    value: tz,
  });

  const columns = useMemo(() => toReactTableColums(columnsConf, { ...deleteConf, canDelete, canEdit }, hasActions, formatURL("", page, search, pageSize, filters, ""), sort, desc), [])

  async function loadData(url, pageIndex, size, filtersParams) {
    try {
      setLoading(true);
      setError('');
      const res = await fetchData(url, pageIndex, search, size, filtersParams, sort, desc);

      setData({...data, [pageIndex]: res.data.items});
      setPageData(res.data.items);
      setPageCount(Math.ceil(res.data.pagination.total / res.data.pagination.limit));
    } catch (e) {
      const errorMsg = (e.response && e.response.data.error) || e.message;
      setError(errorMsg);
    } finally {
      setLoading(false);
    }
  }

  const fetchPageData = ({ pageSize: size, pageIndex }) => {
    setLoading(true);
    setError('');

    if (has(data, pageIndex)) {
      setPageData(data[pageIndex]);
      setLoading(false);
      return;
    }
    loadData(dataUrl, pageIndex, size, filters);
  };
  return (
    <div className="container">
      {showTz && (
        <div style={{ display: 'inline-block', marginBottom: 10 }}>
          <TimeZoneSelect selectedTimeZone={timeZone} onChangeZone={setTimeZone} />
        </div>
      )}
      {title && <h3>title</h3>}
      {error && <div className="alert alert-error">{error}</div>}
      {!error && (
        <div>
          <Table
            pageData={pageData}
            fetchPageData={fetchPageData}
            loading={loading}
            pageCount={pageCount}
            columns={columns}
            pageSize={pageSize}
            pageInitialIndex={page}
            timeZone={timeZone}
            showPagination={showPagination}
          />
        </div>
      )}
    </div>
  );
}

export default List;
