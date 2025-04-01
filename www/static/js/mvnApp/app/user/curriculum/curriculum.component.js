function CurriculumController(Users, AppUtils, $window, ngDialog) {
	const vm = this

	vm.$onInit = () => {
		vm.loading = true
		Users.getCurriculum().then(
			curr => {
				if (curr.plain()[0]) {
					vm.curriculumData = curr.plain().find(c => c.active)
					if (vm.curriculumData) {
						vm.curriculumData.steps.reverse()
						vm.needsIntro = !vm.curriculumData.steps.find(step => !!step.completed_at)
						_styleActions()
					}
				}
				vm.loading = false
			},
			e => {
				console.log("Error getting curriculum", e)
				vm.loading = false
			}
		)

		vm.needsSpecialStyles = AppUtils.videoCompatibleBrowser.isIE
		vm.carouselBreakpoints = [
			{
				breakpoint: 768,
				centerMode: true,
				centerPadding: "20px",
				settings: {
					centerPadding: "20px",
					centerMode: true,
					slidesToShow: 1,
					draggable: true
				}
			}
		]
	}

	vm.viewCurriculumStep = ($event, id) => {
		$event.preventDefault()
		const url = $event.target.href

		let onComplete = () => {
			_markCompleted(id, url)
		}

		if (vm.needsIntro) {
			_welcomeToCurriculum(onComplete, id, url)
		} else {
			onComplete()
		}
	}

	const _markCompleted = (id, url) => {
		const timestamp = moment()
			.utc()
			.format("YYYY-MM-DDTHH:mm:ss")

		Users.completeCurriculumStep(id, { completed_at: timestamp })
			.then(() => {
				vm.curriculumData.steps.find(step => step.id === id).completed_at = timestamp
				$window.location.href = url
			})
			.catch(e => {
				console.log("Issue marking complete:", e)
				$window.location.href = url // the user should still be able to get to the resource even if there's an issue marking it complete
			})
	}

	const _welcomeToCurriculum = onComplete =>
		ngDialog.open({
			className: "mvndialog carddialog",
			templateUrl: "/js/mvnApp/app/user/curriculum/_curriculum-welcome.html",
			showClose: false,
			closeByDocument: false,
			closeByEscape: false,
			controller: [
				"$scope",
				function($scope) {
					$scope.welcomeModal = vm.curriculumData.welcome_modal
					$scope.closeAndGo = function() {
						onComplete()
						ngDialog.close()
					}
				}
			]
		})

	const _styleActions = () => {
		vm.curriculumData.steps.forEach(step => {
			step.action.btnclass = "btn btn-secondary-cta"
		})
	}

	vm.slickDots = function(slider, i) {
		return "<span></span>"
	}
}

angular.module("app").component("curriculum", {
	templateUrl: "/js/mvnApp/app/user/curriculum/index.html",
	controller: CurriculumController
})
