/**
 * @ngdoc function
 * @description
 * Maven User Service
 */
angular.module("user").factory("Users", [
	"$rootScope",
	"$http",
	"$q",
	"Restangular",
	"noSession",
	"AuthService",
	"Session",
	"AUTH_EVENTS",
	function($rootScope, $http, $q, Restangular, noSession, AuthService, Session, AUTH_EVENTS) {
		var globaluser

		/* Create */
		var createNewUser = function(user) {
			return $http.post("/api/v1/users", user)
		}

		/* Read */
		var getWithProfile = function(reload) {
			if (!globaluser || reload) {
				return Restangular.one("me")
					.get({ include_profile: true })
					.then(
						function(u) {
							globaluser = u
							return u
						},
						function(e) {
							return false
						}
					)
			} else {
				return $q.resolve(globaluser)
			}
		}

		/* Update */
		var updateUserAccount = function(uid, user) {
			var uaPromise = Restangular.one("users", uid).customPUT(user)
			return uaPromise
		}

		var updateUserProfile = function(uid, user) {
			// TODO - nix this soon. We are setting both tel_number AND phone_number as old mobile device builds use phone_number, and as we send the whole user profile object here, there is no way for backend to know which of these should take precedence if phone_number already exists and we send new tel_number. So we're just overwriting old phone_number with new tel_number for now.
			user.phone_number = user.tel_number ? user.tel_number : user.phone_number
			var udPromise = Restangular.one("users").customPUT(user, uid + "/profiles/member")
			return udPromise
		}

		var updateUserPhone = function(uid, phone_number) {
			var data = {"phone_number": phone_number}
			var udPromise = Restangular.one("users").customPUT(data, uid + "/profiles/member")
			return udPromise
		}

		var getPasswordStrength = function(pw) {
			return $http.post("/api/v1/_/password_strength_score", { password: pw })
		}

		/* --- Enterprise-specific stuff --- */

		/* Associate user with an organization employee */
		///users/{user_id}/organizations
		var updateUserOrgs = function(uid, data) {
			var udPromise = Restangular.one("users", uid)
				.one("organizations")
				.customPOST(data)
			return udPromise
		}

		// /v1/_/manual_census_verification
		var manualVerificationRequest = function(data) {
			return $http.post("/ajax/api/v1/_/manual_census_verification", data)
		}

		/* Invite a user to a Maven enterprise organization */
		// /invite
		var newInvitee = function(data) {
			var newInvitePromise = Restangular.one("invite").customPOST(data)
			return newInvitePromise
		}

		/* Claim an invite to an enterprise account */
		// /invite/claim?invite_id={id}
		var claimEnterpriseInvite = function(data) {
			var claimInvitePromise = Restangular.one("invite/claim").customPOST(data)
			return claimInvitePromise
		}

		/* Claim get the information from an invite */
		// /invite/{id}
		var getInvite = function(invite_id) {
			var getInvitePromise = Restangular.one("invite/" + invite_id).get()
			return getInvitePromise
		}

		/* --- New Partner invite via pediatrics --- */
		var claimPartnerInvite = function(data) {
			var claimPartnerInvitePromise = Restangular.one("partner_invite/claim").customPOST(data)
			return claimPartnerInvitePromise
		}

		/* Get census data we have on an org employee */
		///users/{user_id}/organizations
		const getOrgEmployeeData = uid => {
			let empData = Restangular.one("users", uid).one("organization_employee")
			return empData
		}

		/* Enterprise user dashboards */
		var getDashboard = uid =>
			Restangular.one("users", uid)
				.one("dashboard")
				.get()

		/* Curriculum */
		var getCurriculum = () => Restangular.one("curriculum").get()
		var completeCurriculumStep = (id, data) => {
			const completedPromise = Restangular.one("curriculum_step", id).customPUT(data)
			return completedPromise
		}

		/* Dismiss user card/prompts */
		/* POST /users/{user_id}/dismissals */
		const dismissCard = (uid, data) => Restangular.one(`users/${uid}/dismissals`).customPOST(data)

		/* Program Transitions (LEGACY) */

		/* GET /users/{user_id}/transitions/programs - get user's current program and available transitions */
		const getUserPrograms = uid => Restangular.one(`users/${uid}/transitions/programs`).get()

		const updateUserPrograms = (uid, data) => Restangular.one(`users/${uid}/transitions/programs`).customPOST(data)

		/* Tracks Transition (Replaces Program Transitions above ^) */ 
		
		// GET /tracks - get user's current track and available transitions
		const getUserTrack = () => Restangular.one('tracks').get()

		// POST /tracks/{track_id}/start-transition
		const updateUserTrack = (trackId, destination) => Restangular.one(`tracks/${trackId}/start-transition`).customPOST({'destination': destination})

		/* --- Campus-specific stuff --- */

		// CONFIRM PAYER EMAIL ADDRESS
		// subscription_plans/payers/{email}/email_confirm{?token}
		var confirmPayerEmail = function(email) {
			return noSession.one("/subscription_plans/payers/" + email + "/email_confirm")
		}

		var getPayerInfo = function(email) {
			return noSession.one("/subscription_plans/payers/" + email)
		}

		const userService = {
			createNewUser,
			updateUserProfile,
			updateUserPhone,
			updateUserAccount,
			getWithProfile,
			getPasswordStrength,

			updateUserOrgs,
			newInvitee,
			claimEnterpriseInvite,
			claimPartnerInvite,
			getInvite,
			getOrgEmployeeData,
			getDashboard,
			getCurriculum,
			completeCurriculumStep,

			dismissCard,

			getUserPrograms,
			updateUserPrograms,
			getUserTrack,
			updateUserTrack,

			confirmPayerEmail,
			getPayerInfo,
			manualVerificationRequest
		}
		// userService.createNewUser = createNewUser
		// userService.updateUserProfile = updateUserProfile
		// userService.updateUserAccount = updateUserAccount
		// userService.getWithProfile = getWithProfile
		// userService.getPasswordStrength = getPasswordStrength

		// userService.updateUserOrgs = updateUserOrgs
		// userService.newInvitee = newInvitee
		// userService.claimEnterpriseInvite = claimEnterpriseInvite
		// userService.getInvite = getInvite
		// userService.getOrgEmployeeData = getOrgEmployeeData
		// userService.getDashboard = getDashboard
		// userService.getCurriculum = getCurriculum
		// userService.completeCurriculumStep = completeCurriculumStep

		// userService.dismissCard = dismissCard

		// userService.getUserPrograms = getUserPrograms
		// userService.updateUserPrograms = updateUserPrograms

		// userService.confirmPayerEmail = confirmPayerEmail
		// userService.getPayerInfo = getPayerInfo
		// userService.manualVerificationRequest = manualVerificationRequest

		return userService
	}
])
