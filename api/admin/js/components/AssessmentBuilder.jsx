import React, { Component } from 'react';
import Form from 'react-jsonschema-form';
import debounce from 'lodash/debounce';
import Editor from './Editor.jsx';

import { schemaConfig } from '../configs/schema.js';

import './AssessmentBuilder.scss';
import '../bootstrap/css/bootstrap.scss';
import '../bootstrap/css/bootstrap-theme.scss';

const generateQuizBodyWait = 500;
const toJson = (val) => JSON.stringify(val, null, 2);
const liveValidateSchema = { type: 'boolean', title: 'Live validation' };

const copyToTextArea = (formData) => {
  document.getElementById('quiz_body').value = formData;
};

class AssessmentBuilder extends Component {
  constructor(props) {
    super(props);
    const { schema, uiSchema, formData, validate } = schemaConfig;
    this.state = {
      form: false,
      schema,
      uiSchema,
      formData,
      validate,
      liveValidate: false,
    };
  }

  componentDidMount() {
    this.load(schemaConfig);
  }

  onFormDataEdited = (formData) => this.setState({ formData });

  onFormDataChange = debounce(({ formData }) => {
    this.setState({ formData });
  }, generateQuizBodyWait);

  setLiveValidate = ({ formData }) => this.setState({ liveValidate: formData });

  load = (data) => {
    // Reset the ArrayFieldTemplate whenever you load new data
    const { ArrayFieldTemplate, ObjectFieldTemplate } = data;

    let { formData } = this.state;
    const quizBodyValue = document.getElementById('quiz_body').value;
    if (quizBodyValue.length > 1) {
      formData = JSON.parse(quizBodyValue);
    }

    // force resetting form component instance
    this.setState({ form: false }, () =>
      this.setState({
        ...data,
        form: true,
        ArrayFieldTemplate,
        ObjectFieldTemplate,
        formData,
      }),
    );
  };

  render() {
    const {
      schema,
      uiSchema,
      formData,
      liveValidate,
      validate,
      ArrayFieldTemplate,
      ObjectFieldTemplate,
      transformErrors,
      form,
    } = this.state;

    return (
      <div className="container-fluid assessment-builder">
        <div className="page-header">
          <h1>Assessment Builder</h1>
          <div className="row">
            <div className="col-sm-2">
              <Form
                schema={liveValidateSchema}
                formData={liveValidate}
                onChange={this.setLiveValidate}
              />
            </div>
            <button
              type="button"
              onClick={() => copyToTextArea(toJson(formData))}
              className="btn-copy top"
            >
              Copy to Quiz Body
            </button>
          </div>
        </div>
        <div className="col-sm-6 fields">
          {form && (
            <React.Fragment>
              <Form
                ArrayFieldTemplate={ArrayFieldTemplate}
                ObjectFieldTemplate={ObjectFieldTemplate}
                liveValidate={liveValidate}
                schema={schema}
                uiSchema={uiSchema}
                formData={formData}
                onChange={this.onFormDataChange}
                validate={validate}
                transformErrors={transformErrors}
              />
              <button
                type="button"
                onClick={() => copyToTextArea(toJson(formData))}
                className="btn-copy bottom"
              >
                Copy to Quiz Body
              </button>
            </React.Fragment>
          )}
        </div>
        <div className="col-sm-6 editor">
          <Editor title="formData" code={toJson(formData)} onChange={this.onFormDataEdited} />
        </div>
      </div>
    );
  }
}

export default AssessmentBuilder;
