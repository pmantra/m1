/**
 * @ngdoc overview
 * @name mavenApp
 * @description
 * # mavenApp
 *
 * Main module of the application.
 */

angular.module("mavenApp").controller("MvnCtrl", [
	"$scope",
	"$rootScope",
	"$cookies",
	"ngNotify",
	"ngDialog",
	"$window",
	"$state",
	"$location",
	"AuthService",
	"Users",
	"Session",
	"ModalService",
	"MvnStorage",
	"AUTH_EVENTS",
	"Plow",
	"staticPlans",
	"UrlHelperService",
	function(
		$scope,
		$rootScope,
		$cookies,
		ngNotify,
		ngDialog,
		$window,
		$state,
		$location,
		AuthService,
		Users,
		Session,
		ModalService,
		MvnStorage,
		AUTH_EVENTS,
		Plow,
		staticPlans,
		UrlHelperService
	) {
		var goTo

		$scope.pg = {}

		/* Listen for events and react accordingly... */
		$scope.$on(AUTH_EVENTS.loginSuccess, function(evt, u, from) {
			$scope.user = u
			var nextPath = from ? UrlHelperService.urldecode(from) : "/app/dashboard"
			$window.location.href = nextPath
		})

		$scope.$on(AUTH_EVENTS.notAuthenticated, function(evt, fromLoc) {
			AuthService.logout(fromLoc)
		})

		$scope.$on(AUTH_EVENTS.logoutSuccess, function(evt, fromLoc) {
			delete $rootScope.user
			delete $scope.user

			// If we have a register param, don't show the error and take the user to the register page instead of login.
			if (fromLoc && UrlHelperService.getParamValue(UrlHelperService.urldecode(fromLoc), "register")) {
				// if we were redirected from somewhere and have the 'register' param, go to /register not /login
				goTo = UrlHelperService.appendParam("/register", "from", fromLoc)
				$window.location.href = goTo
			} else {
				if (fromLoc) {
					// TODO && fromLoc !== register/dashboard
					goTo = UrlHelperService.appendParam("/login", "from", fromLoc)
					$window.location.href = goTo
				} else {
					$window.location.href = "/login"
				}

				ngNotify.set("Please sign in to continue", "error")
			}
		})

		$scope.$on(AUTH_EVENTS.loginNotNeeded, function(evt) {
			$window.location.href = "/app/dashboard"
		})

		/* Listen for changes to our user object (if theyve become enterprise/subscriber etc) and save the new user obj on the rootscope. */

		$scope.$on("updateUser", function(evt, u) {
			$scope.setUser(u)
		})

		$scope.setUser = function(u) {
			$scope.user = u
			$scope.isEnterprise = $scope.user ? $scope.user.organization : false
			$scope.hasSubscription = $scope.user ? $scope.user.subscription_plans : false
		}

		/* HTTP Error handling */

		$scope.$on("401_error", function(e) {
			e.preventDefault()
			// If the user was signed in at some point, and, for example, their session has expired by us or by time, throw a login modal.
			if ($scope.user) {
				var onComplete = function() {
					$state.reload()
				}
				ModalService.forceLoginModal(onComplete)
				//tell the rest of our app we need to log in again, so we can stop checking for messages etc.
				$scope.$broadcast("forceLogin")
			} else {
				e.preventDefault()
			}
		})

		$scope.$on("403_error", function(e, args) {
			ngNotify.set("Sorry, you don't have permission to do that! (" + args + ")", "error")
		})
		$scope.$on("500_error", function(e, args) {
			ngNotify.set(
				"There seems to be a problem. Try again or contact support@mavenclinic.com if the issue persists.",
				"error"
			)
		})
		$scope.$on("unknown", function(e, args) {
			var arg = args
				? args
				: "Sorry there seems to have been a problem. Try again or contact support@mavenclinic.com if the issue persists"
			ngNotify.set(arg, "error")
		})

		/* Receive tracking events, send to snowplow */
		$scope.$on("trk", function(event, data) {
			Plow.send(data)
		})

		/* Logout */
		$scope.logout = function() {
			AuthService.logout()
			var evt = {
				event_name: "logout"
			}
			Plow.send(evt)
		}

		/* Check if we have mc_id or retarget cookies already set - if so, update tracking accordingly */

		var mcId = $cookies.get("mc_id"),
			mvnRetarget = $cookies.get("mvn_retarget"),
			espId = $cookies.get("esp_id")

		if (mcId) {
			Plow.updateTrack({ mc_id: mcId })
		}

		if (mvnRetarget) {
			Plow.updateTrack({ mvn_retarget: mvnRetarget })
		}

		if (espId) {
			Plow.updateTrack({ esp_id: espId })
		}

		/* Set tracking params to localStorage so they persist throughout sessions until user signs up */
		var _installParams = ["install_source", "install_campaign", "install_content", "install_ad_unit"],
			_trackParams = MvnStorage.getItem("local", "mvnInst") ? JSON.parse(MvnStorage.getItem("local", "mvnInst")) : {},
			_invite_id,
			_httpReferrer = document.referrer

		var _parseParams = function(theParams) {
			for (var key in theParams) {
				if (_installParams.indexOf(key) >= 0) {
					_trackParams[key] = theParams[key]
				}
				// If we have an invite id, grab it
				if (key === "plan_invite_id") {
					_invite_id = theParams["plan_invite_id"]
				}

				if (key === "mc_id") {
					$cookies.put("mc_id", theParams[key])
					Plow.updateTrack({ mc_id: theParams[key] })
				}

				if (key === "esp_id") {
					$cookies.put("esp_id", theParams[key])
					Plow.updateTrack({ esp_id: theParams[key] })
				}

				if (key === "retarget") {
					$cookies.put("mvn_retarget", theParams[key])
					Plow.updateTrack({ retarget: theParams[key] })
				}
			}

			if (_httpReferrer) {
				// if we have a new page referrer, set it
				_trackParams["http_page_referrer"] = _httpReferrer
			} else {
				// if we don't, check for any existing page referrer values and use that instead if it exists
				if (MvnStorage.getItem("local", "mvnInst")) {
					_trackParams.http_page_referrer = JSON.parse(MvnStorage.getItem("local", "mvnInst")).http_page_referrer
						? JSON.parse(MvnStorage.getItem("local", "mvnInst")).http_page_referrer
						: null
				}
			}

			if (!_.isEmpty(_trackParams)) {
				MvnStorage.setItem("local", "mvnInst", JSON.stringify(_trackParams))
			}
		}

		// If we have url param present, check them and parse tracking stuff
		if ($location.search()) {
			_parseParams($location.search())
			// if we have a "from" path AND that "from" path has params, convert the params to an object and parse install params (welp)
			if ($location.search().from && UrlHelperService.urldecode($location.search().from).split("?")[1]) {
				var listParams = UrlHelperService.convertParamsToObj(
					UrlHelperService.urldecode($location.search().from).split("?")[1]
				)
				if (listParams) {
					_parseParams(listParams)
				}
			}
		}

		// save our invite id to rootscope...
		if (_invite_id) {
			$rootScope.invite_id = _invite_id
		}

		$scope.$on("setPageTitle", function(evt, data) {
			$scope.pageTitle = (data.title ? data.title : "Maven") + " | Maven. The Digital Clinic for Women."
		})

		// Set base page meta, title, class etc.
		$rootScope.setPageData = function(data) {
			$scope.pageTitle = (data.title ? data.title : "Maven") + " | Maven. The Digital Clinic for Women."
			$scope.pageMeta = data.meta
				? data.meta
				: "Book video appointments with doctors, nurses, pregnancy specialists, nutritionists, lactation consultants and other women's health experts – all via your iPhone."
			$scope.controller = data.bodyClass ? data.bodyClass : ""
		}

		$scope.$on("$stateChangeStart", function(event, toState, toParams, fromState, fromParams, options) {
			var memberOnly = toState.data.memberOnly,
				pracOnly = toState.data.pracOnly

			// Redirect to new react codebase for routes we've replatformed!
			if (toState.react) {
				event.preventDefault()
				let reactPath = `/app${!!toState.reactUrl ? toState.reactUrl : toState.url}${window.location.search}`
				UrlHelperService.redirectToReact(reactPath)			
			}

			if (!toState.data.noAuth) {
				if ($scope.user) {
					// if this requires auth but we already have our user, carry on
					if ($scope.user.role === "practitioner" && memberOnly) {
						if (!$scope.user.profiles.practitioner.is_cx) {
							// If the prac is not CX, prevent them from accessing member-only routes
							event.preventDefault()
							ngDialog.open({
								// TODO - make openConfirm
								template: "/js/mvnApp/app/shared/dialogs/_member-only.html",
								className: "mvndialog",
								showClose: true,
								closeByDocument: true,
								closeByEscape: true
							})
						}
					}
					if ($scope.user.role !== "practitioner" && pracOnly) {
						event.preventDefault()
						ngDialog.open({
							template: "/js/mvnApp/app/shared/dialogs/_practitioner-only.html",
							className: "mvndialog",
							showClose: true,
							closeByDocument: true,
							closeByEscape: true
						})
					}
				} else {
					// if we don't have a user.....
					// we do require authentication
					var loc = UrlHelperService.urlencode($window.location.href)
					event.preventDefault()
					Users.getWithProfile().then(function(u) {
						if (!u) {
							// We don't have an active session, so kick you out to login
							$scope.$broadcast(AUTH_EVENTS.notAuthenticated, loc)
						} else {
							// yay we've go ourselves a session, so let's set our user...
							$scope.user = u
							Session.create()
							$state.transitionTo(toState, toParams)
							// the route is ONLY accessible to an enterprise user or practitioner
							if (toState.data.enterpriseOnly) {
								if (!$scope.user.organization && $scope.user.role !== 'practitioner') { // if this is null then it's false so do something else
									event.preventDefault()
									$window.location.href = "/app/restricted"
									// this is a custom route because we wanted to use the same hmm... message that is for library, but since that hmm... message is a react component we needed it to go through a react route...rather than creating that component in Angular
								}
							}
						}
					})
				}
			}
		})

		// Add body class per page on page change
		$scope.$on("$stateChangeSuccess", function(ev, data) {
			window.scrollTo(0, 0);
			$scope.setPageData(data)
		})

		// MENU
		$rootScope.nav = {
			hideNav: true
		}

		// toggle the value of menu nav.hideNav value.
		$scope.toggle = function() {
			$scope.nav.hideNav = !$scope.nav.hideNav
		}

		// Copyright
		$scope.copyrightYear = new Date().getFullYear()

		/* Global static college subscription price plans... till we figure out the best way of not having this be static :/ */
		$scope.staticPlans = staticPlans

		// Source of entry
		$rootScope.source = $location.$$search.mc_id ? "email" : "directOpen"
	}
])
