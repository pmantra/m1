# Deploy Process V2 (Tag-based)

We use a tag-based release process that utilizes a single branch `main` and cuts releases by tagging the latest commit on `main` on a set sechedule.

After tagging to release, the release-candidate will deploy to staging where E2E tests will run on it overnight.

If those E2E tests pass, the deploy to production will happen automatically on a set schedule.

## Schedule

On each release day, at 11am EST, production releases will go out.

Before each release we:
1. (day before) [automation] Tag `main` to mark the release code
2. (day before) Update `#mono-release-coordination` channel topic with the link to the release changelog.
3. (day before) [automation] Deploy the release to staging
4. (day before) [automation] Run E2E tests against it on staging
5. (day of release) [automation] Deploy the release to production

### Notifications:

Automation will handle each step and report to the following slack channels:

1. `#mono-release-coordination`
2. `#staging-e2e-web-alerts` for e2e tests

Deployment updates are sent to:

1. `#deploy-staging`
2. `#deploy-maven`

## Automation

### Changing Schedules

Scheduled automation can be found in the [scheduled pipelines](https://gitlab.com/maven-clinic/maven/maven/-/pipeline_schedules) page for mono.

Automation schedules can only be adjusted by the pipeline owner because of Gitlab limitations. Feel free to reach out to the pipeline owner to have any schedules changed.

### Pausing automation

Automation is paused automatically during a scheduled deploy freeze and when hotfixes are created (which sets a deploy freeze).

To pause automation without a deploy freeze, TODO: create a button for this.


### Release Changelog

A release changelog will be generated each time `main` is tagged for the RC. A notification is sent to `#mono-release-coordination` with the link. Please update the `#mono-release-coordination` topic with a link to this changelog.

The changelog detects the last deployed version from Flux and generates the changelog between that tag and the current tag.

### Regenerating the changelog

It can be regenerated with a new starting point if needed (for example, if there was race condition between the deployments and the changelog generator).

1. Open the `regenerate-changelog` job in the tag pipeline and enter the `OVERRIDE_PREVIOUS_TAG` set to the desired starting tag.
2. Run the job

## Handling deployment failures

Deployment failures can either be caused by 1) a code change regression or 2) system instability (flakiness).

1. A Datadog alert will appear in the deployment slack channel with links to logs and events to help debug the issue.
2. If the failure is caused by a code-regression, you will need to coordinate with authors to revert the buggy code and cut a new tag to re-deploy.
3. If the cause is due to system instability, the deploy can be retried using the [Retry Latest Deploy buttons](https://www.notion.so/mavenclinic/Application-Rollbacks-Special-Deployment-Actions-13f15ef5a647804f85e9d55593d6905b)

## Handling smoketest failures

Smoketests run after each deploy in staging and production. If they fail, the deploy will rollback to the previous stable version.

1. Investigate the failures in Cypress Cloud
2. You may need to reach out to the owning Pod about the failure
3. Deployments can be retried using the [Retry Latest Deploy buttons](https://www.notion.so/mavenclinic/Application-Rollbacks-Special-Deployment-Actions-13f15ef5a647804f85e9d55593d6905b)

## Handling failed E2E tests that block production release

The production release can be manually triggered after the release manager has performed due diligence to inspect the failed E2E tests and reached out to owning pods to gain confidence in the release.

1. Visit the `#staging-e2e-web-alerts` channel to inspect the failing tests in Cypress.
2. TODO - finish this section
3. Open the `tag` pipeline and click the `promote-production` job to kick off the production deploy.


## Manually re-running E2E tests

1. Open the [New Pipeline](https://gitlab.com/maven-clinic/maven/maven-web/-/pipelines/new) page in `maven/maven-web`.
2. Add the following variables to the pipeline:
   - `TRIGGER_ID` set to `e2e`
   - `ENV` set to `staging`
3. Click `run pipeline`

## Manually creating a tag

### Situations where this is needed

In certain situations you may need to manually create a tag:
1. Code needed to be reverted from the release candidate due to a bug
2. New code needs to be added to the release candidate to fix a bug.

In all situations where new code is added or reverted, you'll need to create a new tag, get it deployed to staging, and re-run the E2E tests yourself manually.

> Each time you create a new tag, it will include more code changes that need to be validated before release.

### How to create a new tag

#### Best way:

1. After merging a code change into `main`, go to the newly created pipeline on `main` (this should appear in the MR page, or you can search the [pipelines](https://gitlab.com/maven-clinic/maven/maven/-/pipelines?page=1&scope=all&ref=main) page filtered by `main`.)
2. At the end of the pipeline is a manual job named `create-api-release-tag`. Run the job to create a new tag on the associated commit.


#### Very manual way:

> Feel free to reach out to `@eng-exp-on-call` for this.

1. Go to the [Gitlab tags page](https://gitlab.com/maven-clinic/maven/maven/-/tags)
2. Click `New Tag` (blue button) on the top right
3. **Name**: increment the patch version of the previous tag by 1. So if `api/v2024.10.02.1` is bad, increment the last number by 1 to `api/v2024.10.02.2`.
4. On the [history page](https://gitlab.com/maven-clinic/maven/maven/-/commits/main/?ref_type=HEADS), find the commit sha of the commit you want to tag. Paste that into **Create from**
5. Click "Create Tag"


