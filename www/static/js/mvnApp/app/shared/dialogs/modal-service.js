angular.module("app").factory("ModalService", [
	"$rootScope",
	"$state",
	"ngNotify",
	"ngDialog",
	"AuthService",
	"Users",
	"Session",
	"AssessmentService",
	"Plow",
	"AUTH_EVENTS",
	"UrlHelperService",
	function ($rootScope, $state, ngNotify, ngDialog, AuthService, Users, Session, AssessmentService, Plow, AUTH_EVENTS, UrlHelperService) {
		var modalService = {}

		modalService.closeModal = function (modalId) {
			if (modalId) {
				ngDialog.close(modalId)
			} else {
				ngDialog.closeAll()
			}
		}

		modalService.loginRegModal = function (completeFn, opts) {
			var loginRegDialog = ngDialog.open({
				name: "login-reg-modal",
				template: "/js/mvnApp/app/shared/dialogs/_unauth-dialog.html",
				className: "mvndialog authdialog",
				controller: [
					"$scope",
					function ($scope) {
						$scope.cb = completeFn
						$scope.formState = opts && opts.formState ? opts.formState : "register"
						$scope.loginGreeting = opts && opts.loginGreeting ? opts.loginGreeting : "Welcome back"
						$scope.registerGreeting = opts && opts.registerGreeting ? opts.registerGreeting : "Join the conversation"
						$scope.hideToggle = opts && opts.hideToggle

						$scope.toggleLoginReg = function (toggleTo) {
							$scope.formState = toggleTo
						}
					}
				]
			})

			return loginRegDialog
		}

		modalService.forceLoginModal = function (completeFn) {
			return ngDialog.open({
				template: "/js/mvnApp/app/shared/dialogs/_unauth-dialog.html",
				className: "mvndialog dialogdark authdialog",
				showClose: false,
				closeByDocument: false,
				closeByEscape: false,
				controller: [
					"$scope",
					function ($scope) {
						$scope.cb = completeFn
						$scope.formState = "login"
						$scope.loginGreeting = "Please sign in to continue"
						$scope.registerGreeting = "Create your account to get started"
						$scope.forceLogin = true
						$scope.toggleLoginReg = function (toggleTo) {
							$scope.formState = toggleTo
						}
					}
				]
			})
		}


		modalService.gaveBirth = function (user, onComplete) {
			return ngDialog.open({
				templateUrl: "/js/mvnApp/app/dashboard/shared/_gave-birth.html",
				className: "mvndialog",
				showClose: false,
				closeByDocument: false,
				closeByEscape: false,
				controller: [
					"$rootScope",
					"$scope",
					"Users",
					"Healthbinder",
					function ($rootScope, $scope, Users, Healthbinder) {
						var removeDueDate = function () {
							var toUpdate = {
								due_date: null
							}

							Healthbinder.updateHB(user.id, toUpdate).then(function (d) {
								ppSwitchComplete()
							})
						}

						var ppSwitchComplete = function () {
							Users.getWithProfile(true).then(function (newU) {
								$rootScope.$broadcast("updateUser", newU)
								$scope.user = newU
								$scope.addedChild = true
							})
						}

						$scope.cb = onComplete

						$scope.sexes = ["female", "male", "intersex"]

						$scope.doAddChild = function (childName, childDob, childGender) {
							var newChildData = {
								birthday: moment.utc([childDob.year, childDob.month - 1, childDob.day, 0, 0, 0]).format("YYYY-MM-DD"),
								name: childName,
								gender: childGender
							}

							Healthbinder.updateChild(user.id, newChildData).then(
								function (h) {
									$scope.err = false
									$scope.errMsg = ""
									removeDueDate()
								},
								function (e) {
									$scope.err = true
									$scope.errMsg = e.data.message
								}
							)
						}

						$scope.startNeedsAssessment = function () {
							ngDialog.close()
							AssessmentService.getAllAssessments({ type: "POSTPARTUM" }).then(
								assessments => {
									let assessment = assessments[0] // Hacky..
									$state.go("app.assessments.one.take", {
										id: assessment.id,
										slug: assessment.slug,
										qid: "2"
									})
								},
								e => {
									ngNotify.set("Sorry there seems to have been a problem", "error")
								}
							)
						}

						// Check this reloads
						$scope.doneWithPregnancy = function () {
							ngDialog.close()
							$state.go("app.dashboard", { reload: true })
							onComplete() // pass new user obj back
						}
					}
				]
			})
		}

		modalService.addUsername = function (theUser, onComplete, canClose) {
			return ngDialog.open({
				templateUrl: "/js/mvnApp/app/shared/dialogs/_add-username.html",
				className: "mvndialog",
				showClose: false,
				closeByDocument: false,
				closeByEscape: false,
				controller: [
					"$rootScope",
					"$scope",
					"Users",
					function ($rootScope, $scope, Users) {
						$scope.cb = onComplete
						var userToUpdate = theUser

						$scope.newUname = theUser.username ? theUser.username : null

						$scope.canClose = canClose

						$scope.updateUsername = function (uname) {
							var uNameUd = {
								first_name: userToUpdate.first_name,
								middle_name: userToUpdate.middle_name,
								last_name: userToUpdate.last_name,
								username: uname,
								email: userToUpdate.email,
								image_id: userToUpdate.image_id
							}

							Users.updateUserAccount(userToUpdate.id, uNameUd).then(
								function (u) {
									$scope.err = false
									$scope.errMsg = ""
									Users.getWithProfile(true).then(function (usr) {
										$rootScope.$broadcast("updateUser", usr)
										$scope.cb(usr)
										ngDialog.close()
									})
								},
								function (e) {
									$scope.err = true
									$scope.errMsg = e.data.message
									console.log(e)

									// Used to retrigger screenreader error reading
									const errorMsg = document.querySelector(".notify.error")
									errorMsg.setAttribute("role", "alert")

									setTimeout(() => {
										errorMsg.removeAttribute("role")
									}, 400)
								}
							)
						}
					}
				]
			})
		}

		modalService.newPractitionerMessage = function (messageChannel, completeFn, msgBody, msgStep) {
			return ngDialog.open({
				template: "/js/mvnApp/app/messages/dialogs/_new-message.html",
				className: "mvndialog",
				resolve: {
					msgCredits: [
						"Messages",
						function (Messages) {
							return Messages.getMessageCredits().then(function (c) {
								return c
							})
						}
					],
					msgProducts: [
						"Messages",
						function (Messages) {
							return Messages.getMessageProducts().then(function (mp) {
								return mp
							})
						}
					],
					messageChannel: function () {
						return messageChannel
					},
					msgStep: function () {
						return msgStep
					},
					msgBody: function () {
						return msgBody
					},
					completeFn: function () {
						return completeFn
					}
				},
				controller: [
					"$rootScope",
					"$scope",
					"$state",
					"Messages",
					"Payments",
					"ngNotify",
					"msgCredits",
					"msgProducts",
					"messageChannel",
					"msgBody",
					"msgStep",
					"completeFn",
					function (
						$rootScope,
						$scope,
						$state,
						Messages,
						Payments,
						ngNotify,
						msgCredits,
						msgProducts,
						messageChannel,
						msgBody,
						msgStep,
						completeFn
					) {
						var initMessage = () => {
							//Message steps: ['writeNew', 'showPackages', 'addCC', 'confirmCreditPurchase', 'confirmMessageSend'];
							$scope.msgSteps = {}
							$scope.msgSteps.step = msgStep ? msgStep : "writeNew"

							// Get available credits, if any
							$scope.msgCreditsAvail = msgCredits.available_messages
							$scope.msgProducts = msgProducts

							$scope.messageChannel = messageChannel

							// unfortunately we can't extendModel for single channel GET... so if we're grabbing this modal under those circumstanges, we may have to find the other participant ourselves..
							$scope.recipient = _.filter($scope.messageChannel.participants, function (participant) {
								return participant.user.id !== $scope.user.id
							})[0]

							// callback once we're done
							$scope.cb = completeFn

							// show billing / first free etc if user is not enterprise (or, later, subscriber)

							$scope.isPractitioner = $scope.user.role === "practitioner"
							const isEnterpriseUser = $scope.user.organization
							const isCampusUser = $scope.user.subscription_plans
							const isInternalMsg = $scope.messageChannel.internal

							const getsFreeMessaging = isEnterpriseUser || isCampusUser || isInternalMsg || $scope.isPractitioner

							$scope.billMessages = !getsFreeMessaging

							$scope.newMessage = msgBody ? { body: msgBody } : {}

							// If message isn't first message and is billable, check whether the user has message credits or not
							$scope.checkMessageCredits = function () {
								if ($scope.msgCreditsAvail > 0) {
									$scope.msgSteps.step = "confirmMessageSend"
								} else {
									$scope.msgSteps.step = "showPackages"
								}
							}

							$scope.selectMsgProd = function (msgProd) {
								$scope.loading = true
								$scope.msgProd = msgProd
								// See if the user has enough Maven credit available to purchase message credits
								Payments.getUserCredits($scope.user.id).then(function (credit) {
									$scope.err = false
									$scope.errorMsg = null
									$scope.userCredits = credit.meta.total_credit
									if (parseFloat($scope.userCredits) >= parseFloat($scope.msgProd.price)) {
										$scope.msgSteps.step = "confirmMessagePurchase"
										$scope.messagePurchaseMethod = $scope.msgProd.price + " of Maven credit"
									} else {
										// If credits won't cover it, check and see if our user has a credit card on file. If not, get them to add it...
										Payments.getUserPaymentMethod($scope.user.id).then(
											function (p) {
												if (!!p.data[0]) {
													$scope.msgSteps.step = "confirmMessagePurchase"
													$scope.messagePurchaseMethod = "card ending " + p.data[0].last4
												} else {
													$scope.msgSteps.step = "addCC"
												}
											},
											function (e) {
												$scope.hasPaymentMethod = false
												$scope.err = true
												$scope.errorMsg = e.data.message
											}
										)
									}
								})
							}

							$scope.stripeProcess = function (code, result) {
								if (result.error) {
									$scope.err = true
									$scope.errorMsg = result.error.message
								} else {
									Payments.addUserPaymentMethods($scope.user.id, { stripe_token: result.id }).then(
										function (d) {
											$scope.err = false
											$scope.errorMsg = null
											$scope.purchaseMessageCredits()
											ngNotify.set("Credits purchased successfully", "success")
											$scope.msgSteps.step = "confirmMessageSend"
										},
										function (e) {
											$scope.err = true
											$scope.errorMsg = e.data.message
										}
									)
								}
							}

							$scope.purchaseMessageCredits = function () {
								Messages.purchaseMessageCredits($scope.msgProd.id).then(
									function (p) {
										$scope.err = false
										$scope.errorMsg = null
										$scope.msgSteps.step = "confirmMessageSend"
									},
									function (e) {
										$scope.err = true
										$scope.errorMsg = e.data.message
									}
								)
							}

							$scope.sendMessage = function (msg) {
								$scope.messageIsSending = true
								Messages.sendMessage($scope.messageChannel.id, msg).then(
									function (m) {
										$scope.err = false
										$scope.errMsg = null
										ngDialog.close()
										$scope.messageIsSending = false
										// complete function we've passed in. We want to close this modal now as on the "complete" step we don't want the user to be able to "x" out of the current dialog, but force a refresh of the current state so we can update billing etc. And we dont want to do that for all steps here as we'd lose the message body etc.
										$scope.cb()
									},
									function (e) {
										$scope.err = true
										$scope.errorMsg = e.data.message
										$scope.messageIsSending = false
									}
								)
							}
						}

						$scope.onInit = () => {
							if ($scope.user) {
								initMessage()
							} else {
								Users.getWithProfile().then(u => {
									if (u) {
										$scope.user = u
										initMessage()
									} else {
										return
									}
								})
							}
						}

						$scope.onInit()
					}
				]
			})
		}

		modalService.messageSent = function () {
			return ngDialog.open({
				template: "/js/mvnApp/app/messages/dialogs/_message-sent.html",
				className: "mvndialog",
				showClose: false,
				closeByDocument: false,
				closeByEscape: false,
				controller: [
					"$scope",
					function ($scope) {
						$scope.closeMsgDialog = function () {
							ngDialog.close()
							$state.reload()
						}
					}
				]
			})
		}

		modalService.noteSharing = function () {
			return ngDialog.open({
				template: "/js/mvnApp/app/shared/dialogs/_note-sharing-info.html",
				className: "mvndialog",
				showClose: false,
				closeByDocument: false,
				closeByEscape: false,
				controller: [
					"$scope",
					function ($scope) {
						$scope.closeMsgDialog = function () {
							ngDialog.close()
							$state.reload()
						}
					}
				]
			})
		}

		modalService.needPrescription = function (searchReq) {
			var evt
			return ngDialog.open({
				template: "/js/mvnApp/app/shared/dialogs/_need-prescription.html",
				className: "mvndialog",
				controller: [
					"$scope",
					function ($scope) {
						$scope.searchReq = searchReq

						$scope.yesPrescription = function () {
							$scope.needsPrescription()
							evt = {
								event_name: "web_book_yes_wants_prescription",
								user_id: $scope.user.id
							}
							$scope.$emit("trk", evt)
						}

						$scope.dontKnowPrescription = function () {
							$scope.maybePrescription()
							evt = {
								event_name: "web_book_dont_know_if_wants_prescription",
								user_id: $scope.user.id
							}
							$scope.$emit("trk", evt)
						}

						$scope.needsPrescription = function () {
							$scope.searchReq.prescribe = true
							$scope.searchReq.show_prescribers = true
							ngDialog.close()
							$state.go("app.practitioner-list.view", $scope.searchReq)
						}

						$scope.maybePrescription = function () {
							$scope.searchReq.show_prescribers = true
							ngDialog.close()
							$state.go("app.practitioner-list.view", $scope.searchReq)
						}

						$scope.noPrescription = function () {
							ngDialog.close()
							$state.go("app.practitioner-list.view", $scope.searchReq)
							evt = {
								event_name: "web_book_doesnt_want_prescription",
								user_id: $scope.user.id
							}
							$scope.$emit("trk", evt)
						}
					}
				]
			})
		}

		modalService.notifyOfPracAvailability = function (prac) {
			var practitioner = prac

			return ngDialog.open({
				template: "/js/mvnApp/app/shared/dialogs/_notify-of-prac-availability.html",
				className: "mvndialog",
				controller: [
					"$scope",
					"Users",
					"Practitioners",
					function ($scope, Users, Practitioners) {
						$scope.notifyLoading = false
						$scope.practitioner = practitioner
						$scope.notifyForm = {}
						$scope.reqSubmitted = false

						var sendReq = function () {
							Practitioners.notifyOfAvailability()
								.post("", { practitioner_id: $scope.practitioner.id, note: $scope.notifyForm.note })
								.then(
									function (n) {
										$scope.err = false
										$scope.errMsg = ""
										$scope.reqSubmitted = true
										$scope.notifyLoading = false
									},
									function (e) {
										$scope.err = true
										$scope.errMsg = e.data.message
										$scope.notifyLoading = false
									}
								)
						}

						$scope.submitReq = function () {
							$scope.notifyLoading = true
							if ($scope.notifyForm.phone) {
								$scope.user.profiles.member.tel_number = $scope.notifyForm.phone
								Users.updateUserProfile($scope.user.id, $scope.user.profiles.member).then(function (u) {
									sendReq()
								})
							} else {
								sendReq()
							}
						}
					}
				]
			})
		}

		modalService.viewNeedsAssessmentAnswers = function (aType, aAnswers, aVersion) {
			return ngDialog.open({
				templateUrl: "/js/mvnApp/app/user/assessments/needs_assessment/_view-needs-assessment.html",
				className: "mvndialog",
				resolve: {
					questions: [
						"AssessmentService",
						function (AssessmentService) {
							return AssessmentService.getQuestions(aType, aVersion).then(function (q) {
								return q.data.questions
							})
						}
					]
				},
				controller: [
					"$scope",
					"AssessmentService",
					"questions",
					function ($scope, AssessmentService, questions) {
						var answers = aAnswers,
							naArray = [],
							qAnswer

						for (var i = questions.length - 1; i >= 0; i--) {
							qAnswer = _.find(answers, function (o) {
								if (o.id === questions[i].id) {
									return o
								}
							})

							if (qAnswer) {
								naArray.push({
									question: questions[i].body,
									id: questions[i].id,
									parent: questions[i].parent,
									answertype: questions[i].widget.type,
									answer: qAnswer
								})
							}
						}

						$scope.needsAssessment = naArray.reverse()
					}
				]
			})
		}

		modalService.assessmentPostComplete = (template, onComplete, autoAdvance) => {
			return ngDialog.open({
				templateUrl: "/js/mvnApp/app/user/assessments/templates/" + template + "/_complete.html",
				className: "dialog-full dialog-page-overlay ob-celebrate center",
				closeByDocument: false,
				closeByEscape: false,
				closeByNavigation: false,
				showClose: false,
				controller: [
					"$scope",
					"$interval",
					function ($scope, $interval) {
						$scope.percentDone = 0

						let randomIncrement = max => Math.floor(Math.random() * Math.floor(max))

						$scope.intervalFn = () => {
							$scope.percentDone = $scope.percentDone + Math.min(randomIncrement(7), 100 - $scope.percentDone)
							if ($scope.percentDone >= 100) {
								$scope.canProgress = true
								$scope.cancelInt()
								if (autoAdvance) {
									$scope.goProgress()
								}
							}
						}

						$scope.counterInterval = $interval($scope.intervalFn, 80)

						$scope.cancelInt = () => {
							if (angular.isDefined($scope.counterInterval)) {
								$interval.cancel($scope.counterInterval)
							}
						}
						$scope.goProgress = () => {
							onComplete()
							ngDialog.closeAll()
						}
						$scope.$on("destroy", function () {
							$scope.cancelInt()
						})
					}
				]
			})
		}

		modalService.exitAssessment = function (onComplete, aType, templateUrl) {
			return ngDialog.open({
				className: "mvndialog",
				templateUrl: templateUrl,
				controller: [
					"$scope",
					function ($scope) {
						var cb = onComplete
						$scope.doExit = function () {
							cb()
							ngDialog.close()
						}
					}
				]
			})
		}

		modalService.postExitAssessment = function (templateUrl, assessment, questionId) {
			return ngDialog.open({
				scope: false,
				templateUrl: templateUrl,
				controller: [
					"$scope",
					"$state",
					($scope, $state) => {
						$scope.goBack = () => {
							$state.go("app.assessments.one.take", {
								id: assessment.id,
								slug: assessment.slug,
								qid: questionId
							})
						}
					}
				],
				className: "mvndialog",
				showClose: true,
				closeByDocument: true,
				closeByEscape: true
			})
		}

		modalService.openPostDetail = function (post, cats) {
			ngDialog.open({
				scope: true,
				showClose: false,
				closeByEscape: false,
				closeByDocument: false,
				closeByNavigation: true,
				controller: [
					"$scope",
					function ($scope) {
						$scope.cats = cats
					}
				],
				className: "dialog-full dialog-page-overlay post-detail-modal",
				templateUrl: "/js/mvnApp/app/forum/detail/_post-detail-modal.html"
			})
		}

		modalService.editProfileImage = function (user, onComplete) {
			ngDialog.open({
				showClose: false,
				closeByEscape: false,
				closeByDocument: false,
				closeByNavigation: false,
				className: "dialog-full dialog-page-overlay profile-image-dialog",
				controller: [
					"$rootScope",
					"$scope",
					"ngNotify",
					"Images",
					"Users",
					function ($rootScope, $scope, ngNotify, Images, Users) {
						var cb = onComplete

						$scope.imguser = user

						var _updateUserImage = function (image_id) {
							$scope.imguser.image_id = image_id
							Users.updateUserAccount($scope.imguser.id, $scope.imguser).then(function (u) {
								_updateGlobalUser()
								ngNotify.set("Added your profile image! Looking good!", "success")
							})
						},
							_updateGlobalUser = function () {
								Users.getWithProfile(true).then(function (u) {
									$rootScope.$broadcast("updateUser", u)
									$scope.imguser = u
								})
							},
							_uploadPhoto = function (file) {
								$scope.uploadingPhoto = true
								Images.uploadImage(file).then(
									function (i) {
										_updateUserImage(i.id)
										$scope.toUpload = null
										$scope.uploadingPhoto = false
									},
									function (e) {
										$scope.uploadingPhoto = false
									}
								)
							}

						$scope.removePhoto = function () {
							_updateUserImage("0")
						}

						$scope.$watch("toUpload", function (newV, oldV) {
							if (newV) {
								if (newV !== oldV) {
									_uploadPhoto($scope.toUpload)
								}
							}
						})

						$scope.onComplete = onComplete
						$scope.doExit = function () {
							cb($scope.imguser)
							$scope.toUpload = null
							$scope.$destroy()
							ngDialog.close()
						}
					}
				],
				templateUrl: "/js/mvnApp/app/user/profile/shared/_user-profile-edit-image.html"
			})
		}

		modalService.showCareTeamInfo = function (pracs) {
			return ngDialog.open({
				className: "mvndialog",
				templateUrl: "/js/mvnApp/app/user/care-team/_care-team-info.html",
				controller: [
					"$scope",
					"Plow",
					function ($scope, Plow) {
						var pracName,
							pracVerticalArticle,
							pracVertical,
							pracInfo = [],
							evt

						var getPracVerticalArticle = function (vertical) {
							var vowels = ["a", "e", "i", "o", "u"]
							return vowels.indexOf(vertical[0].toLowerCase()) >= 0 ? "an" : "a"
						}

						for (var i = pracs.length - 1; i >= 0; i--) {
							pracName = pracs[i].first_name
							pracVertical = pracs[i].profiles.practitioner.verticals[0]
							pracVerticalArticle = getPracVerticalArticle(pracVertical)

							if (i === pracs.length - 1 && pracs.length > 1) {
								pracInfo.push("and " + pracName + ", " + pracVerticalArticle + " " + pracVertical + ", ")
							} else {
								pracInfo.push(pracName + ", " + pracVerticalArticle + " " + pracVertical + ", ")
							}
						}

						$scope.pracInfo = pracInfo.reverse()
						$scope.contactCXPrac = function () {
							ngDialog.close()
							evt = {
								event_name: "ent_careteam_click_contact_cx_re_book_intro_appt",
								user_id: $scope.user.id
							}
							Plow.send(evt)
						}
					}
				]
			})
		}

		modalService.showCoronaInfo = () => {
			return ngDialog.open({
				className: "mvndialog corona",
				templateUrl: "/js/mvnApp/app/dashboard/shared/_corona-modal.html",
				controller: [
					"$scope",
					function ($scope) {
						$scope.findProvider = () => {
							if ($scope.user.organization) {
								UrlHelperService.redirectToReact("/app/book?group=ent-Coronavirus%20support&term=coronavirus%20support")
							} else {
								UrlHelperService.redirectToReact("/app/book?group=Coronavirus%20Support&term=coronavirus%20support")
							}
						}
					}
				]
			})
		}

		modalService.showCareCoordinatorWelcome = function (user, moduleType) {
			return ngDialog.open({
				className: "mvndialog welcome",
				templateUrl: "/js/mvnApp/app/dashboard/shared/_ent-dash-care-coordinator-welcome.html",
				controller: [
					"$scope",
					function ($scope) {
						var cxPracId = user.care_coordinators[0] ? user.care_coordinators[0].id : "25159",
							evt

						$scope.moduleType = moduleType
						$scope.goBookWithCareC = function () {
							ngDialog.close()
							$state.go("app.practitioner-profile", { practitioner_id: cxPracId, openbook: true })
							evt = {
								event_name: "ent_click_book_intro_appointment_with_cc_post_ob",
								user_id: user.id,
								module: moduleType
							}

							Plow.send("trk", evt)
						}
					}
				]
			})
		}

		modalService.openBio = person => {
			return ngDialog.open({
				className: "mvndialog",
				templateUrl: "/js/mvnApp/public/team/_bio.html",
				controller: [
					"$scope",
					function ($scope) {
						$scope.person = person
					}
				]
			})
		}

		modalService.addPhoneNumber = function (onComplete) {
			return ngDialog.open({
				showClose: false,
				className: "mvndialog",
				templateUrl: `/js/mvnApp/app/shared/dialogs/_add-phone-number-for-sms-the-app.html`,
				controller: [
					"$rootScope",
					"$scope",
					"Users",
					function ($rootScope, $scope, Users) {
						var cb = onComplete

						$scope.userPhone = {}

						$scope.updatePhone = phoneForm => {
							Users.getWithProfile(true).then(function (newU) {
								newU.profiles.member.tel_number = phoneForm.tel_number
								Users.updateUserProfile($scope.user.id, newU.profiles.member).then(
									function (a) {
										$rootScope.$broadcast("updateUser", newU)
										$scope.user = newU
										$scope.err = false
										$scope.errorMsg = ""

										cb($scope.user)
										ngDialog.close()
									},
									function (e) {
										console.log(e)
										$scope.err = true
										$scope.errorMsg = JSON.parse(e.data.error.replace(/'/g, '"'))
									}
								)
							})
						}
					}
				]
			})
		}

		modalService.agreementsUpdateModal = (agreements, onComplete) => {
			return ngDialog.open({
				className: "mvndialog",
				templateUrl: "/js/mvnApp/app/shared/dialogs/_member-agreements-update.html",
				showClose: false,
				closeByEscape: false,
				closeByDocument: false,
				closeByNavigation: false,
				controller: [
					"$scope",
					"Agreements",
					($scope, Agreements) => {
						$scope.agreements = agreements
						$scope.agreeToAgreements = () => {
							$scope.isAgreeing = true
							const formattedAgreements = {
								agreements
							}
							Agreements.sendAgreement(formattedAgreements)
								.then(a => {
									ngDialog.closeAll()
									onComplete()
								})
								.catch(e => {
									console.log("Error updating agreements...")

									ngDialog.closeAll()
									onComplete()
								})
						}
					}
				]
			})
		}

		return modalService
	}
])
