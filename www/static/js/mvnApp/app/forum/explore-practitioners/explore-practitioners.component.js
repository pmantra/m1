function ExplorePractitionersController() {
	var vm = this

	vm.$onInit = function() {}
}

angular.module("forum").component("explorePractitioners", {
	templateUrl: "/js/mvnApp/app/forum/explore-practitioners/_explore-practitioners.html",
	controller: ExplorePractitionersController,
	bindings: {
		user: "<"
	}
})
