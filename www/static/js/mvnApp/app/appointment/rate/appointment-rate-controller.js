angular.module('appointment')
	.controller('AppointmentRateCtrl', ['$scope', '$rootScope', '$state', 'ngNotify', 'appt', 'Appointments', function($scope, $rootScope, $state, ngNotify, appt, Appointments) {
	
		$scope.apptToRate = appt;
		$scope.ratings = {};
		$scope.ratings.reliability = "0";
		$scope.ratings.satisfaction = "0";
		$scope.ratings.empathy = "0";
		$scope.ratings.credibility = "0";

		$scope.submitFeedback = function() {
			Appointments.updateAppointment($scope.apptToRate.id, { "ratings" :  $scope.ratings }).then(function(a) {
				ngNotify.set('Thanks for your feedback!', 'success');
				$state.go('app.appointment.my.list.appointment-detail', { "appointment_id" : $scope.apptToRate.id}, {reload: true});
			}, function(e) {
				ngNotify.set(e.data.message, 'error');
			});
		}

	}]);