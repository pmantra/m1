function UserProfileController($q, Users, Categories) {
	var vm = this;

	var getCats = Categories.getCats().then(function(c) {
		return c;
	})

	var getUser = Users.getWithProfile().then(function(u) {
		return u;
	})

	vm.$onInit = function() {
		vm.loading = true;
		$q.all([getUser, getCats]).then(function(res) {
			vm.user = res[0];
			vm.cats = res[1];
			vm.loading = false;
		})
	}
}
angular.module('forum').component('userProfile', {
	templateUrl: '/js/mvnApp/app/user/profile/index.html',
	controller: UserProfileController
});