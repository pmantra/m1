import React, { useState } from 'react';
import axios from 'axios';
import { isFinite, isNil } from 'lodash';

import '../bootstrap/css/bootstrap.scss';
import '../bootstrap/css/bootstrap-theme.scss';

function GlobalControlForm({ onSubmit, onChange, label, val }) {
  return (
    <form onSubmit={onSubmit} style={{ marginBottom: '0px' }}>
      <div className="input-append">
        <label htmlFor="control-form-input">
          {label}
          <input
            id="control-form-input"
            min="0"
            value={val}
            onChange={(e) => onChange(e.target.value)}
            style={{ height: '30px', width: '100px' }}
            type="number"
            className="span2"
          />
        </label>
        <button type="submit" value="Submit" className="btn">
          Apply
        </button>
      </div>
    </form>
  );
}

function CareTeamGlobalControls({
  globalPrepBufferMax,
  globalBookingBufferMax,
  globalMaxCapacityMax,
}) {
  const [prepBuffer, setPrepBuffer] = useState('');
  const [bookingBuffer, setBookingBuffer] = useState('');
  const [maxCapacity, setMaxCapacity] = useState('');
  const [error, setError] = useState(false)

  const handlePrepBufferSubmit = (e) => {
    setError(null)
    e.preventDefault();

    const parsedPrepBuffer = parseInt(prepBuffer, 10);
    if (!isFinite(parsedPrepBuffer)) {
      return;
    }

    if (parsedPrepBuffer > globalPrepBufferMax) {
      alert(`global prep buffer must be between 0 and ${globalPrepBufferMax}`);
      return;
    }

    if (
      !window.confirm(
        `Setting the global prep buffer to: ${parsedPrepBuffer} minutes, press OK to continue.`,
      )
    ) {
      return;
    }

    axios
      .post('/admin/care_team_control_center/global_prep_buffer', {
        global_prep_buffer: parsedPrepBuffer,
      })
      .then(({ data }) => {
        alert(`${data.count} cx prep buffers updated`);
        window.location.reload();
      })
      .catch((err) => {
        alert(`error: ${err.response.data}`);
      });
  };

  const handleBookingBufferSubmit = (e) => {
    e.preventDefault();

    const parsedBookingBuffer = parseInt(bookingBuffer, 10);
    if (!isFinite(parsedBookingBuffer)) {
      return;
    }

    if (parsedBookingBuffer > globalBookingBufferMax) {
      alert(`global booking buffer must be between 0 and ${globalBookingBufferMax}`);
      return;
    }

    if (
      !window.confirm(
        `Setting the global booking buffer to: ${parsedBookingBuffer} minutes, press OK to continue.`,
      )
    ) {
      return;
    }

    axios
      .post('/admin/care_team_control_center/global_booking_buffer', {
        global_booking_buffer: parsedBookingBuffer,
      })
      .then(({ data }) => {
        alert(`${data.count} cx booking buffers updated`);
        window.location.reload();
      })
      .catch((err) => {
        alert(`error ${err.response.data}`);
      });
  };

  const handleMaxCapacitySubmit = (e) => {
    e.preventDefault();

    const parsedMaxCapacity = parseInt(maxCapacity, 10);
    if (!isFinite(parsedMaxCapacity)) {
      return;
    }

    if (parsedMaxCapacity > globalMaxCapacityMax) {
      alert(`global max capacity must be between 0 and ${globalMaxCapacityMax}`);
      return;
    }

    if (
      !window.confirm(
        `Setting the global max capacity to: ${parsedMaxCapacity}, press OK to continue.`,
      )
    ) {
      return;
    }

    axios
      .post('/admin/care_team_control_center/global_max_capacity', {
        global_max_capacity: parsedMaxCapacity,
      })
      .then(({ data }) => {
        alert(`${data.count} cx max capacity updated`);
        window.location.reload();
      })
      .catch((err) => {
        const errorMsg = (err.response && err.response.data.error) || err.message || err.error;
        setError(errorMsg);
      });
  };

  return (
    <div classNmae="set-global">
      {error && <div className="alert alert-error" width="100%">{error}</div>}
    <table className="table" width="100%" style={{ marginBottom: '0px' }}>
      <tbody>
        <tr>
          <td style={{ borderTop: 'none', width: '40%' }}>
            <h2>Care Advocate Capacity</h2>
          </td>
          <td style={{ borderTop: 'none', width: '20%' }}>
            <GlobalControlForm
              label="Global Prep Buffer"
              onSubmit={handlePrepBufferSubmit}
              onChange={setPrepBuffer}
              val={prepBuffer}
            />
          </td>
          <td style={{ borderTop: 'none', width: '20%' }}>
            <GlobalControlForm
              label="Global Booking Buffer"
              onSubmit={handleBookingBufferSubmit}
              onChange={setBookingBuffer}
              val={bookingBuffer}
            />
          </td>
          <td style={{ borderTop: 'none', width: '20%' }}>
            <GlobalControlForm
              label="Global Total Daily Capacity"
              onSubmit={handleMaxCapacitySubmit}
              onChange={setMaxCapacity}
              val={maxCapacity}
            />
          </td>
        </tr>
      </tbody>
    </table>
      </div>
  );
}

function CareTeamControlCenter({ args }) {
  const allAssignableCx = args.all_assignable_cx || [];

  return (
    <div className="container">
      <CareTeamGlobalControls
        globalBookingBufferMax={args.GLOBAL_BOOKING_BUFFER_MAX}
        globalMaxCapacityMax={args.GLOBAL_MAX_CAPACITY_MAX}
        globalPrepBufferMax={args.GLOBAL_PREP_BUFFER_MAX}
      />
      <table className="table table-striped" width="100%">
        <thead>
          <tr>
            <th style={{ width: '40%' }}>Name</th>
            <th style={{ width: '15%' }}>Prep Buffer</th>
            <th style={{ width: '15%' }}>Booking Buffer</th>
            <th style={{ width: '15%' }}>Total Daily Capacity</th>
            <th style={{ width: '15%' }}>Daily Intro Capacity</th>
          </tr>
        </thead>
        <tbody>
          {allAssignableCx.map((aa) => (
            <tr key={aa.practitioner_id}>
              <td>
                <a target="_new" href={`practitionerprofile/edit/?id=${aa.practitioner_id}`}>
                  {aa.full_name}
                </a>
              </td>
              <td>{aa.prep_buffer} mins </td>
              <td>{aa.booking_buffer} mins</td>
              <td>
                <a target="_new" href={`/admin/assignableadvocate/edit/?id=${aa.practitioner_id}`}>
                  {isNil(aa.max_capacity) ? 'not set' : `${aa.max_capacity} appts`}
                </a>
              </td>
              <td>
                <a target="_new" href={`/admin/assignableadvocate/edit/?id=${aa.practitioner_id}`}>
                  {isNil(aa.daily_intro_capacity) ? 'not set' : `${aa.daily_intro_capacity} appts`}
                </a>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default CareTeamControlCenter;
