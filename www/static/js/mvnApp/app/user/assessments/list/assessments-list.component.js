function AssessmentsListController(AssessmentService) {
	var vm = this;
	var pageLimit = 10;
	var pageStart = 0;
	var allLoaded = false;

	var getAssessments = function(onComplete) {
		const req = {
			type: vm.atype,
			limit: pageLimit,
			offset: pageStart
		}
		
		AssessmentService.getAllAssessments(req).then(function(a) {
			onComplete(a);
		})
	}
	
	var gotAssessments = (assessments) => {
		vm.assessments = assessments
		vm.loading = false;
		if (vm.assessments.length >= vm.assessments.pagination.total) {
			allLoaded = true
		}
	}
	
	var gotMoreAssessments = (assessments) => {
		angular.forEach(assessments, a => {
			vm.assessments.push(a)
		})
		vm.loadingMore = false
		if (vm.assessments.length >= vm.assessments.pagination.total) {
			allLoaded = true
		}
	}
	
	var getMoreAssessments = () => {
		vm.loadingMore = true
		pageStart += pageLimit
		getAssessments(gotMoreAssessments)
	}
	
	vm.loadMoreAssessments = () => {
		if (!vm.loadingMore && !allLoaded) getMoreAssessments()
	}
	
	vm.$onInit = function () {
		let currentProgram = vm.user.structured_programs[_.findIndex(vm.user.structured_programs, 'active')];
		if (currentProgram) {
			//req.module = currentProgram.current_module
		} 

		vm.loading = true;
		getAssessments(gotAssessments);
	};
}

angular.module('app').component('assessmentsList', {
	templateUrl: '/js/mvnApp/app/user/assessments/list/_assessments-list.html',
	controller: AssessmentsListController,
	bindings: {
		user: '<', 
		atype: '@'
	}
});