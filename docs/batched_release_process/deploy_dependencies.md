# Mono API & Default Maven Deploy Dependencies

## Overview

- Each time you trigger a deploy by merging code, the new `mono/api` deployment will go first. It will run migrations, it will run smoketests.
- The old `maven/default` deployment (which contains Admin and RQ) will deploy second, waiting for `mono/api` smoketests to pass before it starts its deploy.
- If `mono/api` fails, Admin and RQ will not deploy and everything remain on the same previous version.
- If `mono/api` succeeds, but admin/rq fails, they will remain on different versions until the deployment issue with Admin and/or RQ is resolved. This should not be considered an incident, however, if there is backwards compatibility on api endpoints that serve Admin / RQ requests during the release and forwards-compatibility on those requests.
- This dependency itself does not relate to rollbacks and/or force deploys. Those will still be handled separately via the existing tooling.


## Notes for release managers and devs

- During a typical deploys, there will be a period of 10-15 minutes when the version of `mono/api` is ahead of the code in Admin and RQ.
- Engineers should continue to make sure that the mono api endpoints that serve Admin and RQ requests are backwards-compatible for each batched release and that Admin and RQ requests are forwards compatible for that release.