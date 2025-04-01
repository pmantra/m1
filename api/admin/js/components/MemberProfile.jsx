import React from 'react';
import Select from 'react-select';
import moment from 'moment-timezone';
import { uniqueId } from 'lodash';
import defaultTimezones from './timezones.json';
import commonTimezones from './most-common-timezones.json';


function Appointments({ appointments, timeZone, dateTimeFormat, formatDateTime, lastRescheduleRecordDic }) {

  return (
    <div>
      <table cellPadding="8" border="1" width="100%">
        <thead>
          <tr>
            <th>ID</th>
            <th>State</th>
            <th>Scheduled Start</th>
            <th>Scheduled End</th>
            <th>Practitioner</th>
            <th>Rescheduled From</th>
          </tr>
        </thead>
        <tbody>
          {appointments.map((appointment) => (
            <tr key={uniqueId()}>
              <td>
                <a href={`/admin/appointment/edit/?id=${appointment.id}`} target="_blank" rel="noreferrer">{appointment.id}</a>
              </td>
              <td>
                {appointment.state}
                {
                      (appointment.state==="CANCELLED") ? ` at ${  formatDateTime(appointment.cancelled_at, timeZone, dateTimeFormat)}` : ""
                }
              </td>
              <td>{formatDateTime(appointment.scheduled_start, timeZone, dateTimeFormat)}</td>
              <td>{formatDateTime(appointment.scheduled_end, timeZone, dateTimeFormat)}</td>
              <td><a href={`/admin/practitionerprofile/edit/?id=${appointment.practitioner.id}`}>{appointment.practitioner.full_name}</a>, {appointment.product.name}</td>
              <td>{ (appointment.id in lastRescheduleRecordDic) ? 
              formatDateTime(lastRescheduleRecordDic[appointment.id], timeZone, dateTimeFormat) : "Null"
              }</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const getTimeZoneOptions = (timeZones) =>
  Object.keys(timeZones).map((tz) => ({
    label: tz,
    value: timeZones[tz],
  }));

const formatDateTime = (dateTime, timeZone, format = 'LT') => {
  if (!dateTime) {
    return null;
  }
  return moment.utc(dateTime).tz(timeZone).format(format);
};

class MemberProfile extends React.Component {
  constructor(props) {
    super(props);
    this.state = {
      timeZone: { label: '(GMT-05:00) Eastern Time', value: 'America/New_York' },
    };
  }
  
  onChangeZone = (timeZone) => {
    this.setState({ timeZone });
  };

  render() {
    const {
      timeZone,
    } = this.state;
    const dateTimeFormat = 'MMMM Do YYYY, h:mm a';

    const {
      args: { appointments, lastRescheduleRecordDic },
    } = this.props;

    return (
      <div>
        <div style={{ display: 'inline-block', marginRight: 10, marginBottom: 10}}>
          <h3 htmlFor="available-times-time-zone">Appointments</h3>
          <Select
            options={[
              { label: 'common', options: getTimeZoneOptions(commonTimezones) },
              { label: 'more', options: getTimeZoneOptions(defaultTimezones) },
            ]}
            onChange={this.onChangeZone}
            defaultValue={timeZone}
            inputId="available-times-time-zone"
            style={{ width: 200 }}
            styles={{
              input: (provided) => ({ ...provided, '& input': { boxShadow: 'none !important' } }),
            }}
          />
        </div>


        <Appointments
          timeZone={timeZone.value}
          dateTimeFormat={dateTimeFormat}
          appointments={appointments}
          formatDateTime={formatDateTime}
          lastRescheduleRecordDic={lastRescheduleRecordDic}
        />
      </div>
    );
  }
}

export default MemberProfile;
