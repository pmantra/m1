function BookPractitionerStandalone($state, $q, Users, Practitioners) {
	const vm = this
	const pracId = $state.params.practitioner_id

	const getPrac = Practitioners.getPractitioner(pracId).then(function(practitioner) {
		return practitioner.plain().data[0]
	})

	const getUser = Users.getWithProfile().then(function(u) {
		return u
	})

	vm.goBackToPrac = () => {
		window.location.assign(`/app/select-practitioner${window.location.search ? window.location.search : ''}`)
	}

	vm.$onInit = () => {
		vm.loading = true
		vm.pracId = $state.params.practitioner_id
		vm.backParams = location.search

		if (!pracId) {
			vm.noPrac = true
		}

		$q.all([getUser, getPrac]).then(function(res) {
			vm.user = res[0]
			vm.prac = res[1]
			vm.loading = false
			if (!vm.prac) {
				vm.noPrac = true
			}
		})
	}
}

angular.module("app").component("bookPractitionerStandalone", {
	templateUrl: "js/mvnApp/app/practitioner/profile/book-practitioner-standalone/index.html",
	controller: BookPractitionerStandalone,
	bindings: {}
})
