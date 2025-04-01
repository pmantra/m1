angular.module('app').factory('AppActionsService', [
	'$rootScope',
	'$window',
	'$state',
	'$uiRouterGlobals',
	'ngDialog',
	'ngNotify',
	'Plow',
	'UrlHelperService',
	'Users',
	'Subscriptions',
	function(
		$rootScope,
		$window,
		$state,
		$uiRouterGlobals,
		ngDialog,
		ngNotify,
		Plow,
		UrlHelperService,
		Users,
		Subscriptions
	) {
		var evt

		var _doCustomOb = function(cb) {
			var obVersion = $uiRouterGlobals.params.ob || 'generic'
			ngDialog
				.openConfirm({
					template: '/js/mvnApp/app/user/onboarding/custom/index.html',
					controller: [
						'$scope',
						function($scope) {
							$scope.obVersion = obVersion
							$scope.obStep = {
								step: '1'
							}
							evt = {
								event_name: 'web_ads_onboarding',
								user_id: $rootScope.user.id
							}

							$scope.$emit('trk', evt)

							$scope.goToStep = function(stepId) {
								$scope.obStep.step = stepId
							}
						}
					],
					className: 'dialog-page-overlay ads-onboarding',
					showClose: false,
					closeByDocument: false,
					closeByEscape: false
				})
				.then(function(s) {
					evt = {
						event_name: 'web_ads_complete_onboarding',
						user_id: $rootScope.user.id,
						onboarding_version: obVersion
					}

					Plow.send(evt)
					if (cb) {
						cb()
					}
				})
		}

		var _campusClaim = function() {
			var inviteId = UrlHelperService.getParamValue($window.location.href, 'inviteid')
			if (inviteId) {
				Subscriptions.acceptInvite(inviteId).then(
					function(p) {
						Users.getWithProfile(true).then(function(u) {
							$rootScope.$broadcast('updateUser', u)
							ngDialog.open({
								templateUrl: '/js/mvnApp/app/shared/dialogs/_new-college-subscriber-welcome.html',
								className: 'mvndialog'
							})
							var newParams = angular.copy($uiRouterGlobals.params)
							newParams.doaction = null
							newParams.inviteid = null
							$state.go($state.current, newParams)
						})
					},
					function(e) {
						ngNotify.set(
							'Sorry there seems to have been a problem! (' +
								e.data.message +
								') Please contact support@mavenclinic.com',
							'error'
						)
					}
				)
			} else {
				ngNotify.set(
					'Sorry there seems to have been a problem! Please contact support@mavenclinic.com',
					'error'
				)
			}
		}

		var _claimInvite = function() {
			var inviteId = UrlHelperService.getParamValue($window.location.href, 'inviteid')
			if (inviteId) {
				Users.claimEnterpriseInvite({ invite_id: inviteId }).then(
					function(p) {
						Users.getWithProfile(true).then(function(u) {
							$rootScope.$broadcast('updateUser', u)
							var newParams = angular.copy($uiRouterGlobals.params)
							newParams.doaction = null
							newParams.inviteid = null
							$state.go($state.current, newParams)
						})
					},
					function(e) {
						$state.go('app.dashboard')
						ngNotify.set(
							'Sorry there seems to have been a problem! (' +
								e.data.message +
								') Please contact support@mavenclinic.com',
							'error'
						)
					}
				)
			} else {
				$state.go('app.dashboard')
				ngNotify.set(
					'Sorry there seems to have been a problem! Please contact support@mavenclinic.com',
					'error'
				)
			}
		}

		var _showMessage = function(cb) {
			var theMessage = UrlHelperService.getParamValue($window.location.href, 'msgcontent')
			if (theMessage) {
				// Todo - "error" option vs defaulting
				ngNotify.set(UrlHelperService.urldecode(theMessage), 'success')
			}
		}

		return {
			doAction: function(actionName, cb) {
				if (actionName === 'custom-ob') {
					_doCustomOb(cb)
				} else if (actionName === 'campus-claim') {
					_campusClaim()
				} else if (actionName === 'show-message') {
					_showMessage(cb)
				} else if (actionName === 'claim-invite') {
					// claim enterprise invite
					_claimInvite()
				} else {
					return
				}
			}
		}
	}
])
