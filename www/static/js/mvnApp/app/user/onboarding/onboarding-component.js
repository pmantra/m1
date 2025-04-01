function OnboardingController(Users) {
	const vm = this;

	vm.loading = true;

	vm.$onInit = () => {
		vm.progress = vm.progress || 1;
		Users.getWithProfile().then(u => {
			vm.user = u;
		}, e => {
			console.log(e)
		})
	}

	vm.updateUser = (newU) => {
		vm.user = newU;
	}
	vm.updateProgress = (newProg) => {
		vm.progress = newProg.percentage;
	}

	
}

angular.module('app').component('onboarding', {
	templateUrl: 'js/mvnApp/app/user/onboarding/onboarding.html',
	controller: OnboardingController,
	bindings: {
	}
});