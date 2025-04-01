angular.module("app").directive("mvnNeedsAssessment", [
	"AssessmentService",
	function(AssessmentService) {
		return {
			scope: {
				quiztype: "@",
				uid: "=",
				appt: "=",
				version: "="
			},
			link: function(scope, elm, attrs) {
				scope.loading = true
				var quiz = []

				AssessmentService.getQuestions(scope.quiztype).then(
					function(q) {
						scope.questions = q.data.questions
						scope.assessmentVersion = q.data.meta.version

						if (scope.questions) {
							scope.others = []
							scope.completed = false

							var answerBody

							for (var i = scope.questions.length - 1; i >= 0; i--) {
								quiz[i] = scope.questions[i]

								answerBody = quiz[i].widget.type === "multiselect" ? [] : null

								quiz[i].answer = {
									id: quiz[i].id,
									body: answerBody
								}
							}
							scope.loading = false
							scope.quiz = quiz
						} else {
							scope.loading = false
							scope.quiz = null
						}
					},
					function(e) {
						scope.quiz = null
						scope.loading = false
						console.log(e)
					}
				)

				// filter to show/hide child questions
				scope.notApplicable = function(q) {
					var pq
					if (q.parent) {
						pq = _.find(scope.quiz, function(o) {
							return o.id === q.parent.id
						})
						if (pq.answer.body !== q.parent.requiredValue) {
							return true
						}
					}
				}
				scope.saveAnswers = function(quiz, isComplete) {
					var completed = isComplete ? true : false,
						req = {
							answers: [],
							meta: {
								completed: completed,
								type: scope.quiztype,
								appointment_id: scope.appt.id
							}
						}

					if (scope.assessmentVersion) {
						req.meta.version = scope.assessmentVersion
					}

					for (var q in quiz) {
						if (quiz.hasOwnProperty(q)) {
							if (quiz[q].answer.body && quiz[q].answer.body.length >= 1) {
								req.answers.push(quiz[q].answer)
							}
						}
					}

					AssessmentService.sendAnswers(scope.appt.member.id, req).then(
						function(a) {
							scope.completed = true
						},
						function(e) {
							console.log(e)
						}
					)
				}
			},
			templateUrl: "/js/mvnApp/app/user/assessments/needs_assessment/_needs-assessment-form.html"
		}
	}
])
