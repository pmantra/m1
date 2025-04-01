import React from 'react';
import { Button, Collapse } from 'react-bootstrap';

class ObjectFieldTemplate extends React.Component {
  constructor(props) {
    super(props);
    this.state = {
      open: true,
    };
  }

  render() {
    const { open } = this.state;
    const { title, description, properties } = this.props;
    return (
      <React.Fragment>
        {title && (
          <Button
            className="collapse-btn btn-primary "
            onClick={() => this.setState({ open: !open })}
            aria-controls="example-collapse-text"
            aria-expanded={open}
          >
            <i className="glyphicon glyphicon-chevron-down" />
          </Button>
        )}
        <h2 className="question">{title}</h2>
        <span>{description}</span>
        <Collapse in={open}>
          <div className="rowz" id="example-collapse-text">
            {properties.map((prop) => (
              <div key={prop.content.key}>{prop.content}</div>
            ))}
          </div>
        </Collapse>
        {title && (
          <Button
            className={`collapse-btn-bottom btn-primary open-${open}`}
            onClick={() => this.setState({ open: !open })}
            aria-controls="example-collapse-text"
            aria-expanded={open}
          >
            <i className="glyphicon glyphicon-chevron-up" />
          </Button>
        )}
      </React.Fragment>
    );
  }
}

export default ObjectFieldTemplate;
