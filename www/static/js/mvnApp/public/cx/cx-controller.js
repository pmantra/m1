/**
 * CX controller
 */

angular.module('publicpages')
	.controller('CxCtrl', ['$scope', '$state', 'Cx', function($scope, $state, Cx) {
		var theToken = $state.params.token,
			theReport = $state.params.report;

		$scope.loading = true;

		if (!!(theToken) && !!(theReport)) {
			Cx.setOverflow(theToken, theReport).then(function(s) {
				$scope.loading = false;
				if (theReport == 'YES') {
					$scope.reportYes = true;
				} else {
					$scope.reportNo = true;
				}
				
			}, function(e) {
				$scope.loading = false;
				$scope.err = true;
				$scope.errMsg = e.data.message;
			});
		} else {
			$scope.loading = false;
			$scope.err = true;
		}
	}]);
