/**
 * @ngdoc function
 * @description
 * Maven Pharmacy Service
 */
angular.module('appointment')
	.factory('Pharmacy', ['Restangular', function(Restangular) {

		var pharmacyService = {};

		var searchPharmacy = function (apptId, zip, pharmacy_name) {
			var req = {
				'zip_code' : zip
			}
			
			if (pharmacy_name) {
				req.pharmacy_name = pharmacy_name;
			}

			return Restangular.one('/prescriptions/pharmacy_search/', apptId).get(req);
		}
		// /prescriptions/pharmacy_search/{appointment_id}?{zip_code, pharmacy_name} 

		pharmacyService.searchPharmacy = searchPharmacy;

		return pharmacyService;

	}]);
