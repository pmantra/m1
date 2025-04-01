function OnboardingVerifyEnterpriseController(
	$rootScope,
	$state,
	ngDialog,
	Users,
	Healthbinder,
	Plow,
	AppUtils,
	MvnToastService,
	NATIVE_PLATFORM,
	NativeAppCommsService
) {
	const vm = this

	const _updateUserProfileAndVerify = toVerify => {
			Users.updateUserProfile(vm.user.id, vm.user.profiles.member)
				.then(a => {
					_updateUserOrgs(toVerify)
				})
				.catch(e => {
					let msg = JSON.parse(e.data.error.replace(/'/g, '"'))
					_showError(msg[0])
				})
		},
		_updateUserOrgs = toVerify => {
			Users.updateUserOrgs(vm.user.id, toVerify)
				.then(o => {
					if (o.can_invite_partner) {
						toVerify.can_invite_partner = true
					}
					_updateUserHB(toVerify)
				})
				.catch(function(e) {
					// on error, if we are in default "de" verification flow, we want to get the user to confirm they've entered their info correctly.
					//If they have, punt them to "fls" flow. If they made an error/typo, try again
					// if they're already in "fls" flow and verification fails, send their data to manual verification endpoint & flow.

					if (vm.verificationType === "fls") {
						// if it failed in 'fls' verify, punt to manual verify
						_manualVerificationRequest(toVerify)
					} else {
						let onComplete = () => {
							toVerify.verify = "fls"
							vm.verificationType = "fls"
							vm.goToAltVerify()
						}
						_showVerifyConfirm(toVerify, onComplete, vm.userState.ispartner)
					}

					let evt = {
						event_name: "enterprise_onboarding_verify_info_fail",
						user_id: vm.user.id,
						error_resp: e.data.message
					}
					Plow.send(evt)
				})
		},
		_manualVerificationRequest = toVerify => {
			let evt = {
				event_name: "enterprise_onboarding_try_manual_verification",
				user_id: vm.user.id
			}
			Plow.send(evt)

			Users.manualVerificationRequest(toVerify)
				.then(o => {
					vm.manualVerify = true
					_updateUserHB(toVerify)
				})
				.catch(function(e) {
					_showError(e.data.message)
					let evt = {
						event_name: "enterprise_onboarding_alt_verification_verify_info_fail",
						user_id: vm.user.id
					}
					Plow.send(evt)
				})
		},
		_updateUserHB = toVerify => {
			let hbToUpdate = {
				birthday: vm.userState.ispartner ? toVerify.own_date_of_birth : toVerify.date_of_birth
			}

			Healthbinder.updateHB(vm.user.id, hbToUpdate)
				.then(h => {
					_updateGlobalUser(toVerify)
				})
				.catch(function(e) {
					let msg = JSON.parse(e.data.error.replace(/'/g, '"'))
					_showError(msg[0])
				})
		},
		_updateGlobalUser = toVerify => {
			Users.getWithProfile(true).then(u => {
				$rootScope.user = u
				$rootScope.$broadcast("updateUser", u)
				vm.user = u
				vm.updateUser(u)
				_completeOnboarding(toVerify)
			})
		},
		_completeOnboarding = toVerify => {
			vm.loading = false
			let evt = {
				event_name: "ent_ob_account_link_success",
				user_id: vm.user.id
			}
			Plow.send(evt)

			if (vm.manualVerify) {
				$state.go("app.onboarding.alt-verification-post-verify")
			} else {
				// if is partner
				if (vm.userState.ispartner) {
					MvnToastService.setToast({
						title: "Success!",
						content: "Your Maven membership is covered by your company.",
						type: "timed",
						iconClass: "icon-thumbsup"
					})
					// should we check this? or should anywhere that can_invite_partner is true show invite partner stuff?
					if (toVerify.can_invite_partner) {
						$state.go("app.onboarding.invite-partner")
					} else {
						$state.go("app.dashboard")
					}
				} else {
					if (
						vm.user.structured_programs[0] &&
						vm.user.structured_programs[0].type !== "pending_enterprise_verification"
					) {
						MvnToastService.setToast({
							title: "Success!",
							content: "Your Maven membership is covered by your company.",
							type: "timed",
							iconClass: "icon-thumbsup"
						})
						const currentProgram = vm.user.structured_programs[_.findIndex(vm.user.structured_programs, "active")],
							currentModule = currentProgram.modules[currentProgram.current_module] // this will error out if we don't have an active module. But that should never happen during real/non-testing use cases.

						if (currentModule.onboarding_assessment_id) {
							// if we have an onboarding assessment specified... go to the care team intro screen. Unless we're in the loss track - in which case go straight to the assessment (gifts and confetti are not really appropriate...)
							if (currentProgram.current_module === "pregnancyloss") {
								$state.go("app.onboarding.onboarding-assessment.one.take", {
									id: currentModule.onboarding_assessment_id,
									slug: "intro-assessment"
								})
							} else {
								$state.go("app.onboarding.address-confirmation")
							}
						} else {
							if (vm.isNative) {
								let msg = {
									type: "dashboard",
									event: "dashboard"
								}
								NativeAppCommsService.sendMessage(msg)
							} else {
								$state.go("app.dashboard")
							}
						}
					} else {
						$state.go("app.onboarding.enterprise-use-case", vm.userState)
					}
				}
			}
		},
		_showError = msg => {
			vm.loading = false
			ngDialog.open({
				showClose: false,
				controller: [
					"$scope",
					$scope => {
						$scope.msg = msg
					}
				],
				templateUrl: "/js/mvnApp/app/user/onboarding/enterprise/_enterprise-verify-form-error.html"
			})
		},
		_showVerifyConfirm = (data, oncomplete, ispartner = false) => {
			vm.loading = false
			ngDialog.open({
				showClose: false,
				controller: [
					"$scope",
					$scope => {
						$scope.data = data
						$scope.isPartner = ispartner
						$scope.onComplete = oncomplete
					}
				],
				templateUrl: "/js/mvnApp/app/user/onboarding/enterprise/_enterprise-confirm-submitted-info.html"
			})
		},
		getTemplate = (verifyType = "de") => {
			// We want to switch the template based on whether the user is in "main" verify state or alternate verification state.

			switch (verifyType) {
				case "fls":
					return `js/mvnApp/app/user/onboarding/enterprise/_onboarding-alt-verify-enterprise.html`
				default:
					return `js/mvnApp/app/user/onboarding/enterprise/_onboarding-verify-enterprise.html`
			}
		}

	vm.$onInit = () => {
		vm.isNative = NATIVE_PLATFORM
		vm.verifyEnterpriseInfo = {}
		vm.dobFields = {}
		vm.userState = $state.params || {}
		vm.templateUrl = "js/mvnApp/app/user/onboarding/enterprise/_onboarding-verify-enterprise.html"
		vm.noDatePicker = !Modernizr.inputtypes.date
		vm.states = AppUtils.availableStates

		vm.templateUrl = getTemplate(vm.userState.verify)

		if (!vm.userState.track) {
			$state.go("app.onboarding.lifestage")
		}
		let progress = {
			percentage: 30
		}
		vm.updateProgress()(progress)
	}

	vm.$onChanges = changes => {
		vm.templateUrl = getTemplate(vm.userState ? vm.userState.verify : null)
	}

	vm.goToAltVerify = () => {
		vm.userState.verify = "fls"
		$state.go("app.onboarding.verify-enterprise", vm.userState)
	}

	vm.cancelAltVerify = () => {
		vm.userState.verify = false
		let newParams = angular.copy($state.params)
		newParams.verify = null
		$state.go($state.current, newParams)
	}

	vm.verifyEnterprise = form => {
		vm.loading = true
		let toVerify = {
			date_of_birth: moment(form.date_of_birth).format("YYYY-MM-DD")
		}

		vm.verificationType = vm.userState.verify

		toVerify.verification_reason = vm.userState.track

		if (vm.userState.ispartner) {
			toVerify.own_date_of_birth = form.own_date_of_birth
		}

		if (vm.verificationType == "fls") {
			toVerify.first_name = form.first_name
			toVerify.last_name = form.last_name
			toVerify.work_state = form.work_state
			toVerify.company_name = form.company_name
		} else {
			toVerify.company_email = form.company_email
		}

		vm.user.profiles.member.tel_number = form.tel_number

		_updateUserProfileAndVerify(toVerify)
	}
}

angular.module("app").component("onboardingVerifyEnterprise", {
	template: '<div ng-include="$ctrl.templateUrl">',
	//templateUrl: 'js/mvnApp/app/user/onboarding/enterprise/_onboarding-verify-enterprise.html',
	controller: OnboardingVerifyEnterpriseController,
	bindings: {
		user: "<",
		updateUser: "&",
		updateProgress: "&"
	}
})
