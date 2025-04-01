function AssessmentViewController($state, AssessmentService, Plow ) {
	var vm = this;
		
	vm.$onInit = function () {
		AssessmentService.setBodyClass(vm.assessment.type)
	}
	
}

angular.module('app').component('assessmentView', {
	//template: '<div ng-include="$ctrl.templateUrl">',
	templateUrl: '/js/mvnApp/app/user/assessments/one/view/index.html',
	controller: AssessmentViewController, 
	bindings: {
		user: '<',
		assessment: '<'
	}
});