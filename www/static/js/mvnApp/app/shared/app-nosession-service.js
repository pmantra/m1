angular.module('mavenApp').factory('noSession', function(Restangular) {
	return Restangular.withConfig(function(RestangularConfigurer) {
		RestangularConfigurer.setBaseUrl('/api/v1/');
	});
});