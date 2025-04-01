import React, { useState } from 'react';
import Select from 'react-select';

import axios from "axios";
import defaultTimezones from './timezones.json';
import commonTimezones from './most-common-timezones.json';

const getTimeZoneOptions = (timeZones) =>
  Object.keys(timeZones).map((tz) => ({
    label: tz,
    value: timeZones[tz],
  }));

const defaultTimeZone = { label: '(GMT-05:00) Eastern Time', value: 'America/New_York' };

function TimeZoneSelect({ onChangeZone, inputId, selectedTimeZone=defaultTimeZone }) {
  const [timeZone, setTimeZone] = useState(selectedTimeZone);

  async function postNewTimezone(newTimeZone) {
    try {
      const tzUrl = `/admin/practitionerprofile/new_time_zone?tz=${newTimeZone}`;
      await axios.get(tzUrl);
    } catch (e) {
      const errorMsg = (e.response && e.response.data.error) || e.message;
      alert(errorMsg);
    }
  }

  return (
    <Select
      options={[
        { label: 'common', options: getTimeZoneOptions(commonTimezones) },
        { label: 'more', options: getTimeZoneOptions(defaultTimezones) },
      ]}
      onChange={(newTimeZone) => {
        setTimeZone(newTimeZone);
        onChangeZone(newTimeZone);
        // Let backend know time zone has changed, this will be used for the Next Availability filter
        postNewTimezone(newTimeZone.value);
      }}
      defaultValue={timeZone}
      inputId={inputId}
      style={{ width: 200 }}
      styles={{
        input: (provided) => ({ ...provided, '& input': { boxShadow: 'none !important' } }),
      }}
    />
  );
}

export default TimeZoneSelect;
