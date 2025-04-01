/**
 * @ngdoc function
 * @name PayerUpdatePaymentMethod
 * @description
 * # PayerConfirmEmail
 * Maven Payer email confirmation controller
 */
angular.module("user").controller("PayerUpdatePaymentMethod", [
	"$scope",
	"$state",
	"Users",
	function($scope, $state, Users) {
		var saveNewCC = function(token) {
			Users.getPayerInfo($state.params.email)
				.customPUT({ stripe_token: token, token: $state.params.token })
				.then(
					function(c) {
						$scope.err = false;
						$scope.errorMsg = null;
						$scope.paymentMethodUpdated = true;
					},
					function(e) {
						$scope.err = true;
						$scope.errorMsg = e.data.message;
					}
				);
		};

		var stripeRespHandler = function(status, resp) {
			if (resp.error) {
				$scope.err = true;
				$scope.errorMsg = resp.error.message;
				$scope.loading = false;
				$scope.$apply();
			} else {
				saveNewCC(resp.id);
			}
		};

		var getStripeToken = function(cc) {
			Stripe.card.createToken(
				{
					number: cc.cardNumber,
					cvc: cc.cardCvc,
					exp: cc.cardExpiry
				},
				stripeRespHandler
			);
		};

		$scope.cc = {};

		if (!$state.params.token || !$state.params.email) {
			$scope.invalidCredentials = true;
		} else {
			Users.getPayerInfo($state.params.email)
				.get({ token: $state.params.token })
				.then(
					function(u) {
						$scope.invalidCredentials = false;
						$scope.gotPayer = true;
					},
					function(e) {
						$scope.gotPayer = false;
						$scope.invalidCredentials = true;
						$scope.payerErrorMsg = e.data.message;
					}
				);
		}

		$scope.addNewCard = function(newCard) {
			getStripeToken(newCard);
		};
	}
]);
