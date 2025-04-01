"use strict"

/**
 * @ngdoc function
 * @name mavenApp.controller:AuthCtrl
 * @description
 * # AuthCtrl
 * Maven login controller
 */
angular.module("auth").controller("AuthCtrl", [
	"$scope",
	"$rootScope",
	"$window",
	"$state",
	"AuthService",
	"UrlHelperService",
	"Subscriptions",
	"MvnStorage",
	"MarketingUtils",
	"NATIVE_PLATFORM",
	"Plow",
	"Users",
	function(
		$scope,
		$rootScope,
		$window,
		$state,
		AuthService,
		UrlHelperService,
		Subscriptions,
		MvnStorage,
		MarketingUtils,
		NATIVE_PLATFORM,
		Plow,
		Users
	) {
		var evt,
			hasRedirectPath = $state.params.from ? true : false

		const redirectToUrl = hasRedirectPath && UrlHelperService.isValidFromPath($state.params.from)

		const platform = NATIVE_PLATFORM || "web"
		evt = {
			event_name: `${platform}_loginScreen`,
			user_id: $scope.user ? String($scope.user.id) : '',
			source: $rootScope.source
			}
		Plow.send(evt)

		if (!$scope.user) MarketingUtils.promoteApp()

		$scope.loginForm = {}
		$scope.errorMsg = false

		$scope.postAuthParams = $state.params

		var _reloadAndGoTo = function(newPath) {
			newPath = newPath ? newPath : "/app/dashboard"
			$window.location.href = newPath
		}

		var _postLogin = function(postLoginOptions) {
			if (postLoginOptions.campusInviteId) {
				_claimPlanInvite(postLoginOptions.campusInviteId)
			} else {
				if (postLoginOptions.doRedirect) {
					//if (postLoginOptions.redirectPath) {
					_reloadAndGoTo(postLoginOptions.redirectPath)
					//}
				} else {
					if (postLoginOptions.persistData) {
						//save to cookie
						_setDataToPersist(postLoginOptions.persistData)
						//on create post / create reply page, check for cookie data and populate fields w info on load. THEN, delete cookie.
					}
					_reloadAndGoTo($window.location.href)
				}
			}
		}

		var _claimPlanInvite = function(inviteId) {
			Subscriptions.acceptInvite(inviteId).then(
				function(p) {
					var newRedirect = UrlHelperService.appendParam("/app/dashboard", "doaction", "campus-claim")
					_reloadAndGoTo(newRedirect)
				},
				function(e) {
					//TODO - test
					var newRedirect = UrlHelperService.appendParam("/app/dashboard", "doaction", "show-message")
					newRedirect = UrlHelperService.appendParam(newRedirect, "msgcontent", e.data.message)
					_reloadAndGoTo(newRedirect)
				}
			)
		}

		var _setDataToPersist = function(theData) {
			if (theData.type && theData.content) {
				MvnStorage.setItem("session", theData.type, JSON.stringify(theData.content))
			} else {
				return
			}
		}

		$scope.login = function(credentials, redir, persistData) {
			var postLoginOptions = {
				doRedirect: redir,
				redirectPath: redirectToUrl,
				campusInviteId: $rootScope.invite_id,
				persistData: persistData
			}

			AuthService.login(credentials).then(
				function(resp) {
					$scope.errorMsg = false
					Users.getWithProfile().then(function(u) {
						evt = {
							event_name: `${platform}_loginSuccessful`,
							user_id: String(u.id),
							source: $rootScope.source
						}
						Plow.send(evt)
						_postLogin(postLoginOptions)
					})
				},
				function(err) {
					$scope.errorMsg = true
					$scope.err = err.data
				}
			)
		}

		$scope.$on("$stateChangeSuccess", function(event, currRoute, prevRoute) {
			$scope.uid = $scope.user ? $scope.user.id : undefined

			if (!!currRoute.trk_event) {
				var trackEv = currRoute.trk_event ? currRoute.trk_event : currRoute.url
				evt = {
					event_name: trackEv,
					user_id: String($scope.uid)
				}
				$scope.$emit("trk", evt)
			}
		})
	}
])
