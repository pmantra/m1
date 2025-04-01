/**
 * @ngdoc function
 * @name ReferralCodes service
 * @description
 * # ReferralCodesService
 * Maven ReferralCodes service
 */
angular.module('app')
	.factory('ReferralCodes', ['Restangular', function(Restangular) {
		
		return {
				addCode: function(ref) {
					return Restangular.one('referral_code_uses').customPOST({"referral_code" :ref});
				},
				getUserCode: function(uid) {
					return Restangular.one('referral_codes').get({ "owner" : uid});
				}
		 };
	}]);
