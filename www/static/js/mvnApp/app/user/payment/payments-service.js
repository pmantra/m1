/**
 * @ngdoc function
 * @name Payments service
 * @description
 * # PaymentsService
 * Maven Payments service
 */
angular.module('app')
	.factory('Payments', ['Restangular', function(Restangular) {
		
		return {
				addUserPaymentMethods: function(uid, token) {
					return Restangular.one('users').customPOST(token, uid + '/payment_methods');
				},
				getUserPaymentMethod: function(uid) {
					return Restangular.one('users').customGET(uid + '/payment_methods');
				},
				deleteUserPaymentMethod: function(uid, card) {
					return Restangular.one('users').customDELETE(uid + '/payment_methods/' + card);
				},
				getUserCredits: function (uid) {
					return Restangular.one('users').customGET(uid + '/credits');
				},
				getCreditInfo: function(req) {
					return Restangular.one('referral_code_info').get(req);
				}
		 };
	}]);
