angular.module('user')
	.controller('PaymentsCtrl', ['$scope', '$location', '$anchorScroll', '$state', 'Users', 'loadStripe', 'Payments', 'ReferralCodes', 'ngNotify', function($scope, $location, $anchorScroll, $state, Users, loadStripe, Payments, ReferralCodes, ngNotify) {
		
		$scope.loading = true;
		$scope.hasPaymentMethod = false;
		$scope.userCredits = 0;
		$scope.isSubscriber = $scope.user.subscription_plans;
		$scope.isEnterprise = $scope.user.organization;
		$scope.isPractitioner = $scope.user.role === 'practitioner';
		$scope.isMarketplace = !$scope.isPractitioner && !$scope.isSubscriber && !$scope.isEnterprise;
		
		$scope.shouldSeePayments = $scope.isSubscriber || $scope.isMarketplace;
		
		$scope.isEditing = false;

		var evt = {
			"event_name" : "web_user_payments_credits",
			"user_id": $scope.user.id
		};

		$scope.$emit('trk', evt);
		
		$scope.editPayments = function() {
			$scope.isEditing = true;
		}
		
		$scope.lockPayments = function() {
			$scope.isEditing = false;
		}
		
		$scope.cancelEdit = function() {
			$state.reload()
		}
		
		$scope.focusErrors = function() {
			$location.hash('payments-errors')
			$anchorScroll()
		}

		$scope.getUserPaymentMethod = function() {
			Payments.getUserPaymentMethod($scope.user.id).then(function(p) {
				$scope.loading = false;
				
				if (!!p.data[0]) {
					$scope.hasPaymentMethod = true;
					// yeeeah nasty but we only have one payment method allowed right now
					$scope.paymentMethod = p.data[0];
				} else {
					$scope.hasPaymentMethod = false;
				}

			}, function(e) {
				$scope.loading = false;
				$scope.hasPaymentMethod = false;
				$scope.err = true;
				$scope.errorMsg = e;
			})
		}

		$scope.removeUserPaymentMethod = function(user, card) {
			Payments.deleteUserPaymentMethod(user, card).then(function(d) {
				$scope.err = false;
				ngNotify.set('Removed card', 'success');
				$scope.hasPaymentMethod = false;
				$scope.lockPayments()
			}, function(e) {
				$scope.err = true;
				$scope.errorMsg = e.data.message;
			})
		}

		$scope.stripeProcess = function (code, result) {
			if (result.error) {
				$scope.err = true;
				$scope.errorMsg = result.error.message;
			} else {
				Payments.addUserPaymentMethods($scope.user.id,{"stripe_token" : result.id}).then(function(d) {
					$scope.err = false;
					ngNotify.set('Successfully added card!', 'success');
					$scope.getUserPaymentMethod();
					$scope.lockPayments();
				}, function(e) {
					$scope.err = true;
					$scope.errorMsg = e.data.message;
				});
			}
		};

		$scope.getUserCredits = function() {
			Payments.getUserCredits($scope.user.id).then(function(credit) {
				$scope.userCredits = credit.meta.total_credit;
			})
		}

		$scope.addNewReferralCode = function(newCode) {
			ReferralCodes.addCode(newCode).then(function(c) {
				ngNotify.set('Successfully added your code!', 'success');
				$scope.getUserCredits();
				$scope.refCode.referral_code = null;
			}, function(e){
				ngNotify.set(e.data.message, 'error');
			})
		}

		$scope.getUserCredits();
}]);
