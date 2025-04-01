import ReactDOM from 'react-dom';
import React from 'react';
import AssessmentBuilder from './components/AssessmentBuilder.jsx';
import ProactiveBooking from './components/ProactiveBooking.jsx';
import PractitionerProfile from './components/PractitionerProfile.jsx';
import MemberProfile from './components/MemberProfile.jsx';
import CareTeamControlCenter from './components/CareTeamControlCenter.jsx';
import VerticalProductEditor from './components/VerticalProductEditor.jsx';
import MatchingRules from './components/MatchingRules/MatchingRules.jsx';
import MonthlyPayments from './components/MonthlyPayments/MonthlyPayments.jsx';
import ServiceMetrics from './components/ServiceMetrics.jsx';
import QualifiedLifeEvent from './components/QualifiedLifeEvent.jsx';
import PayInvoice from './components/PayInvoice.jsx';
import CloseInvoice from './components/CloseInvoice.jsx';
import List from './components/List/List.jsx';
import PractitionerReplacement from './components/PractitionerReplacement.jsx';
import CAMemberTransitions from './components/CAMemberTransitions/CAMemberTransitions.jsx';
import RecalculateCostBreakdown from './components/CostBreakdown/RecalculateCostBreakdown.jsx';
import InlineReimbursementCostBreakdownCalculator from './components/CostBreakdown/InlineReimbursementCostBreakdownCalculator.jsx';
import PractitionerSpecialtyBulkUpdate from './components/PractitionerSpecialtyBulkUpdate.jsx';

import attachFastFind from './utils/fastfind';
import PreviewCostBreakdown from "./components/CostBreakdown/PreviewCostBreakdown";
import CostBreakdownCalculator from "./components/CostBreakdown/CostBreakdownCalculator";

class AdminTool extends React.Component {
  render() {
    const { tool, args } = this.props;

    switch (tool) {
      case 'AssessmentBuilder':
        return <AssessmentBuilder />;
      case 'CareTeamControlCenter':
        return <CareTeamControlCenter args={args} />;
      case 'MatchingRules':
        return (
          <MatchingRules
            countries={args.countries || []}
            organizations={args.organizations || []}
            tracks={args.tracks || []}
            riskFactors={args.riskFactors || []}
            matchingRuleSets={args.matchingRuleSets || []}
            assignableAdvocateId={args.assignableAdvocateId}
          />
        );
      case 'PractitionerProfile':
        return <PractitionerProfile args={args} />;
      case 'MemberProfile':
        return <MemberProfile args={args} />;
      case 'ProactiveBooking':
        return <ProactiveBooking args={args || {}} />;
      case 'ServiceMetrics':
        return <ServiceMetrics args={args} />;
      case 'VerticalProductEditor':
        return <VerticalProductEditor args={args} />;
      case 'MonthlyPayments':
        return <MonthlyPayments args={args} />;
      case 'QualifiedLifeEvent':
        return <QualifiedLifeEvent />;
      case 'PayInvoice':
        return <PayInvoice args={args} />;
      case 'CloseInvoice':
        return <CloseInvoice args={args} />;
      case 'List':
        return <List args={args} />;
      case 'PractitionerReplacement':
        return <PractitionerReplacement args={args} />;
      case 'CAMemberTransitions':
        return <CAMemberTransitions args={args} />;
      case 'CostBreakdownCalculator':
        return <CostBreakdownCalculator args={args} />;
      case 'RecalculateCostBreakdown':
        return <RecalculateCostBreakdown args={args} />;
      case 'InlineReimbursementCostBreakdownCalculator':
        return <InlineReimbursementCostBreakdownCalculator args={args} />;
      case 'PreviewCostBreakdown':
        return <PreviewCostBreakdown args={args} />;
      case 'PractitionerSpecialtyBulkUpdate':
        return <PractitionerSpecialtyBulkUpdate />;
      default:
        return (
          <div>
            Developer error! Did not recognize
            {tool}
          </div>
        );
    }
  }
}

module.exports = function (tool, element, args = {}) {
  ReactDOM.render(<AdminTool tool={tool} args={args} />, element);
};

attachFastFind();