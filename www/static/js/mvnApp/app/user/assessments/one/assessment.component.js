function AssessmentController(
	$rootScope,
	$window,
	$state,
	Users,
	UrlHelperService,
	AssessmentService,
	ModalService,
	Plow,
	NativeAppCommsService,
	NATIVE_PLATFORM
) {
	var vm = this,
		evt,
		assessmentId = $state.params.id,
		exitWarnTemplateUrl,
		exitInfoTemplateUrl

		const getUserFlags = () => {
			Users.getWithProfile().then((u) => {
				vm.flags = u.flags;
			})
		}

	let setUpQuestions = (assessmentId, onComplete) => {
		AssessmentService.getAssessment(assessmentId, { include_json: true }).then(
			function(a) {
				const { slug } = a
				if (slug) {
					UrlHelperService.redirectToReact(`/app/assessments/${slug}`)
				}
				if (a) {
					onComplete(a)
				} else {
					console.log("No assessment with that id...")
				}
			},
			function(e) {
				console.log("error", e)
			}
		)
	}

	let _goBack = () => {
		// UGH this is a terrible way to do this. But hella complicated to do one of the other options....
		// get either question that has that question id as top-level next...
		// or if that doesnt exist... we have to find child questions with that as an option THEN get that question's parent id??? noooooooo........
		// or use some kind of ui-router hack to get prev.....? ughhhhh.
		// TODO if/when we allow people to click into an individual question by id to edit... or something...
		/* var tlQuestions = _getTopLevelQuestions(vm.assessment),
			currQ =  topLevelQuestions.indexOf(vm.question.id),
			prevId = topLevelQuestions[currQ -1];
			$state.go('app.assessments.one.take', {qtype: qtype, qid: prevId});
		*/
		/// Buuuut this doesn't work with the "next" concept. goddammit. TODO: how to get thsi working when, for example your "prev" question is 5 questions ago?

		$window.history.back() //ugh.
	}

	let _onExit = () => {
		vm.currentStatus.showInfoOnExit = false // We're manually exiting, so don't need the hail-mary warning

		if (vm.currentStatus.isComplete) {
			Users.getWithProfile(true).then(function(u) {
				$rootScope.$broadcast("updateUser", u)
				evt = {
					event_name: "web_exit_completed_assessment",
					question_id: vm.currentStatus.questionId,
					user_id: vm.user.id
				}

				Plow.send(evt)

				// CALL NATIVE APP FUNCTION
				if (NATIVE_PLATFORM) {
					let msg = {
						type: "exit"
					}
					NativeAppCommsService.sendMessage(msg)
				} else {
					$state.go("app.dashboard")
				}
			})
		} else {
			var onComplete = function() {
				evt = {
					event_name: "web_exit_incomplete_assessment",
					question_id: vm.currentStatus.questionId,
					user_id: vm.user.id
				}

				Plow.send(evt)

				if (NATIVE_PLATFORM) {
					let msg = {
						type: "exit"
					}
					NativeAppCommsService.sendMessage(msg)
				} else {
					Users.getWithProfile(true).then(function(u) {
						$rootScope.$broadcast("updateUser", u)
					})
				}
			}

			ModalService.exitAssessment(onComplete, vm.assessment.type, exitWarnTemplateUrl)
		}
	}

	vm.$onInit = function() {
		vm.loading = true
		vm.currentStatus = {}
		getUserFlags()

		let onComplete = assessment => {
			vm.assessment = assessment
			vm.loading = false
			vm.showProgressHeader = true
			// We're reusing type FERTILITY_ONBOARDING for our Fertility Status assessment
			vm.assessment.updateFertilityStatus = vm.assessment.type === 'FERTILITY_ONBOARDING' && vm.assessment.title.toLowerCase().includes("status")

			if (vm.assessment.updateFertilityStatus) {
				vm.showProgressHeader = false
				vm.hideMobileHeader = true
			}

			if (vm.assessment.type.includes('REFERRAL')) {
				vm.showProgressHeader = false
			}

			const templatePath =
				"/js/mvnApp/app/user/assessments/templates/" + AssessmentService.getAttrs(vm.assessment).template
			exitWarnTemplateUrl = templatePath + "/_exit-warn.html"
			exitInfoTemplateUrl = templatePath + "/_exit-info.html"
			vm.templateUrl = templatePath + "/_assessment.html"
		}

		if (!assessmentId) {
			vm.loading = false
			console.log("need an assessment ID")
		} else {
			setUpQuestions(assessmentId, onComplete)
		}
	}

	vm.updateStatus = newStatus => {
		vm.currentStatus = newStatus
		vm.progress = newStatus.progress
	}

	vm.triggerBack = () => {
		_goBack()
	}

	vm.triggerExit = () => {
		_onExit()
	}

	vm.$onDestroy = () => {
		if (vm.currentStatus.showInfoOnExit) {
			if (NATIVE_PLATFORM) {
				let msg = {
					type: "exit"
				}
				NativeAppCommsService.sendMessage(msg)
			} else {
				ModalService.postExitAssessment(exitInfoTemplateUrl, vm.assessment, vm.currentStatus.questionId)
			}
		}
	}
}

angular.module("app").component("assessment", {
	template: '<div ng-include="$ctrl.templateUrl">',
	controller: AssessmentController,
	bindings: {
		user: "<"
	}
})
