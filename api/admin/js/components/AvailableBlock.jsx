import React from 'react';

function copyToClipboard(str) {
  const el = document.createElement('textarea');
  el.value = str;
  document.body.appendChild(el);
  el.select();
  document.execCommand('copy');
  document.body.removeChild(el);
}

export class AvailableBlock extends React.Component {
  constructor(props) {
    super(props);
    this.state = {
      copied: false,
      copiedDateTime: false
    };
  }

  copyTime = (startTime) => {
    const { productId } = this.props;
    copyToClipboard(`${startTime} (Product ID ${productId})`);

    this.setState({ copied: true }, () => {
      setTimeout(() => this.setState({ copied: false }), 1000);
    });
  };

  // Copy human readable date/time to clipbaord 
  copyDateTime = (startTime, endTime) => {
    copyToClipboard(`${startTime} - ${endTime}`);

    this.setState({ copiedDateTime: true }, () => {
      setTimeout(() => this.setState({ copiedDateTime: false }), 1000);
    });
  };

  render() {
    const { date, timeBlock, timeZone, formatDateTime } = this.props;
    const [startTime, endTime] = timeBlock;
    const { copied, copiedDateTime } = this.state;

    return (
      <tr key={timeBlock}>
        <td>{date}</td>
        <td>{formatDateTime(startTime, timeZone)}</td>
        <td>{formatDateTime(endTime, timeZone)}</td>
        <td>
          <span
            role="button"
            tabIndex={0}
            style={{ cursor: 'pointer', color: 'blue' }}
            onClick={() => this.copyTime(startTime)}
            onKeyDown={() => this.copyTime(startTime)}
          >
            {copied ? <span style={{ color: 'green' }}>Copied</span> : 'Copy'}
          </span>
        </td>
        <td>
          <i class="icon-calendar"
            role="button"
            tabIndex={0}
            style={{ cursor: 'pointer' }}
            onClick={() => this.copyDateTime(formatDateTime(startTime, timeZone, "ddd, MMMM Do h:mm A"), formatDateTime(endTime, timeZone, "h:mm A z"))}
            onKeyDown={() => this.copyDateTime(formatDateTime(startTime, timeZone, "ddd, MMMM Do h:mm A"), formatDateTime(endTime, timeZone, "h:mm A z"))}
            title="Copy Date"
          ></i>{copiedDateTime ? <span style={{ color: 'green' }}> Copied</span> : ''}
        </td>
      </tr>
    );
  }
}
