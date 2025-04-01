angular.module('app')
	.factory('Subscriptions', ['Restangular', 'noSession', function(Restangular, noSession) {

		var plans =  Restangular.service('subscription_plans');

		return {
			// /subscription_plans
			getAvailablePlans: function() {
				return plans;
			},
			// /subscription_plans/user_info
			getPurchasingUser: function(user_id) {
				return Restangular.one('subscription_plans/user_info');
			}, 

			// Purchase for self using encoded_user_id (not authenticated, so use non-ajax endpoint)
			purchasePlan: function(data) {
				return noSession.one('/subscription_plans/purchases').customPOST(data);
			},

			// Purchase for self with active session
			purchasePlanWithAuth: function(data) {
				return Restangular.one('/subscription_plans/purchases').customPOST(data);
			},

			// Purchase plan for someone else
			purchasePlanForUser: function(data) {
				return noSession.one('/subscription_plans/payers').customPOST(data);
			}, 

			acceptInvite: function(invite_id) {
				return Restangular.one('/subscription_plans/purchases').customPOST({"plan_invite_id": invite_id});
			}
		};
	}]);
