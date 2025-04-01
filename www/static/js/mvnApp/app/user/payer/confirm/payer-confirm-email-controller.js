/**
 * @ngdoc function
 * @name PayerConfirmEmail
 * @description
 * # PayerConfirmEmail
 * Maven Payer email confirmation controller
 */
angular.module("user").controller("PayerConfirmEmail", [
	"$scope",
	"$state",
	"Users",
	function($scope, $state, Users) {
		if (!$state.params.token || !$state.params.email) {
			$scope.hideForm = true;
			$scope.errorMsg = true;
		} else {
			Users.confirmPayerEmail($state.params.email)
				.get({ token: $state.params.token })
				.then(
					function(u) {
						$scope.emailError = false;
						$scope.emailConfirmed = true;
					},
					function(e) {
						$scope.emailConfirmed = false;
						if (e.status === 409) {
							$scope.alreadyConfirmed = true;
						} else {
							$scope.emailError = true;
							$scope.emailErrorMsg = e.data.message;
						}
					}
				);
		}
	}
]);
