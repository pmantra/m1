angular.module("app").directive("mvnToast", [
	"MvnToastService",
	"$state",
	"$timeout",
	function(MvnToastService, $state, $timeout) {
		return {
			scope: {
				opts: "=",
				killToast: "&",
				minimizeToast: "&"
			},
			link: (scope, elm, attrs) => {
				var dismissTimeout, doDismiss // eslint-disable-line no-unused-vars
				scope.opts.type = scope.opts.type || "timed"

				// dismissible toasts shouldn't persist across pages
				if (scope.opts.type === "dismissible" || scope.opts.type === "minimizable") {
					scope.$on("$stateChangeStart", function(e, toState, toParams) {
						e.preventDefault()

						scope.dismissAndGo = () => {
							scope.killToast()
							$state.transitionTo(toState, toParams)
						}

						dismissTimeout = $timeout(scope.dismissAndGo, 50)
						doDismiss = dismissTimeout.then() // eslint-disable-line no-unused-vars
					})
				}

				scope.dismiss = () => {
					scope.killToast()
				}

				scope.minimize = () => {
					scope.minimized = true
					document.getElementsByClassName("mvn-toast")[0].classList.add("toast-minimized")
				}

				scope.tpl = {
					path: "js/mvnApp/app/shared/components/mvn-toasts/templates/" + scope.opts.type + ".html"
				}

				scope.$on("$destroy", () => {
					if (dismissTimeout) {
						$timeout.cancel(dismissTimeout)
					}
				})
			},
			template: '<div ng-include="tpl.path"></div>'
		}
	}
])
