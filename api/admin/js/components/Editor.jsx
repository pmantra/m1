import React, { Component } from 'react';
import { UnControlled as CodeMirror } from 'react-codemirror2';

import 'codemirror/mode/javascript/javascript.js';
import 'codemirror/lib/codemirror.css';

const fromJson = (json) => JSON.parse(json);

const cmOptions = {
  theme: 'default',
  height: 'auto',
  viewportMargin: Infinity,
  mode: {
    name: 'javascript',
    json: true,
    statementIndent: 2,
  },
  lineNumbers: true,
  lineWrapping: false,
  indentWithTabs: false,
  tabSize: 2,
};

class Editor extends Component {
  constructor(props) {
    super(props);
    this.state = {
      valid: true,
      code: props.code,
    };
  }

  UNSAFE_componentWillReceiveProps() {}

  onCodeChange = (editor, metadata, previousCode) => {
    this.setState({ valid: true, code: previousCode });
    setImmediate(() => {
      try {
        const { onChange } = this.props;
        const { code } = this.state;
        onChange(fromJson(code));
      } catch (err) {
        this.setState({ valid: false, code: previousCode });
      }
    });
  };

  render() {
    const { title, code } = this.props;
    const { valid } = this.state;
    const icon = valid ? 'ok' : 'remove';
    const cls = valid ? 'valid' : 'invalid';
    return (
      <div className="panel panel-default">
        <div className="panel-heading">
          {`${title} : ${cls === 'invalid' ? cls.toUpperCase() : cls} `}
          <span className={`${cls} glyphicon glyphicon-${icon}`} />
        </div>
        <CodeMirror
          value={code}
          onChange={this.onCodeChange}
          autoCursor={false}
          options={{ ...cmOptions, ...'default' }}
        />
      </div>
    );
  }
}

export default Editor;
