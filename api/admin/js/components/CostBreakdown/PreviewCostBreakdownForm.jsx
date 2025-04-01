import React, {useState, useEffect} from 'react';
import axios from "axios";
import './PreviewCostBreakdownForm.scss';
import Select from 'react-select';

export default function PreviewCostBreakdownForm({setCostBreakdown, setPending, setError}) {
    const [clinicLocationOptions, setClinicLocationOptions] = useState([]);
    const [procedureOptions, setProcedureOptions] = useState([]);
    const [formData, setFormData] = useState({
        userId: "",
        individualDeductible: "",
        individualOop: "",
        familyDeductible: "",
        familyOop: "",
        hraRemaining: "",
        individualOopLimit: "",
        familyOopLimit: "",
        procedures: [{
            id: 1,
            type: 'medical',
            procedure: {},
            clinic_location: {},
            cost: "",
            tier: "",
            start_date: ""
        }]
    });

    useEffect(() => {
            const fetchOptionsFromServer = async () => {
                const procedureResponse = await fetch('/admin/cost_breakdown_calculator/procedurelist');
                if (!procedureResponse.ok) {
                    setError('Error fetching global procedures options');
                    throw new Error('Failed to fetch procedure options');
                }
                const procedures = await procedureResponse.json();
                setProcedureOptions(procedures);

                const clinicLocationListResponse = await fetch('/admin/cost_breakdown_calculator/cliniclocationlist');
                if (!clinicLocationListResponse.ok) {
                    setError('Error fetching clinic location options');
                    throw new Error('Failed to fetch clinic location options');
                }
                const clinicLocations = await clinicLocationListResponse.json();
                setClinicLocationOptions(clinicLocations);
            };
            fetchOptionsFromServer();

        }, []
    );

    const scrollToButton = () => {
        window.scrollTo({
            top: document.body.scrollHeight,
            behavior: 'smooth'
        });
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        if (!formData.userId) {
            setError('Please fill in user id!');
            return;
        }

        const {procedures} = formData;
        if (procedures.length === 0) {
            setError('Please fill at least one procedure!');
            return;
        }
        for (let i = 0; i < procedures.length; i++) {
            if (procedures[i].type === "pharmacy") {
                if (!procedures[i].cost) {
                    setError(`Please fill in procedure ${i + 1} cost!`);
                    return;
                }
                if (Object.keys(procedures[i].procedure).length === 0) {
                    setError(`Please select procedure ${i + 1} procedure!`);
                    return;
                }
            } else if (procedures[i].type === "medical") {
                if (Object.keys(procedures[i].procedure).length === 0) {
                    setError(`Please select procedure ${i + 1} procedure!`);
                    return;
                }
                if (Object.keys(procedures[i].clinic_location).length === 0) {
                    setError(`Please select procedure ${i + 1} clinic location!`);
                    return;
                }
            }
        }
        scrollToButton();
        setCostBreakdown(null);
        setError(null);
        setPending(true);
        const {data} = await axios.post('/admin/cost_breakdown_calculator/multipleprocedures/submit', formData, {
            headers: {
                'Content-Type': 'application/json',
            },
        }).catch((error) => error.response);
        if (data) {
            if (data.error) {
                setPending(false);
                setError(data.error);
                return;
            }
            setCostBreakdown(data);
        }
        scrollToButton();
        setPending(false);
    }

    const addSubform = () => {
        const newId = formData.procedures.length + 1;
        setFormData({
            ...formData,
            procedures: [...formData.procedures, {
                id: newId,
                type: 'medical',
                procedure: {},
                clinic_location: {},
                tier: "",
                cost: "",
                start_date: ""
            }]
        });
        scrollToButton();
    };

    const removeSubform = (index) => {
        const newProcedures = formData.procedures.filter((_, idx) => idx !== index);
        setFormData({
            ...formData,
            procedures: newProcedures
        });
    };

    const handleMainFieldChange = (event) => {
        const {name, value} = event.target;
        setFormData({
            ...formData,
            [name]: value
        });
    };

    const handleSelectChange = (data, name, index) => {
        const newProcedure = [...formData.procedures];
        if (["procedure", "clinic_location"].includes(name)) {
            newProcedure[index][name] = {"id": data.value, "name": data.label};
        } else {
            newProcedure[index][name] = data.value;
        }
        setFormData({
            ...formData,
            procedures: newProcedure
        });
    };


    const handleSubformFieldChange = (event, index) => {
        const {name, value} = event.target;
        const newProcedure = [...formData.procedures];
        newProcedure[index][name] = value;
        setFormData({
            ...formData,
            procedures: newProcedure
        });
    };


    const renderSubformFields = (index) => {
        const {type, clinic_location, cost, tier } = formData.procedures[index];

        switch (type) {
            case 'medical':
                return (
                    <div>
                        <div className="form-group">
                            {/* eslint-disable-next-line jsx-a11y/label-has-associated-control */}
                            <label htmlFor={`clinic_location${index}`}>Select Clinic Location: <strong
                                style={{color: "red"}}>*</strong></label>
                            <Select
                                id={`clinic_location${index}`}
                                value={{value: clinic_location.id, label: clinic_location.name}}
                                name="clinic_location"
                                onChange={(e) => handleSelectChange(e, "clinic_location", index)}
                                isSearchable
                                className="select"
                                options={
                                    clinicLocationOptions.map(([id, name]) => (
                                        {value: id, label: name}
                                    ))
                                }
                            />
                        </div>
                        <div className="form-group">
                            {/* eslint-disable-next-line jsx-a11y/label-has-associated-control */}
                            <label htmlFor={`cost${index}`}>Cost (in dollar, optional) </label>
                            <input type="number" step="any" id={`cost${index}`} name="cost" value={cost}
                                   onChange={(e) => handleSubformFieldChange(e, index)}/>
                        </div>
                        <div className="form-group">
                            {/* eslint-disable-next-line jsx-a11y/label-has-associated-control */}
                            <label htmlFor={`tier${index}`}>Tier Override (optional) </label>
                            <input type="number" step="any" id={`tier${index}`} name="tier" value={tier}
                                   onChange={(e) => handleSubformFieldChange(e, index)}/>
                        </div>
                    </div>
                )
                    ;
            case 'pharmacy':
                return (
                    <div>
                        <div className="form-group">
                            {/* eslint-disable-next-line jsx-a11y/label-has-associated-control */}
                            <label htmlFor={`cost${index}`}>Cost (in dollar) <strong
                                style={{color: "red"}}>*</strong></label>
                            <input type="number" step="any" id={`cost${index}`} name="cost" value={cost}
                                   onChange={(e) => handleSubformFieldChange(e, index)}/>
                        </div>
                         <div className="form-group">
                            {/* eslint-disable-next-line jsx-a11y/label-has-associated-control */}
                            <label htmlFor={`tier${index}`}>Tier Override (optional) </label>
                            <input type="number" step="any" id={`tier${index}`} name="tier" value={tier}
                                   onChange={(e) => handleSubformFieldChange(e, index)}/>
                        </div>
                    </div>
                );
            default:
                return null;
        }
    };

    return (
        <form className="preview-cost-breakdown-form">
            <div className="main-form">
                <div className="form-group">
                    {/* eslint-disable-next-line jsx-a11y/label-has-associated-control */}
                    <label htmlFor="userId">Member ID: <strong style={{color: "red"}}>*</strong></label>
                    <input type="text" id="userId" name="userId"
                           onChange={handleMainFieldChange}/>
                </div>

                <div className="form-group">
                    {/* eslint-disable-next-line jsx-a11y/label-has-associated-control */}
                    <label htmlFor="individualDeductible">YTD Individual Deductible amount (in dollar): </label>
                    <input type="text" id="individualDeductible" name="individualDeductible"
                           onChange={handleMainFieldChange}/>
                </div>

                <div className="form-group">
                    {/* eslint-disable-next-line jsx-a11y/label-has-associated-control */}
                    <label htmlFor="individualOop">YTD Individual OOP amount (in dollar): </label>
                    <input type="text" id="individualOop" name="individualOop"
                           onChange={handleMainFieldChange}/>
                </div>

                <div className="form-group">
                    {/* eslint-disable-next-line jsx-a11y/label-has-associated-control */}
                    <label htmlFor="familyDeductible">YTD Family Deductible amount (in dollar): </label>
                    <input type="text" id="familyDeductible" name="familyDeductible"
                           onChange={handleMainFieldChange}/>
                </div>

                <div className="form-group">
                    {/* eslint-disable-next-line jsx-a11y/label-has-associated-control */}
                    <label htmlFor="familyOop">YTD Family OOP amount (in dollar): </label>
                    <input type="text" id="familyOop" name="familyOop"
                           onChange={handleMainFieldChange}/>
                </div>

                <div className="form-group">
                    {/* eslint-disable-next-line jsx-a11y/label-has-associated-control */}
                    <label htmlFor="hraRemaining">HRA Remaining amount (in dollar): </label>
                    <input type="text" id="hraRemaining" name="hraRemaining"
                           onChange={handleMainFieldChange}/>
                </div>

                <div className="form-group">
                    {/* eslint-disable-next-line jsx-a11y/label-has-associated-control */}
                    <label htmlFor="individualOopLimit">Individual OOP Limit amount (in dollar, relevant for HDHP plans): </label>
                    <input type="text" id="individualOopLimit" name="individualOopLimit"
                           onChange={handleMainFieldChange}/>
                </div>

                <div className="form-group">
                    {/* eslint-disable-next-line jsx-a11y/label-has-associated-control */}
                    <label htmlFor="familyOopLimit">Family OOP Limit amount (in dollar, relevant for HDHP plans): </label>
                    <input type="text" id="familyOopLimit" name="familyOopLimit"
                           onChange={handleMainFieldChange}/>
                </div>
            </div>
            {formData.procedures.map((procedure, index) => (
                // eslint-disable-next-line react/no-array-index-key
                <div key={index} className="subform">
                    <h3 className="subform-header">Procedure {index + 1}</h3>
                    <div className="form-group">
                        {/* eslint-disable-next-line jsx-a11y/label-has-associated-control */}
                        <label htmlFor={`type${index}`}>Type: <strong style={{color: "red"}}>*</strong></label>
                        <Select
                            id={`type${index}`}
                            value={{value: procedure.type, label: procedure.type}}
                            name="type"
                            onChange={(e) => handleSelectChange(e, "type", index)}
                            isSearchable
                            className="select"
                            options={[
                                {value: "medical", label: "medical"},
                                {value: "pharmacy", label: "pharmacy"}
                            ]}
                        />
                    </div>

                    <div className="form-group">
                        {/* eslint-disable-next-line jsx-a11y/label-has-associated-control */}
                        <label htmlFor={`procedure${index}`}>Select Procedure: <strong style={{color: "red"}}>*</strong></label>
                        <Select
                            id={`procedure${index}`}
                            value={{value: procedure.procedure.id, label: procedure.procedure.name}}
                            name="procedure"
                            onChange={(e) => handleSelectChange(e, "procedure", index)}
                            isSearchable
                            className="select"
                            options={
                                procedureOptions.map(([id, name]) => (
                                    {value: id, label: name}
                                ))
                            }
                        />
                    </div>

                    <div className="form-group">
                        {/* eslint-disable-next-line jsx-a11y/label-has-associated-control */}
                        <label htmlFor={`start_date${index}`}>Procedure Start Date: <strong style={{color: "red"}}>*</strong></label>
                        <input
                            id={`start_date${index}`}
                            name="start_date"
                            onChange={(e) => handleSubformFieldChange(e, index)}
                            required
                            type="date"
                        />
                    </div>

                    {renderSubformFields(index)}
                    <button className="delete-button" type="button"
                            onClick={() => removeSubform(index)}>&#10006;{/* Unicode for 'X' character */}
                    </button>
                </div>
            ))}
            <div className="button-group">
                <button className="button" type="button" onClick={addSubform}>Add Procedure</button>
                <button className="button" type="submit" onClick={handleSubmit}>Submit</button>
            </div>
        </form>
    )
}