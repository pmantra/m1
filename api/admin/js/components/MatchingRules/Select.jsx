import React from 'react';
import Select from 'react-select';
import { find, size } from 'lodash';

export const anyOption = { value: 'any', label: 'Any' };
export const noneOption = { value: 'none', label: 'None' };

function MavenSelect({
  label, value, onChange, options, includeAny, includeNone, isMulti, isIndented, addAll, sort='ASC'
}) {
  const sortOrder = { ASC: 'ASC', DESC: 'DESC' }

  let newOptions = options;
  if (includeAny) {
    newOptions = [anyOption].concat(newOptions);
  }

  if (includeNone) {
    newOptions = [noneOption].concat(newOptions);
  }

  if (addAll && !includeAny) {
    newOptions = [addAll].concat(newOptions)
  }

  // Will try to run on a new ruleset (which doesn't have any values to sort yet)
  if (value) {
    switch (sort) {
      case sortOrder.ASC:
        value.sort((a, b) => a.label.localeCompare(b.label))
        break;
      case sortOrder.DESC:
        value.sort((a, b) => b.label.localeCompare(a.label))
        break;
      default: // default sort ascending
        value.sort((a, b) => a.label.localeCompare(b.label))
    }
  }

  const onChangeHandleNoneAny = v => {
    if (addAll && find(v, addAll)) {
      onChange(options);
      return;
    }

    if (find(v, noneOption) || find(v, anyOption)) {
      newOptions = []
      if (find(v, noneOption)){
        newOptions.push(noneOption);
      }
      if (find(v, anyOption)){
        newOptions.push(anyOption);
      }
      onChange(newOptions);
      return;
    }
    onChange(v);
  }
   
  const shouldRenderAddAll = (opts, val) => size(opts) !== size(val);

  /*
    react select component inherently handles typeahead. but when adding this filter option to include the addAll
    functionality, this somehow breaks typeahead. this might be a bug with react similar
    to this: https://github.com/JedWatson/react-select/issues/1547. therefore we implemented our own low weight
    typeahead here instead
  */
  const filterOption = (option, inputValue) => {
    const labelStripped = option.label.trim().toLowerCase();
    const inputValueStripped = inputValue.trim().toLowerCase();
    const renderAll = shouldRenderAddAll(options, inputValueStripped);
    
    const otherKey = options.filter(opt => {
      if (opt.label !== labelStripped) return false
      if (!opt.label.includes(inputValueStripped)) return false
      if (opt.data === addAll) return true

      return renderAll
    });
    return labelStripped.includes(inputValueStripped) || otherKey.length > 0;
  };

  return (
    <div className="control-group">
      <p style={isIndented ? { marginLeft: '50px', width: '179px' } : {}} className="control-label">
        {label}
      </p>
      <div className="controls">
        <Select
          styles={{ input: (styles) => ({ ...styles, ...{ '& input': { minWidth: 'auto !important' } } }) }}
          value={value}
          onChange={onChangeHandleNoneAny}
          isMulti={isMulti}
          options={newOptions}
          filterOption={filterOption}

        />
      </div>
    </div>
  );
}

export default MavenSelect;
