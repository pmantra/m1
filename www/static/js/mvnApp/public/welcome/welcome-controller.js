/**
 * @ngdoc function
 * @name forum.controller:WelcomeCtrl
 * @description
 * # WelcomeCtrl
 * Maven Welcome controller
 */
angular.module('app')
	.controller('WelcomeCtrl', ['$scope', '$state', function($scope, $state) {

		var evt = {
			"event_name": "welcome"
		};

		$scope.$emit('trk', evt);

		$scope.selection = 'account-select';

		$scope.switchState = function(s) {
			$scope.selection = s;
			evt = {
				"event_name": "welcome_" + s
			};

			$scope.$emit('trk', evt);
		}

	}]);