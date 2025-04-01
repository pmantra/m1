angular.module('publicpages')
	.factory('Unauthenticated', ['$http', function($http) {
		
		return {
				
				buyPackage: function(pkg) {
					return $http.post('/api/v1/unauthenticated/gifting', pkg).then(function(t) {
						return t;
					}, function(e) {
						return e;
					})
				}
		 };
	}]);