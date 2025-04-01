import React from 'react';
import moment from 'moment-timezone';
import axios from 'axios';
import { uniqueId } from 'lodash';
import { AvailableBlock } from './AvailableBlock.jsx';
import TimeZoneSelect from './TimeZoneSelect.jsx';

import { formatDateTime } from '../utils/time.js';

const practitionerDefaultTimeZone = { label: '(GMT-05:00) Eastern Time', value: 'America/New_York' };

function ScheduledAvailability({
  scheduledAvailability,
  formatDate,
  timeZone,
  dateTimeFormat,
}) {
  return (
    <div>
      <div>
        <h3>Scheduled Availability</h3>
      </div>
      <div style={{ maxHeight: 500, overflow: 'auto' }}>
        <table cellPadding="8" border="1" width="100%">
          <thead>
            <tr>
              <th>Starts At</th>
              <th>Ends At</th>
              <th>Description</th>
              <th>Created At</th>
            </tr>
          </thead>
          <tbody>
            {scheduledAvailability.map((availability) => (
              <tr key={uniqueId()}>
                <td>{formatDate(availability.starts_at, timeZone, dateTimeFormat)} </td>
                <td>{formatDate(availability.ends_at, timeZone, dateTimeFormat)} </td>
                <td>{availability.description}</td>
                <td>{formatDate(availability.created_at, timeZone, dateTimeFormat)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Appointments({ appointments, title, timeZone, dateTimeFormat, formatDate }) {
  return (
    <div>
      <div>
        <h3>{title}</h3>
      </div>
      <table cellPadding="8" border="1" width="100%">
        <thead>
          <tr>
            <th>ID</th>
            <th>Scheduled Start</th>
            <th>Scheduled End</th>
            <th>Is Intro</th>
            <th>Member Name</th>
            <th>Member ID</th>
            <th>Cancelled At</th>
            <th>Rescheduled From</th>
          </tr>
        </thead>
        <tbody>
          {appointments.map((appointment) => (
            <tr key={uniqueId()}>
              <td>
                <a href={`/admin/appointment/edit/?id=${appointment.id}`}>{appointment.id}</a>
              </td>
              <td>{formatDate(appointment.scheduled_start, timeZone, dateTimeFormat)}</td>
              <td>{formatDate(appointment.scheduled_end, timeZone, dateTimeFormat)}</td>
              <td>{appointment.is_intro ? 'Intro' : ''}</td>
              <td>{appointment.member.full_name}</td>
              <td>{appointment.member.id}</td>
              <td>{formatDate(appointment.cancelled_at, timeZone, dateTimeFormat)}</td>
              <td>{formatDate(appointment.rescheduled_from_previous_appointment_time, timeZone, dateTimeFormat)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const getFutureDate = (daysOut) => moment().add(daysOut, 'days').format('YYYY-MM-DD');

class PractitionerProfile extends React.Component {
  constructor(props) {
    super(props);
    const minStartDate = moment().format('YYYY-MM-DD');
    const minEndDate = getFutureDate(props.args.BOOKABLE_TIMES_MIN_DAYS);


    this.state = {
      availableBlocks: [],
      scheduledAvailability: [],
      upcomingAppointments: [],
      pastAppointments: [],
      timeZone: practitionerDefaultTimeZone,
      productId: props.args.products[0] ? props.args.products[0].id : null,
      endDate: minEndDate,
      startDate: minStartDate,
      errorMessage: null,
      loading: true,
    };
  }

  componentDidMount() {
    const { productId } = this.state;
    if (productId) {
      this.loadData();
    }
  }

  onChangeZone = (timeZone) => {
    this.setState({ timeZone });
  };

  onChangeProduct = (productId) => {
    this.setState({ productId }, this.loadData);
  };

  onChangeEndDate = (endDate) => {
    const { minEndDate, maxEndDate } = this.state;
    if (endDate < minEndDate || endDate > maxEndDate) {
      return;
    }

    this.setState({ endDate }, this.loadData);
  };

  onChangeStartDate = (startDate) => {
    const { minStartDate, maxStartDate } = this.state;
    if (startDate < minStartDate || startDate > maxStartDate) {
      return;
    }

    this.setState({ startDate }, this.loadData);
  };

  loadData() {
    const { productId, endDate, startDate } = this.state;
    const {
      args: { practitionerId },
    } = this.props;
    const days = moment(endDate).diff(moment(startDate), 'days') + 1;
    const url = `/admin/practitionerprofile/bookable_times/?id=${practitionerId}&product_id=${productId}&days=${days}&start_date=${startDate}`;

    axios.get(url).then((response) => {
      if (response.data.error) {
        this.setState({ errorMessage: response.data.error, loading: false });
        return;
      }

      const availableBlocks = response.data.available_times;
      const scheduledAvailability = response.data.scheduled_availability;
      const upcomingAppointments = response.data.upcoming_appointments;
      const pastAppointments = response.data.past_appointments;
      
      this.setState({
        scheduledAvailability,
        upcomingAppointments,
        pastAppointments,
        availableBlocks,
        errorMessage: null,
        loading: false,
      });
    });
  }

  render() {
    const { args } = this.props;
    const {
      loading,
      availableBlocks,
      timeZone,
      productId,
      endDate,
      minEndDate,
      maxEndDate,
      startDate,
      minStartDate,
      maxStartDate,
      errorMessage,
      scheduledAvailability,
      upcomingAppointments,
      pastAppointments,
    } = this.state;
    const dateTimeFormat = 'MMMM Do YYYY, h:mm a';

    /**
     * Returns a mapping of a formatted date to an array of timestamps e.g.:
     *
     * {
     *     "Fri, June 4th 2021": ["2021-06-04T15:34:11", "2021-06-04T15:34:11"]
     * }
     */
    const groupedTimes = availableBlocks.reduce((accumulator, timeBlock) => {
      const startTime = timeBlock.scheduled_start;
      const formattedDate = [timeBlock.scheduled_start, timeBlock.scheduled_end];

      const date = formatDateTime(startTime, timeZone.value, 'ddd, MMMM Do YYYY');

      return { ...accumulator, [date]: [...(accumulator[date] || []), formattedDate] };
    }, {});

    if (!productId) {
      return <div>No products</div>;
    }

    if (loading) {
      return (
        <div>
          <h3>Available Times</h3>
          <div className="spinner-border" role="status">
            <span className="sr-only">Loading...</span>
          </div>
        </div>
      );
    }
    return (
      <div>
        <div style={{ display: 'inline-block', marginRight: 10 }}>
          <p htmlFor="available-times-time-zone">Time Zone</p>
          <TimeZoneSelect onChangeZone={this.onChangeZone} inputId="available-times-time-zone" selectedTimeZone={practitionerDefaultTimeZone} />
        </div>
        <div>
          <h3>Available Times</h3>
          {errorMessage && <div className="alert alert-error">{errorMessage}</div>}
          <div style={{ display: 'block', marginRight: 10 }}>
            <label htmlFor="available-times-product" style={{display: 'inline-block'}}>Product
            <select
              id="available-times-product"
              onChange={(event) => this.onChangeProduct(event.target.value)}
              style={{ width: 100, marginLeft: 5 }}
            >
              {args.products.map((product) => (
                <option value={product.id} key={product.id}>
                  {product.minutes} min
                </option>
              ))}
            </select>
            </label>
          </div>


          <div style={{ display: 'inline-block', marginRight: 10 }}>
            <label htmlFor="available-times-start-date">
              Start Date
              <input
                id="available-times-start-date"
                onChange={(event) => this.onChangeStartDate(event.target.value)}
                type="date"
                value={startDate}
                min={minStartDate}
                max={maxStartDate}
                style={{ height: 30, marginLeft: 5 }}
              />
            </label>
          </div>

          <div style={{ display: 'inline-block', marginRight: 10 }}>
            <label htmlFor="available-times-end-date">
              End Date
              <input
                id="available-times-end-date"
                onChange={(event) => this.onChangeEndDate(event.target.value)}
                type="date"
                value={endDate}
                min={minEndDate}
                max={maxEndDate}
                style={{ height: 30, marginLeft: 5 }}
              />
            </label>
          </div>

        </div>
        <div style={{ maxHeight: 500, overflow: 'auto' }}>
          <table cellPadding="8" border="1" width="100%">
            <thead>
              <tr>
                <th>Date</th>
                <th>Start Time</th>
                <th>End Time</th>
                <th>Copy ID</th>
                <th>Copy<br />Date/Time</th>
              </tr>
            </thead>
            <tbody>
              {Object.keys(groupedTimes).map((date) =>
                groupedTimes[date].map((timeBlock, index) => (
                  <AvailableBlock
                    productId={productId}
                    key={timeBlock}
                    date={date}
                    timeBlock={timeBlock}
                    index={index}
                    timeZone={timeZone.value}
                    formatDateTime={formatDateTime}
                  />
                )),
              )}
            </tbody>
          </table>
        </div>
        <ScheduledAvailability
          timeZone={timeZone.value}
          dateTimeFormat={dateTimeFormat}
          scheduledAvailability={scheduledAvailability}
          formatDate={formatDateTime}
        />
        <Appointments
          timeZone={timeZone.value}
          dateTimeFormat={dateTimeFormat}
          appointments={upcomingAppointments}
          formatDate={formatDateTime}
          title="Upcoming Appointments"
        />
        <Appointments
          timeZone={timeZone.value}
          dateTimeFormat={dateTimeFormat}
          appointments={pastAppointments}
          formatDate={formatDateTime}
          title="Past Appointments (last 72 UTC hours)"
        />
      </div>
    );
  }
}

export default PractitionerProfile;
