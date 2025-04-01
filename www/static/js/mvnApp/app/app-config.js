/*
 *
 *
 * Configuration and routes for Public pages
 *
 *
 */

angular.module("app").config([
	"$stateProvider",
	"ngDialogProvider",
	"intlTelInputOptions",
	"$mdThemingProvider",
	function ($stateProvider, ngDialogProvider, intlTelInputOptions, $mdThemingProvider) {
		ngDialogProvider.setDefaults({
			className: "mvndialog",
			trapFocus: true,
			preserveFocus: true
		})

		angular.extend(intlTelInputOptions, {
			nationalMode: true,
			utilsScript: "/vendor/intl-tel-input/utils.js",
			defaultCountry: "us",
			preferredCountries: ["us", "ca", "gb"],
			autoFormat: true,
			autoPlaceholder: true
		})

		$mdThemingProvider.disableTheming()

		$stateProvider.state("app.dashboard-marketplace", {
			url: "/dashboard",
			react: true
		})

		$stateProvider.state("app.dashboard", {
			resolve: {
				itemsResult: [
					"UrlHelperService",
					UrlHelperService => {
						UrlHelperService.redirectToReact("/app/dashboard")
						return true
					}
				]
			}
		})


		$stateProvider.state("app.onboarding", {
			abstract: true,
			bodyClass: "page-onboarding custom-nav",
			url: "/onboarding?ispartner&track&verify",
			template: '<onboarding class="onboarding"></onboarding>'
		})

		$stateProvider.state("app.react-careteam", {
			url: "/onboarding/care-team-intro",
			react: true
		})

		$stateProvider.state("app.react-life-stage", {
			url: "/onboarding/life-stage",
			react: true
		})

		$stateProvider.state("app.my-schedule", {
			url: "/my-schedule",
			react: true
		})

		$stateProvider.state("app.onboarding.onboarding-assessment", {
			abstract: true,
			url: "/onboarding-assessment",
			bodyClass: "assessments page-onboarding-assessment page-onboarding",
			template: "<assessments></assessments>"
		})

		$stateProvider.state("app.onboarding.onboarding-assessment.one", {
			// assessment by ID
			abstract: true,
			template: '<assessment user="$ctrl.user"></assessment>'
		})

		$stateProvider.state("app.onboarding.onboarding-assessment.one.take", {
			// take an assessment
			url: "/:id/:slug/take/:qid",
			title: "Let's get to know each other",
			bodyClass: "assessments page-onboarding-assessment page-onboarding",
			params: {
				qid: "1"
			},
			template:
				'<take-assessment ng-if="$ctrl.assessment" user="$ctrl.user" assessment="$ctrl.assessment" update-status="$ctrl.updateStatus"  trigger-back="$ctrl.triggerBack()" class="take-assessment"></take-assessment>'
		})

		$stateProvider.state("app.onboarding.complete", {
			url: "/complete",
			title: "Complete!",
			bodyClass: "page-onboarding onboarding-complete",
			trk_event: "web_onboarding_screen_onboarding_complete",
			templateUrl: "js/mvnApp/app/user/onboarding/_onboarding-complete.html"
		})

		$stateProvider.state("app.onboarding.enterprise-use-case", {
			url: "/onboarding-use-case",
			title: "Unable to confirm",
			bodyClass: "page-onboarding onboarding-no-header",
			controller: [
				"$scope",
				"$state",
				"NATIVE_PLATFORM",
				function ($scope, $state, NATIVE_PLATFORM) {
					if ($state.params.track === "pregnancyloss") {
						$scope.needsConfirmation = true
					}

					$scope.isNative = NATIVE_PLATFORM

					$scope.nativeCtaOpts = {
						type: "dashboard",
						btnstyle: "btn btn-cta",
						cta: {
							text: "Explore Maven"
						}
					}
					$scope.nativeCtaMsgOpts = {
						type: "message",
						btnstyle: "btn btn-tertiary",
						cta: {
							text: "Send a message"
						}
					}
				}
			],
			trk_event: "web_onboarding_screen_post_complete_use_case",
			templateUrl: "js/mvnApp/app/user/onboarding/enterprise/_onboarding-use-case.html"
		})

		$stateProvider.state("app.onboarding.alt-verification-post-verify", {
			url: "/onboarding-post-verify",
			title: "Unable to verify",
			bodyClass: "page-onboarding onboarding-no-header",
			controller: [
				"$scope",
				"$state",
				"NATIVE_PLATFORM",
				function ($scope, $state, NATIVE_PLATFORM) {
					$scope.isNative = NATIVE_PLATFORM

					if ($state.params.track === "other") {
						$scope.isOther = true
					}

					$scope.nativeCtaOpts = {
						type: "dashboard",
						btnstyle: "btn btn-cta",
						cta: {
							text: "Explore Maven"
						}
					}
				}
			],
			trk_event: "web_onboarding_screen_alt_verify_post_complete_use_case",
			templateUrl: "js/mvnApp/app/user/onboarding/enterprise/_onboarding-alt-verification-post-verify.html"
		})
	}
])
