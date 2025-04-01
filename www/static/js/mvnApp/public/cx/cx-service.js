/**
 * CX controller
 */

angular.module('publicpages').factory('Cx', ['$http', function($http) {

		var cxService = {};

		cxService.setOverflow = function(token, report) {
			var params = {
				token: token,
				report: report
			}
			return $http.post('/api/v1/overflow_report', params).then(function(resp) {
				return resp;
			})
		};

		return cxService;
}])