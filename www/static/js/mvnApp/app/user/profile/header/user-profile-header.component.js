function UserProfileHeaderController(ngNotify, ModalService) {
	var vm = this;

	var onComplete = function(newU) {
		vm.user = newU;
		ngNotify.set('Added your username!', 'success');
	}

	vm.addUsername = function() {
		ModalService.addUsername(vm.user, onComplete, true)
	}
	vm.$onInit = function() {
		
	}
}
angular.module('forum').component('userProfileHeader', {
	templateUrl: '/js/mvnApp/app/user/profile/header/index.html',
	controller: UserProfileHeaderController,
	bindings: {
		user: '='
	}
});