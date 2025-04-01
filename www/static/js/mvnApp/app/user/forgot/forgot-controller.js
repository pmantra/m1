/**
 * @ngdoc function
 * @name UserForgotPassword
 * @description
 * # UserForgotPassword
 * Maven User password reset controller
 */
angular.module("user").controller("UserForgotPassword", [
	"$scope",
	"$http",
	function($scope, $http) {
		$scope.forgotForm = {};
		$scope.errorMsg = false;

		//TODO: move to service
		$scope.resetpw = function(user) {
			$http
				.get("/api/v1/users/" + $scope.forgotForm.email + "/password_reset")
				.then(
					function(data) {
						$scope.errorMsg = false;
						$scope.success = true;
					},
					function(e) {
						$scope.errorMsg = true;
						$scope.err = e.message;
					}
				);
		};
	}
]);
