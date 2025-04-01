/**
 * @ngdoc function
 * @name UserConfirmEmail
 * @description
 * # UserConfirmCtrl
 * Maven User confirmation controller
 */
angular.module("user").controller("UserConfirmEmail", [
	"$scope",
	"$http",
	"$state",
	function($scope, $http, $state) {
		$http
			.get(
				"/api/v1/users/" +
					encodeURIComponent($state.params.email) +
					"/email_confirm?token=" +
					encodeURIComponent($state.params.token)
			)
			.then(
				function(data) {
					$scope.emailError = false;
					$scope.emailConfirmed = true;
				},
				function(e) {
					$scope.emailConfirmed = false;
					$scope.emailError = true;
					$scope.emailErrorMsg = e.message;
				}
			);
	}
]);
