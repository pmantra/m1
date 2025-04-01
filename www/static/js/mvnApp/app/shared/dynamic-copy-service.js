angular.module('mavenApp')
	.factory('DynamicCopy', ['$http', function($http) {

		return {
				getHomeTips: function() {
					return $http.get('/_app_support/home-tips.json');
				},

				getEnterprisePhaseContent: function(phaseContentPath) {
					return $http.get(phaseContentPath);
				},

				getLifeStages: function() {
					return $http.get('/_app_support/enterprise/life-stages.json');
				},

				getProducts: function() {
					return $http.get('/_app_support/products/breastmilk-shipping-products.json');
				},

		 };
	}]);

