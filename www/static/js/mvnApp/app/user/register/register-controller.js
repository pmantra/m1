/**
 * @ngdoc function
 * @name UserRegister
 * @description
 * # UserRegisterCtrl
 * Maven User registrations controller
 */
angular.module("user").controller("UserRegisterCtrl", [
	"$rootScope",
	"$scope",
	"$window",
	"$state",
	"AuthService",
	"Users",
	"MvnStorage",
	"AUTH_EVENTS",
	"UrlHelperService",
	"Plow",
	function ($rootScope, $scope, $window, $state, AuthService, Users, MvnStorage, AUTH_EVENTS, UrlHelperService, Plow) {
		const instParams = MvnStorage.getItem("local", "mvnInst")
		const installParams = instParams ? JSON.parse(instParams) : {}

		const hasRedirectPath = $state.params.from && UrlHelperService.isValidFromPath($state.params.from)

		const redirectToUrl = hasRedirectPath && UrlHelperService.isValidFromPath($state.params.from)

		const ref_code = $state.params.ref_code ? $state.params.ref_code : ""

		$scope.hideSponsorToggle = true

		const _isEntReg = () => {
			$scope.regForm.is_enterprise = "isEnterprise"
			$scope.hideEntToggle = true
		}

		const _isSponsored = () => {
			_isEntReg()
			$scope.regForm.is_sponsored = "isSponsored"
			$scope.hideSponsoredToggle = true
		}

		const _isClaimingInvite = inviteId => {
			$scope.regForm.invite_id = inviteId
			$scope.regForm.is_enterprise = "notEnterprise" // well ok technically they *will* be enterprise, but they're not the one associating their account with an organization employee record...
			$scope.hideEntToggle = true
		}

		const _isClaimingPartnerInvite = inviteId => {
			$scope.regForm.partner_invite_id = inviteId
			$scope.regForm.is_enterprise = "notEnterprise"
			$scope.hideEntToggle = true
			$scope.showPhoneField = true
			if ($state.params.inviting_user && $state.params.inviting_user.length) {
				$scope.rg_header = $state.params.inviting_user + " has invited you to join Maven!"
			} else {
				$scope.rg_header = "You've been invited to join Maven!"
			}
		}

		const _getPageTitles = titleType => {
			if (titleType === "rg_header") {
				if ($state.params.rg_header) {
					return $state.params.rg_header
				} else if (hasRedirectPath && UrlHelperService.getParamValue(redirectToUrl, "rg_header")) {
					return UrlHelperService.urldecode(UrlHelperService.getParamValue(redirectToUrl, "rg_header"))
				} else {
					return `Create your Maven account`
				}
			}

			if (titleType === "rg_subhead") {
				if ($state.params.ref) {
					return `Wondering if Maven is right for you? `
				}

				if ($state.params.rg_subhead) {
					return $state.params.rg_subhead
				}
				if (hasRedirectPath && UrlHelperService.getParamValue(redirectToUrl, "rg_subhead")) {
					return UrlHelperService.urldecode(UrlHelperService.getParamValue(redirectToUrl, "rg_subhead"))
				}
			}

			return
		}

		const postRegAction = postRegOptions => {
			if (postRegOptions.campusInviteId) {
				_claimCampusPlanInvite(postRegOptions.campusInviteId)
			} else {
				if (postRegOptions.doRedirect) {
					// if we want to go to a new place after reg, vs just reloading current screen
					if (postRegOptions.hasRedirectPath) {
						// if we have a url specified to go to post reg
						if (postRegOptions.customOnboarding) {
							var newRedirect = UrlHelperService.appendParam(redirectToUrl, "doaction", "custom-ob")
							_reloadAndGoTo(newRedirect)
						} else {
							_reloadAndGoTo(redirectToUrl)
						}
					} else {
						// if we don't have a specific place to go, do standard onboarding flow
						if (postRegOptions.isEnterprise) {
							const verifyType = $state.params.verify || postRegOptions.verifyType
							const isPrimaryEmployee = $state.params.isemp || verifyType === "sponsored"
							const org = postRegOptions.org

							// if we have the isemp param, we want to skip the select-beneficiary screen
							// #MASSHEALTH - this org thing is horribly hacky and this whole block of code needs rewriting out of if statement hell. But aint nobody got time for that right now. sorry yall. //SG
							if (verifyType) {
								if (isPrimaryEmployee) {
									let url = `/app/onboarding/verify-employer?verify=${verifyType}&isemp=${isPrimaryEmployee}`
									if (org) {
										url += `&org=${org}`
									}
									_reloadAndGoTo(url)
								} else {
									_reloadAndGoTo(`/app/onboarding/select-beneficiary?verify=${verifyType}`)
								}
							} else {
								if (isPrimaryEmployee) {
									_reloadAndGoTo(`/app/onboarding/verify-employer?isemp=${isPrimaryEmployee}`)
								} else {
									_reloadAndGoTo(`/app/onboarding/select-beneficiary`)
								}
							}
						} else if (postRegOptions.enterpriseInviteId) {
							_claimEnterpriseInvite(postRegOptions.enterpriseInviteId)
						} else if (postRegOptions.partnerInviteId) {
							_claimPartnerInvite(postRegOptions.partnerInviteId)
						} else {
							_reloadAndGoTo("/app/dashboard")
						}
					}
				} else {
					// if we *don't* want to go to a specific place post-reg and want to just reload the current screen...
					if (postRegOptions.persistData) {
						//save to sessionstorage
						_setDataToPersist(postRegOptions.persistData)
						//on create post / create reply page, check for cookie data and populate fields w info on load. THEN, delete persisted data.
					}
					_reloadAndGoTo($window.location.href)
				}
			}
		}

		const _reloadAndGoTo = newPath => {
			newPath = newPath ? newPath : "/app/dashboard"
			$window.location.href = newPath
		}

		const _claimCampusPlanInvite = inviteId => {
			let newRedirect = UrlHelperService.appendParam("/app/dashboard", "doaction", "campus-claim")
			newRedirect = UrlHelperService.appendParam(newRedirect, "inviteid", inviteId)
			_reloadAndGoTo(newRedirect)
		}

		const _claimEnterpriseInvite = inviteId => {
			document.location.assign(`/app/onboarding/welcome?inviteid=${inviteId}`)
		}

		const _claimPartnerInvite = inviteId => {
			Users.claimPartnerInvite({ invite_id: inviteId })
				.then(res => {
					if (res.success) {
						document.location.assign(`/app/pediatrics/install-app`)
					} else {
						document.location.assign(`/app/onboarding/verification-issues`)
					}
				})
				.catch(() => {
					document.location.assign(`/app/onboarding/verification-issues`)
				})
		}

		const _setDataToPersist = theData => {
			if (theData.type && theData.content) {
				MvnStorage.setItem("session", theData.type, JSON.stringify(theData.content))
			} else {
				return
			}
		}

		const _loginPostReg = (newUser, postRegOptions) => {
			AuthService.login(newUser).then(
				function () {
					let evt = {
						event_name: "web.signup:create_account_complete",
						user_id: newUser.id
					}
					if (postRegOptions.userPhoneNumber) {
						Users.updateUserPhone(newUser.id, postRegOptions.userPhoneNumber)
					}
					$rootScope.$broadcast("trk", evt)
					$scope.loading = false

					postRegAction(postRegOptions)
				},
				function (resp) {
					$rootScope.$broadcast(AUTH_EVENTS.loginFailed)
					$scope.errorMsg = true
					$scope.err = resp.data.message
				}
			)
		}

		const _getPwStrength = () => {
			const pw = $scope.regForm.password
			Users.getPasswordStrength(pw).then(res => {
				const { data } = res
				const { feedback, password_strength_score: pwScore, password_strength_ok: pwValid } = data

				$scope.pwValid = pwValid
				$scope.pwFeedback = feedback
				$scope.pwScore = pwScore
				$scope.verbalScore = ""
				$scope.errMessage = ""

				switch ($scope.pwScore) {
					case 0:
					case 1:
						$scope.verbalScore = "weak"
						$scope.errMessage = "Password is too weak"
						break
					case 2:
					case 3:
						$scope.verbalScore = "medium"
						$scope.errMessage = "Password could be stronger"
						break
					case 4:
						$scope.verbalScore = "strong"
						$scope.errMessage = "Strong password"
						break
					default:
						$scope.verbalScore = "weak"
						break
				}
			})
		}

		$scope.checkPwStrength = _.debounce(_getPwStrength, 600)

		$scope.register = (user, doRedirect, persistData) => {
			$scope.loading = true

			var newUser = user,
				regObj = _.extend(newUser, installParams),
				regPromise = Users.createNewUser(regObj),
				postRegOptions = {
					isEnterprise: user.is_enterprise === "isEnterprise" || user.is_sponsored === "isSponsored",
					verifyType: user.is_sponsored ? "sponsored" : null,
					org: $state.params.org || user.org || null,
					enterpriseInviteId: user.invite_id,
					doRedirect: doRedirect, // if we want to go to a new place after reg, vs just reloading current screen
					hasRedirectPath: hasRedirectPath, // if we have a url specified to go to post reg
					campusInviteId: $rootScope.invite_id, // if we're claiming a campus invite
					customOnboarding: redirectToUrl ? UrlHelperService.getParamValue(redirectToUrl, "ob") : "", // if we're inserting non-standard onboarding screen, for example, from ads etc
					persistData: persistData, // if we want to persist data to use post-reg in a cookie or whatevs. Type: object with "type"(string) and "content"(object of data)

					// data for partner invite
					partnerInviteId: $state.params.invite_id,
					userPhoneNumber: $scope.regForm.phone
				}

			regPromise
				.then(function (resp) {
					$scope.errorMsg = false
					// we need the user id to save the users phone number, so add it here to user obj
					newUser.id = resp.data.id
					_loginPostReg(newUser, postRegOptions)
				})
				.catch(function (resp) {
					$scope.loading = false
					$scope.errorMsg = true
					$scope.err = resp.data.message
					document.getElementById("email").focus()
				})
		}

		$scope.onInit = () => {
			$scope.regForm = {
				is_sponsored: false
			}
			$scope.errorMsg = false
			$scope.started = false
			$scope.loading = false

			$scope.rg_header = _getPageTitles("rg_header")
			$scope.rg_subhead = _getPageTitles("rg_subhead")
			if ($state.params.ref !== undefined) {
				$scope.ref = $state.params.ref + "?no_redir=1"
			}

			$scope.fPath = $state.params

			if (ref_code) {
				$scope.regForm.referral_code = ref_code
			}

			const isSponsoredAccount = $state.params.verify && $state.params.verify === "sponsored"

			/* Stuff to hide enterprise toggle if "employee" param is present" */
			if (
				($state.params.employee && $state.params.employee === "true") ||
				isSponsoredAccount ||
				(hasRedirectPath && UrlHelperService.getParamValue(redirectToUrl, "employee"))
			) {
				_isEntReg()
			}

			if (isSponsoredAccount) {
				_isSponsored()
			}

			/* Stuff to hide enterprise toggle if "employee" param is present" */
			if (
				($state.params.claiminvite && $state.params.claiminvite.length) ||
				(hasRedirectPath && UrlHelperService.getParamValue(redirectToUrl, "claiminvite"))
			) {
				if (hasRedirectPath && UrlHelperService.getParamValue(redirectToUrl, "claiminvite")) {
					_isClaimingInvite(UrlHelperService.getParamValue(redirectToUrl, "claiminvite"))
				} else {
					_isClaimingInvite($state.params.claiminvite)
				}
			}

			if ($state.params.invite_id && $state.params.invite_id.length) {
				_isClaimingPartnerInvite($state.params.invite_id)
			}

			let evt = {
				event_name: "registration_start"
			}
			Plow.send(evt)
		}

		$scope.onInit()
	}
])
