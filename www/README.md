## INSTALL

**_You should only really need to do this once/on a new system_**

- Install node (+npm) from https://nodejs.org/en/ - min version 9.10.0 (hint: use nvm to manage/switch node versions)

## SETUP

**_Get our frontend environment ready._**

- Install all our node modules
- `cd www`
  **then:**
  `npm install`

Compile our vendor.js file, which contains all 3rd party dependencies – the default `gulp` task will just run everything once, then finish.
`npm run gulp`

## DAY TO DAY

- **Start the local webserver && watch files for changes:**
  `cd` into `www` folder and run `npm start`

Reminder: you'll have to have run `npm run gulp` once before running `npm start` for the first time - otherwise you won't have 3rd party deps (including angular!) available so you'll have a bad time mmmkay?

## PROCESS AND TROUBLESHOOTING

Checkout the docs at

https://sites.google.com/mavenclinic.com/engineering/maven-frontend/day-to-day

and

https://sites.google.com/mavenclinic.com/engineering/maven-frontend/troubleshooting
