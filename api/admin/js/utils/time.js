import moment from 'moment-timezone';

export const formatDateTime = (dateTime, timeZone, format = 'LT') => {
  if (!dateTime) {
    return null;
  }
  return moment.utc(dateTime).tz(timeZone).format(format);
};

