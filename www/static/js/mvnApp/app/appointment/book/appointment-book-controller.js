/* Booking appointment controller */

angular.module("appointment").controller("AppointmentBookCtrl", [
	"$rootScope",
	"$scope",
	"$state",
	"VerticalGroupService",
	"ModalService",
	"config",
	function($rootScope, $scope, $state, VerticalGroupService, ModalService, config) {
		var evt

		$scope.emptyCat = {
			name: "book"
		}

		var vgToGet

		evt = {
			event_name: "web_book_choose_vertical_grouping",
			user_id: $scope.user.id
		}
		$scope.$emit("trk", evt)

		$scope.loading = true
		$scope.pracSearch = {}

		if ($scope.user.organization) {
			vgToGet = $scope.user.organization.vertical_group_version
		} else if ($scope.user.subscription_plans) {
			vgToGet = config.default_college_vertical_group
		} else {
			vgToGet = "v2"
		}

		VerticalGroupService.get(vgToGet).then(function(resp) {
			$scope.verticalGroups = resp
			$scope.loading = false

			if (!!$state.params.verticalgroup) {
				$scope.selectVg($state.params.verticalgroup)
			}
		})

		$scope.selectVg = function(vgName) {
			$scope.pracSearch.selectedVg = _.find($scope.verticalGroups, ["name", vgName])
			$scope.setPageData({
				bodyClass: "app appointment-book right-active two-panel"
			})
			evt = {
				event_name: "web_book_show_specialties",
				user_id: $scope.user.id,
				vertical_group: vgName
			}
			angular.element(function() {
				if (document.getElementById("list-item-one") !== null) {
					document.getElementById("list-item-one").focus()
				}
			})

			$scope.$emit("trk", evt)
		}

		$scope.checkPrescriptionNeeded = function(specId) {
			// If any of the verticals in our selected vertical groups can prescribe, check with the user if they need a prescription.
			var shouldCheck = _.find($scope.pracSearch.selectedVg.verticals, ["can_prescribe", true]),
				specialtyId = specId,
				searchOpts = {
					refine: $scope.pracSearch.selectedVg.name
				}

			if (specialtyId) {
				searchOpts.specialties = specialtyId
			}

			if (shouldCheck) {
				ModalService.needPrescription(searchOpts)
				evt = {
					event_name: "web_book_ask_if_need_rx",
					user_id: $scope.user.id
				}
				$scope.$emit("trk", evt)
			} else {
				$state.go("app.practitioner-list.view", searchOpts)
			}
		}

		$scope.backToVerticalGroups = function() {
			$scope.setPageData({
				bodyClass: "app appointment-book"
			})
			$scope.pracSearch = {}
		}
	}
])
