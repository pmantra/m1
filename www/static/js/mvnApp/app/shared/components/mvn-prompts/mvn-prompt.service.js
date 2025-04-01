angular.module("app").factory("MvnPromptService", function($rootScope, Restangular, ngDialog, ngNotify, Users) {
	const getPrompt = userId => Restangular.one(`users/${userId}/prompt`).get()

	const showPrompt = (uid, promptData, onClose, dismissAction = null) => {
		let $newScope = $rootScope.$new(true)
		$newScope.data = promptData
		$newScope.cardType = $newScope.data.type
		$newScope.dismissAction = dismissAction
		return ngDialog
			.openConfirm({
				templateUrl: "/js/mvnApp/app/shared/components/mvn-prompts/_prompt.html",
				showClose: false,
				closeByDocument: false,
				closeByEscape: false,
				scope: $newScope,
				className:
					$newScope.data.style === "fullscreen"
						? "dialog-full dialog-page-overlay prompt-fullscreen"
						: "mvndialog carddialog",
				controller: [
					"$scope",
					function($scope) {
						// - actionCallback is a function we pass through our templates (ugh) into the mvnDynamicCta directive.
						// - The mvnDynamicCta directive calls this function (optionally - currently only used by "dismiss" && "program-transition" action types)
						// - This also exists dashboard blocks component (/app/dashboard/enterprise/blocks/dashboard-block.component.js)
						// - We want actionCallback to be optional and contextual (so we can do different things based on where the mvnDynamicCta exists). Here, we call the onClose callback, with optional param to reload the dashboard, passed in from enterprise dashboard component.
						$scope.actionCallback = () => {
							$scope.$destroy()
							let refreshDash = $scope.data.actions
								.filter(d => d.type === `program-transition`)
								.filter(a => a.subject.destination === `commit-transition`)[0]
								? true
								: false
							onClose(refreshDash)
						}
						$scope.hidePrompt = () => {
							$scope.$destroy()
							ngDialog.closeAll()
						}

						$scope.dismissCard = dismissAction => {
							if (dismissAction.type === "dismiss") {
								Users.dismissCard(uid, dismissAction.subject).then(
									d => {
										$scope.actionCallback()
									},
									e => {
										console.log("Error dismissing card...", e)
									}
								)
							} else if (dismissAction.type === "program-transition") {
								Users.updateUserPrograms(uid, dismissAction.subject).then(
									u => {
										$scope.callActionCallback()
									},
									e => {
										ngNotify.set(e.message, "error")
										console.log("Error with program transition...", e)
									}
								)
							} else {
								$scope.actionCallback()
							}
						}
					}
				]
			})
			.then(function(v) {
				getPrompt(uid)
			})
	}

	return {
		getPrompt,
		showPrompt
	}
})
