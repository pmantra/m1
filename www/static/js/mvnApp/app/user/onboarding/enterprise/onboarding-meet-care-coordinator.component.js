function OnboardingMeetCareCoordinator($state, Users) {
	const vm = this

	vm.$onInit = function() {
		vm.loading = true

		Users.getWithProfile(true).then(
			u => {
				vm.user = u

				vm.activeModule = vm.user.structured_programs[_.findIndex(vm.user.structured_programs, "active")].current_module

				// vm.testGroup =
				// 	$state.params.testgroup && ($state.params.testgroup === "a" || $state.params.testgroup === "b")
				// 		? $state.params.testgroup
				// 		: u.test_group

				vm.careCoordinator = vm.user.care_coordinators[0] || {
					first_name: "Kaitlyn",
					last_name: "Hamilton",
					id: 25159
				}

				vm.careCoordinator.profile_image = `meet-${vm.careCoordinator.first_name.toLowerCase()}.jpg`

				switch (vm.activeModule) {
					case "pregnancy":
						vm.customBullet =
							"I can connect you to the practitioners on your Care Team, including: prenatal nutritionists, therapists, OB-GYNs, and more."
						break
					case "postpartum":
						vm.customBullet =
							"I can connect you to the practitioners on your Care Team, including: lactation consultants, infant sleep coaches, therapists, and more."
						break
					case "fertility":
						vm.customBullet =
							"I can connect you to the practitioners on your Care Team, including: fertility specialists, reproductive endocrinologists, therapists, and more."
						break
					case "egg_freezing":
						vm.customBullet =
							"I can connect you to the practitioners on your Care Team, including: egg freezing specialists, reproductive endocrinologists, therapists, and more."
						break
					case "adoption":
						vm.customBullet =
							"I can connect you to the practitioners on your Care Team, including: adoption specialists, therapists, and more."
						break
					case "surrogacy":
						vm.customBullet =
							"I can connect you to the practitioners on your Care Team, including: surrogacy specialists, therapists, and more."
						break
					case "pregnancyloss":
						vm.customBullet =
							"I can connect you to the practitioners on your Care Team, including: loss specialists, OB-GYNs, therapists, and more."
						break
					default:
						vm.customBullet = "I can connect you to expert specialists available on Maven 24/7"
				}
				vm.loading = false
			},
			e => {
				console.log(e)
				vm.loading = false
			}
		)

		let progress = {
			percentage: 80
		}
		vm.updateProgress()(progress)
	}
}

angular.module("app").component("onboardingMeetCareCoordinator", {
	templateUrl: "js/mvnApp/app/user/onboarding/enterprise/_onboarding-meet-care-coordinator.html",
	controller: OnboardingMeetCareCoordinator,
	bindings: {
		user: "<",
		updateProgress: "&"
	}
})
