angular.module("mavenApp").factory("AssessmentService", [
	"$rootScope",
	"Restangular",
	"$http",
	function($rootScope, Restangular, $http) {
		const assessmentService = {}

		// All available assessments - agnostic of whether user has taken or not
		// GET /assessments{?type,version,module,phase,include_json}
		assessmentService.getAllAssessments = req => {
			return Restangular.all("assessments").getList(req)
		}

		// Get an assessment by ID
		// GET /assessments/{id}
		assessmentService.getAssessment = (id, req) => {
			return Restangular.one("assessments", id).get(req)
		}

		// Get user-specfic instances of assessment(s) that a user has started|completed
		// GET /users/{id}/assessments{?type,version,appointment_id}]
		assessmentService.getUserAssessments = (uid, req) => {
			return Restangular.one("users", uid)
				.all("assessments")
				.getList(req)
		}

		// Send answers for the first time
		// POST /users/{user_id}/assessments
		assessmentService.sendAnswers = (uid, req) => {
			return Restangular.one("users", uid).customPOST(req, "assessments", {}, {})
		}

		// Edit or add additional answers
		// PUT [/users/{user_id}/assessments/{assessment_id}]
		assessmentService.updateAnswers = (uid, needs_assessment_id, req) => {
			return Restangular.one("users", uid).customPUT(req, "assessments/" + needs_assessment_id, {}, {})
		}

		/* Legacy get json files - for preg needs assessment */
		assessmentService.getQuestions = (assessmentName, assessmentVersion) => {
			var aName = assessmentName,
				aVersion = assessmentVersion ? assessmentVersion : "latest"
			return $http.get("/_app_support/assessments/" + aName + "/" + aVersion + ".json")
		}

		// Hacky getting of template based on assessment type
		assessmentService.getAttrs = assessment => {
			let assessmentType = assessment.type

			if (/_ONBOARDING/.test(assessmentType)) {
				if (assessment.updateFertilityStatus) {
					return {
						template: "onboarding",
						postComplete: {
							triggerNativeAction: true
						}
					}
				}
				
				let attrs = assessment.question_json.attrs
				if (attrs) {
					let redir
					switch (attrs.redirect) {
						case "dashboard":
							redir = "app.dashboard"
							break

						default:
							redir = "app.dashboard"
							break
					}

					return {
						template: "onboarding",
						postComplete: {
							redirectPath: redir,
							triggerNativeAction: attrs.exitmob
						}
					}
				}
				return {
					template: "onboarding",
					postComplete: {
						redirectPath: "app.react-careteam",
						showLoader: false,
						triggerNativeAction: false
					}
				}
			} else if (assessmentType === "POSTPARTUM") {
				return {
					template: "self-assessment",
					postComplete: {
						redirectPath: "app.dashboard",
						showLoader: true,
						autoAdvance: true,
						triggerNativeAction: true // Whether we call a native app action on complete, for example to trigger "exit" or some other kick-back-to-native thing. If not, we'll carry on handling links within the webapp (here).
					}
				}
			} else if (assessmentType === "M_QUIZ") {
				return {
					template: "mquiz",
					postComplete: {
						redirectPath: "app.assessments.one.results",
						redirectParams: {
							id: assessment.id,
							slug: assessment.slug
						},
						triggerNativeAction: false
					}
				}
			} else if (assessmentType === "E_QUIZ") {
				return {
					template: "equiz",
					postComplete: {
						redirectPath: "app.assessments.one.results",
						redirectParams: {
							id: assessment.id,
							slug: assessment.slug
						},
						triggerNativeAction: false
					}
				}
			} else if (assessmentType === "C_QUIZ") {
				return {
					template: "cquiz",
					postComplete: {
						redirectPath: "app.assessments.one.results",
						redirectParams: {
							id: assessment.id,
							slug: assessment.slug
						},
						triggerNativeAction: false
					}
				}
			} else {
				return {
					template: "onboarding", // ooor a generic type?? later we'll just return assessmentType
					postComplete: {
						redirectPath: "app.dashboard",
						showLoader: true,
						triggerNativeAction: false
					}
				}
			}
		}

		/* Assessment helpers */

		assessmentService.setBodyClass = assessmentType => {
			if (/_QUIZ/.test(assessmentType)) {
				//wooooo hackyyyyyy

				$rootScope.setPageData({
					bodyClass: "assessments page-quiz"
				})
			}
		}

		assessmentService.setBodyClass = assessmentType => {
			/* for REFERRAL_REQUEST and REFERRAL_FEEDBACK assessment types, add the onboarding classes below but hide onboarding progress header */
			if (assessmentType.includes('REFERRAL')) {
				//wooooo hackyyyyyy

				$rootScope.setPageData({
					bodyClass: "assessments page-onboarding-assessment page-onboarding"
				})
			}
		}

		assessmentService._setUpQuestions = a => {
			let theAssessment = [],
				assessmentQuestions = a.question_json.questions // TODO - catch where empty

			if (assessmentQuestions) {
				var answerBody

				// for each question, add an `answers` property that we'll populate later. if multiple answers per question possible, make answer an empty array.
				for (var i = assessmentQuestions.length - 1; i >= 0; i--) {
					theAssessment[i] = assessmentQuestions[i]
					answerBody = theAssessment[i].widget.type === "multiselect" ? [] : null
					theAssessment[i].answer = {
						id: theAssessment[i].id,
						body: answerBody
					}
				}

				return theAssessment
			} else {
				console.log("no questions....")
				return
			}
		}

		/* Get all child questions in the assessment */
		assessmentService._getAllChildQuestions = questions => {
			var childQuestionIds = []
			for (var i = questions.length - 1; i >= 0; i--) {
				if (questions[i].hasOwnProperty("children")) {
					for (var c = questions[i].children.length - 1; c >= 0; c--) {
						childQuestionIds.push(questions[i].children[c].id)
					}
				}
			}
			return childQuestionIds
		}

		/* Get all top level questions - so we can use this for progress bar etc */
		assessmentService._getTopLevelQuestions = questions => {
			var topLevelQuestionIds,
				allQuestionIds = [],
				childQs = assessmentService._getAllChildQuestions(questions)

			for (var i = questions.length - 1; i >= 0; i--) {
				allQuestionIds.push(questions[i].id)
			}
			topLevelQuestionIds = _.difference(allQuestionIds, childQs).sort(function(a, b) {
				return a - b
			})
			return topLevelQuestionIds
		}

		assessmentService._setUpProgressBar = (theQuestions, currQId) => {
			let topLevelQuestions = assessmentService._getTopLevelQuestions(theQuestions)
			let maxQ = topLevelQuestions[topLevelQuestions.length - 1]
			let currProgress = (topLevelQuestions.indexOf(currQId) / topLevelQuestions.indexOf(maxQ)) * 100
			return currProgress
		}

		assessmentService._isFreeTextMultiValid = theQuestion => {
			// well goddamn. what fun.
			if (_.isEmpty(theQuestion.answer.body)) {
				return false
			} else {
				let requiredFields = _.filter(theQuestion.widget.options, "required")
				if (requiredFields.length) {
					let validFields = 0
					for (var i = requiredFields.length - 1; i >= 0; i--) {
						if (
							theQuestion.answer.body[requiredFields[i].value] ||
							(typeof theQuestion.answer.body[requiredFields[i].value] === "number" &&
								theQuestion.answer.body[requiredFields[i].value] >= 0)
						) {
							validFields++
						}
					}
					return requiredFields.length === validFields
				}
			}
		}

		assessmentService._isColorCalloutCheckboxesSectionedValid = theQuestion => {
			return theQuestion.required && theQuestion.answer.body ? theQuestion.answer.body.filter(a => a).length : false
		}

		assessmentService._isCQuizValid = theQuestion => {
			return theQuestion.answer.body !== null && theQuestion.answer.body > -1 // wowowow in case you're wondering why this looks so stupid, it's because null > -1 evaluates to *true* #blessed
		}

		/* IF OUR QUESTION HAS CHILD QUESTIONS, SET THOSE UP... */
		assessmentService._getChildQuestions = function(question, rawQuestions) {
			//rawquestions
			var childQuestions = [],
				c
			for (var i = question.children.length - 1; i >= 0; i--) {
				c = _.find(rawQuestions, function(a) {
					return a.id == question.children[i].id
				})
				childQuestions.push(c)
			}
			return childQuestions
		}

		/* SET UP THE ASSESSMENT */
		assessmentService._setUpAssessmentAnswers = function(rQuestions, aAnswers, noDatePicker) {
			var questions = rQuestions

			for (var q = questions.length - 1; q >= 0; q--) {
				if (questions[q].widget.type === "freetextmulti") {
					questions[q].answer.body = {}
					for (var o = questions[q].widget.options.length - 1; o >= 0; o--) {
						questions[q].answer.body[questions[q].widget.options[o].value] = ""
					}
				}

				if (
					questions[q].widget.type === "panel-multi-choice-sectioned" ||
					questions[q].widget.type === "color-callout-checkboxes-sectioned"
				) {
					questions[q].answer.body = []
					for (var m = questions[q].widget.options.length - 1; m >= 0; m--) {
						questions[q].answer.body.push("")
					}
					if (questions[q].widget.other) {
						questions[q].answer.body.push("")
					}
				}
			}

			// If we have answers already, append those to the main questions object.
			if (aAnswers) {
				var answers = aAnswers,
					qAnswer

				for (var i = questions.length - 1; i >= 0; i--) {
					qAnswer = _.find(answers, function(o) {
						if (o.id === questions[i].id) {
							return o
						}
					})

					if (qAnswer) {
						if (questions[i].widget.type === "date" && !_.isEmpty(questions[i].body)) {
							if (noDatePicker) {
								questions[i].answer.body = {
									day: moment(qAnswer.body).format("DD"),
									month: moment(qAnswer.body).format("MM"),
									year: moment(qAnswer.body).format("YYYY")
								}
							} else {
								questions[i].answer.body = new Date(moment(qAnswer.body).utc())
							}
						} else {
							questions[i].answer.body = qAnswer.body
						}
					}
				}
			}
			return questions
		}

		return assessmentService
	}
])
