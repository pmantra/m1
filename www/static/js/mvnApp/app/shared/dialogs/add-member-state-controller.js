angular.module('practitioner')
	.controller('AddMemberStateCtrl', ['$scope', 'ngDialog', 'ngNotify', 'Users', 'AppUtils', function ($scope, ngDialog, ngNotify, Users, AppUtils) {
		$scope.userStateForm = {"state" : undefined};

		$scope.states = AppUtils.availableStates;
		// clicking the "save" button triggers the ngDialog "close" method
		$scope.$on('ngDialog.closing', function(e, dialog) {
			$scope.updateProfile($scope.userStateForm)
		})

		$scope.updateProfile = function(userState) {
			
			var profileUpdatePromise = Users.updateUserProfile($scope.user.id,userState);
			
			profileUpdatePromise.then(function(resp) {

				var evt = {
					"event_name" : "user_profile_add_state",
				};
				$scope.$emit('trk', evt);
				
			}, function(err) {
				ngNotify(err.message, 'error');
				return false;
			});
		}

	}]);