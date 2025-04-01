import React from 'react';

import Tabs from '../Tabs.jsx';
import ValidateInvoices from './ValidateInvoices.jsx';
import GenerateFees from './GenerateFees.jsx';
import GenerateInvoices from './GenerateInvoices.jsx';
import CreateInvoice from './CreateInvoice.jsx';
import ViewIncompleteInvoices from './ViewIncompleteInvoices.jsx';

import '../../bootstrap/css/bootstrap.scss';
import '../../bootstrap/css/bootstrap-theme.scss';

export default function MonthlyPayments() {
  return (
    <div className="container">
      <h2>Monthly Payments</h2>
      <Tabs>
        <div label="Validate Invoices" identifier="validate-invoices">
          <ValidateInvoices />
        </div>
        <div label="Generate Fees" identifier="generate-fees">
          <GenerateFees />
        </div>
        <div label="Generate Invoices" identifier="generate-invoices">
          <GenerateInvoices />
        </div>
        <div label="Create Invoice" identifier="create-invoice">
          <CreateInvoice />
        </div>
        <div label="View Incomplete Invoices" identifier="view-incomplete-invoice">
          <ViewIncompleteInvoices />
        </div>
      </Tabs>
    </div>
  );
}
