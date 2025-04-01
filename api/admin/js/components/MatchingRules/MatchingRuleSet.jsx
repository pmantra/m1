import React, { useState } from 'react'
import { findIndex, mapValues } from 'lodash'
import MavenSelect from './Select.jsx'


const getRulesIds = (rules = []) => rules.reduce((acc, rule) => {
    acc.push(...rule.identifiers)
    return acc
  }, [])

const extractRules = rules => mapValues(rules, rule => getRulesIds(rule))

export const hasPregnancy = (options) => {
  if (findIndex(options, ['label', 'Pregnancy']) > -1) {
    return true;
  }
  if (findIndex(options, ['label', 'pregnancy']) > -1) {
    return true;
  }
  return false;
};

export const hasFertility = (options) => {
  if (findIndex(options, ['label', 'Fertility']) > -1) {
    return true;
  }
  if (findIndex(options, ['label', 'fertility']) > -1) {
    return true;
  }
  return false;
};

export const isRiskFactorVisible = (trackIds) => hasPregnancy(trackIds) || hasFertility(trackIds)

function MatchingRuleSet({
  countries = [],
  organizations = [],
  tracks = [],
  riskFactors = [],
  deleteRuleSet,
  rules,
  saveRuleSet,
  ix,
  id,
}) {

  const extractedRules = extractRules(rules)
  const [countryRuleCodes, setCountryCodes] = useState(extractedRules.country_rule)
  const [organizationRuleIds, setOrganizationIds] = useState(extractedRules.organization_rule)
  const [organizationExcludeRuleIds, setOrganizationExcludeIds] = useState(extractedRules.organization_exclude_rule)
  const [trackRuleIds, setTrackIds] = useState(extractedRules.track_rule)
  const [riskFactorRuleIds, setRiskFactorIds] = useState(extractedRules.risk_factor_rule)


  const [showRiskFactors, setShowRiskFactors] = useState(isRiskFactorVisible(trackRuleIds))

  const onSubmit = (e, ruleIx, ruleId) => {
    e.preventDefault();

    saveRuleSet(ruleIx, ruleId, {
      countryRuleCodes,
      organizationRuleIds,
      organizationExcludeRuleIds,
      trackRuleIds,
      riskFactorRuleIds,
    });
  };

  const onTrackChange = (value) => {
    if (isRiskFactorVisible(value)) {
      setShowRiskFactors(true);
    } else {
      setRiskFactorIds(riskFactorRuleIds);
      setShowRiskFactors(false);
    }
    setTrackIds(value);
  };

  return (
    <div className="inline-field well well-small fresh" style={{ marginLeft: '5px' }}>
      <div>
        <span
          role="button"
          tabIndex={0}
          aria-label="delete-rule-set"
          onClick={() => deleteRuleSet(ix, id)}
          onKeyDown={() => deleteRuleSet(ix, id)}
          className="pull-right icon-trash"
          style={{ cursor: 'pointer' }}
        />
        <h4 style={{ padding: '1px', fontWeight: 'bold', cursor: 'default' }}>Matching Rule Set</h4>
      </div>
      <form onSubmit={(e) => onSubmit(e, ix, id)} className="form-horizontal">
        <MavenSelect
          value={countryRuleCodes}
          onChange={setCountryCodes}
          isMulti
          includeAny
          label="Countries"
          options={countries}
          sort="ASC"
        />
        <MavenSelect
          value={organizationRuleIds}
          onChange={setOrganizationIds}
          isMulti
          includeAny
          label="Organizations"
          options={organizations}
          sort="ASC"
        />
        <MavenSelect
          value={organizationExcludeRuleIds}
          onChange={setOrganizationExcludeIds}
          isMulti
          includeNone
          isIndented
          label="Exceptions"
          options={organizations}
          sort="ASC"
        />
        <MavenSelect
          value={trackRuleIds}
          onChange={onTrackChange}
          isMulti
          label="Tracks"
          options={tracks}
          addAll={{value: "all", label: "Add All Tracks"}}
          sort="ASC"
        />
        {showRiskFactors ? (
          <MavenSelect
            value={riskFactorRuleIds}
            onChange={setRiskFactorIds}
            isMulti
            includeNone
            includeAny
            isIndented
            label="With Risk Factors"
            options={riskFactors}
            sort="ASC"
          />
        ) : null}
        <button type="submit" value="Save" className="btn">
          Save
        </button>
      </form>
    </div>
  );
}


export default MatchingRuleSet
