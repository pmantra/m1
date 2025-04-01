angular.module("practitioner").config([
	"$stateProvider",
	function($stateProvider) {
		$stateProvider
			/* STANDALONE PRACTITIONER PROFILE */
			.state("app.practitioner-profile", {
				url:
					"/practitioner/:practitioner_id?register&ob&install_source&install_campaign&install_content&install_ad_unit&plan_invite_id&rg_header&rg_subhead&instabook&avail_max&refcode&openbook",
				resolve: {
					itemsResult: [
						"$stateParams", "UrlHelperService",
						($stateParams, UrlHelperService) => {
							UrlHelperService.redirectToReact(`/app/practitioner/${$stateParams.practitioner_id}`)
							return true
						}
					]
				}
			})

			.state("app.book-practitioner-standalone", {
				url: "/book-practitioner/:practitioner_id?specialties&term&vids",
				template:
					'<book-practitioner-standalone user="$ctrl.user" class="app-page book-practitioner-standalone"></book-practitioner-standalone>',
				bodyClass: "practitioner practitioner-profile profile-standalone book-practitioner-standalone-screen",
				data: {
					memberOnly: true
				},
				resolve: {
					loadStripe: [
						"$ocLazyLoad",
						"$injector",
						"$window",
						"config",
						function($ocLazyLoad, $injector, $window, config) {
							//lulz hacky... but this makes ocLazyLoader think this is a .js file (as it thinks js.stripe.com/v2/ is a directory otherwise) :) gz @zach
							return $ocLazyLoad.load("https://js.stripe.com/v2/#mvn.js").then(function() {
								$window.Stripe.setPublishableKey(config.stripe_publishable_key)
							})
						}
					]
				},
				title: "Book an appointment"
			})

			/* PRACTITIONER MAIN LIST 2 PANEL WRAPPER */
			.state("app.practitioner-list", {
				abstract: true,
				bodyClass: "practitioners",
				data: {
					memberOnly: true
				}
			})
			/* PRACTITIONER LIST */
			.state("app.practitioner-list.view", {
				url: "/select-practitioner",
				react: true
			})
			/* PRACTITIONER PROFILE – LIST VIEW */
			.state("app.practitioner-list.view.practitioner-profile", {
				url: "/practitioner/:practitioner_id?register&instabook&openbook",
				resolve: {
					itemsResult: [
						"$stateParams", "UrlHelperService",
						($stateParams, UrlHelperService)=> {
							UrlHelperService.redirectToReact(`/app/practitioner/${$stateParams.practitioner_id}`)
							return true
						}
					]
				}
			})
	}
])
