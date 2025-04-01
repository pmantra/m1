module.exports = {
	env: {
		browser: true,
		es6: true
	},
	extends: "eslint:recommended",
	globals: {
		$: true,
		angular: true,
		_: true,
		$scope: true,
		moment: true,
		ga: true,
		Modernizr: true,
		Stripe: true,
		OT: true,
		webkitMediaStream: true
	},
	rules: {
		//"strict": [1, "global"],
		"linebreak-style": ["error", "unix"],
		"no-unused-vars": ["error", { args: "none" }],
		"no-console": 0,
		"no-extra-boolean-cast": 0,
		"no-mixed-spaces-and-tabs": ["warn", "smart-tabs"], // yeaaaah clean this stuff up sometime!
		"linebreak-style": 0,
		"no-extra-semi": 0,
		"no-prototype-builtins": 0
	},
	overrides: [{ files: "!static/js/**/*.test.js" }]
}
