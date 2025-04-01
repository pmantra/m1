function OnboardingDueDateController($state, Plow, Healthbinder, AppUtils) {
	const vm = this;

	vm.$onInit = () => {
		vm.noDatePicker = !Modernizr.inputtypes.date;

		vm.newU = {
			dueDate: null
		};
		vm.dateToday = AppUtils.removeTimeZone(moment());

		vm.userState = $state.params;

		let progress = {
			percentage: 15
		};
		vm.updateProgress()(progress);
	};

	vm.saveDueDate = function() {
		var dueDateUpdate = {
			due_date: moment(vm.newU.dueDate).format("YYYY-MM-DD")
		};
		Healthbinder.updateHB(vm.user.id, dueDateUpdate).then(function(h) {
			vm.newU.dueDate = new Date(vm.newU.dueDate);
			$state.go("app.onboarding.verify-enterprise", vm.userState);
			let evt = {
				event_name: "enterprise_onboarding_save_due_date",
				user_id: vm.user.id
			};
			Plow.send(evt);
		});
	};
}

angular.module("app").component("onboardingDueDate", {
	templateUrl: "js/mvnApp/app/user/onboarding/lifestages/1.html",
	controller: OnboardingDueDateController,
	bindings: {
		user: "<",
		updateProgress: "&"
	}
});
