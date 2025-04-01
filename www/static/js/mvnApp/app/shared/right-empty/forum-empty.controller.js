/**
 * Forum empty right panel
 */
angular.module("app").controller("RightPanelEmpty", [
	"$scope",
	"$state",
	"Categories",
	function($scope, $state, Categories) {
		if (!!$state.params.community) {
			$scope.emptyCat = Categories.currentCat(
				$state.params.community,
				$scope.cats
			);
		} else {
			if ($state.current.name === "app.practitioner-list.view") {
				$scope.emptyCat = {
					name: "practitioners"
				};
			}
			if ($state.current.name === "app.appointment.my.list") {
				$scope.emptyCat = {
					name: "my-appointments"
				};
			}

			if ($state.current.name === "app.messages-list.view") {
				$scope.emptyCat = {
					name: "messages"
				};
			}
		}
	}
]);
