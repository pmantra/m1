/*
 *
 *
 * Configuration and routes for Public pages
 *
 *
 */

angular.module("publicpages").config([
	"$stateProvider",
	"$locationProvider",
	function ($stateProvider, $locationProvider) {
		$stateProvider

			.state("public.home", {
				url: "/?r&install_source&install_campaign&install_content&install_ad_unit",
				templateUrl: "/js/mvnApp/public/home/index.html",
				controller: "MainCtrl",
				bodyClass: "page-marketing page-home",
				title:
					"Maven is the leading women's and family healthcare company, disrupting how global employers support women's health, family planning, and diversity in the workforce by improving maternal outcomes, reducing medical costs, and retaining more women.",
				meta: "With Maven, book video appointments with doctors, nurses, pregnancy specialists, nutritionists, lactation consultants and other women's health experts."
			})
			.state("public.how-it-works", {
				url: "/how-it-works",
				redirectTo: "public.for-individuals"
			})
			.state("public.about", {
				url: "/about",
				templateUrl: "/js/mvnApp/public/about/index.html",
				bodyClass: "page-marketing page-about page-sept18-landing",
				title: "About Maven",
				meta: "With Maven, book video appointments with doctors, nurses, pregnancy specialists, nutritionists, lactation consultants and other women's health experts –  from your computer or mobile device."
			})

			.state("public.practitioners", {
				url: "/practitioners",
				templateUrl: "/js/mvnApp/public/practitioners/index.html",
				bodyClass: "page-marketing page-practitioners",
				controller: "PractitionersCtrl",
				title: "Become a Maven Practitioner",
				meta: "Are you a doctor, nurse, pregnancy specialist, nutritionist, lactation consultant or other women's health expert? Apply to become a Maven Practitioner."
			})
			.state("public.download", {
				url: "/download-the-app?ref=",
				templateUrl: "/js/mvnApp/public/download/index.html",
				bodyClass: "page-marketing page-download",
				title: "Download the Maven app",
				meta: "Download the Maven app for iPhone and iPad."
			})
			.state("public.mental-health-packages", {
				url: "/mental-health-packages?step",
				redirectTo: "public.404"
			})

			.state("public.nutritionist-packages", {
				url: "/nutritionist-packages?step",
				redirectTo: "public.404"
			})

			.state("public.maven-maternity", {
				url: "/maven-maternity",
				redirectTo: "public.enterprise"
			})

			.state("public.for-business", {
				url: "/for-business",
				redirectTo: "public.enterprise"
			})

			.state("public.enterprise", {
				url: "/for-employers",
				templateUrl: "/js/mvnApp/public/enterprise/index.html",
				bodyClass: "page-marketing page-sept18-landing page-for-employers",
				controller: "EntMktgCtrl",
				title: "Maven for Employers – Pregnancy, Postpartum, and Back-To-Work Programs",
				meta: "Maven Maternity provides tailored pregnancy, postpartum and back-to-work programs, with an extensive network of highly vetted women's health experts. Book video appointments with doctors, nurses, pregnancy specialists, nutritionists, lactation consultants and other women's health specialists."
			})

			.state("public.enterprise-impact", {
				url: "/impact",
				templateUrl: "/js/mvnApp/public/enterprise-impact/index.html",
				bodyClass: "page-marketing page-impact",
				controller: "EntMktgCtrl",
				title: "Our impact",
				meta: "Maven Maternity provides tailored pregnancy, postpartum and back-to-work programs, with an extensive network of highly vetted women's health experts. Book video appointments with doctors, nurses, pregnancy specialists, nutritionists, lactation consultants and other women's health specialists."
			})

			.state("public.enterprise-testimonials", {
				url: "/testimonials",
				templateUrl: "/js/mvnApp/public/enterprise-testimonials/index.html",
				bodyClass: "page-marketing page-testimonials",
				controller: "EntMktgCtrl",
				title: "Testimonials",
				meta: "Maven Maternity provides tailored pregnancy, postpartum and back-to-work programs, with an extensive network of highly vetted women's health experts. Book video appointments with doctors, nurses, pregnancy specialists, nutritionists, lactation consultants and other women's health specialists."
			})

			.state("public.for-health-plans", {
				url: "/for-health-plans",
				templateUrl: "/js/mvnApp/public/for-health-plans/index.html",
				bodyClass: "page-marketing page-sept18-landing page-for-health-plans",
				controller: "EntMktgCtrl",
				title: "Maven For Health Plans – Pregnancy, Postpartum, and Back-To-Work Programs",
				meta: "Maven Maternity provides tailored pregnancy, postpartum and back-to-work programs, with an extensive network of highly vetted women's health experts. Book video appointments with doctors, nurses, pregnancy specialists, nutritionists, lactation consultants and other women's health specialists."
			})

			.state("public.for-individuals", {
				url: "/for-individuals",
				templateUrl: "/js/mvnApp/public/for-individuals/index.html",
				bodyClass: "page-marketing page-sept18-landing page-for-individuals",
				controller: "ForIndividualsCtrl",
				title: "Maven For Individuals – Pregnancy, Postpartum, and Back-To-Work Programs",
				meta: "Maven Maternity provides tailored pregnancy, postpartum and back-to-work programs, with an extensive network of highly vetted women's health experts. Book video appointments with doctors, nurses, pregnancy specialists, nutritionists, lactation consultants and other women's health specialists."
			})

			.state("public.breast-milk-shipping", {
				url: "/maven-milk",
				templateUrl: "/js/mvnApp/public/maven-milk/index.html",
				bodyClass: "page-marketing page-sept18-landing page-bms",
				controller: "MavenMilkCtrl",
				title: "Maven Milk – Breast Milk Shipping for Working Parents",
				meta: "Maven Maternity provides tailored pregnancy, postpartum and back-to-work programs, with an extensive network of highly vetted women's health experts. Book video appointments with doctors, nurses, pregnancy specialists, nutritionists, lactation consultants and other women's health specialists."
			})

			.state("public.breast-milk-shipping-faq", {
				url: "/maven-milk-faq",
				react: true
			})

			.state("public.breast-milk-shipping-terms", {
				url: "/maven-milk-terms",
				templateUrl: "/js/mvnApp/public/maven-milk/_terms.html",
				bodyClass: "page-marketing page-sept18-landing page-bms",
				title: "Maven Milk – Breast Milk Shipping for Working Parents – Terms",
				meta: "Maven Maternity provides tailored pregnancy, postpartum and back-to-work programs, with an extensive network of highly vetted women's health experts. Book video appointments with doctors, nurses, pregnancy specialists, nutritionists, lactation consultants and other women's health specialists."
			})

			// Case studies
			.state("public.case-studies", {
				abstract: true,
				bodyClass: "page-marketing page-case-study",
				templateUrl: "/js/mvnApp/public/case-studies/index.html"
			})

			.state("public.case-studies.snap", {
				url: "/case-studies/snap",
				templateUrl: "/js/mvnApp/public/case-studies/snap/index.html",
				bodyClass: "page-marketing page-case-study",
				controller: "CaseStudyCtrl",
				title: "Maven Snap Case Study – Pregnancy, Postpartum, and Back-To-Work Programs",
				meta: "Maven Maternity provides tailored pregnancy, postpartum and back-to-work programs, with an extensive network of highly vetted women's health experts. Book video appointments with doctors, nurses, pregnancy specialists, nutritionists, lactation consultants and other women's health specialists."
			})

			.state("public.case-studies.cleary", {
				url: "/case-studies/cleary",
				templateUrl: "/js/mvnApp/public/case-studies/cleary/index.html",
				bodyClass: "page-marketing page-case-study",
				controller: "CaseStudyCtrl",
				title: "Maven Cleary Case Study – Pregnancy, Postpartum, and Back-To-Work Programs",
				meta: "Maven Maternity provides tailored pregnancy, postpartum and back-to-work programs, with an extensive network of highly vetted women's health experts. Book video appointments with doctors, nurses, pregnancy specialists, nutritionists, lactation consultants and other women's health specialists."
			})

			.state("public.terms", {
				url: "/terms",
				templateUrl: "/js/mvnApp/public/terms/index.html",
				bodyClass: "public page-terms",
				title: "Maven Terms & Conditions",
				meta: "Maven Terms and Conditions"
			})
			.state("public.privacy", {
				url: "/privacy-policy",
				templateUrl: "/js/mvnApp/public/privacy/index.html",
				bodyClass: "public page-privacy",
				title: "Maven Privacy Policy",
				meta: "Maven Privacy Policy"
			})

			/* New public-but-authenticated state - we don't want to be using the shared public.html template as that contains tagmanager stuff, and we dont want to track these routes that contain personal info */
			.state("public-authed", {
				abstract: true,
				templateUrl: "/js/mvnApp/public/shared/public-authed.html",
				data: {
					noAuth: true
				},
				title:
					"Maven is the leading women's and family healthcare company, disrupting how global employers support women's health, family planning, and diversity in the workforce by improving maternal outcomes, reducing medical costs, and retaining more women.",
				meta: "With Maven, book video appointments with doctors, nurses, pregnancy specialists, nutritionists, lactation consultants and other women's health experts – all via your iPhone."
			})

			/* Subscription Plan purchase. TODO: not repeat all the things for iOS */

			.state("public-authed.plan-purchase-check-user", {
				url: "/plan-purchase-check-user?plan_id",
				templateUrl: "/js/mvnApp/public/plan-purchase/plan-purchase-check-user/index.html",
				bodyClass: "public page-plan-check-user",
				resolve: {
					userService: "Users",
					user: [
						"$rootScope",
						"$window",
						"$transition$",
						"userService",
						function ($rootScope, $window, $transition$, userService) {
							var planId = $transition$.params().plan_id

							return userService.getWithProfile().then(function (u) {
								if (!u) {
									$rootScope.isAuthenticated = false
									return false
								} else {
									//set our user...
									$rootScope.user = u
									$rootScope.isAuthenticated = true
									// If we already have a user/active session, skip the check and take them straight to the purchase page
									$window.location.href = "/plan-purchase?plan_id=" + planId + "&purchase_for_self=true"
								}
							})
						}
					]
				},
				controller: [
					"$scope",
					"$state",
					"$window",
					function ($scope, $state, $window) {
						var planId = $state.params.plan_id

						$scope.cb = function () {
							$window.location.href = "/plan-purchase-check-user?plan_id=" + planId + "&purchase_for_self=true"
						}

						$scope.toggleLoginReg = function (toggleTo) {
							$scope.formState = toggleTo
						}
					}
				]
			})

			/*Web Marketing Subscription plan purchasing */
			.state("public-authed.plan-purchase", {
				url: "/plan-purchase?plan_id&referrer_id&purchase_for_self",
				templateUrl: "/js/mvnApp/public/plan-purchase/index.html",
				bodyClass: "public page-plan-purchase ",
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
					],

					available_plans: [
						"Subscriptions",
						function (Subscriptions) {
							// GET /subscription_plans/plans from our service
							return Subscriptions.getAvailablePlans()
								.getList()
								.then(
									function (p) {
										return p
									},
									function (e) {
										console.log(e)
									}
								)
						}
					],
					// do we have an encoded_user_id here? either because we were referred or because we've come from iOS?
					purchasing_user: [
						"$rootScope",
						"$transition$",
						"$state",
						"Users",
						"Payments",
						"Subscriptions",
						function ($rootScope, $transition$, $state, Users, Payments, Subscriptions) {
							var constructUserObj = function (user) {
								var usrObj = {
									email: user.email,
									is_auth: true
								}

								// Get user's total credit
								return Payments.getUserCredits(user.id).then(function (credit) {
									usrObj.available_credits = credit.meta.total_credit

									return Payments.getUserPaymentMethod(user.id).then(
										function (p) {
											if (!!p.data[0]) {
												usrObj.stripe_token = true
											} else {
												usrObj.stripe_token = false
											}
											return usrObj
										},
										function (e) {
											$scope.err = true
											$scope.errorMsg = e
											return false
										}
									)
								})
							}

							// Check if we're logged in and should use that info instead.
							// Check if user is already set...
							if (!$rootScope.user) {
								// if it's not set, hit /me and grab our profile if we're authenticated. If not, we're not logged in.
								return Users.getWithProfile().then(function (u) {
									// If we're not signed in, see if we have an encoded_user_id available to grab user info from
									if (!u) {
										// encoded_id passed through
										if ($transition$.params().referrer_id) {
											return Subscriptions.getPurchasingUser()
												.get({
													encoded_user_id: $transition$.params().referrer_id
												})
												.then(
													function (u) {
														// add encoded_user_id as a property of the user object so we can send it later to purchase.
														u = u.plain()
														u.encoded_user_id = $transition$.params().referrer_id
														return u
													},
													function (e) {
														console.log(e)
														return false
													}
												)
										} else {
											return false
										}
									} else {
										//set our user...
										$rootScope.user = u
										$rootScope.isAuthenticated = true
										$rootScope.isEnterprise = $rootScope.user.organization ? true : false
										$rootScope.hasSubscription = $rootScope.user.subscription_plans
										// Cool, we're signed in. So the user object we'll use for purchasing purposes will be constructed out of our info here.
										return constructUserObj(u)
									}
								})
							} else {
								// If we already have root user obj set, create our purchasing_user object from this.
								return constructUserObj($rootScope.user)
							}
						}
					],

					/// 	WE PROBABLY DONT NEED THIS STUFF FOR IOS BUT WE CAN RIP IT OUT LATER ;)

					// is this user buying for themselves? or for someone else (their daughter?)
					// if false, we assume parent is buying
					purchase_for_self: [
						"$transition$",
						function ($transition$) {
							return $transition$.params().purchase_for_self
						}
					],

					// if we've already chosen a plan, like from a marketing page, pass that into our form to preselect.
					plan_id: [
						"$transition$",
						function ($transition$) {
							return $transition$.params().plan_id
						}
					]
				},
				controller: "PlanPurchaseCtrl",
				title: "Maven – Purchase a subscription"
			})

			/* 404 */
			.state("public.404", {
				url: "/404",
				templateUrl: "js/mvnApp/public/shared/404.html",
				bodyClass: "public page-404",
				title: "Page Not Found",
				controller: "404Ctrl",
				meta: "Maven Page Not Found"
			})

			/* Landing/SEO pages */
			.state("public.ads", {
				abstract: true,
				template: "<ui-view/>"
			})

			/* Back-to-work whitepaper as web page */
			.state("public.back-to-work-whitepaper", {
				url: "/back-to-work-whitepaper",
				templateUrl: "/js/mvnApp/public/enterprise/resources/back-to-work-whitepaper/index.html",
				bodyClass: "public page-btw-whitepaper landing-business-a page-landing",
				title: "Maven Maternity – Back-To-Work Program",
				meta: "Maven Maternity provides tailored pregnancy, postpartum and back-to-work programs, with an extensive network of highly vetted women's health experts. Book video appointments with doctors, nurses, pregnancy specialists, nutritionists, lactation consultants and other women's health specialists."
			})

			/* Claim partner invite */
			.state("public-authed.claim-enterprise-invite", {
				url: "/claim-invite/:claiminvite",
				template: "<enterprise-claim-invite></enterprise-claim-invite>",
				bodyClass: "page-marketing claim-enterprise-invite app-static",
				title: "Maven Maternity – the suite of family benefits that advances women and new parents in the workforce",
				meta: "With Maven, book video appointments with doctors, nurses, pregnancy specialists, nutritionists, lactation consultants and other women's health experts"
			})

			/* Thank You Pages */
			.state("public.thank-you-demo-request", {
				url: "/thank-you/demo-request",
				templateUrl: "/js/mvnApp/public/thank-you/_demo-thank-you.html",
				bodyClass: "public mvn-landing page-landing",
				title: "Maven Maternity – Back-To-Work Program",
				meta: "Maven Maternity provides tailored pregnancy, postpartum and back-to-work programs, with an extensive network of highly vetted women's health experts. Book video appointments with doctors, nurses, pregnancy specialists, nutritionists, lactation consultants and other women's health specialists."
			})

			.state("public.thank-you-btw", {
				url: "/thank-you/back-to-work",
				templateUrl: "/js/mvnApp/public/thank-you/_btw-thank-you.html",
				bodyClass: "public mvn-landing page-landing",
				title: "Maven Maternity – Back-To-Work Program",
				meta: "Maven Maternity provides tailored pregnancy, postpartum and back-to-work programs, with an extensive network of highly vetted women's health experts. Book video appointments with doctors, nurses, pregnancy specialists, nutritionists, lactation consultants and other women's health specialists."
			})

			.state("public.thank-you-sp", {
				url: "/thank-you/shifting-paradigm",
				templateUrl: "/js/mvnApp/public/thank-you/_sp-thank-you.html",
				bodyClass: "public mvn-landing page-landing",
				title: "Maven Maternity – Back-To-Work Program",
				meta: "Maven Maternity provides tailored pregnancy, postpartum and back-to-work programs, with an extensive network of highly vetted women's health experts. Book video appointments with doctors, nurses, pregnancy specialists, nutritionists, lactation consultants and other women's health specialists."
			})

			.state("public.ads.back-pain?pid&c&af_sub1", {
				url: "/how-to-fix-back-ache-pain",
				templateUrl: "js/mvnApp/public/landing/back-pain/index.html",
				bodyClass: "public page-landing back-pain",
				title:
					"Find out how to fix back ache and pain on Maven. Maven is healthcare designed exclusively for women. Video appointments with MDs, Nurses and Pregnancy specialists, all from your mobile device.",
				meta: "With Maven, book video appointments with doctors, nurses, pregnancy specialists, nutritionists, lactation consultants and other women's health experts –  from your computer or mobile device."
			})

			.state("public.ads.depression?pid&c&af_sub1", {
				url: "/do-i-have-depression-am-i-depressed",
				templateUrl: "js/mvnApp/public/landing/depression/index.html",
				bodyClass: "public page-landing depression",
				title:
					"Find a therapist on Maven. Maven is healthcare designed exclusively for women. Video appointments with MDs, Nurses and Pregnancy specialists, all from your mobile device.",
				meta: "With Maven, book video appointments with doctors, nurses, pregnancy specialists, nutritionists, lactation consultants and other women's health experts –  from your computer or mobile device."
			})

			.state("public.ads.allergies?pid&c&af_sub1", {
				url: "/treat-seasonal-allergies-allergy-treatment",
				templateUrl: "js/mvnApp/public/landing/allergies/index.html",
				bodyClass: "public page-landing allergies",
				title:
					"Get advice and a prescription quickly to combat allergies with Maven. Maven is healthcare designed exclusively for women. Video appointments with MDs, Nurses and Pregnancy specialists, all from your mobile device.",
				meta: "With Maven, book video appointments with doctors, nurses, pregnancy specialists, nutritionists, lactation consultants and other women's health experts –  from your computer or mobile device."
			})

			/* Back to work landing page */

			.state("public.back-to-work-landing", {
				url: "/back-to-work",
				templateUrl: "/js/mvnApp/public/landing/enterprise/back-to-work-landing/index.html",
				bodyClass: "public page-enterprise landing-business-a page-landing back-to-work-landing",
				controller: "EntMktgCtrl",
				title: "Maven for Business"
			})

			/* Shifting paradigm landing page */

			.state("public.shifting-paradigm-landing", {
				url: "/the-shifting-paradigm-for-maternity-benefits",
				templateUrl: "/js/mvnApp/public/landing/enterprise/shifting-paradigm-landing/index.html",
				bodyClass: "public page-enterprise landing-business-a page-landing shifting-paradigm-landing",
				controller: "EntMktgCtrl",
				title: "Maven for Business"
			})

			.state("public.press", {
				url: "/press",
				templateUrl: "/js/mvnApp/public/press/index.html",
				bodyClass: "page-marketing page-press",
				controller: "PressCtrl",
				title: "Maven Press"
			})

			/* CX automation pages */
			.state("public.cx-appointment-finished-confirm", {
				url: "/_/appointment_overflow_report/:token/:report",
				templateUrl: "/js/mvnApp/public/cx/overflow/index.html",
				bodyClass: "public cx-overflow",
				controller: "CxCtrl",
				title: "Maven Completed Appointment Status"
			})

			/* App webviews for public screens */
			.state("public-authed.ios-app", {
				templateUrl: "/js/mvnApp/public/shared/ios-app.html"
			})
			.state("public-authed.ios-app.about-maven-forum", {
				url: "/webview/about-maven-forum",
				templateUrl: "/js/mvnApp/public/ios-app/about-maven-forum/index.html",
				bodyClass: "public app-static page-about-maven-forum",
				controller: "PublicCtrl",
				title: "About the Maven forum"
			})
			.state("public-authed.ios-app.community-guidelines", {
				url: "/webview/community-guidelines",
				templateUrl: "/js/mvnApp/public/ios-app/community-guidelines/index.html",
				bodyClass: "public app-static page-communityguidelines",
				controller: "PublicCtrl",
				title: "Maven Community Guidelines"
			})
			.state("public-authed.ios-app.terms", {
				url: "/webview/terms",
				templateUrl: "/js/mvnApp/public/ios-app/terms/index.html",
				bodyClass: "public app-static page-terms",
				controller: "PublicCtrl",
				title: "Maven Terms of Use"
			})
			.state("public-authed.ios-app.terms-of-service", {
				url: "/webview/terms-of-service",
				templateUrl: "/js/mvnApp/public/ios-app/terms-of-service/index.html",
				bodyClass: "public app-static page-terms-of-service",
				controller: "PublicCtrl",
				title: "Maven Terms of Service"
			})
			.state("public-authed.ios-app.privacy", {
				url: "/webview/privacy",
				templateUrl: "/js/mvnApp/public/ios-app/privacy/index.html",
				bodyClass: "public app-static page-privacy",
				controller: "PublicCtrl",
				title: "Maven Privacy Policy"
			})
			.state("public-authed.ios-app.help", {
				url: "/webview/help",
				templateUrl: "/js/mvnApp/public/ios-app/help/index.html",
				bodyClass: "public app-static page-help ",
				controller: "PublicCtrl",
				title: "Maven – Help"
			})
			.state("public-authed.ios-app.practitioner-help", {
				url: "/webview/practitioner-help",
				templateUrl: "/js/mvnApp/public/ios-app/practitioner-help/index.html",
				bodyClass: "public app-static page-practitioner-help ",
				controller: "PublicCtrl",
				title: "Maven – Practitioner Help"
			})
			.state("public-authed.ios-app.telehealth-consent", {
				url: "/webview/consent-to-care-via-telehealth",
				templateUrl: "/js/mvnApp/public/ios-app/consent-to-care-via-telehealth/index.html",
				bodyClass: "public app-static page-telehealth-consent ",
				controller: "PublicCtrl",
				title: "Maven – Consent to Care via Telehealth"
			})
	}
])
