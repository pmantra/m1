function AssessmentResultsController(
	AssessmentService,
	NativeAppCommsService,
	NATIVE_PLATFORM
) {
	var vm = this,
		qtype,
		rawQuestions;

	// Default state for button is disabled... we update to not disabled if parent question is answered, but NOT child question... yet..........
	vm.btnDisabled = true;
	vm.currProgress = 100;
	vm.atype = qtype;

	/* LET'S GOOOOO */
	let getAssessmentAnswers = rawQuestions => {
		//raw questions: arr of questions, with empty answers property
		AssessmentService.getUserAssessments(vm.user.id, {
			assessment_id: vm.assessment.id
		}).then(
			function(a) {
				if (a[0]) {
					// while we're being all hacky and not caring if the user has >1 needs assessment, just get the newest one... hashtagYolo
					let userAnswers = a[a.length - 1];

					vm.answers = userAnswers.answers;
					vm.isComplete = userAnswers.meta.completed;
					vm.score = userAnswers.meta.computed_score;
					vm.results = userAnswers.meta.band_results;
					vm.userAssessmentId = userAnswers.meta.id; // User needs_assessment ID .. !== assessment.id (one assessment can have multiple needs assessments)
				}

				vm.userAssessment = AssessmentService._setUpAssessmentAnswers(
					rawQuestions,
					vm.answers
				); // add user's answers to empty assessment
				vm.loading = false;
			},
			function(e) {
				console.log(e);
				return false;
			}
		);
	};

	vm.optionIsCorrect = (question, opt) => {
		// TODO - DRY.. move into service
		return question.widget.solution.value.indexOf(opt) >= 0;
	};

	vm.nativeResultsCta = theCta => {
		NativeAppCommsService.sendMessage(theCta);
	};

	vm.$onInit = function() {
		vm.loading = true;
		vm.isNative = NATIVE_PLATFORM;

		AssessmentService.setBodyClass(vm.assessment.type);

		qtype = vm.assessment.type;

		rawQuestions = AssessmentService._setUpQuestions(vm.assessment); // gives us array of questions with empty answer properties as arr/obj to be populated where necessary appended

		getAssessmentAnswers(rawQuestions);
		let currStatus = {
			showInfoOnExit: false,
			progress: 100,
			isComplete: true
		};

		vm.updateStatus()(currStatus);
	};

	vm.$onChanges = changes => {
		if (changes.assessment && vm.assessment) {
			let theTemplate = AssessmentService.getAttrs(vm.assessment).template;
			vm.templateUrl =
				"/js/mvnApp/app/user/assessments/templates/" +
				theTemplate +
				"/_assessment-results.html";
		}
	};
}

angular.module("app").component("assessmentResults", {
	template: '<div ng-include="$ctrl.templateUrl">',
	controller: AssessmentResultsController,
	bindings: {
		user: "<",
		assessment: "<",
		updateStatus: "&"
	}
});
