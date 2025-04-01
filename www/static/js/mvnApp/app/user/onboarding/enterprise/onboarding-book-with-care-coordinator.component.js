function OnboardingBookWithCareCoordinator($state, Users, Plow, NATIVE_PLATFORM) {
	const vm = this;

	vm.nativeCtaOpts = {
		"type": "dashboard",
		"btnstyle": "btn btn-cta",
		"cta": {
			"text": "Continue to Maven"
		}
	}

	vm.$onInit = function () {
		vm.isNative = NATIVE_PLATFORM;
		vm.loading = true;
		Users.getWithProfile().then(u => {
			vm.user = u;
			vm.loading = false;
		}, e => {
			console.log(e)
			vm.loading = false;
		})

		let progress = {
			percentage: 90
		}
		vm.updateProgress()(progress)
	}

}

angular.module('app').component('onboardingBookWithCareCoordinator', {
	templateUrl: 'js/mvnApp/app/user/onboarding/enterprise/_onboarding-book-with-care-coordinator.html',
	controller: OnboardingBookWithCareCoordinator,
	bindings: {
		user: '<',
		updateProgress: '&'
	}
});