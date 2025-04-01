function HealthbinderController(
	$state,
	ngNotify,
	ngDialog,
	Appointments,
	Healthbinder,
	ModalService,
	FileAttachments,
	AssessmentService
) {
	var vm = this

	vm.$onInit = function() {
		Healthbinder.getHB(vm.user.id).then(function(hbData) {
			vm.hb = hbData
			vm.uneditedHb = angular.copy(hbData)
			vm.hbLoaded = !!vm.hb
		})

		vm.loadInsuranceProviders()
		vm.loadAllergyGroups()

		if (vm.user.organization) vm.getBpAppt()

		if (vm.user.structured_programs) {
			let currentProgram = vm.user.structured_programs[_.findIndex(vm.user.structured_programs, "active")]
			if (
				currentProgram &&
				currentProgram.current_module === "postpartum" &&
				currentProgram.modules.postpartum.assessments.POSTPARTUM
			) {
				vm.showNA = true
			}
		}
	}

	vm.loadInsuranceProviders = function() {
		vm.insuranceProviders = [
			"Aetna Health Group",
			"Blue Cross Blue Shield Assoc.",
			"Cigna Health Group",
			"Humana Group",
			"Kaiser Foundation Group",
			"United Health Group",
			"WellPoint Inc. Group",
			"Other"
		]
	}

	vm.loadAllergyGroups = function() {
		vm.medicationAllergyOptions = ["Sulfa drugs", "Penicillins", "Other", "None"]
		vm.foodAllergyOptions = ["Shellfish", "Wheat", "Soy", "Nuts", "Dairy", "Eggs", "Other", "None"]
	}

	vm.cancelEdit = function() {
		vm.hb = angular.copy(vm.uneditedHb)
		$state.reload()
	}

	vm.saveHb = function(hb) {
		Healthbinder.updateHB(vm.user.id, hb).then(
			function(updatedHb) {
				vm.hb = updatedHb
				ngNotify.set("Saved the changes to your health history", "success")
				vm.errorMsg = false
				vm.e = null
			},
			function(e) {
				console.log(e)
				ngNotify.set("Hmm... there seems to have been a problem. Please check and try again", "error")
				vm.errorMsg = true
				vm.e = e.data.message
			}
		)
	}

	// Pregnancy
	vm.addPregnancy = function() {
		var onComplete = function(p) {
			vm.hb.due_date = p
			ngNotify.set("Saved your due date", "success")
		}

		ModalService.addPregnancy(onComplete)
	}

	vm.editPregnancy = function() {
		var onEditDD = function(p) {
			vm.hb.due_date = p
			ngNotify.set("Saved", "success")
		}

		var onCompleteNewChild = function(c) {
			c.due_date = null
			Healthbinder.updateHB(vm.user.id, c).then(function(h) {
				vm.hb = h
				ngNotify.set("Saved", "success")
			})
		}

		var onCompleteLoss = function(l) {
			vm.hb.due_date = null
			ngNotify.set("Saved", "success")
		}

		ModalService.editPregnancy(vm.hb.due_date, onEditDD, onCompleteNewChild, onCompleteLoss, vm.user)
	}

	// Children
	vm.addChild = function() {
		var onComplete = function(d) {
			vm.hb.children = d.children
			ngNotify.set("Saved child to your health profile", "success")
		}
		ModalService.addChild(onComplete)
	}

	vm.removeChild = function(childId) {
		Healthbinder.removeChild(vm.user.id, childId).then(function(h) {
			vm.hb = h
			ngNotify.set("Removed child", "success")
		})
	}

	// Birth plan
	vm.openBp = function() {
		ngDialog.open({
			templateUrl: "/js/mvnApp/app/shared/dialogs/_birth-plan-standalone.html",
			className: "mvndialog",
			controller: [
				"$scope",
				"FileAttachments",
				function($scope, FileAttachments) {
					vm.hasUrl = false

					var req = {
						id: vm.user.id,
						appointment_id: vm.bpApptId,
						type: "BIRTH_PLAN"
					}

					FileAttachments.getFileAttachment(req).then(
						function(f) {
							if (f.plain().length >= 1) {
								$scope.bpUrl = f[0].signed_url
								$scope.hasUrl = true
							} else {
								$scope.hasUrl = false
							}
						},
						function(e) {
							$scope.hasUrl = false
							console.log(e)
						}
					)
				}
			]
		})
	}

	vm.getBp = function(apptid) {
		vm.bpApptId = apptid

		var req = {
			id: vm.user.id,
			appointment_id: apptid,
			type: "BIRTH_PLAN"
		}

		FileAttachments.getFileAttachment(req).then(
			function(f) {
				if (f.plain().length >= 1) {
					vm.showBp = true
				} else {
					vm.hasBirthPlan = false
				}
			},
			function(e) {
				vm.hasBirthPlan = false
				console.log(e)
			}
		)
	}

	vm.getBpAppt = function() {
		var req = {
			scheduled_start: moment()
				.utc()
				.subtract(11, "months")
				.format("YYYY-MM-DD HH:mm:ss"),
			scheduled_end: moment()
				.add(15, "minutes")
				.utc()
				.format("YYYY-MM-DD HH:mm:ss"),
			limit: 1,
			offset: 0,
			order_direction: "desc",
			purposes: "birth_planning",
			exclude_statuses: "CANCELLED"
		}

		Appointments.getAppointments()
			.getList(req)
			.then(function(appointments) {
				if (appointments.length >= 1) {
					vm.getBp(appointments[0].id)
				}
			})
	}

	vm.getPPAssessment = () => {
		AssessmentService.getUserAssessments(vm.user.id, { type: "POSTPARTUM" }).then(
			assessments => {
				let assessment = assessments[0] // Hacky.. but we don't have the notion of a user having more than on PP assessment just yet :/
				if (assessment.meta.completed) {
					$state.go("app.assessments.one.take", {
						id: assessment.meta.assessment_id,
						slug: "post-baby-evaluation",
						qid: "1"
					})
					//$state.go('app.assessments.one.results', { "id": assessment.meta.assessment_id, "slug": "post-baby-evaluation" }) // TODO.. when we have a real "results" screen for this
				} else {
					$state.go("app.assessments.one.take", {
						id: assessment.meta.assessment_id,
						slug: "post-baby-evaluation",
						qid: "1"
					})
				}
			},
			e => {
				ngNotify.set("Sorry there seems to have been a problem", "error")
			}
		)
	}
}

angular.module("user").component("healthbinder", {
	templateUrl: "/js/mvnApp/app/user/healthbinder/index.html",
	controller: HealthbinderController,
	bindings: {
		user: "<"
	}
})
