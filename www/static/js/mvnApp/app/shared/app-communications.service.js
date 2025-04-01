angular.module('app')
	.factory('Communications', ['$http', ($http) => {
		return {
				smsTheApp: (data) => {
					return $http.post('/api/v1/unauthenticated/sms', data).then(d => {
						return d;
					}, (e) => {
						return e;
					})
				}
		 };
	}]);