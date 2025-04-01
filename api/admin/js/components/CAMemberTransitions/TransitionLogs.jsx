import React from 'react';

import List from '../List/List.jsx';


export default function TransitionLogs({ args }) {

  return (
    <div>
      <List args={ {...args, "sort":args.transitionsLogSortColumn} } />
    </div>
  );
}
