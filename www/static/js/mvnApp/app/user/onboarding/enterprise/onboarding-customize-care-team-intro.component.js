function OnboardingCustomizeCareTeamIntro($state, Users, Plow, AssessmentService) {
	const vm = this;

	vm.loading = true;

	const getObAssessmentId = (user) => {
		let currentModule = user.structured_programs[_.findIndex(user.structured_programs, 'active')].current_module;
		return user.structured_programs[0].modules[currentModule].onboarding_assessment_id;
	}

	const doSetUp = () => {
		let onboardingAssessmentId = $state.params.amtid || getObAssessmentId(vm.user);

		if (onboardingAssessmentId) {

			AssessmentService.getAssessment(onboardingAssessmentId).then(a => {// Remove when assessment slug is returned on structured_program
				vm.loading = false
				vm.onboardingAssessment = a;
			}, e => {
				console.log(e)
			})
		} else {
			$state.go('app.onboarding.meet-care-coordinator')
		}
	}

	vm.startOnboardingAssessment = () => {
		$state.go('app.onboarding.onboarding-assessment.one.take', { "id": vm.onboardingAssessment.id, "slug": vm.onboardingAssessment.slug })
	}

	vm.$onInit = function () {
		vm.loading = true;
		
		if (!vm.user.structured_programs[_.findIndex(vm.user.structured_programs, 'active')]) {
			Users.getWithProfile(true).then(u => {
				vm.user = u;
				doSetUp()
			}, e => {
				console.log(e.data.message)
			})
		} else {
			doSetUp()
		}

		
	}

	
}

angular.module('app').component('onboardingCustomizeCareTeamIntro', {
	templateUrl: 'js/mvnApp/app/user/onboarding/enterprise/_onboarding-customize-care-team-intro.html',
	controller: OnboardingCustomizeCareTeamIntro,
	bindings: {
		user: '<'
	}
});