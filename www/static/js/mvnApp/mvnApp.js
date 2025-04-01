/*
 *
 * Angular module definition
 *
 */
"use strict"

var initInjector = angular.injector(["ng"])
var $http = initInjector.get("$http")
var nativeAppPlatform

if (navigator.userAgent.match(/MAVEN_IOS/i)) {
	nativeAppPlatform = "iOS"
} else if (navigator.userAgent.match(/MAVEN_ANDROID/i)) {
	nativeAppPlatform = "Android"
}

const isMavenNativeAppWebView = nativeAppPlatform === "iOS" || nativeAppPlatform === "Android"

var mavenApp = angular.module("mavenApp", [
	"ui.router",
	"ui.router.state.events",
	"ngSanitize",
	"ngAnimate",
	"ngCookies",
	"ngMessages",
	"ngAria",
	"restangular",
	"ui.select",
	"oc.lazyLoad",
	"ngDialog",
	"auth",
	"user",
	"app",
	"forum",
	"library",
	"publicpages",
	"practitioner",
	"appointment",
	"messages",
	"resources",
	"products"
])

// We need to get info from the meta endpoint before everything else... so here goes.
var getMeta = function () {
	return $http.get("/api/v1/_/metadata").then(
		function (response) {
			mavenApp.constant("config", response.data)
		},
		function (errorResponse) {
			bootstrapApp()
			console.log(errorResponse)
			document.getElementById("loader-content").innerHTML =
				'<div style="width: 620px; max-width: 100%; padding: 24px; text-align: center"><h2>Sorry...</h2><br/><p>We seem to be having some problems right now. Please check back again soon &mdash; we\'re working hard on a fix!</p></div>'
		}
	)
}

// Bootstraps our index.html app with 'mavenApp' as the root of the angular application. Better/more flexible way of ng-app="mvnApp" in html.
var bootstrapApp = function () {
	angular.element(document).ready(function () {
		angular.bootstrap(document, ["mavenApp"])

		if (isMavenNativeAppWebView) {
			document.body.classList.add("is-webview")
			let msg = {
				type: "ready"
			}
			if (nativeAppPlatform === "iOS" && window.messageHandlers) {
				window.messageHandlers.notification.postMessage(msg)
			}
			if (nativeAppPlatform === "Android" && window.APP_INTERFACE) {
				window.APP_INTERFACE.sendObject(JSON.stringify(msg))
			}
		} else {
			document.body.classList.remove("is-loading")
		}
	})
}

var storeAndExtractTokens = function (tokens) {
  if (!tokens) {
    return {}
  }
  const refresh_token_key = "mvn_refresh_token"
  localStorage.setItem(refresh_token_key, tokens.refreshToken)
  return tokens
}

var mvnInit = function (authKey, tokens) {
  mavenApp.value("AUTHORIZATION", storeAndExtractTokens(tokens))
  mavenApp.constant("APIKEY", authKey) // if we don't have a key, this is just an empty constant. But as we're injecting it, we have to set it to *something* or angular gets grumpy.
  mavenApp.constant("NATIVE_PLATFORM", nativeAppPlatform)
  getMeta().then(bootstrapApp)
}

// This gets called from within the native apps, with api key as the value
window.mvnGetNativeKey = function (theKey, tokens) {
  if (tokens) {
		mvnInit(null, tokens)
  } else if (theKey) {
		mvnInit(theKey)
	} else {
		mvnInit() // Gotta cover our asses in case for some reason the native apps don't send the key.
	}
}

// If we aren't loading the app in a native webview, initialise the app.
if (!isMavenNativeAppWebView) {
	document.body.classList.add("is-loading")
	mvnInit()
}
