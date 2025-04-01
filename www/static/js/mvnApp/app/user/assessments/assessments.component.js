function AssessmentsController(Users) {
	var vm = this;

	var getUser = function () {
		Users.getWithProfile().then(function (u) {
			vm.user = u;
			vm.loading = false;
		})
	}

	vm.$onInit = function () {
		vm.loading = true;
		getUser();
	};

	vm.$onDestroy = () => {

	}
}

angular.module('app').component('assessments', {
	templateUrl: '/js/mvnApp/app/user/assessments/index.html',
	controller: AssessmentsController,
	bindings: {
	}
});
