function OnboardingPostBookGetApp($state, Plow, MvnToastService, NATIVE_PLATFORM) {
	const vm = this

	vm.finishOnboarding = () => {
		let evt = {
			event_name: "web_complete_onboarding",
			user_id: vm.user.id
		}
		Plow.send(evt)
		$state.go("app.dashboard")
	}

	vm.smsSent = () => {
		let evt = {
			event_name: "web_post_booked_sms_the_app_sent",
			user_id: vm.user.id
		}
		Plow.send(evt)

		MvnToastService.setToast({
			title: "Sent!",
			content: `Check your phone for a link to download the Maven app.`,
			type: "timed",
			progress: true,
			iconClass: "icon-sms-sent"
		})
		vm.finishOnboarding()
	}

	vm.noToDownload = () => {
		MvnToastService.setToast({
			title: "All set!",
			content: `You can get the Maven app anytime by searching “Maven Clinic” (available on iOS and Android).`,
			type: "timed",
			progress: true,
			iconClass: "icon-thumbsup"
		})

		let progress = {
			percentage: 100
		}
		vm.updateProgress()(progress)
		vm.finishOnboarding()
	}

	vm.nativeCtaOpts = {
		type: "dashboard",
		btnstyle: "btn btn-cta",
		cta: {
			text: "Continue to Maven"
		}
	}

	vm.$onInit = function() {
		vm.isNativePlatform = NATIVE_PLATFORM
		let progress = {
			percentage: 95
		}
		vm.updateProgress()(progress)
	}
}

angular.module("app").component("onboardingPostBookGetApp", {
	templateUrl: "js/mvnApp/app/user/onboarding/enterprise/_onboarding-post-book-get-app.html",
	controller: OnboardingPostBookGetApp,
	bindings: {
		user: "<",
		updateProgress: "&"
	}
})
