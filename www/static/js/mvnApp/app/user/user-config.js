/*
 *
 *
 * Configuration and routes for User
 *
 *
 */
angular.module("user").config([
	"$stateProvider",
	"$locationProvider",
	"RestangularProvider",
	function ($stateProvider, $locationProvider, RestangularProvider) {
		$stateProvider
			.state("app.account", {
				abstract: true
			})
			.state("app.account.edit", {
				url: "/account",
				react: true
			})
			.state("app.healthbinder", {
				url: "/healthprofile",
				react: true
			})
			.state("app.healthbinder-redirect", {
				url: "/healthbinder",
				react: true
			})
			.state("app.help-and-contact", {
				url: "/help-contact",
				title: "Help & Contact",
				template: '<help-and-contact class="app-page" user="user" ></help-and-contact>',
				bodyClass: "page-help-contact",
				data: {
					memberOnly: true
				},
				trk_event: "help-contact"
			})
			/* USER CARE TEAM */
			.state("app.care-team", {
				url: "/care-team",
				react: true
			})

			/* USER PROGRAMS AND AVAILABLE TRANSITIONS */

			.state("app.user-programs", {
				url: "/my-programs",
				react: true
			})

			/* NEW ASSESSMENTS Redirect */
			.state("app.new-assessments", {
				url: "/assessments/:slug",
				title: "Let's get to know eachother",
				data: {
					memberOnly: true
				},
				template: '<new-assessments></new-assessments>'
			})
			.state("app.new-assessments.take", {
				url: "/take/:qid",
				title: "Let's get to know each other",
				params: {
					qid: "1"
				},
				template: '<new-assessments></new-assessments>'
			})

			/* ASSESSMENTS */
			.state("app.assessments", {
				abstract: true,
				url: "/assessments",
				bodyClass: "assessments custom-nav",
				data: {
					memberOnly: true
				},
				template: '<assessments class="app-page app-page-full"></assessments>'
			})
			.state("app.assessments.quizzes", {
				// all available quizzes
				url: "/quizzes",
				bodyClass: "bg-dk",
				template: '<assessments-list user="$ctrl.user" atype="M_QUIZ,E_QUIZ,C_QUIZ"></assessments-list>'
			})
			/*
		.state('app.assessments.my', { // only assessments I've started or completed
			template: '<my-assessments></my-assessments>'
		})
		*/
			.state("app.assessments.one", {
				// assessment by ID
				abstract: true,
				bodyClass: "custom-nav",
				template: '<assessment user="$ctrl.user"></assessment>'
			})
			.state("app.assessments.one.view", {
				// assessment by ID - view
				url: "/:id/:slug",
				bodyClass: "custom-nav",
				template: () => {
					return '<assessment-view user="$ctrl.user" assessment="$ctrl.assessment"></assessment-view>'
				}
			})
			.state("app.assessments.one.take", {
				// take an assessment
				url: "/:id/:slug/take/:qid",
				bodyClass: "custom-nav",
				params: {
					qid: "1"
				},
				template:
					'<take-assessment ng-if="$ctrl.assessment" trigger-back="$ctrl.triggerBack()" user="$ctrl.user" assessment="$ctrl.assessment" update-status="$ctrl.updateStatus" class="take-assessment"></take-assessment>'
			})
			.state("app.assessments.one.results", {
				// view an assessment
				url: "/:id/:slug/results",
				bodyClass: "custom-nav",
				template:
					'<assessment-results ng-if="$ctrl.assessment" user="$ctrl.user" assessment="$ctrl.assessment" update-status="$ctrl.updateStatus"></assessment-results>'
			})
	}
])
