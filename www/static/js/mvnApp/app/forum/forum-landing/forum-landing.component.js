function ForumLandingController($state, $q, Users, Categories, Plow) {
	var vm = this,
		evt

	vm.$onInit = function() {
		vm.loading = true
		vm.loading = false
		vm.show = 4 // number of popular posts to show

		evt = {
			event_name: "forum_landing",
			user_id: vm.user ? String(vm.user.id) : ''
		}

		Plow.send(evt)
	}
}
angular.module("forum").component("forumLanding", {
	templateUrl: "/js/mvnApp/app/forum/forum-landing/index.html",
	controller: ForumLandingController,
	bindings: {
		user: "<",
		cats: "<",
		showSearchMenu: "="
	}
})
