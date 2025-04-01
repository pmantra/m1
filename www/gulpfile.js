/* eslint-env node */
var gulp = require("gulp"),
	concat = require("gulp-concat"),
	uglify = require("gulp-uglify"),
	ngAnnotate = require("gulp-ng-annotate"),
	sass = require("gulp-sass")(require('sass')),
	minifycss = require("gulp-clean-css"),
	rev = require("gulp-rev"),
	inject = require("gulp-inject"),
	del = require("del"),
	webserver = require("gulp-webserver"),
	args = require("yargs").argv,
	eslint = require("gulp-eslint"),
	babel = require("gulp-babel"),
	autoprefixer = require("gulp-autoprefixer")

var browserSync = require("browser-sync").create()
var Server = require("karma").Server

/* Bypass webserver issue with self-signed certificates */
process.env.NODE_TLS_REJECT_UNAUTHORIZED = "0"

/* ----- JS Tasks ----- */

var appPaths = [
	"static/js/mvnApp/mvnApp.js",
	"static/js/mvnApp/app/auth/auth.js",
	"static/js/mvnApp/app/user/user.js",
	"static/js/mvnApp/app/app.js",
	"static/js/mvnApp/public/public.js",
	"static/js/mvnApp/app/practitioner/practitioner.js",
	"static/js/mvnApp/app/appointment/appointment.js",
	"static/js/mvnApp/app/messages/messages.js",
	"static/js/mvnApp/app/forum/forum.js",
	"static/js/mvnApp/app/library/library.js",
	"static/js/mvnApp/app/resources/resources.js",
	"static/js/mvnApp/app/products/products.js",
	"static/js/mvnApp/**/*.js",
	"!static/js/**/*.test.js"
],
	vendorJSPaths = [
		"node_modules/jquery/dist/jquery.min.js",
		"node_modules/lodash/lodash.js",
		"static/js/vendor/external/modernizr.js",
		"node_modules/angular/angular.js",
		"node_modules/@uirouter/angularjs/release/angular-ui-router.js",
		"node_modules/@uirouter/angularjs/release/stateEvents.js",
		"node_modules/angular-resource/angular-resource.min.js",
		"node_modules/angular-sanitize/angular-sanitize.min.js",
		"node_modules/angular-aria/angular-aria.js",
		"node_modules/angular-messages/angular-messages.js",
		"node_modules/restangular/dist/restangular.min.js",
		"node_modules/angular-cookies/angular-cookies.min.js",
		"node_modules/angular-animate/angular-animate.min.js",
		"node_modules/oclazyload/dist/ocLazyLoad.js",
		"node_modules/slick-carousel/slick/slick.js",
		"node_modules/angular-slick-carousel/dist/angular-slick.js",
		"node_modules/ng-notify/dist/ng-notify.min.js",
		"node_modules/ui-select/dist/select.js",
		"node_modules/angular-payments/lib/angular-payments.js",
		"node_modules/moment/moment.js",
		"node_modules/angular-moment/angular-moment.js",
		"node_modules/clndr/src/clndr.js",
		"node_modules/angular-clndr/angular-clndr.js",
		"node_modules/ng-dialog/js/ngDialog.js",
		"node_modules/videogular/videogular.js",
		"node_modules/re-tree/re-tree.js",
		"node_modules/ua-device-detector/ua-device-detector.js",
		"node_modules/ng-device-detector/ng-device-detector.js",
		"node_modules/ng-file-upload/dist/ng-file-upload.js",
		"node_modules/rx/dist/rx.js",
		"node_modules/rx/dist/rx.lite.compat.js",
		"node_modules/rx-angular/dist/rx.angular.js",
		"node_modules/intl-tel-input/build/js/intlTelInput.js",
		"node_modules/intl-tel-input/build/js/utils.js", // ugh this is huge. todo: lazy-load
		"node_modules/betsol-ng-intl-tel-input/dist/scripts/betsol-ng-intl-tel-input.js",
		"static/js/vendor/external/material/angular-material.js",
		"node_modules/focus-visible/dist/focus-visible.js"
	]

var paths = {
	styles: {
		src: "static/sass/*.scss"
	},
	scripts: {
		app: appPaths,
		vendor: vendorJSPaths
	}
}
/* Clean all the things */

function cleanJs() {
	return del(["static/js/*.js"])
}

function cleanVendorJs() {
	return del(["static/js/vendor/*.js"])
}

function cleanCss() {
	return del(["static/css/*.css"])
}

/* Sass/CSS stuff */
function styles() {
	return gulp
		.src(paths.styles.src)
		.pipe(sass({ style: "compressed" }))
		.pipe(autoprefixer())
		.pipe(minifycss({ keepSpecialComments: 0 }))
		.pipe(concat("static/css/mvn.css"))
		.pipe(rev())
		.pipe(gulp.dest("."))
}

/* Compile our 3rd party JS deps */
function vendorJs() {
	return gulp
		.src(paths.scripts.vendor)
		.pipe(concat("static/js/vendor/vendor.js"))
		.pipe(ngAnnotate())
		.pipe(uglify())
		.pipe(rev())
		.pipe(gulp.dest("."))
}

/* Compile our app js file */
function js() {
	return gulp
		.src(paths.scripts.app, { sourcemaps: true })
		.pipe(concat("static/js/mvn.js"))
		.pipe(ngAnnotate())
		.pipe(
			eslint({
				configFile: ".eslintrc.js"
			})
		)
		.pipe(eslint.format())
		.pipe(eslint.failAfterError())
		.pipe(babel())
		.pipe(uglify())
		.pipe(rev())
		.pipe(gulp.dest("."))
}

function unitTests() {
	/* to reimplement */
	return new Server(
		{
			configFile: __dirname + "/mvn.conf.js",
			singleRun: true
		},
		done
	).start()
}

/* Inject rev'd css & js into index.html */

function index() {
	var sources = gulp.src(["static/js/vendor/*.js", "static/js/*.js", "static/css/*.css"], {
		read: false,
		ignorePath: "static",
		addRootSlash: false
	})

	return gulp
		.src("static/index.html")
		.pipe(inject(sources, { ignorePath: "static" }))
		.pipe(gulp.dest("static/"))
}

/* Run our browsersync server to reload and sync pages */
function initBrowserSync(done = () => true) {
	browserSync.init({
		proxy: "https://www.mvnctl.net:8888",
		host: "www.mvnctl.net",
		ghostMode: false,
		port: "3030",
		open: "local"
	})
	done()
}

/* Reload browsersync */
function reload(done) {
	browserSync.reload()
	done()
}

/* Watch files for changes when developing locally */

function watch() {
	gulp.watch("static/js/mvnApp/**/*.js", gulp.series(cleanJs, js, index, reload))
	gulp.watch("static/sass/**/*.scss", gulp.series(gulp.series(cleanCss, styles), index, reload))
	gulp.watch("static/js/**/*.html", gulp.series(reload))
}

/* Compile all the stuff */
var buildLocal = gulp.series(gulp.parallel(gulp.series(cleanJs, js), gulp.series(gulp.series(cleanCss, styles))), index)

/* Runs a local node server on our machines for local dev */
var localserver = function () {
	if (!args.ANGULAR_APP_API_URL) {
		console.log("\n\n ****** ANGULAR_APP_API_URL must be set to develop off of QA.")
		process.exit()
	}
	const target = `https://www.${args.ANGULAR_APP_API_URL}.mvnapp.net`
	console.log(`Serving: ${target}`)
	return gulp.src(["static"]).pipe(
		webserver({
			port: 8888,
			livereload: false,
			https: true,
			host: "www.mvnctl.net",
			fallback: "index.html",
			proxies: [
				{
					source: "/api",
					target: `${target}/api`
				},
				{
					source: "/saml/consume",
					target: `${target}/saml/consume`
				},
				{
					source: "/saml",
					target: `${target}/saml`
				},
				{
					source: "/ajax",
					target: `${target}/ajax`
				}
			]
		})
	)
}

exports.cleanJs = cleanJs
exports.cleanVendorJs = cleanVendorJs
exports.cleanCss = cleanCss
exports.styles = styles
exports.js = js
exports.vendorJs = vendorJs
exports.index = index
exports.watch = watch
exports.buildLocal = buildLocal

/* Main task - this builds vendor and app js, and css. Should be production-ready. */
var build = gulp.series(
	gulp.parallel(cleanJs, cleanVendorJs, cleanCss),
	gulp.parallel(styles, gulp.series(vendorJs, js)),
	index
)

/* Run local server, build assets, start browsersync and watch for changes */
var localDev = gulp.series(localserver, buildLocal, initBrowserSync, watch)

/* Main gulp tasks */
gulp.task("buildLocal", buildLocal)

gulp.task("localserver", localserver)

gulp.task("build", build)

gulp.task("watch", watch)

gulp.task("start", localDev)

gulp.task("default", build)
