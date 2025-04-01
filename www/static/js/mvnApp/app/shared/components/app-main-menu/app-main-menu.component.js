/* App main menu */
angular.module("app").directive("appMainMenu", [
	"$rootScope",
	"$state",
	"$window",
	"$mdMenu",
	"ngDialog",
	"ngNotify",
	"Categories",
	"UrlHelperService",
	"AuthService",
	"Appointments",
	"Careteam",
	"Plow",
	function (
		$rootScope,
		$state,
		$window,
		$mdMenu,
		ngDialog,
		ngNotify,
		Categories,
		UrlHelperService,
		AuthService,
		Appointments,
		Careteam,
		Plow
	) {
		return {
			scope: {
				user: "=",
				unreadMessages: "="
			},
			link: function (scope, elm, attrs) {
				scope.tpl = {}

				scope.newMsgCount = 0

				scope.msgScreenReaderTxt = "Messages"

				scope.meMsg = "Me"

				scope.rxErrorCount = 0

				scope.programDisplay = undefined

				scope.showPrescribeMenuLink = false

				var _getDoseSpotStatus = function (practitionerID) {
					Appointments.getDosespotErrorUrl(practitionerID)
						.get()
						.then(
							function (resp) {
								scope.rxErrorCount = resp.refill_count + resp.transaction_count
								scope.prescribeUrl = function () {
									if (scope.rxErrorCount > 0) {
										$window.open(resp.url)
									}
								}
							},
							function (e) {
								ngNotify.set(
									"Sorry there seems to have been an issue (" +
									e.data.message +
									"). Please try again or contact practitionersupport@mavenclinic.com if the issue persists.",
									"success"
								)
							}
						)
				}

				var _openDoseSpotInfoWindow = function () {
					scope.prescribeUrl = function () {
						ngDialog.open({
							templateUrl: "/js/mvnApp/app/shared/_view_prescription.html",
							className: "mvndialog"
						})
					}
				}
				scope.openPracFAQs = function () {
					window.open(
						"https://mavenclinic.helpdocs.io/_hd/team_sso?hd_team=" +
						scope.user.profiles.practitioner.faq_password +
						"&redirect_uri=https://mavenclinic.helpdocs.io"
					)
				}

				scope.openPracContact = () => {
					ngDialog.open({
						className: "mvndialog",
						templateUrl: "js/mvnApp/app/shared/components/app-main-menu/_prac-contact.html"
					})
				}

				const _setUpCareTeam = user => {
					const req = {
						types: "APPOINTMENT,MESSAGE,QUIZ,FREE_FOREVER_CODE"
					}

					Careteam.getGetCareTeam(user.id, req)
						.then(ct => {
							if (ct.length >= 1) {
								const careTeamImages = ct.reduce((acc, cv) => {
									cv.image_url && acc.push(cv.image_url)
									return acc
								}, [])

								scope.careTeamImages = careTeamImages.slice(0, 3)
							}
						})
						.catch(e => console.log(e))
				}

				var _setUpMenu = function () {
					var userType

					Categories.getCats().then(function (c) {
						scope.cats = c.filter(ct => !ct.special)
					})

					if (scope.user) {
						scope.isMarketplace = !scope.user.organization
						
						if (scope.user.active_tracks.length) {
							scope.programDisplay = scope.user.active_tracks[0].display_name
						}

						scope.careCoordinator = scope.user.care_coordinators[0] || {
							first_name: "Kaitlyn",
							last_name: "Hamilton",
							id: 25159,
							image_url: "/img/app/user/onboarding/meet-kaitlyn.jpg"
						}

						if (scope.user.role === "practitioner") {
							userType = "practitioner"

							if (scope.user.profiles.practitioner.vertical_objects[0].can_prescribe) {
								scope.showPrescribeMenuLink = true
								if (scope.user.profiles.practitioner.can_prescribe) {
									_getDoseSpotStatus(scope.user.id)
								} else {
									_openDoseSpotInfoWindow()
								}
							}

							if (scope.user.profiles.practitioner.faq_password) {
								scope.showPracFaqs = true
							}
						} else {
							_setUpCareTeam(scope.user)

							if (scope.user.organization) {
								userType = "enterprise"
							} else {
								userType = "member"
							}
						}
					} else {
						userType = "public"
						scope.isMarketplace = false
					}

					scope.tpl.menuPath = "js/mvnApp/app/shared/components/app-main-menu/_main-menu-" + userType + ".html"
				}

				_setUpMenu()

				// Make sure that if a user's role changes (they become enterprise, subscribe etc) that the new user object is propagated to this menu
				$rootScope.$on("updateUser", function (e, u) {
					if (u) {
						scope.user = u
					}
					_setUpMenu()
				})

				scope.goToLink = (path = "app.dashboard-marketplace", params = {}) => {
					$state.go(path, params)
				}

				scope.handleMessagesLink = () => {
					if (scope.user.flags.messages_replatform.value === 'react') {
						UrlHelperService.redirectToReact("/app/messages")
					} else {
						scope.goToLink('app.messages-list.view')
					}
				}

				scope.handleMyScheduleLink = () => {
					UrlHelperService.redirectToReact("/app/mpractice/my-schedule")
				}

				scope.goToWallet = () => {
					Plow.send({
						event_name: "web_nav_Wallet_click"
					})
					UrlHelperService.redirectToReact("/app/wallet")
				}

				scope.startBooking = () => {
					UrlHelperService.redirectToReact("/app/book")
				}

				scope.goToLearn = () => {
					UrlHelperService.redirectToReact("/app/library")
				}

				scope.hideMyFamily = () => {
					return !(scope.user.active_tracks.find(({ name }) => name === 'parenting_and_pediatrics'))
						|| scope.user.flags.pediatrics_my_family.value !== 'on'
				}

				scope.slug = function (s) {
					return UrlHelperService.slug(s)
				}
				scope.deslug = function (s) {
					return UrlHelperService.deslug(s)
				}

				scope.logout = () => {
					AuthService.logout()
					let evt = {
						event_name: "logout"
					}
					Plow.send(evt)
				}

				scope.openConsumerHelp = () => {
					$window.open("https://support.mavenclinic.com", "_blank")
				}

				scope.closeMdMenu = () => {
					$mdMenu.hide()
				}

				scope.navEvt = navItem => {
					let evt = {
						event_name: navItem || "nav_click"
					}
					Plow.send(evt)
				}

				/* Check for and update new messages count */
				scope.$watch("unreadMessages", function (newV, oldV) {
					if (newV !== oldV) {
						if (newV === 0) {
							scope.msgScreenReaderTxt = "Messages"
							scope.meMsg = "Me"
						} else if (newV < 10 && newV > 0) {
							scope.newMsgCount = newV
							scope.msgScreenReaderTxt = newV + " unread messages"
							scope.meMsg = "Me, unread notifications"
							scope.manyUnread = false
						} else {
							scope.newMsgCount = 9
							scope.msgScreenReaderTxt = "9+ unread messages"
							scope.meMsg = "Me, unread notifications"
							scope.manyUnread = true
						}
					}
				})
				/* Check for and update prescribe count */
				scope.$watch("rxErrorCount", function (newV, oldV) {
					if (newV !== oldV) {
						if (newV < 10) {
							scope.rxErrorCount = newV
							scope.manyErrors = false
						} else {
							scope.rxErrorCount = 9
							scope.manyErrors = true
						}
					}
				})
			},
			template: '<div ng-include="tpl.menuPath"></div>'
		}
	}
])
