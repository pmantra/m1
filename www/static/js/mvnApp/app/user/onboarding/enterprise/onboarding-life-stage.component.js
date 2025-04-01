function OnboardingLifeStageController($state, DynamicCopy, MvnUiUtils, Plow) {
	const vm = this

	vm.loading = true

	vm.$onInit = () => {
		vm.userState = {}
		DynamicCopy.getLifeStages().then(stages => {
			vm.loading = false
			vm.lifeStages = stages.data
		})

		vm.selectedLifeStage = ""

		let progress = {
			percentage: 10
		}
		vm.updateProgress()(progress)
	}

	vm.setLifeStage = stage => {
		let life_stage = JSON.parse(stage)

		vm.userState.track = life_stage.verification_reason

		if (life_stage.ispartner) {
			vm.userState.ispartner = true
		}

		if (vm.userState.track === "pregnancy" || vm.userState.track === "partner_pregnant") {
			// Is pregnant or partner s pregnant
			$state.go("app.onboarding.due-date", vm.userState)
		} else if (vm.userState.track === "postpartum" || vm.userState.track === "partner_newparent") {
			// Is new parent or partner of
			$state.go("app.onboarding.child-birthday", vm.userState)
		} else {
			$state.go("app.onboarding.verify-enterprise", vm.userState)
		}

		let evt = {
			event_name: "web_enterprise_onboarding_set_life_stage",
			stage_name: vm.userState.track
		}
		Plow.send(evt)
	}
}

angular.module("app").component("onboardingLifeStage", {
	templateUrl: "js/mvnApp/app/user/onboarding/enterprise/_onboarding-lifestage.html",
	controller: OnboardingLifeStageController,
	bindings: {
		user: "<",
		updateProgress: "&"
	}
})
