/* Message channel list  - individual entry */
angular.module("publicpages").directive("planPurchase", [
	"$window",
	"$rootScope",
	"Subscriptions",
	"Payments",
	"ngNotify",
	"Users",
	function($window, $rootScope, Subscriptions, Payments, ngNotify, Users) {
		return {
			restrict: "E",
			scope: {
				buyingForSelf: "=",
				availablePlans: "=",
				purchasingUser: "=",
				planId: "=",
				purchaseSource: "@",
				loading: "="
			},
			translude: true,
			link: function(scope, element, attrs) {
				var evt,
					installParams = JSON.parse(localStorage.getItem("mvnInst")),
					installAttrs = installParams ? installParams : {}

				// Set up our purchase object...
				scope.purchase = {}
				scope.purchase.availableCredits = 0

				// If we have a plan ID and it exists within our list of available plans, select it. Otherwise just grab the first one...
				scope.purchase.selectedPlan =
					scope.planId &&
					_.find(scope.availablePlans, function(plan) {
						return plan.id == scope.planId
					})
						? _.find(scope.availablePlans, function(plan) {
								return plan.id == scope.planId
						  })
						: scope.availablePlans[1] /// hmmmmmmmm hackyyyyy/dangerousss

				// IF WE HAVE A PURCHASINGUSER
				if (scope.purchasingUser) {
					// Prepopulate/use our purchasing user's email address

					scope.purchase.userEmail = scope.purchasingUser.email

					if (scope.purchasingUser.is_auth && !scope.buyingForSelf) {
						scope.buyingForSelf = true
					}

					// See if we already have a credit card on file
					if (scope.purchasingUser.stripe_token && scope.buyingForSelf) {
						scope.purchase.hasPaymentMethod = true
					}

					// Apply any available credits
					scope.purchase.availableCredits += parseFloat(scope.purchasingUser.available_credits)

					evt = {
						event_name: "web.app:campus_purchase:purchase_form",
						user_id: $rootScope.user ? $rootScope.user.id : null,
						purchase_source: scope.purchaseSource,
						purchase_available_credits: scope.purchase.availableCredits,
						buying_for_self: scope.buyingForSelf
					}
					scope.$emit("trk", evt)
				} else {
					scope.purchase.userEmail = null
					scope.purchase.payerEmail = null

					evt = {
						event_name: "web.app:campus_purchase:purchase_form",
						purchase_source: scope.purchaseSource
					}
					scope.$emit("trk", evt)
				}

				// If we have the buyingForSelf param BUT no purchasing user info, assume this is being bought for someone else. LATER: ask who you're buying for?
				if (scope.buyingForSelf && !scope.purchasingUser) {
					scope.buyingForSelf = false
				}

				/* Handle processing new card */

				var stripeRespHandler = function(status, resp) {
					if (resp.error) {
						scope.err = true
						scope.errorMsg = resp.error.message
						scope.loading = false
						scope.$apply()
					} else {
						scope.token = resp.id
						scope.doPurchase()
					}
				}

				var getStripeToken = function() {
					Stripe.card.createToken(
						{
							number: scope.purchase.cardNumber,
							cvc: scope.purchase.cardCvc,
							exp: scope.purchase.cardExpiry
						},
						stripeRespHandler
					)
				}

				/* ---- Different purchase endpoints depending on who is purchasing... ---*/

				/* Purchase for self with no active session, just encoded_user_id */
				var purchaseForSelf = function(req) {
					Subscriptions.purchasePlan(req).then(
						function(p) {
							scope.loading = false
							scope.purchaseComplete = true
							scope.activeSubscription = p

							evt = {
								event_name: "web.app:campus_purchase:purchase_complete",
								purchase_source: scope.purchaseSource
							}
							scope.$emit("trk", evt)
						},
						function(e) {
							scope.err = true
							scope.errorMsg = e.data.message
							scope.loading = false
						}
					)
				}

				/* Purchase for self if we have an active session */
				var purchaseForSelfWithAuth = function(req) {
					Subscriptions.purchasePlanWithAuth(req).then(
						function(p) {
							scope.loading = false
							scope.purchaseComplete = true
							scope.activeSubscription = p

							evt = {
								event_name: "web.app:campus_purchase:purchase_complete",
								user_id: $rootScope.user ? $rootScope.user.id : null,
								purchase_source: scope.purchaseSource
							}
							scope.$emit("trk", evt)
						},
						function(e) {
							scope.err = true
							scope.errorMsg = e.data.message
							scope.loading = false
						}
					)
				}

				/* Purchase for someone else */
				var purchaseForUser = function(req) {
					Subscriptions.purchasePlanForUser(req).then(
						function(p) {
							scope.loading = false
							scope.purchaseComplete = true
							scope.activeSubscription = p

							evt = {
								event_name: "web.app:campus_purchase:purchase_complete",
								purchase_source: scope.purchaseSource
							}
							scope.$emit("trk", evt)
						},
						function(e) {
							scope.err = true
							scope.errorMsg = e.data.message
							scope.loading = false
						}
					)
				}

				/* Toggle plan */
				scope.selectPlan = function(plan) {
					scope.purchase.selectedPlan = plan
				}

				/* Add referral code */
				scope.addNewReferralCode = function(refCode) {
					scope.addingCode = true
					var req = {
						referral_code: refCode
					}
					if (scope.purchasingUser && scope.purchasingUser.encoded_user_id) {
						req.encoded_user_id = scope.purchasingUser.encoded_user_id
					}

					Payments.getCreditInfo(req).then(
						function(c) {
							ngNotify.set("Successfully applied $" + c.value + " credit", "success")
							scope.addingCode = false
							scope.purchase.availableCredits += c.value
							evt = {
								event_name: "web.app:campus_purchase:applied_referral_code",
								purchase_source: scope.purchaseSource,
								referral_code: refCode
							}
							scope.$emit("trk", evt)
						},
						function(e) {
							scope.addingCode = false
							scope.purchase.referralCode = null
							ngNotify.set("Oh no, that code is invalid! (" + e.data.message + ")", "error")
						}
					)
				}

				/* Let's go buy it! */

				scope.initPurchase = function() {
					scope.loading = true
					// If we don't have a payment method already, assume we've just added card, so process w stripe and grab the token
					if (!scope.purchase.hasPaymentMethod) {
						getStripeToken()
					} else {
						scope.doPurchase()
					}
				}

				scope.doPurchase = function() {
					var baseReq = {
							plan_id: scope.purchase.selectedPlan.id
						},
						req = _.extend(baseReq, installAttrs)

					// if we have a token bc we've just added a card, append this token to the request object.
					if (scope.token) {
						req.stripe_token = scope.token
					}

					if (scope.purchase.referralCode) {
						req.referral_code = scope.purchase.referralCode
					}

					// BUYING FOR SELF
					if (scope.buyingForSelf) {
						if (scope.purchasingUser) {
							// if our user is authenticated, we  want to use the authenticated endpoint and only need to send the plan ID (and optionally referral code)
							if (scope.purchasingUser.is_auth) {
								purchaseForSelfWithAuth(req)
							} else {
								// if we're not authenticated, use the unauth non-ajax endpoint and make sure we send the encoded_user_id
								req.encoded_user_id = scope.purchasingUser.encoded_user_id
								purchaseForSelf(req)
							}
						}

						// REFERRAL PURCHASE
					} else {
						req.email_address = scope.purchase.payerEmailAddress
						// If we've been invited by a student, send their encoded id with the request
						if (scope.purchasingUser && scope.purchasingUser.encoded_user_id) {
							req.encoded_user_id = scope.purchasingUser.encoded_user_id
						} else {
							req.for_email_address = scope.purchase.forEmailAddress
						}
						purchaseForUser(req)
					}
				}

				scope.iOSTerms = function() {
					if ($window.messageHandlers) {
						$window.messageHandlers.notification.postMessage("openTerms")
					} else {
						alert(
							"Sorry there seems to have been a problem! Please contact support@mavenclinic.com or try force-quiting and reopening your app."
						)
					}
				}

				scope.webAppFinish = function() {
					Users.getWithProfile(true).then(
						function(u) {
							if (u) {
								$window.location.href = "/app/dashboard"
							} else {
								ngNotify.set(
									"Sorry there seems to have been a problem, please contact support@mavenclinic.com",
									"error"
								)
								return
							}
						},
						function(e) {
							ngNotify.set(
								"Sorry there seems to have been a problem" +
									e.data.message +
									", please contact support@mavenclinic.com",
								"error"
							)
							console.log(e)
						}
					)
				}

				scope.iosFinish = function() {
					if ($window.messageHandlers) {
						$window.messageHandlers.notification.postMessage("finished")
					} else {
						alert(
							"Sorry there seems to have been a problem! Please contact support@mavenclinic.com or try force-quiting and reopening your app."
						)
					}
				}

				scope.backToIOS = function() {
					if ($window.messageHandlers) {
						$window.messageHandlers.notification.postMessage("back")
					} else {
						alert(
							"Sorry there seems to have been a problem! Please contact support@mavenclinic.com or try force-quiting and reopening your app."
						)
					}
				}
			},
			templateUrl: "/js/mvnApp/public/plan-purchase/_plan-purchase.html"
		}
	}
])
