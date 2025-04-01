angular.module('practitioner')
	.factory('Practitioners', ['Restangular', function(Restangular) {

		var allPractitioners =  Restangular.service('practitioners');
		
		return {
				getPractitioner: function(id) {
					return Restangular.one('practitioners').customGET('', {"user_ids" : id});
				},
				getPractitioners: function() {
					return allPractitioners;
				},
				notifyOfAvailability: function() {
					// /practitioner_availability_notifications
					return Restangular.one('/practitioner_availability_notifications');

				}
		 };
	}]);

