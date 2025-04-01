function UserProgramsCtrl($state, Users) {
	const vm = this

	const getPrograms = user => {
		Users.getUserPrograms(user.id).then(
			programs => {
				vm.programs = programs.plain()
				vm.loading = false
			},
			e => {
				console.log(e)
				vm.loading = false
			}
		)
	}

	vm.initiateTransition = transition => {
		Users.updateUserPrograms(vm.user.id, transition.subject).then(
			u => {
				$state.go("app.dashboard")
			},
			e => {
				console.log("Error with program transition...", e)
			}
		)
	}

	vm.$onInit = () => {
		vm.loading = true
		Users.getWithProfile(true).then(u => {
			vm.user = u
			getPrograms(vm.user)
		})
	}
}

angular.module("user").component("userPrograms", {
	templateUrl: "/js/mvnApp/app/user/programs/index.html",
	controller: UserProgramsCtrl
})
