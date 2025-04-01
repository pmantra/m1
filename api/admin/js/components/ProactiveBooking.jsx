import React, { Component } from 'react';
import * as moment from 'moment-timezone';
import axios from 'axios';
import Select from 'react-select';
import defaultTimezones from './timezones.json';
import mostCommonTimezones from './most-common-timezones.json';


import '../bootstrap/css/bootstrap.scss';
import '../bootstrap/css/bootstrap-theme.scss';

class ProactiveBooking extends Component {
  constructor(props) {
    super(props);

    const instateMatchingGuardrailsFeatureFlag = true;

    this.state = {
      pastedAvailableTime: '',
      date: '',
      timezone: 'America/New_York',
      time: '',
      productId: '',
      loadingProductInfo: false,
      loadingStateMatchNotPermissible: false,
      productInfo: null,
      appointmentType: {label: 'None', value: ''},
      inState: false, // are the member and practitioner in the same state?
      filterByState: false,
      inInStateMatchStates: false, // is the member in one of the states that requires the practitioner to be in-state matched?
      nonPermissibleOutOfStateMatchFound: false,
      isOvernight: false,
      instateMatchingGuardrailsFeatureFlag,
      practitionerAllowsAnon: true,
      stateMatchNotPermissibleError: ''
    };
  }

  getIsOvernight(time, date, timezone) {
    if (date && time && timezone) {
      const estTime = moment.tz(date + 'T' + time, timezone).tz("America/New_York");
      const estTimeStr = estTime.format("HH:mm:ss");
      //  between the hours of 11:00 PM and 7:00 AM Eastern Time
      if(estTimeStr < "07:00:00" || estTimeStr >= "23:00:00") {
        return true;
      }
    }

    return false;
  }

  setDate(date) {
    this.setState({ date }, this.applyToForm);

    const { time, timezone } = this.state;
    this.setState({isOvernight: this.getIsOvernight(time, date, timezone)});
  }

  setTime(time) {
    this.setState({ time }, this.applyToForm);

    const { date, timezone } = this.state;
    this.setState({isOvernight: this.getIsOvernight(time, date, timezone)});

    const {productId} = this.state;
    this.loadProductInfo(productId);
  }

  setTimezone(timezone) {
    this.setState({ timezone }, this.applyToForm);

    const { date, time } = this.state;
    this.setState({isOvernight: this.getIsOvernight(time, date, timezone)});
  }

  setAppointmentType(appointmentType) {
    this.setState({ appointmentType }, this.applyToForm);

    const {productId} = this.state;
    this.loadProductInfo(productId);
  }

  setFilterByState(filterByState) {
    this.setState({ filterByState }, this.applyToForm);
  }

  setInInStateMatchStates(inInStateMatchStates) {
    this.setState({ inInStateMatchStates }, this.applyToForm);
  }

  setProductId(productId) {
    this.setState({ productId }, () => {
      this.loadProductInfo(productId);
      // // Reset practitioner related variables if no product id is given
      if(productId===''){
        this.setState({apptCanBeAnonymous: false})
      }
    });
  }

  applyToForm = () => {
    const {
      date,
      time,
      timezone,
      productId,
      inState,
      appointmentType,
      filterByState,
      inInStateMatchStates,
      instateMatchingGuardrailsFeatureFlag,
      practitionerAllowsAnon,
      nonPermissibleOutOfStateMatchFound
    } = this.state;

    const timeInput = document.getElementById('scheduled_start');
    const productInput = document.getElementById('product_id');
    productInput.value = productId;

    const typeInput = document.getElementById('purpose');
    typeInput.value = appointmentType.value;


    if (date && time) {
      const dateTime = moment.tz(`${date} ${time}`, timezone);
      timeInput.value = dateTime.utc().format('HH:mm:ssTMM-DD-YYYY');
    }

    this.setState({matchConflict: false})

    if ( instateMatchingGuardrailsFeatureFlag ) {

      let apptCanBeAnonymous = false;
      this.setState({apptCanBeAnonymous})

      if ((apptCanBeAnonymous && !practitionerAllowsAnon) || nonPermissibleOutOfStateMatchFound) {
          this.setState({matchConflict: true})
      }
    }
  };


  onPasteAvailableTime = (text) => {
    this.setState({ pastedAvailableTime: text });

    const { timezone } = this.state;
    const matches = text.match(/(.+) \(Product ID ([0-9]+)\)/);

    if (matches && matches.length === 3) {
      const time = matches[1];
      const localTime = moment.utc(time).tz(timezone);
      const dateStr = localTime.format('YYYY-MM-DD');
      const timeStr = localTime.toString().split(" ")[4];
      const productId = matches[2];

      this.setDate(dateStr);
      this.setTime(timeStr);
      this.setState({isOvernight: this.getIsOvernight(timeStr, dateStr, timezone)});
      // format() does not handle midnight correctly
      // localTime.toString() will look like: Thu Dec 15 2022 00:00:00 GMT-0500

      this.setProductId(productId);
    }
  };

  loadProductInfo = (productId) => {

    this.setState({stateMatchNotPermissibleError: ''});

    if (productId === '') {
      this.setState({ productInfo: null });
    } else {

      this.setState({ loadingProductInfo: true });
      axios.get(`/admin/practitionerprofile/products/?product_id=${productId}`).then((response) => {

        if (response.data === false) {
          this.setState({productInfo: null});
        }
        else {
          const productInfo = response.data;

          this.setState({productInfo});

          let {args: {memberState}} = this.props;
          if (memberState === '' && document.getElementById('member_state')) {
            memberState = document.getElementById('member_state').innerText;
          }

          const {isOvernight} = this.state;

          let nonPermissibleOutOfStateMatchFound = false;
          this.setState({nonPermissibleOutOfStateMatchFound});

          const {instateMatchingGuardrailsFeatureFlag} = this.state;

          this.setState({instateMatchingGuardrailsFeatureFlag})
          const userId = document.getElementById('user_id').value;

          if (instateMatchingGuardrailsFeatureFlag) {
            this.setState({inState: productInfo.certified_states.includes(memberState)})
            this.setFilterByState(productInfo.vertical.filter_by_state)
            this.setInInStateMatchStates(productInfo.vertical.in_state_matching_states.includes(memberState))

            if (isOvernight === false) {
              this.setState({ loadingStateMatchNotPermissible: true });
              axios
                .get(`/admin/practitionerprofile/state-match-not-permissible/?product_id=${productId}&user_id=${userId}`)
                .then((oosResponse) => {
                  this.setState({stateMatchNotPermissibleError: ''});
                  const stateMatchInfo = oosResponse.data;
                  if (stateMatchInfo.state_match_not_permissible === true) {
                    nonPermissibleOutOfStateMatchFound = true;
                    this.setState({nonPermissibleOutOfStateMatchFound});
                  }
                   // these must be set within the then() statement to guarantee states are set in the right order
                  this.setState({
                    productInfo,
                    memberState,
                    filterByState: productInfo.vertical.filter_by_state,
                    inInStateMatchStates: productInfo.vertical.in_state_matching_states.includes(memberState),
                    practitionerAllowsAnon: productInfo.anonymous_allowed
                  })
              this.applyToForm();
                })
              .catch((err) => {
                this.setState({stateMatchNotPermissibleError: `Error: ${err.response.data.error}`});
              })
              .finally(() => {
                this.setState({loadingStateMatchNotPermissible: false });
              });
            }
          }
          if ((instateMatchingGuardrailsFeatureFlag && isOvernight) || !instateMatchingGuardrailsFeatureFlag){
            // we already set this if isOvernight is false and feature flag is on
            // must be outside if/else statement to handle the feature flag
            this.setState({
              productInfo,
              memberState,
              filterByState: productInfo.vertical.filter_by_state,
              inInStateMatchStates: productInfo.vertical.in_state_matching_states.includes(memberState),
              practitionerAllowsAnon: productInfo.anonymous_allowed
            })
            this.applyToForm();
          }
        }
        this.setState({loadingProductInfo: false});
      });
    }
  };

  render() {
    const timezones = { ...mostCommonTimezones, ...defaultTimezones };

    const {
        loadingProductInfo,
        loadingStateMatchNotPermissible,
        productInfo,
        pastedAvailableTime,
        productId,
        date,
        timezone,
        time,
        inState,
        appointmentType,
        nonPermissibleOutOfStateMatchFound,
        memberState,
        filterByState,
        instateMatchingGuardrailsFeatureFlag,
        apptCanBeAnonymous,
        practitionerAllowsAnon,
        matchConflict,
        stateMatchNotPermissibleError
    } = this.state;

    return (
      <div>
        <ul>
          <li>This will let you book with any practitioner as long as they are available.</li>
          <li>
            Notifications will be sent to the member/practitioner as if they had just booked the
            appointment.
          </li>
          <li>
            This will fail if the user does not have enough enterprise credit available for the
            appointment.
          </li>
        </ul>
        <div style={{ marginBottom: 20 }}>
          <b style={{ display: 'block' }}>
            Did you copy available time from a practitioner&apos;s profile?
          </b>
          <input
            placeholder="Paste here if you did"
            style={{
              padding: 4,
              marginTop: 3,
              border: '1px solid #ccc',
              width: 250,
            }}
            value={pastedAvailableTime}
            onChange={(e) => this.onPasteAvailableTime(e.target.value)}
          />
        </div>

        <b>Scheduled Start</b> <strong style={{ color: 'red' }}>*</strong>

        <div style={{ clear: 'both', overflow: 'hidden' }}>
          <div style={{ float: 'left', marginRight: 15 }}>
            <div style={{ marginBottom: 2 }}>Date</div>
            <p>
              <input
                type="date"
                style={{ height: 30 }}
                value={date}
                onChange={(event) => this.setDate(event.target.value)}
              />
            </p>
          </div>

          <div style={{ float: 'left', marginRight: 15 }}>
            <div style={{ marginBottom: 2 }}>Time Zone</div>
            <select
              style={{ height: 30 }}
              value={timezone}
              onChange={(event) => this.setTimezone(event.target.value)}
            >
              {Object.keys(timezones).map((tz) => (
                <option value={timezones[tz]} key={timezones[tz]}>
                  {tz}
                </option>
              ))}
            </select>
          </div>

          <div style={{ float: 'left' }}>
            <div style={{ marginBottom: 2 }}>Start Time</div>
            <input
              type="time"
              required
              className="form-control"
              style={{ height: 30 }}
              value={time}
              step="1"
              onChange={(event) => this.setTime(event.target.value)}
            />
          </div>
        </div>

        <p>
          <b>Product ID</b>
          : <strong style={{color: 'red'}}>*</strong>
          <br />
          <input
            className="input"
            type="text"
            value={productId}
            onChange={(event) => this.setProductId(event.target.value)}
            placeholder="product_id"
            required
            style={{
              padding: 4,
              marginTop: 3,
              borderColor: matchConflict ? '#f00' : '#ccc',
              width: 100,
            }}
          />
        </p>

        { stateMatchNotPermissibleError && (
        <div style={{ clear: 'both', overflow: 'hidden', color: 'red' }}>
          {stateMatchNotPermissibleError}
        </div>
        )}

        {productInfo && (!stateMatchNotPermissibleError && !loadingProductInfo && !loadingStateMatchNotPermissible && instateMatchingGuardrailsFeatureFlag && nonPermissibleOutOfStateMatchFound) && (
        <div style={{ clear: 'both', overflow: 'hidden', color: 'red' }}>
          This provider is not licensed in the member&apos;s state. Please find a provider that is licensed in {memberState}
        </div>
        )}

        {productInfo &&(!stateMatchNotPermissibleError && !loadingProductInfo && !loadingStateMatchNotPermissible && apptCanBeAnonymous && !practitionerAllowsAnon ) && (
        <div style={{ clear: 'both', overflow: 'hidden', color: 'red' }}>
            This provider does not allow anonymous appointments. Please book with a different provider.
        </div>
        )}
        {productId && (
          <div
            style={{
              marginTop: 10,
              marginBottom: 20,
              background: '#d9edf7',
              padding: 10,
            }}
          >
            {(loadingProductInfo || loadingStateMatchNotPermissible) && 'Loading product..'}
            {(!productInfo && !loadingProductInfo && !loadingStateMatchNotPermissible) && 'Product not found.'}
            {(productInfo && !loadingProductInfo && !loadingStateMatchNotPermissible) && (
              <div>
                Practitioner: <b>{productInfo.practitioner_name}</b> <br />
                Practitioner Allows Anonymous Appointments: <b>{ productInfo.anonymous_allowed?"Yes":"No" }</b> <br />
                Vertical: <b>{productInfo.vertical.name}</b> <br />
                Certified States: <b>{productInfo.certified_states.join(', ')}</b> <br />
                Product ID: <b>{productInfo.product_id}</b> <br />
                Minutes: <b>{productInfo.minutes}</b> <br />

                {/* nonPermissibleOutOfStateMatchFound will show an error above; don't show another one */}
                {instateMatchingGuardrailsFeatureFlag && !inState && filterByState && !nonPermissibleOutOfStateMatchFound && practitionerAllowsAnon && (

                  <div>
                    <br />
                    <b>
                      This provider is not certified in the member’s state. Please note this will be
                      a coaching & education only appointment. Please book with a provider licensed in
                      the member's state if available.
                    </b>
                  </div>
                )}
              </div>
              )}
          </div>
        )}


        <div style={{ display: 'inline-block', marginRight: 15, clear: 'both' }}>
          <span htmlFor="purpose">
            <b>Appointment type:</b> <br />
            <Select
              options={[
                {label: 'None', value: ''},
                {label: 'Birth Planning', value: 'birth_planning'},
                {label: "Childbirth Education", value: "childbirth_ed"},
                {label: "Pediatric Prenatal Consult", value: "pediatric_prenatal_consult"},
                {label: "Postpartum Planning", value: "postpartum_planning"},
                {label: 'Introduction', value: 'introduction'},
                {label: 'Pregnancy Needs Assessment', value: 'birth_needs_assessment'},
                {label: 'Postpartum Needs Assessment', value: 'postpartum_needs_assessment'},
                {label: 'Introduction (Egg Freezing)', value: 'introduction_egg_freezing'},
                {label: 'Introduction (Fertility)', value: 'introduction_fertility'},
                {label: 'Introduction (Menopause)', value: 'introduction_menopause'},
              ]}
              defaultValue=''
              style={{ width: 250 }}
              styles={{
                input: (provided) => ({ ...provided, '& input': { boxShadow: 'none !important' } }),
              }}
              value={appointmentType}
              onChange={(purpose) => this.setAppointmentType(purpose)}
              id="purpose"
            />
          </span>

          <p style={{ marginTop: 20 }}>
            <input
              type="submit"
              className="btn btn-primary btn-large"
              value="Book!"
              style={{ backgroundImage: 'linear-gradient(to bottom,#6cceaa,#00856f)' }}
              disabled={matchConflict}
            />
          </p>
        </div>
      </div>
    );
  }
}

export default ProactiveBooking;
