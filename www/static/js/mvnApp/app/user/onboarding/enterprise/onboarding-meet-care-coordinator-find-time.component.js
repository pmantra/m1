function OnboardingMeetCareCoordinatorFindTime($state, Users, MvnToastService, Plow, NATIVE_PLATFORM) {
	const vm = this

	vm.isUnconvinced = () => {
		vm.unconvinced = true
		let evt = {
			event_name: "enterprise_onboarding_unconvinced_to_book",
			user_id: vm.user.id
		}
		Plow.send(evt)
	}

	vm.noAppToast = () => {
		MvnToastService.setToast({
			title: "All set!",
			content: `You can get the Maven app anytime by searching “Maven Clinic” (available on iOS and Android).`,
			type: "timed",
			progress: true,
			iconClass: "icon-thumbsup"
		})
		$state.go("app.dashboard")
	}

	vm.smsSent = () => {
		vm.allSet = true
		$state.go("app.dashboard")
		MvnToastService.setToast({
			title: "Sent!",
			content: `Check your phone for a link to download the Maven app.`,
			type: "timed",
			iconClass: "icon-sms-sent"
		})
	}

	vm.nativeCtaOpts = {
		type: "dashboard",
		btnstyle: "btn btn-cta",
		cta: {
			text: "Continue to Maven"
		}
	}

	vm.$onInit = function() {
		vm.loading = true
		vm.isNative = NATIVE_PLATFORM
		Users.getWithProfile().then(
			u => {
				vm.user = u
				vm.activeModule = vm.user.structured_programs[_.findIndex(vm.user.structured_programs, "active")].current_module

				vm.getsGift = !["partner_pregnant", "partner_newparent", "pregnancyloss"].includes(vm.activeModule)

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
					case "postpartum":
						vm.welcomeGift = "welcome-gift-1.png" // maternity kit
						break
					case "fertility":
					case "egg_freezing":
					case "surrogacy":
					case "adoption":
						vm.welcomeGift = "welcome-gift-2.png" // self-care kit
						break
				}

				vm.loading = false
			},
			e => {
				console.log(e)
				vm.loading = false
			}
		)

		let progress = {
			percentage: 82
		}
		vm.updateProgress()(progress)
	}
}

angular.module("app").component("onboardingMeetCareCoordinatorFindTime", {
	templateUrl: "js/mvnApp/app/user/onboarding/enterprise/_onboarding-meet-care-coordinator-find-time.html",
	controller: OnboardingMeetCareCoordinatorFindTime,
	bindings: {
		user: "<",
		updateProgress: "&"
	}
})
