import React, { useState } from 'react';
import axios from 'axios';
import {
  without, compact, isEmpty, mapValues, uniqueId,
} from 'lodash';
import MatchingRuleSet, { isRiskFactorVisible } from './MatchingRuleSet.jsx';
import { Type, Entity } from './constants.js';
import { anyOption, noneOption } from './Select.jsx';

const VALIDATION_ERROR = 'All fields must be filled before saving';

const toFormData = (rules) => mapValues(rules, (rule) => rule.map(r => {
    const ruleWithIds = r;
    if (r.all && r.type === Type.INCLUDE) {
      ruleWithIds.identifiers = [anyOption];
    } else if (r.type === Type.EXCLUDE && isEmpty(r.identifiers)) {
      ruleWithIds.identifiers = [noneOption];
    }

    return ruleWithIds;
  }));

const createBody = (
  countryRuleCodes,
  organizationRuleIds,
  organizationExcludeRuleIds,
  trackRuleIds,
  riskFactorRuleIds,
) => {
  const countryCodes = countryRuleCodes.map((c) => c.value);
  const newCountryRule = {
    type: Type.INCLUDE,
    entity: Entity.COUNTRY,
    all: countryCodes.includes('any'),
    identifiers: without(countryCodes, 'any'),
  };

  const organizationIds = organizationRuleIds.map((o) => o.value);
  const newOrganizationRule = {
    type: Type.INCLUDE,
    entity: Entity.ORGANIZATION,
    all: organizationIds.includes('any'),
    identifiers: without(organizationIds, 'any'),
  };

  const newOrganizationExcludeRule = {
    type: Type.EXCLUDE,
    entity: Entity.ORGANIZATION,
    all: false,
    identifiers: without(
      organizationExcludeRuleIds.map((o) => o.value),
      'none',
    ),
  };

  const trackIds = trackRuleIds.map((t) => t.value);
  const newTrackRule = {
    type: Type.INCLUDE,
    entity: Entity.TRACK,
    all: false,
    identifiers: without(trackIds, 'any'),
  };

  const newRiskFactorRules = []
  if (isRiskFactorVisible(trackRuleIds)) {
    const riskFactorIds = riskFactorRuleIds.map(rf => rf.value)
    if (!(riskFactorIds.includes('any') || riskFactorIds.includes('none'))) {
      newRiskFactorRules.push({
        type: Type.INCLUDE,
        entity: Entity.RISK_FACTOR,
        all: false,
        identifiers: riskFactorIds
      })
    } else {
      if (riskFactorIds.includes('any')) {
        newRiskFactorRules.push({
          type: Type.INCLUDE,
          entity: Entity.RISK_FACTOR,
          all: true,
          identifiers: []
        })
      }

      if (riskFactorIds.includes('none')) {
        newRiskFactorRules.push({
          type: Type.EXCLUDE,
          entity: Entity.RISK_FACTOR,
          all: true,
          identifiers: []
        })
      }
    }
  }

  return {
    matching_rules: compact([
      newCountryRule,
      newOrganizationRule,
      newOrganizationExcludeRule,
      newTrackRule,
      ...newRiskFactorRules
    ])
  }
}



function MatchingRules({
  matchingRuleSets: matchingRuleSetsProp,
  assignableAdvocateId,
  countries,
  organizations,
  tracks,
  riskFactors,
}) {
  const matchingRuleSetsFormData = matchingRuleSetsProp.map((mrs) => (
    { ...mrs, rules: toFormData(mrs.rules) }));
  const [matchingRuleSets, setRules] = useState(matchingRuleSetsFormData);
  const [validationError, setValidationError] = useState('');
  const [info, setInfo] = useState('');

  const addRuleSet = (e) => {
    e.preventDefault();
    setInfo('');
    setRules(matchingRuleSets.concat({ id: null, rules: {}, tempId: uniqueId('rules_sets_') }));
  };

  const deleteRuleSet = (ruleIx, id) => {
    if (window.confirm('You are about to delete a matching rule, There is no undo')) {
      if (id) {
        axios
          .delete(`/admin/assignable-advocates/${assignableAdvocateId}/matching-rule-set/${id}`, {})
          .then(() => {
            setInfo('Matching rule set deleted');
            setRules(matchingRuleSets.filter((mrs) => id !== mrs.id));
          })
          .catch((err) => {
            window.alert(`${JSON.stringify(err.response.data)}`);
          });

        return;
      }

      setRules(matchingRuleSets.filter((_, ix) => ruleIx !== ix));
    }
  };

  const saveRuleSet = (
    ruleIx,
    id,
    {
      countryRuleCodes,
      organizationRuleIds,
      organizationExcludeRuleIds,
      trackRuleIds,
      riskFactorRuleIds,
    },
  ) => {
    const body = createBody(
      countryRuleCodes,
      organizationRuleIds,
      organizationExcludeRuleIds,
      trackRuleIds,
      riskFactorRuleIds,
    );

    const isSomeFieldEmpty = [
      countryRuleCodes,
      organizationRuleIds,
      organizationExcludeRuleIds,
      trackRuleIds].some(
      isEmpty,
    );

    if (isSomeFieldEmpty || (isRiskFactorVisible(trackRuleIds) && isEmpty(riskFactorRuleIds))) {
      setValidationError(VALIDATION_ERROR);
      return;
    }

    const req = id
      ? axios.put(`/admin/assignable-advocates/${assignableAdvocateId}/matching-rule-set/${id}`, body)
      : axios.post(`/admin/assignable-advocates/${assignableAdvocateId}/matching-rule-set`, body);

    req
      .then(({ data }) => {
        matchingRuleSets[ruleIx].id = data.id;
        setValidationError('');
        setInfo('Saved!');
        setRules([...matchingRuleSets]);
      })
      .catch((err) => window.alert(`${JSON.stringify(err.response.data)}`));
  };

  return (
    <div>
      {validationError && <p className="alert alert-danger">{validationError}</p>}
      {info && <p className="alert alert-success">{info}</p>}
      {assignableAdvocateId ? (
        <div>
          {matchingRuleSets.map((r, ix) => (
            <MatchingRuleSet
              key={r.tempId || r.id}
              ix={ix}
              id={r.id || null}
              countries={countries || []}
              organizations={organizations || []}
              tracks={tracks || []}
              riskFactors={riskFactors || []}
              showRiskFactors={false}
              rules={r.rules}
              assignableAdvocateId={assignableAdvocateId}
              deleteRuleSet={deleteRuleSet}
              saveRuleSet={saveRuleSet}
            />
          ))}

          <p className={matchingRuleSets.length > 0 ? 'pull-right' : ''}>
            <button type="button" onClick={addRuleSet}>
              Add
            </button>
          </p>
        </div>
      ) : (
        <p>Please save and continue to add matching rules.</p>
      )}
    </div>
  );
}

export default MatchingRules;
