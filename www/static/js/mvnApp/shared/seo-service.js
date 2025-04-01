angular.module('app').factory('SeoService', ['$rootScope',  function($rootScope) {

	var seoService = {};
	
		seoService.setPageTitle= function(data) {
			$rootScope.$broadcast('setPageTitle', data);
		};

		return seoService;
}])