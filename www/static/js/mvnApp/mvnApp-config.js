/*
*
* Main Angular module config
*
*/

angular.module("mavenApp").config([
	"APIKEY",
	"$compileProvider",
	"$stateProvider",
	"$locationProvider",
	"$urlServiceProvider",
	"RestangularProvider",
	function(APIKEY, $compileProvider, $stateProvider, $locationProvider, $urlServiceProvider, RestangularProvider) {
		// If we have an api key set from iOS/Android app, use the non-ajax path for Restangular base and set request headers to include the api key
		if (APIKEY) {
			RestangularProvider.setBaseUrl("/api/v1/")
			RestangularProvider.addRequestInterceptor(function(element, operation, what, url) {
				RestangularProvider.setDefaultHeaders({ "API-KEY": APIKEY })
				return element
			})
		} else {
			RestangularProvider.setBaseUrl("/ajax/api/v1/")
		}

		// Disable debug. Performace ftw. Thanks HN.
		$compileProvider.debugInfoEnabled(false)

		$urlServiceProvider.rules.otherwise("/404")

		$urlServiceProvider.config.caseInsensitive(true)
		$urlServiceProvider.config.strictMode(false)

		$stateProvider.state("public", {
			templateUrl: "/js/mvnApp/public/shared/public.html",
			data: {
				noAuth: true
			},
			controller: "PublicCtrl",
			title:
				"Maven – healthcare designed exclusively for women. Video appointments with MDs, Nurses and Pregnancy specialists, all from your mobile device.",
			meta:
				"With Maven, book video appointments with doctors, nurses, pregnancy specialists, nutritionists, lactation consultants and other women's health experts – all via your iPhone."
		})

		$stateProvider.state("app", {
			abstract: true,
			views: {
				"@": {
					templateUrl: "/js/mvnApp/app/app.html",
					controller: "AppCtrl"
				}
			},
			data: {
				noAuth: false
			},
			resolve: {
				user: [
					"$rootScope",
					"$state",
					"Users",
					"Session",
					function($rootScope, $state, Users, Session) {
						return Users.getWithProfile().then(function(u) {
							if (!u) {
								$rootScope.isAuthenticated = false
								return false
							} else {
								//set our user...
								$rootScope.user = u
								$rootScope.isAuthenticated = true
								$rootScope.isEnterprise = $rootScope.user.organization ? true : false
								$rootScope.hasSubscription = $rootScope.user.subscription_plans
								return u
							}
						})
					}
				]
			},

			title:
				"Maven – healthcare designed exclusively for women. Video appointments with MDs, Nurses and Pregnancy specialists, all from your mobile device.",
			meta:
				"With Maven, book video appointments with doctors, nurses, pregnancy specialists, nutritionists, lactation consultants and other women's health experts – all via your iPhone."
		})

		$locationProvider.html5Mode(true).hashPrefix("!")

		/* Restangular config */
		//RestangularProvider.setBaseUrl('/ajax/api/v1/');

		RestangularProvider.addResponseInterceptor(function(data, operation, what, url, response) {
			if (data) {
				var extractedData

				if (operation === "getList") {
					extractedData = data.data
					extractedData.meta = data.meta
					extractedData.pagination = data.pagination
				} else {
					extractedData = data.data
				}
				return extractedData
			}
		})

		RestangularProvider.addResponseInterceptor(function(data, operation, what, url, response) {
			var extractedData = data

			if (operation === "get") {
				extractedData = response.data
			}

			return extractedData
		})

		RestangularProvider.addResponseInterceptor(function(data, operation, what, url, response) {
			var returnData = data

			if (operation === "post") {
				returnData = response.data
			}

			return returnData
		})

		RestangularProvider.addResponseInterceptor(function(data, operation, what, url, response) {
			var returnData = data

			if (operation === "customPOST") {
				returnData = response.data
			}

			return returnData
		})

		RestangularProvider.addResponseInterceptor(function(data, operation, what, url, response) {
			var returnData = data

			if (operation === "put") {
				returnData = response.data
			}

			return returnData
		})

		RestangularProvider.addFullRequestInterceptor(function(
			element,
			operation,
			route,
			url,
			headers,
			params,
			httpConfig
		) {
			if ((operation === "put" || "customPUT" || "post" || "customPOST") && !httpConfig.excludeHeaders) {
				return {
					headers: { "Content-Type": "application/json" }
				}
			}
		})

		/* Handle loading states for requests over X ms */
		var pendingRequests = 0

		RestangularProvider.addRequestInterceptor(function(element, operation, what, url) {
			//TODO: this is kinda hacky. But we want to exclude the images resource from blocking page load,
			//as these could well take > 500ms to load... and currently their resource type is Sizexsize (50x50)
			/*var resType = url.split("/")[3];
			if (resType !== "images") {
				// show the loader if request takes more than 500ms to return
				window.setTimeout(function() {
					if (pendingRequests == 0) {
						//TODO: ugh jQuery. Make this into a service (provider)!
						$(".page-loading").addClass("show-loader");
					}
					pendingRequests++;
				}, 1000);
			}
			*/
			return element
		})

		RestangularProvider.addResponseInterceptor(function(data, operation, what, url, response) {
			pendingRequests--
			if (pendingRequests == 0) {
				//TODO: ugh jQuery. Make this into a service (provider)!
				$(".page-loading").removeClass("show-loader")
			}
			return data
		})

		RestangularProvider.addErrorInterceptor(function(response, deferred) {
			pendingRequests--
			if (pendingRequests == 0) {
				//TODO: ugh jQuery. Make this into a service (provider)!
				$(".page-loading").removeClass("show-loader")
			}
			return true // error not handled
		})
	}
])
