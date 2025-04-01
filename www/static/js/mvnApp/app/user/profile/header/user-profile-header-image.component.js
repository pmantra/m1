function UserProfileHeaderImage($rootScope, ngDialog, ModalService) {
	var vm = this,
		onComplete;


	vm.editProfileImage = function() {
		onComplete = function(newU) {
			vm.user = newU;
			$rootScope.$broadcast('updateUser', newU);
		}

		ModalService.editProfileImage(vm.user, onComplete);
	}

	vm.$onInit = function() {
		
	}
}
angular.module('forum').component('userProfileHeaderImage', {
	templateUrl: '/js/mvnApp/app/user/profile/header/_image.html',
	controller: UserProfileHeaderImage,
	bindings: {
		user: '='
	}
});