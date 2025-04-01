/*
 *
 *
 * Configuration and routes for Auth
 *
 *
 */

angular.module("auth").config([
	"$stateProvider",
	function ($stateProvider) {
		$stateProvider
			.state("auth", {
				templateUrl: "/js/mvnApp/app/auth/shared/auth.html",
				data: {
					noAuth: true
				},
				title:
					"Welcome to Maven – healthcare designed exclusively for women. Video appointments with MDs, Nurses and Pregnancy specialists, all from your mobile device.",
				meta:
					"With Maven, book video appointments with doctors, nurses, pregnancy specialists, nutritionists, lactation consultants and other women's health experts – all via your iPhone."
			})
			.state("auth.welcome", {
				url: "/welcome",
				templateUrl: "js/mvnApp/public/welcome/index.html",
				trk_event: "welcome",
				controller: "WelcomeCtrl",
				bodyClass: "base login-reg",
				data: {
					noAuth: true
				},
				resolve: {
					userService: [
						"Users",
						function (Users) {
							return Users
						}
					],
					user: [
						"$rootScope",
						"$state",
						"userService",
						"AUTH_EVENTS",
						function ($rootScope, $state, userService, AUTH_EVENTS) {
							userService.getWithProfile().then(
								function (u) {
									if (u) {
										$rootScope.$broadcast(AUTH_EVENTS.loginNotNeeded)
									} else {
										return
									}
								},
								function () {
									//return false;
								}
							)
						}
					]
				}
			})
			.state("auth.login", {
				url: "/login",
				params: {
					from: {
						value: null
					}
				},
				react: true
			})
			.state("auth.locallogin", {
				url: "/locallogin?from&plan_invite_id&rg_header&rg_subhead&employee",
				params: {
					from: {
						value: null
					}
				},
				react: true,
				reactUrl: '/login'
			})
			.state("auth.register", {
				url: "/register",
				params: {
					from: {
						value: null
					}
				},
				react: true
			})
			.state("auth.localregister", {
				url:
					"/localregister?install_source&install_campaign&install_content&install_ad_unit&plan_invite_id&rg_header&rg_subhead&ref_code&from&employee&claiminvite&verify&isemp&org&ref&invite_id&inviting_user",
				params: {
					from: {
						value: null
					}
				},
				react: true,
				reactUrl: '/register'
			})

			.state("auth.forgot", {
				url: "/forgot-password",
				templateUrl: "js/mvnApp/app/auth/forgot/index.html",
				bodyClass: "base login-reg",
				title: "Forgot your password?",
				controller: "UserForgotPassword",
				trk_event: "forgot-password",
				data: {
					noAuth: true
				},
				react: true
			})
			.state("auth.reset", {
				url: "/reset_password/:email/:reset_token",
				resolve: {
					itemsResult: [
						"$stateParams", "UrlHelperService",
						($stateParams, UrlHelperService) => {
							UrlHelperService.redirectToReact(
								`/app/reset_password/${$stateParams.email}/${$stateParams.reset_token}`
							)
							return true
						}
					]
				}
			})

			.state("auth.confirm_email", {
				url: "/confirm_email?token&email",
				templateUrl: "js/mvnApp/app/user/confirm/index.html",
				bodyClass: "base login-reg",
				title: "Confirm your email",
				controller: "UserConfirmEmail",
				data: {
					noAuth: true
				}
			})
			.state("auth.logout", {
				url: "/logout",
				templateUrl: "js/mvnApp/app/auth/logout/index.html",
				data: {
					noAuth: true
				}
			})

			/* Confirm email for subscription payer */
			.state("auth.confirm_payer_email", {
				url: "/confirm_payer_email/:email/:token",
				templateUrl: "js/mvnApp/app/user/payer/confirm/index.html",
				bodyClass: "base login-reg",
				controller: "PayerConfirmEmail",
				data: {
					noAuth: true
				}
			})

			.state("auth.update_payer_payment_method", {
				url: "/update_payer_payment_method/:email/:token",
				templateUrl: "js/mvnApp/app/user/payer/update-payment/index.html",
				bodyClass: "base login-reg",
				controller: "PayerUpdatePaymentMethod",
				data: {
					noAuth: true
				},
				resolve: {
					loadStripe: [
						"$ocLazyLoad",
						"$injector",
						"$window",
						"config",
						function ($ocLazyLoad, $injector, $window, config) {
							//lulz hacky... but this makes ocLazyLoader think this is a .js file (as it thinks js.stripe.com/v2/ is a directory otherwise) :) gz @zach
							return $ocLazyLoad.load("https://js.stripe.com/v2/#mvn.js").then(function () {
								$window.Stripe.setPublishableKey(config.stripe_publishable_key)
							})
						}
					]
				}
			})
	}
])
