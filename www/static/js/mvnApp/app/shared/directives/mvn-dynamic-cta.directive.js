angular.module("app").directive("mvnDynamicCta", [
	"$state",
	"Users",
	"Messages",
	"NATIVE_PLATFORM",
	"NativeAppCommsService",
	"ModalService",
	"ngDialog",
	"ngNotify",
	"Plow",
	function($state, Users, Messages, NATIVE_PLATFORM, NativeAppCommsService, ModalService, ngDialog, ngNotify, Plow) {
		return {
			restrict: "E",
			scope: {
				user: "=",
				opts: "=",
				btnclass: "@",
				eventName: "=",
				eventObject: "<",
				actionCallback: "&",
				arialabel: "@"
			},
			link: function(scope, element, attributes) {
				var evt
				const doLogin = function() {
					const currentUrl = window.location.href
					window.location = "/login?from=" + currentUrl
				}

				if (scope.opts.label) {
					scope.btnCopy = scope.opts.label
				} else if (scope.opts.cta && scope.opts.cta.text) {
					scope.btnCopy = scope.opts.cta.text
				} else {
					scope.btnCopy = "Go"
				}

				scope.btnclass = scope.btnclass || scope.opts.btnclass

				if (!scope.btnclass) {
					if (scope.opts.btnstyle) {
						switch (scope.opts.btnstyle) {
							case "primary":
								scope.btnclass = "btn btn-cta"
								break
							case "secondary":
								scope.btnclass = "btn btn-action"
								break
							case "tertiary":
								scope.btnclass = "btn btn-tertiary"
								break
							case "cancel":
								scope.btnclass = "btn btn-tertiary"
								break
							case "none":
								scope.btnclass = ""
								break
							default:
								scope.btnclass = "btn btn-cta"
						}
					} else {
						scope.btnclass = scope.opts.type === "link" ? "" : "btn btn-cta"
						scope.btnclass = scope.opts.btnstyle || (scope.opts.type === "link" ? "" : "btn btn-cta")
					}
				}

				const actionType = scope.opts.type

				const doAction = (user, notAuthenticated) => {
					let theUser = user
					switch (actionType) {
						case "book":
							scope.ctaBehavior = "sref"
							scope.stateName = "app.practitioner-profile"
							scope.stateParams = {
								practitioner_id: scope.opts.practitioner_id
							}
							break
						case "check-availability":
						case "practitioner-list":
							scope.ctaBehavior = "sref"
							scope.stateName = "app.practitioner-list.view"
							if (scope.opts.vertical_ids) {
								let vids = _.isArray(scope.opts.vertical_ids)
									? scope.opts.vertical_ids.join(",")
									: scope.opts.vertical_ids // handle where vertical_ids can be comma separated string or array

								scope.stateParams = {
									vids: vids
								}
							}
							if (scope.opts.specialty_ids) {
								let specids = _.isArray(scope.opts.specialty_ids)
									? scope.opts.specialty_ids.join(",")
									: scope.opts.specialty_ids // handle where specialty_ids can be comma separated string or array
								scope.stateParams = {
									specialties: specids
								}
							}

							break
						case "message":
							if (!notAuthenticated) {
								var pracID =
									scope.opts.practitioner_id ||
									(theUser.care_coordinators[0] ? theUser.care_coordinators[0].id : "25159")
								Messages.newChannel(pracID).then(function(c) {
									scope.newChannel = c
									var onComplete = function() {
										ModalService.messageSent()
										evt = {
											event_name: "dynamic_cta_send_message_complete",
											user_id: theUser.id,
											practitioner_id: pracID
										}

										Plow.send(evt)
									}
									ModalService.newPractitionerMessage(scope.newChannel, onComplete)
								})
							} else {
								doLogin()
							}
							break
						case "link":
							scope.ctaBehavior = "url"
							break
						case "create-post":
							scope.ctaBehavior = "sref"
							scope.stateName = "app.forum.create-post"
							scope.stateParams = {
								community: scope.opts.community || null
							}
							break

						case "view-appointment":
							scope.ctaBehavior = "sref"
							scope.stateName = "app.appointment.my.list.appointment-detail"
							scope.stateParams = {
								appointment_id: scope.opts.appointment_id
							}
							break
						case "view-assessment":
							scope.ctaBehavior = "sref"
							scope.stateName = "app.assessments.one.view"
							scope.stateParams = {
								id: scope.opts.assessment_id,
								slug: scope.opts.assessment_slug
							}
							break
						case "take-ob-assessment":
							scope.ctaBehavior = "sref"
							scope.stateName = "app.onboarding.onboarding-assessment.one.take"
							scope.stateParams = {
								id: scope.opts.assessment_id,
								slug: scope.opts.assessment_slug,
								qid: 1
							}
							break
						case "view-channel":
							scope.ctaBehavior = "sref"
							scope.stateName = "app.messages-list.view.channel"
							scope.stateParams = {
								channel_id: scope.opts.channel_id
							}
							break
						case "add-birth":
							if (!notAuthenticated) {
								var onComplete = () => {
									$state.reload()
								}

								ModalService.gaveBirth(theUser, onComplete)
							} else {
								doLogin()
							}
							break
						case "dashboard":
							scope.ctaBehavior = "sref"
							scope.stateName = "app.dashboard"
							break
						case "program-transition":
						case "cancel":
							scope.ctaBehavior = "program-transition"
							break

						case "dismiss":
							scope.ctaBehavior = "dismiss"
							break
						default:
							console.log("No action type specified")
					}
					if (NATIVE_PLATFORM) {
						/* Wrangle our event into the format that iOS requires... */
						scope.opts.cta = scope.opts.cta || {}
						scope.opts.cta.text = scope.opts.cta.text ? scope.opts.cta.text : scope.opts.label || "Go"

						if (scope.opts.type === "practitioner-list") {
							scope.opts.type = "check-availability" // tech debt for naming this thing wrong before we released the app :D
						}

						if (scope.opts.type === "link") {
							scope.opts.cta.url = scope.opts.cta.url
								? scope.opts.cta.url
								: scope.opts.url || "https://www.mavenclinic.com"
						}

						NativeAppCommsService.sendMessage(scope.opts)
					} else {
						let evt = scope.eventObject || {
							event_name: scope.eventName || scope.opts.eventName || "dynamic_cta_tap",
							action_type: scope.opts.type
						}

						if (!notAuthenticated) {
							evt.user_id = theUser.id
						}
						Plow.send(evt)

						if (scope.ctaBehavior === "sref") {
							const isReact = $state.get(scope.stateName).react

							// We need to handle new React routes differently in order to properly capture and pass throught the URL params
							if (isReact) {
								const newPath = `/app${$state.href(scope.stateName)}`
								const params = scope.stateParams
								let fullNewUrl

								if (!!params && !_.isEmpty(params)) {
									// Yeasss way nicer to do this using Object.entries & .map but we don't have that babel polyfill added rn and not sure i want to dive down that rabbithole on this codebase... //SG
									const paramList = []

									for (let prop in params) {
										paramList.push(`${prop}=${params[prop]}`)
									}

									const formattedParams = paramList.join("&")

									fullNewUrl = `${newPath}?${formattedParams}`
								} else {
									fullNewUrl = newPath
								}

								// Redirect if we're not logged in, otherwise go straight to our new url
								if (notAuthenticated) {
									document.location = `/login?from=${encodeURIComponent(fullNewUrl)}`
								} else {
									document.location = fullNewUrl
								}
							} else {
								if (notAuthenticated) {
									let redirectTo = $state.href(scope.stateName, scope.stateParams, { absolute: true }) // we wanna go here post-login so encode the url that we extract from state params
									$state.go("auth.login", {
										from: encodeURIComponent(redirectTo)
									})
								} else {
									ngDialog.closeAll()
									$state.go(scope.stateName, scope.stateParams)
								}
							}
						}
						if (scope.ctaBehavior === "url") {
							let urlPath = scope.opts.cta && scope.opts.cta.url ? scope.opts.cta.url : scope.opts.url || null
							window.location = urlPath
						}

						if (scope.ctaBehavior === "program-transition") {
							let postCallback = scope.eventObject.postActionCallback

							Users.updateUserPrograms(theUser.id, scope.opts.subject).then(
								u => {
									scope.callActionCallback(postCallback)
								},
								e => {
									ngNotify.set(`Sorry... there seems to have been a problem. (${e.data.message})`, "error")
									console.log("Error with program transition...", e)
								}
							)
						}

						if (scope.ctaBehavior === "dismiss") {
							let postCallback = scope.eventObject.postActionCallback
							Users.dismissCard(theUser.id, scope.opts.subject).then(
								d => {
									scope.callActionCallback(postCallback)
								},
								e => {
									ngNotify.set(`Sorry... there seems to have been a problem. (${e.data.message})`, "error")
									console.log("Error dismissing card...", e)
								}
							)
						}
					}
				}

				// postCb is a string - for example "reload-dashboard" - which we can optionally pass in in order to trigger some other conditional action within our calling actionCallback fn (see: prompt service, dashboard block component)
				scope.callActionCallback = postCb => {
					// https://stackoverflow.com/a/29023391
					scope.actionCallback()(postCb)
				}

				scope.goToAction = () => {
					// check if logged in.. if not, open login modal & call the doAction fn on complete
					if (scope.user) {
						doAction(scope.user)
					} else {
						Users.getWithProfile().then(u => {
							if (u) {
								doAction(u)
							} else {
								doAction(scope.user, true) // set not authenticated (2nd) arg to true so we can act accordingly when we hit the ctas above
							}
						})
					}
				}
			},
			template:
				'<a href="" role="button" ng-click="goToAction()" aria-label="{{ arialabel }}" class="{{ btnclass }}">{{ btnCopy }}</a>'
		}
	}
])
