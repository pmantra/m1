import React, { useState, useEffect } from 'react';
import axios from 'axios';
import Select from 'react-select';


function formatProviders(providers = []) {
  return providers.map(({ name, id }) => ({
    label: `${name} (${id})`,
    value: id,
  }));
}

export default function ReplacePractitioner() {
  const [isLoading, setIsLoading] = useState(false);
  const [isLoadingProviders, setIsLoadingProviders] = useState(false);
  const [selectedProvider, setSelectedProvider] = useState(0);
  const [quizType, setType] = useState('');
  const [error, setError] = useState('');
  const [providers, setProviders] = useState([]);
  const [jobIds, setJobIds] = useState([]);
  const [success, setSuccess] = useState(false);
  const [replacedProvider, setReplacedProvider] = useState(0);

  const resetSelectors = () => {
    setSelectedProvider(null);
    setType(null);
  };

  useEffect(() => {
    async function fetchProviders() {
      try {
        setIsLoadingProviders(true);
        const { data } = await axios.get('/admin/actions/list_all_practitioners/');
        setProviders(formatProviders(data.practitioners));
      } catch (e) {
        const errorMsg = (e.response && e.response.data.error) || e.message;
        setError(errorMsg);
      } finally {
        setIsLoadingProviders(false);
      }
    }

    fetchProviders();
  }, []);

  const formatOptionLabel = ({label}) => (
  <div style={{ marginLeft: "10px" }}>
    <div>{label}</div>
  </div>
);

  const submitPractitionerReplacement = async () => {
    try {
      setIsLoading(true);
      const formData = new FormData()
      formData.append("remove_only_quiz_type", quizType.value)
      formData.append("practitioner_id", selectedProvider.value)
      const { data, status } = await axios.post('/admin/actions/replace_practitioner/', formData,{
          headers: {
            'Content-Type': 'multipart/form-data',
          },
      });

      if (status !== 200) {
        setError(status);
        return;
      }
      setJobIds(data.job_ids);
      setReplacedProvider(selectedProvider.value);

      // Display success message for 5 seconds, then clear.
      setSuccess(true);
      setTimeout(() => setSuccess(false), 5000);

      // Reset the selectors
      resetSelectors();

    } catch (e) {
      const errorMsg = (e.response && e.response.data.error) || e.message || e.error;
      setError(errorMsg);
    } finally {
      setIsLoading(false);
    }
  };

  function refreshPage() {
    window.location.reload(false);
  }


  return (
    <div>
      <h3>Replace Practitioner in Care Teams</h3>
      <b>Important note: </b>
      After submitting a replacement request, please do not submit another request for the same practitioner until you have received the email confirming that the first replacement job has finished.
      <p>
        Before using this tool, please ensure the provider has already been deleted from the <a href="/admin/practitionertrackvgc/">Update Care Teams</a> page.
      </p>
        {error && (
          <div className="alert alert-error">
            Error while replacing practitioner: {error}
          </div>
        )}
        {success && (
          <div className="alert alert-success">
            Request to remove Practitioner {replacedProvider} has been submitted.
            {jobIds.length} {jobIds.length > 1 ? ' jobs are ':' job is '}
            handling the request (email sent to you with details).
            You will be emailed when each job is completed.
          </div>
        )}
        <div style={{ width: 250 }}>
          <span htmlFor="providers-list">
            Practitioner: <span style={{ color: "red" }}>&#42;</span>
            <Select
              options={providers}
              value={selectedProvider}
              onChange={(provider) => {
                setError('');
                setSelectedProvider(provider);
              }}
              isClearable
              isSearchable
              inputId="providers-list"
              styles={{ input: (provided) => ({ ...provided, '& input': { boxShadow: 'none !important' } }) }}
              isLoading={isLoadingProviders}
              loadingMessage={() => 'Fetching providers'}
              formatOptionLabel={formatOptionLabel}
            />
          </span>
        </div>
        <hr />
        <div style={{ width: 250, marginBottom: 20 }}>
          <span htmlFor="quiz-type">
            Remove practitioner from care teams where they are present as type: <span style={{ color: "red" }}>&#42;</span>
            <Select
              options={[
                {label: 'QUIZ Type Only', value: 'True'},
                {label: 'All Types', value: 'False'}
              ]}
              value={quizType}
              onChange={(type) => setType(type)}
              inputId="quiz-type"
              styles={{ input: (provided) => ({ ...provided, '& input': { boxShadow: 'none !important' } }) }}
              formatOptionLabel={formatOptionLabel}
            />
          </span>
        </div>
        <button
          type="button"
          className="btn btn-primary"
          onClick={submitPractitionerReplacement}
          disabled={isLoading || !selectedProvider || !quizType}
        >
          Save
        </button>
        &emsp;
        <button
          type="button"
          className="btn btn-secondary"
          disabled={isLoading}
          onClick={refreshPage}
        >
          Cancel
        </button>
        {isLoading && <div>Loading...</div>}
    </div>
  );
}
