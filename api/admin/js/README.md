# Admin JS

## npm and node versions

npm and node versions are specified in the `package.json` file, section `engines`, and forced in the `.npmrc` file with `engine-strict=true`.

We also specify a node version in the `.nvmrc` file for convenience.

## Development

When running tilt, rather than `tilt up` to launch all services, if you're only modifying admin/adminjs you can use `tilt up admin` for faster builds.

When developing locally, you'll need to do the following to generate the JS bundle.

Run

    $ npm install
    $ npm run dev

At this point the app will load using the `app-dev.js` file, which will be available on every view. Webpack will watch for changes to JS files and recompile the bundle as needed, and docker will then sync the updated app-dev.js into the admin container.

In your template file, you can override the `tail_js` block to initiate what you want on your page. See `assessment_edit.html` for an example.

## Frontend environment variables

There’s a mechanism now for propagating environment variables from the backend to the JS on the frontend. If you ever need to do that, you can see how new ones are added by searching for “public_client_side_env” in api/admin/views/base.py- there's a comment there with some additional details.

## Git hooks

There's a post-merge hook (api/admin/js/.husky/post-merge) which should re-run `npm install` whenever you pull down updates to master that contain new packages. (if you're finding that you still need to manually run npm install for this, you may need to reinstall husky/git hooks locally.)

There's also a pre-commit hook to verify linting/formatting before allowing commits to go through.

## Production

During deployment, the pipeline will generate the `app-min-v2.js` bundle with the `prod:v2` npm script.
