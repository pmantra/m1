function OnboardingAssessmentProgressHeader() {
	var vm = this

	vm.$onInit = function() {
		vm.loading = true
		vm.items = [
			{
				id: 1,
				title: "Basics",
				isCompleted: true
			},
			{
				id: 2,
				title: "Health profile",
				isActive: true
			},
			{
				id: 3,
				title: "Care team"
			},
			{
				id: 4,
				title: "Get care"
			}
		]
	}

	vm.$onDestroy = () => {}
}

angular.module("app").component("onboardingAssessmentProgressHeader", {
	templateUrl: "/js/mvnApp/app/user/assessments/templates/onboarding/_onboarding-assessment-progress-header.html",
	controller: OnboardingAssessmentProgressHeader,
	bindings: {}
})
