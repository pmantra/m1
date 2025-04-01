function OnboardingInvitePartner(
	$state,
	$timeout,
	Users,
	Plow,
	ngDialog,
	NativeAppCommsService,
	MvnToastService,
	NATIVE_PLATFORM
) {
	const vm = this
	var newPromise, redirTimeout
	vm.invitePartner = form => {
		vm.loading = true

		let toInvite = {
			date_of_birth: moment.utc(vm.dobFields).format("YYYY-MM-DD"),
			email: vm.invitee_email,
			name: vm.invitee_name,
			tel_number: vm.invitee_phone
		}

		if (vm.dueDateFields) {
			toInvite.due_date = moment.utc(vm.dueDateFields).format("YYYY-MM-DD")
		}

		if (vm.lcbFields) {
			toInvite.last_child_birthday = moment.utc(vm.lcbFields).format("YYYY-MM-DD")
		}

		Users.newInvitee(toInvite).then(
			i => {
				vm.loading = false

				let evt = {
					event_name: "enterprise_onboarding_invite_partner_success",
					user_id: vm.user.id
				}
				Plow.send(evt)

				redirTimeout = $timeout(() => {
					if (NATIVE_PLATFORM) {
						let msg = {
							type: "dashboard"
						}
						NativeAppCommsService.sendMessage(msg)
					} else {
						$state.go("app.dashboard")
					}
				}, 1000)

				newPromise = redirTimeout.then() // eslint-disable-line no-unused-vars

				MvnToastService.setToast({
					title: "Sent!",
					content: `${toInvite.name}'s invite is in their inbox.`,
					type: "timed"
				})
			},
			e => {
				vm.loading = false

				ngDialog.open({
					showClose: false,
					controller: [
						"$scope",
						$scope => {
							$scope.msg = e.data.message
						}
					],
					templateUrl: "/js/mvnApp/app/user/onboarding/enterprise/_enterprise-verify-form-error.html"
				})
			}
		)
	}

	vm.skipInvite = () => {
		if (NATIVE_PLATFORM) {
			let msg = {
				type: "dashboard"
			}
			NativeAppCommsService.sendMessage(msg)
		} else {
			MvnToastService.setToast({
				title: "All set!",
				content: `Welcome to Maven.`,
				type: "timed"
			})
			$state.go("app.dashboard")
		}
	}

	vm.$onInit = function() {
		vm.inviteSuccess = false
		vm.partnerInfo = {}
		vm.yearNow = moment().year()
		vm.noDatePicker = !Modernizr.inputtypes.date

		let progress = {
			percentage: 95
		}

		vm.updateProgress()(progress)

		Users.getWithProfile(true).then(
			u => {
				vm.user = u
				let currentProgram = vm.user.structured_programs[_.findIndex(vm.user.structured_programs, "active")]
				if (currentProgram.current_module === "partner_pregnant") {
					vm.partnerIsPregnant = true
					vm.dueDateFields = ""
				}

				if (currentProgram.current_module === "partner_newparent") {
					vm.partnerIsNewParent = true
					vm.lcbFields = ""
				}
			},
			e => {
				console.log(e.data.message)
			}
		)
	}

	vm.$onDestroy = () => {
		if (newPromise) {
			$timeout.cancel(newPromise)
		}

		if (redirTimeout) {
			$timeout.cancel(redirTimeout)
		}
	}
}

angular.module("app").component("onboardingInvitePartner", {
	templateUrl: "js/mvnApp/app/user/onboarding/enterprise/_onboarding-invite-partner.html",
	controller: OnboardingInvitePartner,
	bindings: {
		updateProgress: "&"
	}
})
