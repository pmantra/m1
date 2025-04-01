import React, { useState } from 'react';

export default function ({ children }) {
  // Set tab if passed with ?tab={identified}, otherwise the first
  const urlParams = new URLSearchParams(window.location.search);
  const initialTab = (urlParams && urlParams.get("tab")) ? urlParams.get("tab") : children[0].props.identifier;
  const [activeTabIdentifier, setActiveTabIdentifier] = useState(initialTab);
  return (
    <div>
      <ol style={{ margin: 0, borderBottom: '1px solid lightgrey' }}>
        {children.map(({ props: { identifier, label } }) => (
          <Tab
            activeTabIdentifier={activeTabIdentifier}
            identifier={identifier}
            label={label}
            onClick={setActiveTabIdentifier}
            key={identifier}
          />
        ))}
      </ol>
      <div>
        {children.map(({ props: { children: innerChildren, identifier } }) =>
          activeTabIdentifier === identifier ? innerChildren : null,
        )}
      </div>
    </div>
  );
}

const activeTabStyle = {
  backgroundColor: 'white',
  border: 'solid lightgrey',
  borderTopLeftRadius: '10px',
  borderTopRightRadius: '10px',
  borderWidth: '1px 1px 0 1px',
};

function Tab({ onClick, label = '', identifier = '', activeTabIdentifier = '' }) {
  let style = {
    cursor: 'pointer',
    display: 'inline-block',
    marginBottom: '-1px',
    padding: '10px 20px',
    listStyle: 'none',
  };

  if (identifier === activeTabIdentifier) {
    style = {
      ...style,
      ...activeTabStyle,
    };
  }

  return (
    <li style={style} onClick={() => onClick(identifier)} onKeyDown={() => onClick(identifier)}>
      {label}
    </li>
  );
}
