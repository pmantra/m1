/* Shared Plan Purchase controller.
	Used by:
		Marketing site upsell
		iOS webview
		WebApp purchase
*/

angular.module('publicpages').controller("PlanPurchaseCtrl", ['$rootScope', '$scope', 'available_plans', 'purchasing_user', 'purchase_for_self', 'plan_id', function($rootScope, $scope, available_plans, purchasing_user, purchase_for_self, plan_id) {
	//SET SHIT UP
	$scope.purchase = {};
	$scope.purchase.availablePlans = available_plans;
	if (purchasing_user) {
		$scope.purchase.purchasingUser = purchasing_user;
	}
	if (purchase_for_self) {
		$scope.purchase.buyingForSelf = purchase_for_self;
	}
	if (plan_id) {
		$scope.purchase.planId = plan_id;
	} else {
		$scope.purchase.planId = available_plans[0].id;
	}

}]);