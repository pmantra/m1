/**
 * @ngdoc overview
 * @name App controller
 * @description
 * # AppCtrl
 *
 * App controller
 */

angular.module("app").controller("AppCtrl", [
	"$window",
	"$scope",
	"$state",
	"$interval",
	"ModalService",
	"Users",
	"Messages",
	"UrlHelperService",
	"AppActionsService",
	"NATIVE_PLATFORM",
	function (
		$window,
		$scope,
		$state,
		$interval,
		ModalService,
		Users,
		Messages,
		UrlHelperService,
		AppActionsService,
		NATIVE_PLATFORM
	) {
		var msgListener

		$scope.unreadMessages = 0

		$scope.uid = $scope.user ? $scope.user.id : undefined

		if (NATIVE_PLATFORM) {
			$scope.hideNav = true
		}

		// User agreements update modal
		if ($scope.user && $scope.user.pending_agreements && $scope.user.pending_agreements.length > 0) {
			const onClose = () => {
				Users.getWithProfile(true).then(u => {
					$scope.setUser(u)
				})
			}
			const pendingAgreements = $scope.user.pending_agreements

			ModalService.agreementsUpdateModal(pendingAgreements, onClose)
		}

		$scope.$on("$stateChangeSuccess", function (event, currRoute, prevRoute) {
			if (!!currRoute.trk_event) {
				var trackEv = currRoute.trk_event ? currRoute.trk_event : currRoute.url
				var evt = {
					event_name: trackEv,
					user_id: String($scope.uid)
				}
				$scope.$emit("trk", evt)
			}

			angular.element(function () {
				if (document.getElementsByTagName("body")[0] !== null) {
					document.getElementsByTagName("body")[0].focus()
				}
			})
		})

		// a11y support for ngNotify
		const ngnEl = document.getElementsByClassName("ngn")[0]
		if (ngnEl) {
			ngnEl.setAttribute("role", "alert")
			ngnEl.setAttribute("aria-live", "assertive")
		}

		// if we have any post-login/load actions in the url, go do them
		if (UrlHelperService.getParamValue($window.location.href, "doaction")) {
			var cb = function () {
				var newParams = angular.copy($state.params)
				newParams.doaction = null
				$state.go($state.current, newParams)
			}
			AppActionsService.doAction(UrlHelperService.getParamValue($window.location.href, "doaction"), cb)
		}

		/* Date formatting for practitioner list view */
		moment.locale("en", {
			calendar: {
				lastDay: "[Yesterday at] LT",
				sameDay: "[Today from] LT",
				nextDay: "[Tomorrow from] LT",
				lastWeek: "[last] dddd [from] LT",
				nextWeek: "dddd [from] LT",
				sameElse: "L"
			}
		})

		if ($scope.user) {
			if (
				$scope.user.role !== "practitioner" ||
				($scope.user.role === "practitioner" && $scope.user.profiles.practitioner.messaging_enabled)
			) {
				$scope.checkForNewMessages = function () {
					Messages.getUnreadCount().then(function (c) {
						if (c !== $scope.unreadMessages) {
							$scope.unreadMessages = c
						}
					})
				}

				/* Check for new messages at interval ... currently every 30mins*/
				msgListener = $interval($scope.checkForNewMessages, 1800000)

				/* check on first load */
				$scope.checkForNewMessages()

				// kill our interval when we destroy the scope
				$scope.$on("$destroy", function () {
					$interval.cancel(msgListener)
				})

				// kill the interval if our session expires
				$scope.$on("forceLogin", function () {
					$interval.cancel(msgListener)
				})
			}
		}
	}
])
