function TakeAssessmentController(
	$rootScope,
	$window,
	$state,
	$timeout,
	ngNotify,
	Healthbinder,
	Users,
	AssessmentService,
	ModalService,
	Plow,
	NativeAppCommsService,
	NATIVE_PLATFORM,
	UrlHelperService
) {
	// vm.assessment = raw assessment object
	// vm.userAssessment = our custom assessment object, with answers constructed etc
	var vm = this,
		evt,
		thequestion = $state.params.qid, // question id from url params
		qversion,
		nextQ,
		qtype,
		hbToAdd = {},
		theQuestionId,
		rawQuestions,
		hbObj = {}

	// Default state for button is disabled... we update to not disabled if parent question is answered, but NOT child question... yet..........
	vm.btnDisabled = true

	vm.atype = qtype

	vm.noDatePicker = !Modernizr.inputtypes.date

	const _formatDate = date => {
		return moment.utc(date).format("YYYY-MM-DD")
	}

	var _mergeDate = function (d) {
		return moment.utc([d.year, d.month - 1, d.day, 0, 0, 0]).format("YYYY-MM-DD")
	}

	const _exitDashboard = () => {
		if (NATIVE_PLATFORM) {
			const msg = {
				type: "dashboard"
			}
			NativeAppCommsService.sendMessage(msg)
		}
		vm.triggerBack()
	}

	/* GET THE CURRENT QUESTION */
	// 'thequestion' is what we've grabbed from the url param
	var _setUpQuestion = function () {
		// get the question from the full assessment object, by id.
		vm.question = _.find(vm.userAssessment, function (a) {
			return a.id == thequestion
		})

		if (!vm.question) {
			ngNotify.set(`Oh no, that question (id: ${theQuestionId}) doesn't exist!`, "error")
			return
		}

		vm.questionState = {
			firstQ: vm.question.id == vm.userAssessment[0].id
		}

		vm.currProgress = AssessmentService._setUpProgressBar(vm.assessment.question_json.questions, vm.question.id)

		if (vm.question.widget.type === "color-callout-checkboxes-sectioned") {
			let cbSections = vm.question.widget.sections
			let cbOptions = vm.question.widget.options

			cbSections.forEach(section => {
				let sectionOptions = []

				section.items.forEach((item, index) => {
					sectionOptions.push(cbOptions.filter(option => option.value === item)[0])
				})

				section.options = sectionOptions
			})

			vm.checkboxSections = cbSections
		}

		evt = {
			event_name: "assessment_view_question_" + vm.assessment.type + "_" + "q" + vm.question.id + "_v" + qversion, // assessment_view_question_PREGNANCY_ONBOARDING_q2_v1
			question_id: vm.question.id,
			assessment_type: vm.assessment.type,
			user_id: vm.user.id
		}

		/* GET CHILD QUESTIONS */
		if (vm.question.children) {
			vm.childQuestions = AssessmentService._getChildQuestions(vm.question, vm.userAssessment)
			evt.has_child_questions = vm.childQuestions[0].id
		}

		Plow.send(evt)

		let currStatus = {
			showInfoOnExit:
				!vm.isComplete && (vm.assessment.question_json.attrs && vm.assessment.question_json.attrs.noexitwarn),
			progress: vm.currProgress,
			questionId: vm.question.id,
			isComplete: vm.isComplete
		}

		vm.updateStatus()(currStatus)
		vm.onChange()
	}

	/* DETERMINE WHICH QUESTION TO GO TO NEXT.... */
	var _getNext = function () {
		var nextQ, currQuestion

		// If this question has children, AND we've chosen the answer that corresponds to one of the children, use that question to determine the next steo
		if (vm.childQuestions && vm.shouldShowChild(vm.question)) {
			currQuestion = vm.childQuestions[0] // TODO... handle where multiple children... but for now, we only have 1 level of children so *kicks can*
		} else {
			// otherwise, just use the parent question
			currQuestion = vm.question
		}

		// If the current, main question has a "next'" property, just go to that...
		if (currQuestion.next) {
			if (currQuestion.next === "end") {
				vm.lastQ = true
			} else {
				vm.lastQ = false
			}
			return currQuestion.next
		} else {
			// if it doesnt have it's own "next" property, figure out where to go based on the user's selected answer, and corresponding "next" property from the questions options
			nextQ = _.find(currQuestion.widget.options, function (q) {
				if (q.value == currQuestion.answer.body) {
					return q.next
				}
			})

			if (nextQ) {
				if (nextQ.next === "end") {
					vm.lastQ = true
				} else {
					vm.lastQ = false
				}
				return nextQ.next
			} else {
				return
				//console.log('where do we go from here?', vm.question.id);
			}
		}
	}

	var _endAssessment = function () {
		let currStatus = {
			showInfoOnExit: false,
			progress: vm.currProgress,
			questionId: vm.question.id,
			isComplete: true
		}

		vm.updateStatus()(currStatus)

		evt = {
			event_name: "web_finish_assessment",
			user_id: vm.user.id,
			assessment_type: qtype
		}

		Plow.send(evt)
		Users.getWithProfile(true).then(function (u) {
			$rootScope.$broadcast("updateUser", u)
			let postCompleteAction = AssessmentService.getAttrs(vm.assessment).postComplete
			let postCompleteTemplate = AssessmentService.getAttrs(vm.assessment).template
			let postCompleteRedirect = () => {
				// IF NATIVE APP:
				if (NATIVE_PLATFORM && postCompleteAction.triggerNativeAction) {
					let msg = {
						type: "exit",
						link: $state.href(postCompleteAction.redirectPath, postCompleteAction.redirectParams, {
							absolute: true
						}),
						cta: {
							url: $state.href(postCompleteAction.redirectPath, postCompleteAction.redirectParams, {
								absolute: true
							})
						}
					}
					if (vm.assessment.updateFertilityStatus) {
						msg.selection = vm.question.answer.body
					}
					NativeAppCommsService.sendMessage(msg)
				} else {
					// For fertiltiy status assessment: User can transition to Pregnancy track
					if (vm.assessment.updateFertilityStatus) {
						const selection = vm.question.answer.body
						if (vm.question.answer.body === "successful_pregnancy") {
							Users.getUserTrack.then((tracks) => {
								const fertilityTrack = tracks.active_tracks.filter(track => track.name ==='fertility')
								const activeTrackID = fertilityTrack[0].id 
								Users.updateUserTrack(activeTrackID, "pregnancy").then(() =>
									UrlHelperService.redirectToReact("/app/dashboard")
								)
							})
						} else {
							UrlHelperService.redirectToReact(`/app/message-ca?type=fertility-status&selection=${selection}`)
						}
					} else {
						// ELSE... we ain't on a native app right now, Toto (or, we want to stick in webappworld for now)
						$state.go(postCompleteAction.redirectPath, postCompleteAction.redirectParams)
					}
				}
			}
			if (postCompleteAction.showLoader) {
				let doAutoAdvance = postCompleteAction.autoAdvance

				/* if referral type, do not show meet your care provider page */
				if (qtype.includes('REFERRAL')) {
					postCompleteRedirect()
				} else {
					ModalService.assessmentPostComplete(postCompleteTemplate, postCompleteRedirect, doAutoAdvance)
				}
			} else {
				postCompleteRedirect()
			}
		})
	}

	/* ADVANCE TO THE NEXT QUESTION */
	var _goToNextQuestion = function () {
		nextQ = _getNext()
		if (nextQ === "end") {
			_endAssessment()
		} else {
			// if our assessment type is onboarding, use the "by id" method to get their assessment. if not, use the "by type"
			if (/_ONBOARDING/.test(vm.assessment.type)) {
				$state.go("app.onboarding.onboarding-assessment.one.take", {
					type: qtype,
					qid: nextQ,
					id: vm.assessment.id,
					slug: vm.assessment.slug
				})
			} else {
				$state.go("app.assessments.one.take", { type: qtype, qid: nextQ })
			}
		}
	}

	var _saveNewAssessment = function (req) {
		AssessmentService.sendAnswers(vm.user.id, req).then(
			function (a) {
				_goToNextQuestion()
			},
			function (e) {
				console.log(e)
			}
		)
	}

	var _updateAssessment = function (req) {
		AssessmentService.updateAnswers(vm.user.id, req.needs_assessment_id, req).then(
			function (a) {
				_goToNextQuestion()
			},
			function (e) {
				console.log(e)
			}
		)
	}

	/* LET'S GOOOOO */
	let getAssessmentAnswers = rawQuestions => {
		//raw questions: arr of questions, with empty answers property
		AssessmentService.getUserAssessments(vm.user.id, {
			assessment_id: vm.assessment.id
		}).then(
			function (a) {
				if (a[0]) {
					// while we're being all hacky and not caring if the user has >1 needs assessment, just get the newest one... hashtagYolo
					vm.answers = a[a.length - 1].answers
					vm.isComplete = a[a.length - 1].meta.completed
					vm.userAssessmentId = a[a.length - 1].meta.id // User needs_assessment ID .. !== assessment.id (one assessment can have multiple needs assessments)
					qversion = a[a.length - 1].meta.version // If the user has completed this assessment, make sure we use that for assessment version
				} else {
					qversion = vm.assessment.meta.version
				}

				vm.userAssessment = AssessmentService._setUpAssessmentAnswers(rawQuestions, vm.answers, vm.noDatePicker) // add user's answers to empty assessment

				// Now we have our populated userAssessment object.. we move on to setting up the question..
				_setUpQuestion()
			},
			function (e) {
				console.log(e)
				return false
			}
		)
	}

	/* ng-show filter for showing child questions based on parent answer value. */
	vm.shouldShowChild = function (q) {
		var reqValues

		if (q && q.children) {
			for (var i = q.children.length - 1; i >= 0; i--) {
				reqValues = q.children[i].requiredValues
				return reqValues.indexOf(q.answer.body) >= 0
			}
		}
	}

	/* SAVE THE ANSWER(s) */
	vm.saveAnswers = function () {
		var req = {
			answers: [],
			meta: {
				completed: vm.isComplete,
				type: vm.assessment.type,
				assessment_id: vm.assessment.id, // The ID of the assessment - NOT the user's needs_assessment
				version: qversion,
				healthbinder: hbToAdd
			}
		}

		for (var i = vm.userAssessment.length - 1; i >= 0; i--) {
			if (vm.userAssessment[i].answer.body) {
				if (vm.userAssessment[i].widget.type === "date") {
					if (vm.noDatePicker) {
						vm.userAssessment[i].answer.body = _mergeDate(vm.userAssessment[i].answer.body)
						req.answers.push(vm.userAssessment[i].answer)
					} else {
						// we have to manually insert this answer (vs just setting & doing req.answers.push(vm.userAssessment[i].answer) otherwise ng-model throws an error about expecting a date object. So we update what we send to the server but not the UI value.
						let formattedAnswer = {
							id: vm.userAssessment[i].answer.id,
							body: _formatDate(vm.userAssessment[i].answer.body)
						}
						req.answers.push(formattedAnswer)
					}
				} else {
					req.answers.push(vm.userAssessment[i].answer)
				}
				if (vm.userAssessment[i].healthbinder) {
					let hbKey = vm.userAssessment[i].healthbinder.name,
						hbValue = vm.userAssessment[i].answer.body

					if (hbValue.length || !_.isEmpty(hbValue) || (hbValue instanceof Date && !isNaN(hbValue))) {
						// create healthbinder obj to send to HB service
						if (hbValue instanceof Date) {
							hbValue = _formatDate(hbValue)
						}
						if (hbKey === "children") {
							// if we're trying to save a child to helathbinder, gotta format it as an object and add to an array
							let newChildData = formatNewChild(hbValue)
							hbObj[hbKey] = [newChildData]
						} else {
							if (hbValue instanceof Date) {
								hbValue = _formatDate(hbValue)
							}

							hbObj[hbKey] = hbValue
						}
					}
				}

				if (vm.userAssessment[i].widget.options) {
					for (var s = vm.userAssessment[i].widget.options.length - 1; s >= 0; s--) {
						if (vm.userAssessment[i].widget.options[s].healthbinder) {
							// save hbObj to send to HB service

							let hbKeyName = vm.userAssessment[i].widget.options[s].healthbinder.name

							// if we're trying to save a child to healthbinder, gotta format it as an object and add to an array
							if (hbKeyName === "children") {
								let newChildData = {
									children: formatNewChild(vm.userAssessment[i].answer.body.children)
								}
								hbObj["children"] = [newChildData]
							} else {
								let hbPropName = vm.userAssessment[i].widget.options[s].healthbinder.name
								let hbPropValue = vm.userAssessment[i].answer.body[hbPropName]

								if (hbPropValue) {
									hbObj[hbPropName] = vm.userAssessment[i].answer.body[hbPropName]
								}
							}
						}
					}
				}
			}
			// console.log(hbObj)
		}

		evt = {
			event_name: "web_assessment_save_answers",
			question_id: vm.question.id,
			user_id: vm.user.id
		}

		Plow.send(evt)

		if (vm.lastQ) {
			req.meta.completed = true
		}

		if (Object.keys(hbObj).length >= 1) {
			Healthbinder.updateHB(vm.user.id, hbObj)
				.then(h => {
					saveOrUpdateAssessment(req)
				})
				.catch(e => {
					console.log(e)
					ngNotify.set(e.data.message, "error")
				})
		} else {
			saveOrUpdateAssessment(req)
		}
	}

	const formatNewChild = data => {
		return {
			birthday: moment.utc(data).format("YYYY-MM-DD"),
			name: "Child"
			//gender: childGender
		}
	}

	const saveOrUpdateAssessment = req => {
		if (vm.answers) {
			//PUT new answers to existing assessment
			req.needs_assessment_id = vm.userAssessmentId
			_updateAssessment(req)
		} else {
			// no answers? cool. let's POST us a new assessment.
			_saveNewAssessment(req)
		}
		vm.submitting = true
	}

	var screenIsValid = function () {
		let parentIsValid = vm.question.answer.body && vm.assessmentParentAnswer.$valid

		// If we have child questions, use those to decide if our screen is valid
		// So. Much. Ugh. TODO: why the fuck is vm.assessmentChildAnswer.$valid not a thingggg. grrr.
		if (vm.question.children) {
			if (parentIsValid) {
				if (vm.shouldShowChild(vm.question)) {
					if (vm.childQuestions[0].answer.body) {
						if (vm.childQuestions[0].widget.type === "date" && vm.noDatePicker) {
							if (vm.noDatePicker) {
								if (
									vm.childQuestions[0].answer.body.day &&
									vm.childQuestions[0].answer.body.month &&
									vm.childQuestions[0].answer.body.year
								) {
									return true
								}
							} else {
								return vm.childQuestions[0].answer.body instanceof Date && !isNaN(vm.childQuestions[0].answer.body)
							}
						} else {
							return vm.childQuestions[0].answer.body
						}
					}
				} else {
					return true
				}
			} else {
				return false
			}

			// otherwise if no children, check if question itself is required
		} else if (vm.question.required) {
			if (vm.question.widget.type === "freetextmulti") {
				return AssessmentService._isFreeTextMultiValid(vm.question)
			} else if (vm.question.widget.type === "color-callout-checkboxes-sectioned") {
				return AssessmentService._isColorCalloutCheckboxesSectionedValid(vm.question)
			} else if (vm.question.widget.type === "c-quiz-question") {
				return AssessmentService._isCQuizValid(vm.question)
			} else {
				return parentIsValid
			}
		} else if (vm.question.widget.type === "c-quiz-question") {
			return AssessmentService._isCQuizValid(vm.question)
		} else {
			return true
		}
	}

	// Use this to proactively determine the next step - and use to update button copy to "finish" at the last step
	vm.onChange = function () {
		let callTimeout = () => {
			_getNext()
			vm.btnDisabled = !screenIsValid()
		}
		$timeout(callTimeout, 50)
	}

	/**
	 * Set focus on the main heading within assessments (onboarding and quizzes)
	 * so screenreaders skip and read the most relevant content.
	 */
	vm.focusMainHeading = function () {
		$timeout(() => {
			const heading = document.querySelector('.assessments-main-heading');
			if (heading) {
				heading.focus();
			}
		}, 0);
	}

	vm.onAnswerClick = function (opt) {
		if (vm.question.answered) {
			return;
		}

		vm.question.answer.body = opt.value;

		vm.onChange();
	}

	let _isAnswerCorrect = q => {
		return q.widget.solution.value.indexOf(q.answer.body) >= 0
	}

	vm.optionIsCorrect = (question, opt) => {
		return question.widget.solution.value.indexOf(opt) >= 0
	}

	vm.showAnswer = function () {
		vm.question.answered = true
		vm.isCorrect = _isAnswerCorrect(vm.question)
		vm.focusMainHeading();
	}
	vm.updateMultiAnswer = function (question, ansIndex, ans) {
		if (question.answer.body && question.answer.body[ansIndex]) {
			question.answer.body[ansIndex] = ans
		} else {
			question.answer.body[ansIndex] = ""
		}
		vm.onChange()
	}

	vm.multiAnswerIsSelected = function (question, ansIndex, ans) {
		return question.answer.body && question.answer.body[ansIndex] === ans
	}

	vm.$onInit = function () {
		vm.isNative = NATIVE_PLATFORM
		vm.submitting = false
		vm.assessmentParentAnswer = {}
		vm.showTooltip = true
		vm.showTermsAndPolicyLinks = true
		vm.showBackBtn = false
		vm.nextBtnCopy = "Next"
		vm.goBackHandler = vm.triggerBack
		AssessmentService.setBodyClass(vm.assessment.type)

		qtype = vm.assessment.type

		if (vm.assessment.updateFertilityStatus) {
			vm.showBackBtn = true
			vm.showTermsAndPolicyLinks = false
			vm.nextBtnCopy = "Save"
			vm.goBackHandler = _exitDashboard
		}

		rawQuestions = AssessmentService._setUpQuestions(vm.assessment) // gives us array of questions with empty answer properties as arr/obj to be populated where necessary appended

		if (!$state.params.qid) {
			theQuestionId = rawQuestions[0].id
		} else {
			theQuestionId = $state.params.qid
		}

		let theQuestion = _.find(rawQuestions, function (a) {
			return a.id == theQuestionId
		})

		vm.question = theQuestion ? theQuestion : rawQuestions[0]

		vm.loading = false
		getAssessmentAnswers(rawQuestions)

		/**
		 * - On mobile + tablet, `onboarding-container` is the scrollable element
		 * - On desktop, window is the scrollable element
		 */
		const container = document.querySelector('.onboarding-container')
		if (container) {
			container.scrollTop = 0
		}
		$window.scrollTo(0, 0)
	}

	vm.$onChanges = changes => {
		if (changes.assessment && vm.assessment) {
			let theTemplate = AssessmentService.getAttrs(vm.assessment).template
			vm.templateUrl = "/js/mvnApp/app/user/assessments/templates/" + theTemplate + "/_take-assessment.html"
			vm.questionTemplateUrl = "/js/mvnApp/app/user/assessments/templates/" + theTemplate + "/_question.html"
		}
	}

	vm.$onDestroy = () => {
		//_onExit();
	}
}

angular.module("app").component("takeAssessment", {
	template: '<div ng-include="$ctrl.templateUrl">',
	controller: TakeAssessmentController,
	bindings: {
		user: "<",
		assessment: "<",
		updateStatus: "&",
		triggerBack: "&"
	}
})
