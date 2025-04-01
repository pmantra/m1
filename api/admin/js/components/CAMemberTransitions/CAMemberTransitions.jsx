import React from 'react';

import Tabs from '../Tabs.jsx';
import TransitionLogs from './TransitionLogs.jsx';
import EditMessages from './EditMessages.jsx';
import TransitionCAs from './TransitionCAs.jsx';


import '../../bootstrap/css/bootstrap.scss';
import '../../bootstrap/css/bootstrap-theme.scss';

export default function CAMemberTransitions({ args }) {
  return (
    <div className="container">
      <h2>CA-Member Transitions</h2>
      <Tabs>
        <div label="Transition Logs" identifier="transition-logs">
          <TransitionLogs args={ {...args,
            "dataUrl":args.transitionLogDataUrl,
            "columnsConf":args.transitionLogsColumnsConf,
            "canDelete":args.transitionLogsCanDelete,
            "canEdit":args.transitionLogsCanEdit,
          } }/>
        </div>
        <div label="Edit Messages" identifier="edit-messages">
          <EditMessages args={ {...args,
            "dataUrl":args.transitionTemplateDataUrl,
            "columnsConf":args.transitionTemplatesColumnsConf,
            "canDelete":args.transitionTemplatesCanDelete,
            "canEdit":args.transitionTemplatesCanEdit,
          } }/>
        </div>
        <div label="Transition CAs" identifier="transition-CAs">
          <TransitionCAs />
        </div>
      </Tabs>
    </div>
  );
}
