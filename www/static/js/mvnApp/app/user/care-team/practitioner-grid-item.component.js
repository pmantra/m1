function PractitionerGridItem(config) {
	var vm = this

	vm.$onInit = function() {
		vm.hideBook = vm.practitioner.profiles.practitioner.is_cx && !vm.user.profiles.member.can_book_cx
	}
}

angular.module("app").component("practitionerGridItem", {
	templateUrl: "/js/mvnApp/app/user/care-team/_practitioner-grid-item.html",
	controller: PractitionerGridItem,
	bindings: {
		practitioner: "<",
		user: "<"
	}
})
