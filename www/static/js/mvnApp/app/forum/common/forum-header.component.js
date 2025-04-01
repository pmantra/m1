function ForumHeaderController($state, Plow) {
	var vm = this

	vm.$onInit = function() {
		vm.title = vm.title ? vm.title : "Community"
		vm.q = $state.params.q ? $state.params.q : null
		vm.showSearchMenu = false
	}
}
angular.module("forum").component("forumHeader", {
	templateUrl: "/js/mvnApp/app/forum/common/_forum-header.html",
	controller: ForumHeaderController,
	bindings: {
		title: "@",
		cats: "<",
		showSearchMenu: "="
	}
})
