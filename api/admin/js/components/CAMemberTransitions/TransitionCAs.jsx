import React, { useState } from 'react';
import moment from 'moment';
import axios from 'axios';

// T = literal "T" datetime-local input requires to seperate date and time
const DATETIME_FORMAT_INPUT = 'YYYY-MM-DDTHH:mm';
// A = AM/PM
const DATETIME_FORMAT_OUTPUT = 'MM/DD/YYYY hh:mm A';

export default function TransitionCAs() {
  const [allowToTransition, setAllowToTransition] = useState(false);
  const [date, setDate] = useState(moment().utc().tz("America/New_York").format(DATETIME_FORMAT_INPUT))
  const [error, setError] = useState(false)
  const [success, setSuccess] = useState(false)
  

  const handleValidateTransitions = async () => {
    const formData = new FormData();
    const csv = document.querySelector('#validate-transition-file');
    if (!csv.files.length) {
      setError('Please upload a file with your desired transitions.');
      return;
    }
    formData.append('transitions_csv', csv.files[0]);   

    if(!document.querySelector('input[name="sendOption"]:checked')) {
      setError('Please select an option under ‘Submit Transition.’');
      return;
    }
    const sendOption = document.querySelector('input[name="sendOption"]:checked').value;
    if (sendOption === "now")
      formData.append('transition_date', moment().utc().format(DATETIME_FORMAT_OUTPUT));
    else
      formData.append('transition_date', moment(date, DATETIME_FORMAT_INPUT).utc().format(DATETIME_FORMAT_OUTPUT));

    // Clear the csv file input
    csv.value = null;
    setError(null)
    setSuccess(null)

    try {
      const { data, status, statusText } = await axios.post('/admin/ca_member_transitions/submit', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });

      if (status !== 200) {
          setError(statusText);
        return;
      }

      if (data) {
        // check if transition date was scheduled for now or in the future
        if (sendOption === "now") {
          setSuccess('Transition processing. You\'ll receive an email when complete. This may take up to 30 minutes.')
        } else {
          setSuccess('Transition scheduled. You\'ll receive an email when complete')
        }

        return;
      }
    } catch (e) {
      if (e.response && e.response.data.error) {
        const errors = e.response.data.error.map(x => <div>{x}</div>)
        setError(errors)
      } else {
        setError(e.message);
      }
    } 
  };

  const handleCancelTransitions = () => {
    // Redirect to ca_member_transitions
    window.location = "/admin/ca_member_transitions";
  }

  return (
    <div>      
      <form className="form-group" style={{marginTop: "25px"}}>
        <label htmlFor="validate-transition-file">
            <h4 style={{fontWeight:"initial"}}>Upload CSV <strong style={{color: "red"}}>*</strong></h4>
            <div>(CSV format: member_id, old_cx_id, new_cx_id, messaging)</div>
          <input
            id="validate-transition-file"
            onChange={() => setError('')}
            type="file"
            accept=".csv,"
            className="form-control"
            style={{ marginBottom: 15 }}
          />
        </label>
        {error && <div className="alert alert-error">{error}</div>}

        <div>
          <h4 style={{fontWeight:"initial"}}>Finalize Transition</h4>
          <p>I confirm I have uploaded the correct CSV and made any required edits to messages.<br />
          I acknowledge that changes cannot be made after completing the Transition.</p>
          <div>
            <label htmlFor="allow-transition" style={{ marginBottom: '15px' }}>
              Check box to confirm <strong style={{color: "red"}}>*</strong>
              <input
                onChange={() => setAllowToTransition(!allowToTransition)}
                style={{ marginLeft: '10px', marginTop: '0px' }}
                id="allow-transition"
                type="checkbox"
                checked={allowToTransition}
              />
            </label>
          </div>
        </div>
        <div style={{marginTop: "10px"}}>
          <h4 style={{fontWeight:"initial"}}>Submit Transition</h4>
          <div>Select One <strong style={{color: "red"}}>*</strong></div>
          <p style={{marginTop:"8px"}}>
            <label htmlFor="now">
              <input type="radio" id="now" name="sendOption" value="now" style={{marginRight: '15px', marginBottom: '7px'}} />
            Transition Now</label>
            <label htmlFor="scheduled">
              <input type="radio" id="scheduled" name="sendOption" value="scheduled" style={{marginRight: '15px', marginBottom: '7px'}} />
              Schedule Transition (EST):
              <input
                className="form-control"
                id="schedule_datetime"
                onChange={(e) => setDate(e.target.value)}
                value={date}
                type="datetime-local"
                style={{ height: "28px", position: "relative", left: "10px", top: "4px" }}
              />
            </label>
          </p>
        </div>

        <div>
          {success && <div className="alert alert-success">{success}</div>}
          <button type="button" id="submitTransition" className="btn btn-primary" onClick={handleValidateTransitions} disabled={!allowToTransition}>
            Submit
          </button>
            &emsp;
          <button type="button" id="cancelTransition" className="btn btn-danger" onClick={handleCancelTransitions}>
            Cancel
          </button>
        </div>
      </form>
    </div>

  );
}
