function CareTeamType($rootScope, $state, Careteam, ngNotify, Healthbinder, ModalService, AssessmentService, Plow, SeoService) {
	const vm = this;
	var pageLimit = 9,
		pageStart = 0;

	vm.loadingMore = false;

	const getCareTeam = (req, onComplete) => {
		Careteam.getGetCareTeam(vm.user.id, req).then((practitioners) => {
			vm.totalPractitioners = practitioners.pagination.total;
			onComplete(practitioners);
		});
	}

	const gotMorePractitioners = (practitioners) => {
		angular.forEach(practitioners, (post) => {
			vm.practitioners.push(post);
		});
		vm.loadingMore = false;
	}

	vm.loadMore = () => {
		pageStart = pageStart + pageLimit;
		if (vm.totalPractitioners >= pageStart) {
			vm.loadingMore = true;
			let req = {
				"types" : vm.teamType,
				"limit": pageLimit,
				"offset": pageStart
			}
			getCareTeam(req, gotMorePractitioners);
		} else {
			return false;
		}
	}

	vm.startCareTeamEval = () => {
		let currentProgram = vm.user.structured_programs[_.findIndex(vm.user.structured_programs, 'active')];
		if (currentProgram) {

			let goToEval = () => {
				let currentModule = currentProgram.current_module;
				let obAssessmentId = currentProgram.modules[currentModule].onboarding_assessment_id;

				AssessmentService.getAssessment(obAssessmentId).then(a =>
					$state.go('app.onboarding.onboarding-assessment.one.take', { "id": a.id, "slug": a.slug })
				, e => {
					ngNotify.set('Sorry there seems to have been a problem', 'error')
					console.log(e)
				})

			}

			Healthbinder.getHB(vm.user.id).then((hb) => {
				if (hb.birthday) {
					goToEval()
				} else {
					ModalService.addBirthday(vm.user, goToEval)
				}
			});
		} else {
			ngNotify.set('Sorry there seems to have been a problem', 'error')
		}

	}


	vm.$onInit = () => {

		let evt = {
			"event_name" : "web_care-team_list",
			"user_id" : vm.user.id,
			"practitioner_list_count": vm.totalPractitioners
		};

		Plow.send(evt);

		SeoService.setPageTitle({
			title: 'Your Maven Care Team | Maven Clinic ',
			bodyClass: 'practitioner-list '
		});

		vm.loading = true;
		let req = {
			"types" : vm.teamType,
			"limit": pageLimit,
			"offset": pageStart
		}
		let onComplete = (practitioners) => {
			vm.practitioners = practitioners;
			vm.loading = false;
		}
		getCareTeam(req, onComplete)
	}
}

angular.module('app').component('careTeamType', {
	templateUrl: '/js/mvnApp/app/user/care-team/_care-team-type.html',
	controller: CareTeamType,
	bindings: {
		user: "<",
		teamType: "@",
		heading: "@"
	}
});
