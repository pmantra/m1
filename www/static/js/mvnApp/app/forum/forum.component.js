function ForumController($state, $q, Users, Categories, MarketingUtils) {
	var vm = this

	// const getCats = Categories.getCats().then(function(c) {
	// 	c.map(cat => {
	// 		cat.subCats = Categories.getSubCats(cat.name).then(function(sc) {
	// 			console.log(sc)
	// 			return sc
	// 		})
	// 	})

	// 	return c
	// })
	const getCats = Categories.getCats().then(function(c) {
		return c
	})

	const getUser = Users.getWithProfile().then(function(u) {
		return u
	})

	vm.$onInit = function() {
		vm.loading = true
		vm.showSearchMenu = false
		// window.scrollTo(0, 0)
		
		$q.all([getUser, getCats]).then(function(res) {
			vm.user = res[0]
			vm.cats = res[1]
			vm.loading = false

			if (!vm.user) {
				MarketingUtils.promoteApp()
				MarketingUtils.showToast("covid", 2000)
			}
		})
	}

	vm.toggleSearchMenu = function() {
		vm.showSearchMenu = !vm.showSearchMenu
	}

	vm.$onDestroy = function() {
		vm.showSearchMenu = false
		angular.element(document.querySelector("#search-toggle")).remove()
	}
}
angular.module("app").component("forum", {
	templateUrl: "/js/mvnApp/app/forum/index.html",
	controller: ForumController
})
