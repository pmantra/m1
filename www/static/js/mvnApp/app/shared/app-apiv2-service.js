angular.module('mavenApp').factory('v2Api', ['Restangular', 'APIKEY', function(Restangular, APIKEY) {
	return Restangular.withConfig(function(RestangularConfigurer) {
		if (APIKEY) {
			RestangularConfigurer.setBaseUrl('/api/v2/');
		} else {
			RestangularConfigurer.setBaseUrl('/ajax/api/v2/');
		}
	});
}]);