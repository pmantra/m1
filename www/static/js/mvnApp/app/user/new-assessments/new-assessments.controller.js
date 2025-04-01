function NewAssessmentsController(UrlHelperService) {
	var vm = this;

	vm.$onInit = () => {
		var pathArray = window.location.pathname.split("/");
		var slug = pathArray[2];
		UrlHelperService.redirectToReact(`/app/assessments/${slug}`)
	};
}

angular.module('app').component('newAssessments', {
	templateUrl: '/js/mvnApp/app/user/new-assessments/index.html',
	controller: NewAssessmentsController,
	bindings: {
		user: "<"
	}
});
