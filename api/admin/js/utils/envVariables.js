import { noop } from 'lodash';

const tryParseJSON = (val, errCallback = noop) => {
  try {
    return JSON.parse(val);
  } catch (e) {
    errCallback(e);

    return null;
  }
};

// partially derived from the Environment enum in api/common/constants.py.
// returns one of (local_dev, qa1, qa2, production, sandbox, staging).
// Can also return empty string if it's an env unrecognized by that enum.
export const ENV = {
  local_dev: 'local_dev',
  qa1: 'qa1',
  qa2: 'qa2',
  production: 'production',
  sandbox: 'sandbox',
  staging: 'staging',
};

export const extractEnvVars = () => {
  // window.envJSON is injected via extra_js in api/admin/views/base.py
  const envFromServer = window.envJSON;

  const parsed = tryParseJSON(envFromServer, () => {
    // malformed window.envJSON value
    // eslint-disable-next-line no-console
    console.log('Failed to parse env.');
  });

  const envVariables = { ...parsed };
  const getClientEnvironment = (environmentValFromServer) => {
    // the local env is not directly indicated by the server's ENVIRONMENT value as it is currently implemented, so we still need to verify via the hostname
    const isLocalDev = window.location.hostname === 'localhost';
    if (isLocalDev) {
      return ENV.local_dev;
    }

    return environmentValFromServer ? environmentValFromServer.toLowerCase() : '';
  };

  window.envJSON = undefined;

  return {
    CLIENT_ENVIRONMENT: getClientEnvironment(envVariables.ENVIRONMENT),
  };
};
