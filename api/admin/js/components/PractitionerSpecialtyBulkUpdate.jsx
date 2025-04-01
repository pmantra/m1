import React, { useState } from 'react';
import axios from 'axios';


export default function PractitionerSpecialtyBulkUpdate() {
  const [error, setError] = useState('');
  const [info, setInfo] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  async function handleBulkUpdate(formEvent) {
    formEvent.preventDefault();
    const formData = new FormData();
    const csv = formEvent.target["specialty_csv"];

    formData.append('specialty_csv', csv.files[0]);

    try {
      setIsLoading(true);

      const { data, status, statusText } = await axios.post('/admin/practitioner_specialty_bulk_update/upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });

      if (status === 200) {
        setInfo(JSON.stringify(data, null, '\r\n'));
        return;
      }

    } catch (e) {
      const errorMsg = (e.response && e.response.data.error) || e.message;
      setError(errorMsg);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <form className="container" onSubmit={handleBulkUpdate}>
      <h2>Practitioner/Specialty Bulk Update</h2>
      <p>
        Bulk replacement of practitioners' specialties using a csv with headers: 
        "Provider ID" and "Specialties". The specialties column should be a comma
        seperated list of specialty names.
      </p>
      <br />
      <div>
         <input
           id="specialty_csv"
           onChange={() => setError("")}
           type="file"
           accept=".csv"
           className="form-control"
           style={{ marginBottom: 15 }}
           required
         />
      </div>
      {info && <div className="alert alert-info">{info}</div>}
      {error && <div className="alert alert-error">{error}</div>}
      <button type="submit" className="btn btn-primary" disabled={isLoading}>
        Upload
      </button>
    </form>
  );
}
